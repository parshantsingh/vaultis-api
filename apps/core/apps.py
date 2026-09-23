from django.apps import AppConfig
from django.core.signals import request_finished


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self) -> None:
        from .logs import clear_request_id

        request_finished.connect(clear_request_id, dispatch_uid="clear_request_id")
