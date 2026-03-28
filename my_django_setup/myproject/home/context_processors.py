from django.urls import reverse

from home.auth_utils import get_profile_role


def portal_navigation(request):
    user = request.user
    data = {
        'show_admin_portal_nav': False,
        'portal_nav_items': [],
    }
    if not user.is_authenticated:
        return data
    role = get_profile_role(user)
    if user.is_superuser or role == 'admin':
        data['show_admin_portal_nav'] = True
        data['portal_nav_items'] = [
            {'label': 'Django admin', 'url': reverse('admin:index')},
            {'label': 'Staff', 'url': reverse('staff_dashboard')},
            {'label': 'Designer', 'url': reverse('designer_dashboard')},
            {'label': 'Manufacturer', 'url': reverse('manufacturer_dashboard')},
            {'label': 'Customer quote', 'url': reverse('customer_request_quote')},
        ]
    return data
