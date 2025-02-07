# ALX Travel App

A Django-based travel application API for managing property listings and bookings.

## API Endpoints

### Listings

- `GET /api/listings/` - List all property listings
- `POST /api/listings/` - Create a new listing
- `GET /api/listings/{id}/` - Retrieve a specific listing
- `PUT /api/listings/{id}/` - Update a listing
- `DELETE /api/listings/{id}/` - Delete a listing

### Bookings

- `GET /api/bookings/` - List all bookings
- `POST /api/bookings/` - Create a new booking
- `GET /api/bookings/{id}/` - Retrieve a specific booking
- `PUT /api/bookings/{id}/` - Update a booking
- `DELETE /api/bookings/{id}/` - Delete a booking

## API Usage

### Example Listing Object
```json
{
    "title": "Luxury Beach Villa",
    "description": "Beautiful villa with ocean view",
    "property_type": "villa",
    "location": "Miami Beach",
    "price_per_night": 299.99,
    "bedrooms": 3,
    "bathrooms": 2,
    "max_guests": 6
}
```

### Example Booking Object
```json
{
    "listing": 1,
    "user": 1,
    "check_in_date": "2024-02-01",
    "check_out_date": "2024-02-05",
    "guests_count": 4,
    "total_price": 1199.96,
    "status": "pending"
}
```

## Testing

You can test these endpoints using tools like Postman or curl. Make sure to include proper headers and authentication if required.
