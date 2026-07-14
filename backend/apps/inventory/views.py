from __future__ import annotations

from django.db.models import F, Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import ReadOnlyOrManager

from .models import ItemKind, StockItem, StockMovement
from .serializers import (
    RawMaterialReceiveSerializer,
    StockAdjustSerializer,
    StockItemSerializer,
    StockMovementSerializer,
    StockWriteOffSerializer,
)


class StockItemViewSet(mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       viewsets.GenericViewSet):
    """Read-only listing of on-hand stock. Mutations go through dedicated actions."""

    queryset = StockItem.objects.select_related("product", "raw_material").all()
    serializer_class = StockItemSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["kind"]
    ordering_fields = ["quantity", "updated_at"]
    search_fields = ["product__name", "raw_material__name",
                     "product__sku", "raw_material__sku"]

    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        """Items at or below their reorder threshold."""
        product_low = Q(kind=ItemKind.PRODUCT, quantity__lte=F("product__reorder_threshold"))
        material_low = Q(
            kind=ItemKind.RAW_MATERIAL, quantity__lte=F("raw_material__reorder_threshold")
        )
        qs = self.get_queryset().filter(product_low | material_low)
        page = self.paginate_queryset(qs)
        ser = self.get_serializer(page or qs, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    @action(detail=False, methods=["post"], url_path="adjust")
    def adjust(self, request):
        serializer = StockAdjustSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        movement = serializer.save()
        return Response(
            StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["post"], url_path="receive")
    def receive(self, request):
        serializer = RawMaterialReceiveSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        movement = serializer.save()
        return Response(
            StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["post"], url_path="write-off")
    def write_off(self, request):
        """Record waste/loss: decrements stock (no finance Expense is booked).

        The response still carries an ``expense`` key for backwards
        compatibility; it is always ``null`` now that waste is non-cash.
        """
        serializer = StockWriteOffSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        movement, expense = serializer.save()
        return Response(
            {
                "movement": StockMovementSerializer(movement).data,
                "expense": {
                    "id": str(expense.id),
                    "category_name": expense.category.name,
                    "amount": str(expense.amount),
                    "incurred_on": expense.incurred_on.isoformat(),
                } if expense else None,
            },
            status=status.HTTP_201_CREATED,
        )


class StockMovementViewSet(mixins.ListModelMixin,
                           mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):
    queryset = (
        StockMovement.objects
        .select_related("stock_item__product", "stock_item__raw_material", "created_by")
        .all()
    )
    serializer_class = StockMovementSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["reason", "stock_item"]
    ordering_fields = ["created_at", "quantity_delta"]
    search_fields = ["reference", "note"]
