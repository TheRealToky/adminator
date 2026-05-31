from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import ReadOnlyOrManager

from .models import Sale
from .serializers import (
    PaymentMethodChoiceSerializer,
    SaleChannelChoiceSerializer,
    SaleCreateSerializer,
    SaleSerializer,
)


class SaleViewSet(mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    """List + retrieve sales. New sales are created via `record/`."""

    queryset = (
        Sale.objects.select_related("served_by")
        .prefetch_related("items__product")
        .all()
    )
    serializer_class = SaleSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["payment_method", "channel", "served_by"]
    search_fields = ["receipt_number", "customer_name", "customer_phone", "notes"]
    ordering_fields = ["occurred_at", "total"]

    @action(detail=False, methods=["post"], url_path="record")
    def record(self, request):
        serializer = SaleCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        sale = serializer.save()
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)


class PaymentMethodListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PaymentMethodChoiceSerializer.list_all())


class SaleChannelListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(SaleChannelChoiceSerializer.list_all())
