from django.shortcuts import render
from django.contrib import messages
from home.models import Order 
import json
from django.http import JsonResponse
from home.models import OrderItem

def manufacturer_panel(request):
    """View for Manufacturers to update stages and view client logs."""
    context = {}
    
    # If the user clicks "Load Order"
    if request.method == 'POST':
        search_id = request.POST.get('order_id')
        
        try:
            # Look up the order in the database
            order = Order.objects.get(order_id=search_id)
            context['order'] = order
            
        except Order.DoesNotExist:
            # If they type a fake ID, throw an error message
            messages.error(request, f"Order ID '{search_id}' could not be found.")

    return render(request, 'manufacturer/manufacturer_panel.html', context)

def update_item_status(request):
    """Hidden endpoint to update the database via Javascript AJAX."""
    if request.method == 'POST':
        try:
            # Read the data sent from the Javascript
            data = json.loads(request.body)
            item_id = data.get('item_id')
            step_number = data.get('step')
            is_done = data.get('is_done')

            # Find the specific item in the database
            item = OrderItem.objects.get(id=item_id)

            # Update the correct step based on what button was clicked
            if step_number == 1:
                item.step_1_programming = is_done
            elif step_number == 2:
                item.step_2_cutting = is_done
            elif step_number == 3:
                item.step_3_forming = is_done
            elif step_number == 4:
                item.step_4_joining = is_done
            elif step_number == 5:
                item.step_5_delivery = is_done

            # Save the changes!
            item.save()
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request'})