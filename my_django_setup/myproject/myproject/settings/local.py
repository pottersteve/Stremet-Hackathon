"""Local development defaults (default when DJANGO_SETTINGS_ENV is not production)."""

from .base import *  # noqa: F403

SECRET_KEY = "django-insecure-_-36pd3z$=9qla21d!apb+j$37%wax^7m62$*z8t8gfhm^j_gg"
DEBUG = True
ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "0.0.0.0"]
