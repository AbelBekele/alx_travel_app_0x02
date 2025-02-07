from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from listings.models import Listing, Booking, Review
from datetime import datetime, timedelta
import random

class Command(BaseCommand):
    help = 'Seed the database with sample data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting database seeding...')

        # Create sample users
        self.create_users()
        
        # Create sample listings
        self.create_listings()
        
        # Create sample bookings and reviews
        self.create_bookings_and_reviews()

        self.stdout.write(self.style.SUCCESS('Database seeding completed successfully!'))

    def create_users(self):
        # Create sample users
        User.objects.create_user(username='user1', email='user1@example.com', password='password123')
        User.objects.create_user(username='user2', email='user2@example.com', password='password123')

    def create_listings(self):
        # Sample data for listings
        listings_data = [
            {
                'title': 'Luxury Beach Villa',
                'description': 'Beautiful villa with ocean view',
                'property_type': 'villa',
                'location': 'Miami Beach',
                'price_per_night': 299.99,
                'bedrooms': 3,
                'bathrooms': 2,
                'max_guests': 6
            },
            {
                'title': 'Mountain Cottage',
                'description': 'Cozy cottage in the mountains',
                'property_type': 'cottage',
                'location': 'Aspen',
                'price_per_night': 199.99,
                'bedrooms': 2,
                'bathrooms': 1,
                'max_guests': 4
            },
            # Add more sample listings as needed
        ]

        for listing_data in listings_data:
            Listing.objects.create(**listing_data)

    def create_bookings_and_reviews(self):
        users = User.objects.all()
        listings = Listing.objects.all()

        # Create sample bookings
        for listing in listings:
            for user in users:
                check_in = datetime.now().date() + timedelta(days=random.randint(1, 30))
                check_out = check_in + timedelta(days=random.randint(1, 7))
                
                Booking.objects.create(
                    listing=listing,
                    user=user,
                    check_in_date=check_in,
                    check_out_date=check_out,
                    guests_count=random.randint(1, listing.max_guests),
                    total_price=listing.price_per_night * 3,
                    status='confirmed'
                )

                # Create sample reviews
                Review.objects.create(
                    listing=listing,
                    user=user,
                    rating=random.randint(3, 5),
                    comment='Great experience! Would recommend.'
                )