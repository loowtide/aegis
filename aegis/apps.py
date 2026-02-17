from django.apps import AppConfig
from typing import Any

class AegisConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aegis"
    defaults = {"cooldown": 10}
    RateLimitDefaults: dict[str, Any]={
    'CAPACITY': 10.0,
    'REFILL_RATE': 1.0,
    'EXPIRATION_DAYS': 7,
    }
