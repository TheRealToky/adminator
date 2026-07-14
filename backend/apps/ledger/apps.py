from django.apps import AppConfig


class LedgerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ledger"
    verbose_name = "General Ledger"

    def ready(self) -> None:
        # Wire the shadow-mode posting signals for sales, finance, inventory,
        # production and processed-material events.
        from . import signals  # noqa: F401
