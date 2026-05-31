from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ProductCategoryViewSet,
    ProductViewSet,
    RawMaterialViewSet,
    RecipeItemViewSet,
    SupplierViewSet,
    UnitListView,
)

router = DefaultRouter()
router.register("categories", ProductCategoryViewSet, basename="category")
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("raw-materials", RawMaterialViewSet, basename="raw-material")
router.register("products", ProductViewSet, basename="product")
router.register("recipes", RecipeItemViewSet, basename="recipe")

urlpatterns = [
    path("units/", UnitListView.as_view(), name="units"),
    path("", include(router.urls)),
]
