from django.shortcuts import render
from django.contrib import messages
from home.models import Order  # <--- Crucial: importing the database from home

def customer_panel(request):
    """View for Customers to track orders via Order ID."""
    order = None
    chat_msgs = []
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        try:
            order = Order.objects.get(order_id=order_id)
            chat_msgs = order.chat_logs.all().order_by('timestamp')
        except Order.DoesNotExist:
            messages.error(request, f"Order ID '{order_id}' could not be found.")

    return render(
        request,
        'customer/customer_panel.html',
        {'order': order, 'chat_msgs': chat_msgs},
    )