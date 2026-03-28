"""Customer URLs are mounted at /customer/; order lookup lives in home.views."""

from home.views import customer_panel

__all__ = ["customer_panel"]
