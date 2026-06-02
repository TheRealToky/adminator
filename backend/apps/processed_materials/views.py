from __future__ import annotations

from django.db.models import F
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import ReadOnlyOrManager

from .models import (
    ProcessedMaterial,
    ProcessedMaterialBatch,
    ProcessedMaterialRecipeItem,
    ProcessedMaterialStock,
    ProcessedMaterialStockMovement,
    ProductProcessedMaterialUsage,
)
from .serializers import (
    ProcessedMaterialBatchProduceSerializer,
    ProcessedMaterialBatchSerializer,
    ProcessedMaterialRecipeItemSerializer,
    ProcessedMaterialSerializer,
    ProcessedMaterialStockAdjustSerializer,
    ProcessedMaterialStockMovementSerializer,
    ProcessedMaterialStockSerializer,
    ProcessedMaterialStockWriteOffSerializer,
    ProductProcessedMaterialUsageSerializer,
)


class ProcessedMaterialViewSet(viewsets.ModelViewSet):
    queryset = (
        ProcessedMaterial.objects
        .select_related("stock")
        .prefetch_related(
            "recipe_items__raw_material",
            "recipe_items__sub_processed_material",
            "used_in_products__product",
        )
        .all()
    )
    serializer_class = ProcessedMaterialSerializer
    permission_classes = [ReadOnlyOrManager]
    search_fields = ["name", "sku", "notes"]
    filterset_fields = ["is_active", "unit"]
    ordering_fields = ["name", "sku", "unit_cost", "created_at"]


class ProcessedMaterialRecipeItemViewSet(viewsets.ModelViewSet):
    queryset = ProcessedMaterialRecipeItem.objects.select_related(
        "processed_material", "raw_material", "sub_processed_material"
    ).all()
    serializer_class = ProcessedMaterialRecipeItemSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["processed_material", "raw_material", "sub_processed_material"]
    ordering_fields = ["processed_material__name", "raw_material__name"]


class ProductProcessedMaterialUsageViewSet(viewsets.ModelViewSet):
    queryset = ProductProcessedMaterialUsage.objects.select_related(
        "product", "processed_material"
    ).all()
    serializer_class = ProductProcessedMaterialUsageSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["product", "processed_material"]
    ordering_fields = ["product__name", "processed_material__name"]


class ProcessedMaterialStockViewSet(mixins.ListModelMixin,
                                    mixins.RetrieveModelMixin,
                                    viewsets.GenericViewSet):
    """Read-only stock listing. Mutations via dedicated actions."""

    queryset = ProcessedMaterialStock.objects.select_related("processed_material").all()
    serializer_class = ProcessedMaterialStockSerializer
    permission_classes = [ReadOnlyOrManager]
    search_fields = ["processed_material__name", "processed_material__sku"]
    ordering_fields = ["quantity", "updated_at"]

    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        qs = self.get_queryset().filter(
            quantity__lte=F("processed_material__reorder_threshold")
        )
        page = self.paginate_queryset(qs)
        ser = self.get_serializer(page or qs, many=True)
        return (
            self.get_paginated_response(ser.data)
            if page is not None else Response(ser.data)
        )

    @action(detail=False, methods=["post"], url_path="adjust")
    def adjust(self, request):
        ser = ProcessedMaterialStockAdjustSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)
        movement = ser.save()
        return Response(
            ProcessedMaterialStockMovementSerializer(movement).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="write-off")
    def write_off(self, request):
        """Record waste/loss: decrements stock AND books a finance Expense."""
        ser = ProcessedMaterialStockWriteOffSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)
        movement, expense = ser.save()
        return Response(
            {
                "movement": ProcessedMaterialStockMovementSerializer(movement).data,
                "expense": {
                    "id": str(expense.id),
                    "category_name": expense.category.name,
                    "amount": str(expense.amount),
                    "incurred_on": expense.incurred_on.isoformat(),
                } if expense else None,
            },
            status=status.HTTP_201_CREATED,
        )


class ProcessedMaterialStockMovementViewSet(mixins.ListModelMixin,
                                            mixins.RetrieveModelMixin,
                                            viewsets.GenericViewSet):
    queryset = (
        ProcessedMaterialStockMovement.objects
        .select_related("stock__processed_material", "created_by")
        .all()
    )
    serializer_class = ProcessedMaterialStockMovementSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["reason", "stock"]
    search_fields = ["reference", "note"]
    ordering_fields = ["created_at", "quantity_delta"]


class ProcessedMaterialBatchViewSet(mixins.ListModelMixin,
                                    mixins.RetrieveModelMixin,
                                    mixins.DestroyModelMixin,
                                    viewsets.GenericViewSet):
    queryset = ProcessedMaterialBatch.objects.select_related(
        "processed_material", "created_by"
    ).all()
    serializer_class = ProcessedMaterialBatchSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["processed_material", "scheduled_for"]
    search_fields = ["processed_material__name", "processed_material__sku", "notes"]
    ordering_fields = ["scheduled_for", "created_at", "quantity_produced", "cost"]

    @action(detail=False, methods=["post"], url_path="produce")
    def produce(self, request):
        ser = ProcessedMaterialBatchProduceSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)
        batch = ser.save()
        return Response(
            ProcessedMaterialBatchSerializer(batch).data,
            status=status.HTTP_201_CREATED,
        )
