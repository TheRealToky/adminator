from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import ReadOnlyOrManager

from .models import ProductionRun
from .serializers import (
    ProductionExecuteSerializer,
    ProductionRunSerializer,
    ProductionRunUpdateSerializer,
)


class ProductionRunViewSet(mixins.ListModelMixin,
                           mixins.RetrieveModelMixin,
                           mixins.UpdateModelMixin,
                           mixins.DestroyModelMixin,
                           viewsets.GenericViewSet):
    """Read, edit metadata, and delete production runs. New runs are created via `execute/`."""

    queryset = ProductionRun.objects.select_related("product", "created_by").all()
    serializer_class = ProductionRunSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["product", "status", "scheduled_for"]
    search_fields = ["product__name", "product__sku", "notes"]
    ordering_fields = ["scheduled_for", "created_at", "quantity", "cost"]

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return ProductionRunUpdateSerializer
        return ProductionRunSerializer

    def update(self, request, *args, **kwargs):
        # Editing metadata returns the full representation so the client can
        # refresh the row without an extra fetch.
        super().update(request, *args, **kwargs)
        instance = self.get_object()
        return Response(ProductionRunSerializer(instance).data)

    @action(detail=False, methods=["post"], url_path="execute")
    def execute(self, request):
        serializer = ProductionExecuteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        return Response(ProductionRunSerializer(run).data, status=status.HTTP_201_CREATED)
