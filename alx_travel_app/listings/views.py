from django.shortcuts import render
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, action
from .models import Listing, Booking, Payment
from .serializers import ListingSerializer, BookingSerializer, PaymentSerializer
from .tasks import send_booking_confirmation_email
import requests
import json
from django.shortcuts import get_object_or_404
import os
from django.views.decorators.csrf import csrf_exempt
import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)

CHAPA_SECRET_KEY = os.getenv('CHAPA_SECRET_KEY')
CHAPA_API_URL = 'https://api.chapa.co/v1'

class ListingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing listings.
    Provides CRUD operations for Listing model.
    """
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    def perform_create(self, serializer):
        booking = serializer.save()
        # Create a Payment record without triggering email confirmation here
        Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            currency='ETB'
        )
        return booking

    @action(detail=True, methods=['post'])
    def initiate_payment(self, request, pk=None):
        booking = self.get_object()
        try:
            # Retrieve the pending payment record or create a new one
            payment = Payment.objects.get(booking=booking, status='pending')
        except Payment.DoesNotExist:
            payment = Payment.objects.create(
                booking=booking,
                amount=booking.total_price,
                currency='ETB'
            )

        # Delegate the initiation to PaymentViewSet's initiate_payment action
        payment_viewset = PaymentViewSet()
        payment_viewset.request = request
        payment_viewset.format_kwarg = None
        return payment_viewset.initiate_payment(request, pk=payment.pk)


@api_view(['GET'])
def sample_api(request):
    return Response({"message": "Listings API is working"})

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    @action(detail=True, methods=['post'])
    def initiate_payment(self, request, pk=None):
        payment = self.get_object()
        booking = payment.booking

        email = booking.user.email if booking.user.email else "test@gmail.com"
        customization_title = f"BkngPay-{booking.id}"  # must not exceed 16 characters

        payload = {
            'tx_ref': str(payment.reference),
            'amount': str(payment.amount),
            'currency': payment.currency,
            'email': email,
            'first_name': booking.user.first_name,
            'last_name': booking.user.last_name,
            'callback_url': f"{request.build_absolute_uri('/').rstrip('/')}/api/payments/{payment.id}/verify/",
            # Updated return_url: points to the API booking endpoint.
            'return_url': f"{request.build_absolute_uri('/').rstrip('/')}/api/bookings/{booking.id}/",
            'customization': {
                'title': customization_title,
                'description': f"Payment for booking from {booking.check_in_date} to {booking.check_out_date}"
            }
        }

        headers = {
            'Authorization': f'Bearer {CHAPA_SECRET_KEY}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(
                f'{CHAPA_API_URL}/transaction/initialize',
                headers=headers,
                json=payload
            )
            response_data = response.json()

            if response.status_code == 200 and response_data.get('status') == 'success':
                # Attempt to get the transaction_id; if not provided, rely on the webhook to update later.
                transaction_id = response_data.get('data', {}).get('transaction_id')
                checkout_url = response_data.get('data', {}).get('checkout_url')
                if transaction_id:
                    payment.transaction_id = transaction_id
                if checkout_url:
                    payment.payment_url = checkout_url
                payment.save()

                return Response({
                    'status': 'success',
                    'message': 'Payment initiated successfully',
                    'payment_url': payment.payment_url
                })
            else:
                return Response({
                    'status': 'error',
                    'message': 'Failed to initiate payment',
                    'details': response_data
                }, status=status.HTTP_400_BAD_REQUEST)
        except requests.exceptions.RequestException as e:
            return Response({
                'status': 'error',
                'message': 'Failed to connect to payment service',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=True, methods=['post'])
    def verify_payment(self, request, pk=None):
        payment = self.get_object()

        if not payment.reference:
            return Response({
                'status': 'error',
                'message': 'No reference found for this payment'
            }, status=status.HTTP_400_BAD_REQUEST)

        headers = {
            'Authorization': f'Bearer {CHAPA_SECRET_KEY}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.get(
                f'{CHAPA_API_URL}/transaction/verify/{payment.reference}',
                headers=headers
            )
            response_data = response.json()

            if response.status_code == 200 and response_data.get('status') == 'success':
                # Update payment status to "completed" upon successful verification
                payment.status = 'completed'
                payment.save()

                # Update the booking status
                booking = payment.booking
                booking.status = 'confirmed'
                booking.save()

                # Try to send confirmation email, but don't fail if Celery is unavailable
                try:
                    send_booking_confirmation_email.delay(
                        booking_id=booking.id,
                        user_email=booking.user.email,
                        listing_title=booking.listing.title
                    )
                except Exception as e:
                    logger.error(f"Failed to queue confirmation email: {str(e)}")

                return Response({
                    'status': 'success',
                    'message': 'Payment verified successfully'
                })
            else:
                payment.status = 'failed'
                payment.save()
                return Response({
                    'status': 'error',
                    'message': 'Payment verification failed',
                    'details': response_data
                }, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.RequestException as e:
            return Response({
                'status': 'error',
                'message': 'Failed to verify payment',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

@csrf_exempt
@api_view(['POST'])
def chapa_webhook(request):
    """
    Webhook endpoint for Chapa.
    Verifies webhook signature using HMAC SHA256 and processes payment updates.
    """
    # Check both possible header names
    received_signature = (
        request.headers.get('x-chapa-signature') or 
        request.headers.get('Chapa-Signature')
    )
    webhook_secret = os.getenv('CHAPA_WEBHOOK_SECRET')

    if not received_signature or not webhook_secret:
        return Response({'message': 'Invalid or missing signature'}, status=400)

    # Calculate HMAC SHA256 signature
    calculated_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        request.body,
        hashlib.sha256
    ).hexdigest()

    # Add debug logging
    logger.info(f"Webhook Debug: received={received_signature}, calculated={calculated_signature}")
    logger.info(f"Webhook Payload: {request.data}")

    # Compare signatures
    if received_signature != calculated_signature:
        return Response({
            'message': 'Invalid signature',
            'received': received_signature,
            'calculated': calculated_signature
        }, status=400)

    # Get the tx_ref directly from the payload
    tx_ref = request.data.get('tx_ref')
    reference = request.data.get('reference')
    payment_status = request.data.get('status')

    if not tx_ref:
        logger.error("Missing tx_ref in webhook payload")
        return Response({'message': 'Missing tx_ref'}, status=400)

    try:
        payment = Payment.objects.get(reference=tx_ref)
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for tx_ref: {tx_ref}")
        return Response({'message': 'Payment not found'}, status=404)

    # Update payment details
    if reference:
        payment.transaction_id = reference
    payment.status = 'completed' if payment_status == 'success' else 'failed'
    payment.save()

    if payment.status == 'completed':
        booking = payment.booking
        booking.status = 'confirmed'
        booking.save()
        
        # Send confirmation email asynchronously
        try:
            send_booking_confirmation_email.delay(
                booking_id=booking.id,
                user_email=booking.user.email,
                listing_title=booking.listing.title
            )
        except Exception as e:
            logger.error(f"Failed to send confirmation email: {str(e)}")

    return Response({
        'message': 'Webhook processed successfully',
        'status': payment.status
    }, status=200)