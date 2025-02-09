from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_booking_confirmation_email(booking_id, user_email, listing_title):
    subject = f'Booking Confirmation - {listing_title}'
    message = (
        f"Thank you for your booking!\n\n"
        f"Booking Details:\n- Booking ID: {booking_id}\n- Property: {listing_title}\n\n"
        "We hope you enjoy your stay!"
    )
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user_email],
        fail_silently=False,
    )
    
    return f"Confirmation email sent for booking {booking_id}"
