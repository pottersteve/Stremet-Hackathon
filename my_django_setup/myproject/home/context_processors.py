from django.urls import NoReverseMatch, reverse

from home.auth_utils import get_profile_role


def _portal_items_for_user(user):
    """Primary shortcuts only (workspaces and top-level areas)."""
    role = get_profile_role(user)
    is_admin = user.is_superuser or role == "admin"

    if is_admin:
        items = [
            {"label": "Central", "url": reverse("staff_dashboard")},
            {"label": "New order", "url": reverse("admin_panel")},
            {"label": "Clients", "url": reverse("client_directory")},
            {"label": "Designer", "url": reverse("designer_dashboard")},
            {"label": "Manufacturer", "url": reverse("manufacturer_dashboard")},
            {"label": "Warehouse", "url": reverse("warehouse_dashboard")},
            {"label": "Support", "url": reverse("support_hub")},
            {"label": "Quote", "url": reverse("customer_request_quote")},
        ]
        if user.is_staff:
            items.insert(0, {"label": "Django admin", "url": reverse("admin:index")})
        return items, "staff_dashboard"

    if role == "designer":
        return (
            [
                {"label": "Designer", "url": reverse("designer_dashboard")},
                {"label": "Support", "url": reverse("support_hub")},
            ],
            "designer_dashboard",
        )

    if role == "manufacturer":
        return (
            [
                {"label": "Manufacturer", "url": reverse("manufacturer_dashboard")},
                {"label": "Support", "url": reverse("support_hub")},
            ],
            "manufacturer_dashboard",
        )

    if role == "warehouse":
        return (
            [
                {"label": "Warehouse", "url": reverse("warehouse_dashboard")},
                {"label": "Support", "url": reverse("support_hub")},
            ],
            "warehouse_dashboard",
        )

    if role == "customer":
        return (
            [
                {"label": "Request quote", "url": reverse("customer_request_quote")},
                {"label": "Support", "url": reverse("support_hub")},
                {"label": "Track order", "url": reverse("customer_panel")},
            ],
            "customer_request_quote",
        )

    return (
        [
            {"label": "Central", "url": reverse("staff_dashboard")},
            {"label": "Support", "url": reverse("support_hub")},
        ],
        "staff_dashboard",
    )


def portal_navigation(request):
    """
    Top portal bar: primary shortcuts per role, hidden on landing and login.
    """
    data = {
        "show_portal_nav_bar": False,
        "portal_nav_items": [],
        "portal_home_url_name": "staff_dashboard",
    }
    user = request.user
    if not user.is_authenticated:
        return data

    try:
        items, home_name = _portal_items_for_user(user)
    except NoReverseMatch:
        return data

    data["portal_nav_items"] = items
    data["portal_home_url_name"] = home_name

    match = getattr(request, "resolver_match", None)
    url_name = match.url_name if match else None
    hide_bar = url_name in ("home_dashboard", "login")
    data["show_portal_nav_bar"] = bool(items) and not hide_bar

    return data
