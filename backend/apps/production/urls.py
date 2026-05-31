from rest_framework.routers import DefaultRouter

from .views import ProductionRunViewSet

router = DefaultRouter()
router.register("runs", ProductionRunViewSet, basename="production-run")

urlpatterns = router.urls
