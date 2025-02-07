from rest_framework import serializers
from .models import Listing, Booking, Review, Payment

class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = '__all__'

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'booking', 'reference', 'amount', 'currency', 'status', 
                 'transaction_id', 'payment_url', 'created_at', 'updated_at']
        read_only_fields = ['reference', 'transaction_id', 'payment_url']