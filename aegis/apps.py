from typing import Any

from django.apps import AppConfig


class AegisConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aegis"
    defaults = {
        "cooldown": 10,
        "denial-template": "Your IP address {ip} has been blocked. Try again in {cooldown} days.",
    }
    RateLimitDefaults: dict[str, Any] = {
        "CAPACITY": 10.0,
        "REFILL_RATE": 1.0,
        "EXPIRATION_DAYS": 7,
    }
