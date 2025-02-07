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
    """
    ViewSet for viewing and editing bookings.
    Provides CRUD operations for Booking model.
    """
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    def perform_create(self, serializer):
        booking = serializer.save()
        
        # Create a payment record for the booking
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            currency='ETB'  # Ethiopian Birr
        )
        
        # Trigger the email task asynchronously
        send_booking_confirmation_email.delay(
            booking_id=booking.id,
            user_email=booking.user.email,
            listing_title=booking.listing.title
        )
        
        return booking

    @action(detail=True, methods=['post'])
    def initiate_payment(self, request, pk=None):
        """
        Initiate payment for a booking
        """
        booking = self.get_object()
        try:
            payment = Payment.objects.get(booking=booking, status='pending')
        except Payment.DoesNotExist:
            payment = Payment.objects.create(
                booking=booking,
                amount=booking.total_price,
                currency='ETB'
            )

        # Get the payment viewset
        payment_viewset = PaymentViewSet()
        payment_viewset.request = request
        payment_viewset.format_kwarg = None
        
        # Call the initiate_payment action
        return payment_viewset.initiate_payment(request, pk=payment.pk)

@api_view(['GET'])
def sample_api(request):
    return Response({"message": "Listings API is working"})

class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling payments through Chapa.
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    @action(detail=True, methods=['post'])
    def initiate_payment(self, request, pk=None):
        payment = self.get_object()
        booking = payment.booking

        # Prepare the payment data for Chapa
        payload = {
            'amount': str(payment.amount),
            'currency': payment.currency,
            'email': booking.user.email,
            'first_name': booking.user.first_name,
            'last_name': booking.user.last_name,
            'tx_ref': str(payment.reference),
            'callback_url': f"{request.build_absolute_uri('/').rstrip('/')}/api/payments/{payment.id}/verify/",
            'return_url': f"{request.build_absolute_uri('/').rstrip('/')}/bookings/{booking.id}/",
            'customization[title]': f"Booking Payment for {booking.listing.title}",
            'customization[description]': f"Payment for booking from {booking.check_in_date} to {booking.check_out_date}"
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
                # Update payment with transaction details
                payment.transaction_id = response_data['data'].get('transaction_id')
                payment.payment_url = response_data['data'].get('checkout_url')
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

        if not payment.transaction_id:
            return Response({
                'status': 'error',
                'message': 'No transaction ID found for this payment'
            }, status=status.HTTP_400_BAD_REQUEST)

        headers = {
            'Authorization': f'Bearer {CHAPA_SECRET_KEY}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.get(
                f'{CHAPA_API_URL}/transaction/verify/{payment.transaction_id}',
                headers=headers
            )
            response_data = response.json()

            if response.status_code == 200 and response_data.get('status') == 'success':
                # Update payment status
                payment.status = 'completed'
                payment.save()

                # Update booking status
                booking = payment.booking
                booking.status = 'confirmed'
                booking.save()

                # Send confirmation email
                send_booking_confirmation_email.delay(
                    booking_id=booking.id,
                    user_email=booking.user.email,
                    listing_title=booking.listing.title
                )

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