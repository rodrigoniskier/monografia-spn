from django.apps import AppConfig


class ReferencesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "references"
    verbose_name = "Referências"

    def ready(self):
        from . import signals  # noqa: F401
