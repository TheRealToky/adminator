from django.apps import AppConfig


class ProcessedMaterialsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.processed_materials"
    verbose_name = "Processed Materials"
    label = "processed_materials"

    def ready(self) -> None:  # pragma: no cover - import for signal registration
        from . import signals  # noqa: F401
