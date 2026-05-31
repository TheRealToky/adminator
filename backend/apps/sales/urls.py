from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PaymentMethodListView, SaleChannelListView, SaleViewSet

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sale")

urlpatterns = [
    path("payment-methods/", PaymentMethodListView.as_view(), name="payment-methods"),
    path("channels/", SaleChannelListView.as_view(), name="channels"),
    path("", include(router.urls)),
]
