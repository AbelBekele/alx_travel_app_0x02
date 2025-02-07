from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'listings', views.ListingViewSet)
router.register(r'bookings', views.BookingViewSet)

urlpatterns = router.urls
