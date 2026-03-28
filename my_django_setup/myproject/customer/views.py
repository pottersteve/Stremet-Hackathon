from django.shortcuts import render
from django.contrib import messages
from home.models import Order  # <--- Crucial: importing the database from home

def customer_panel(request):
    """View for Customers to track orders via Order ID."""
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        try:
            order = Order.objects.get(order_id=order_id)
            # Notice it now looks inside the 'customer' templates folder!
            return render(request, 'customer/customer_panel.html', {'order': order})
        except Order.DoesNotExist:
            messages.error(request, f"Order ID '{order_id}' could not be found.")
            
    return render(request, 'customer/customer_panel.html')