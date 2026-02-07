from django.apps import AppConfig


class AegisConfig(AppConfig):
    default_auto_field="django.db.models.BigAutoField"
    name = "aegis"
    defaults={
        "cooldown":7
    }