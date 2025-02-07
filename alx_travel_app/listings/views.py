from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import Listing, Booking
from .serializers import ListingSerializer, BookingSerializer
from .tasks import send_booking_confirmation_email

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
        
        # Trigger the email task asynchronously
        send_booking_confirmation_email.delay(
            booking_id=booking.id,
            user_email=booking.user.email,
            listing_title=booking.listing.title
        )
        
        return booking

@api_view(['GET'])
def sample_api(request):
    return Response({"message": "Listings API is working"})