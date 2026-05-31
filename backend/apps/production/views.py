from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import ReadOnlyOrManager

from .models import ProductionRun
from .serializers import ProductionExecuteSerializer, ProductionRunSerializer


class ProductionRunViewSet(mixins.ListModelMixin,
                           mixins.RetrieveModelMixin,
                           mixins.DestroyModelMixin,
                           viewsets.GenericViewSet):
    """Read + delete production runs. New runs are created via `execute/`."""

    queryset = ProductionRun.objects.select_related("product", "created_by").all()
    serializer_class = ProductionRunSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["product", "status", "scheduled_for"]
    search_fields = ["product__name", "product__sku", "notes"]
    ordering_fields = ["scheduled_for", "created_at", "quantity", "cost"]

    @action(detail=False, methods=["post"], url_path="execute")
    def execute(self, request):
        serializer = ProductionExecuteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        return Response(ProductionRunSerializer(run).data, status=status.HTTP_201_CREATED)
