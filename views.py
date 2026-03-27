from django.shortcuts import render, redirect, get_object_or_404
from .models import Order

def dashboard(request):
    """Renders the main three-panel landing page."""
    return render(request, 'manufacturing_app/index.html')

def admin_panel(request):
    """View for Administrators to add and manage orders."""
    # Logic for forms to add new Orders would go here
    return render(request, 'manufacturing_app/admin_panel.html')

def customer_panel(request):
    """View for Customers to track orders via Order ID."""
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, order_id=order_id)
        # Redirect to the specific order tracking page
        return render(request, 'manufacturing_app/customer_tracking.html', {'order': order})
    
    return render(request, 'manufacturing_app/customer_login.html')

def manufacturer_panel(request):
    """View for Manufacturers to update stages and view client logs."""
    active_orders = Order.objects.exclude(status='delivered')
    return render(request, 'manufacturing_app/manufacturer_panel.html', {'orders': active_orders})