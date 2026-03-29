from django.apps import AppConfig


class HomeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "home"

    def ready(self) -> None:
        # Import here to avoid AppRegistryNotReady; preload runs once per process.
        from home.gpt4all_service import preload_gpt4all_at_startup

        preload_gpt4all_at_startup()
