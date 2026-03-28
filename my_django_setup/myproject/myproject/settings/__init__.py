import os

if os.environ.get("DJANGO_SETTINGS_ENV", "").lower() == "production":
    from .production import *  # noqa: F403
else:
    from .local import *  # noqa: F403
