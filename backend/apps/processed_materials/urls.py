from rest_framework.routers import DefaultRouter

from .views import (
    ProcessedMaterialBatchViewSet,
    ProcessedMaterialRecipeItemViewSet,
    ProcessedMaterialStockMovementViewSet,
    ProcessedMaterialStockViewSet,
    ProcessedMaterialViewSet,
    ProductProcessedMaterialUsageViewSet,
)

router = DefaultRouter()
router.register("materials", ProcessedMaterialViewSet, basename="processed-material")
router.register("recipes", ProcessedMaterialRecipeItemViewSet, basename="processed-recipe")
router.register("usages", ProductProcessedMaterialUsageViewSet, basename="processed-usage")
router.register("stock", ProcessedMaterialStockViewSet, basename="processed-stock")
router.register("movements", ProcessedMaterialStockMovementViewSet, basename="processed-movement")
router.register("batches", ProcessedMaterialBatchViewSet, basename="processed-batch")

urlpatterns = router.urls
