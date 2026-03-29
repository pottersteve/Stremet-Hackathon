"""Role-based view decorators (designer / manufacturer portals)."""

from collections.abc import Callable

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse

from .auth_utils import get_profile_role

LOGIN_URL = "login"


def _user_has_any_role(user, *roles: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = get_profile_role(user)
    return role in roles


def role_required(
    *roles: str,
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    """Require login and one of the given profile roles (superusers always pass)."""

    def test(user):
        return _user_has_any_role(user, *roles)

    def decorator(
        view_func: Callable[..., HttpResponse],
    ) -> Callable[..., HttpResponse]:
        return login_required(login_url=LOGIN_URL)(
            user_passes_test(test, login_url=LOGIN_URL)(view_func)
        )

    return decorator


designer_required = role_required("designer", "admin")
manufacturer_required = role_required("manufacturer", "admin")
warehouse_required = role_required("warehouse", "admin")
