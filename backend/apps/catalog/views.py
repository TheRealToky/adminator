from __future__ import annotations

from django.db.models import Count
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import ReadOnlyOrManager

from .models import Product, ProductCategory, RawMaterial, RecipeItem, Supplier
from .serializers import (
    ProductCategorySerializer,
    ProductSerializer,
    RawMaterialSerializer,
    RecipeItemSerializer,
    SupplierSerializer,
    UnitChoiceSerializer,
)


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.annotate(product_count=Count("products"))
    serializer_class = ProductCategorySerializer
    permission_classes = [ReadOnlyOrManager]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [ReadOnlyOrManager]
    search_fields = ["name", "contact_name", "phone", "email"]
    filterset_fields = ["is_active"]
    ordering_fields = ["name", "created_at"]


class RawMaterialViewSet(viewsets.ModelViewSet):
    queryset = RawMaterial.objects.select_related("preferred_supplier").all()
    serializer_class = RawMaterialSerializer
    permission_classes = [ReadOnlyOrManager]
    search_fields = ["name", "sku"]
    filterset_fields = ["is_active", "unit", "preferred_supplier"]
    ordering_fields = ["name", "sku", "unit_cost", "created_at"]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = (
        Product.objects.select_related("category")
        .prefetch_related("recipe_items__raw_material")
        .all()
    )
    serializer_class = ProductSerializer
    permission_classes = [ReadOnlyOrManager]
    search_fields = ["name", "sku", "description"]
    filterset_fields = ["category", "is_active", "unit"]
    ordering_fields = ["name", "sku", "selling_price", "created_at"]


class RecipeItemViewSet(viewsets.ModelViewSet):
    queryset = RecipeItem.objects.select_related("product", "raw_material").all()
    serializer_class = RecipeItemSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["product", "raw_material"]
    ordering_fields = ["product__name", "raw_material__name"]


class UnitListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UnitChoiceSerializer.list_all())
