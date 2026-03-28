import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
# FIXED: Standardized the auth imports so they don't crash
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import Order, Client, OrderImage, OrderItem
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login

def staff_login(request):
    """Handles authentication for all internal staff."""
    # If they are already logged in, send them straight to the dashboard
    if request.user.is_authenticated:
        return redirect('staff_dashboard')
    

    if request.method == 'POST':
        username = request.POST.get('username') 
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('staff_dashboard')
        else:
            messages.error(request, "Invalid username or password.")
            
    # Make sure this matches the actual name of your HTML file!
    return render(request, 'home/staff_login.html')
def staff_logout(request):
    request.user.is_authenticated and logout(request)
    return redirect('staff_login')

def dashboard(request):
    """Renders the main landing page."""
    return render(request, 'home/index.html')

# ==========================================
# UNIFIED AUTHENTICATION
# ==========================================

def login_view(request):
    """Handles login for EVERYONE (Customers, Admins, Manufacturers)."""
    if request.user.is_authenticated:
        # If they already logged in, route them to the right place
        if hasattr(request.user, 'profile') and request.user.profile.role in ['admin', 'manufacturer']:
            return redirect('staff_dashboard')
        return redirect('home_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user) # FIXED: This now works perfectly
            messages.success(request, f"Welcome back, {user.username}!")
            
            # Route them based on their role in the UserProfile database
            if hasattr(user, 'profile') and user.profile.role in ['admin', 'manufacturer']:
                return redirect('staff_dashboard')
            return redirect('home_dashboard')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'home/login.html')

def logout_view(request):
    """Logs the user out and sends them home."""
    logout(request) # FIXED: This now works perfectly
    messages.info(request, "You have successfully logged out.")
    return redirect('login')


# ==========================================
# CUSTOMER PORTAL
# ==========================================

def customer_panel(request):
    """View for Customers to track orders via Order ID."""
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        try:
            order = Order.objects.get(order_id=order_id)
            return render(request, 'home/customer_tracking.html', {'order': order})
        except Order.DoesNotExist:
            messages.error(request, f"Order ID '{order_id}' could not be found.")
            
    return render(request, 'home/customer_tracking.html')


# ==========================================
# UNIFIED STAFF DASHBOARD
# ==========================================


@login_required(login_url='login')
def staff_dashboard(request):
    """
    Unified view: Checks user roles from UserProfile to show the correct features.
    Admins see order creation; Manufacturers see production tracking.
    """
    
    # 1. IDENTIFY USER ROLES USING OUR NEW DATABASE MODEL!
    is_admin = False
    is_mfg = False
    
    if hasattr(request.user, 'profile'):
        is_admin = (request.user.profile.role == 'admin') or request.user.is_superuser
        is_mfg = (request.user.profile.role == 'manufacturer') or request.user.is_superuser
    elif request.user.is_superuser:
        # Superusers get access to everything just in case
        is_admin = True
        is_mfg = True

    if is_admin or request.user.is_superuser:
        return render(request, 'home/dashboard.html')

    context = {
        'is_admin': is_admin,
        'is_mfg': is_mfg,
    }

    # 2. HANDLE FORM SUBMISSIONS
    if request.method == 'POST':
        
        # --- IF ADMINISTRATOR SUBMITTED A NEW ORDER ---
        if is_admin and 'create_order' in request.POST:
            try:
                company_name = request.POST.get('company_name')
                client_email = request.POST.get('client_email')
                
                client, created = Client.objects.get_or_create(
                    email=client_email,
                    defaults={'company_name': company_name}
                )

                thickness = request.POST.get('dim_thickness') or '0'
                width = request.POST.get('dim_width') or '0'
                length = request.POST.get('dim_length') or '0'
                dimensions_str = f"{thickness}mm x {width}mm x {length}mm"

                qty = request.POST.get('quantity_tons')
                if not qty:
                    qty = 0

                new_order = Order.objects.create(
                    order_id=request.POST.get('order_id'),
                    client=client,
                    target_delivery=request.POST.get('target_delivery'),
                    steel_grade=request.POST.get('steel_grade'),
                    product_form=request.POST.get('product_form'),
                    dimensions=dimensions_str,
                    quantity_tons=qty,
                    surface_finish=request.POST.get('surface_finish'),
                    heat_treatment=(request.POST.get('heat_treatment') == 'yes'),
                    ultrasonic_test=(request.POST.get('ultrasonic_test') == 'yes'),
                    mill_certificate=(request.POST.get('mill_certificate') == 'yes'),
                    blueprint_file=request.FILES.get('blueprint_file'),
                    admin_notes=request.POST.get('admin_notes')
                )

                images = request.FILES.getlist('reference_images')
                for img in images:
                    OrderImage.objects.create(order=new_order, image=img)

                messages.success(request, f"Order {new_order.order_id} successfully created!")
                return redirect('staff_dashboard')

            except Exception as e:
                print(f"\n--- DATABASE SAVE ERROR ---\n{e}\n---------------------------\n")
                messages.error(request, f"Error saving order: {e}")
                return redirect('staff_dashboard')

        # --- IF MANUFACTURER SEARCHED FOR AN ORDER ---
        if is_mfg and 'search_order' in request.POST:
            search_id = request.POST.get('order_id')
            try:
                order = Order.objects.get(order_id=search_id)
                context['order'] = order
            except Order.DoesNotExist:
                messages.error(request, f"Order ID '{search_id}' could not be found.")

    return render(request, 'home/unified_staff_panel.html', context)


# ==========================================
# AJAX ENDPOINT FOR THE FLOWCHART
# ==========================================

def update_item_status(request):
    """Hidden endpoint to update the database via Javascript AJAX."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            step_number = data.get('step')
            is_done = data.get('is_done')

            item = OrderItem.objects.get(id=item_id)

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

            item.save()
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required(login_url='login')
def support_hub(request):
    """Centralized page for viewing all support messages, contexts, and files."""
    
    # 1. Determine if the user is staff or a customer
    is_staff = False
    if hasattr(request.user, 'profile') and request.user.profile.role in ['admin', 'manufacturer']:
        is_staff = True
    elif request.user.is_superuser:
        is_staff = True

    # 2. Fetch the correct messages
    if is_staff:
        # Staff get to see a feed of EVERY message, newest first
        messages_feed = ChatMessage.objects.all().order_by('-timestamp')
    else:
        # Customers only see messages they sent (or replies to them)
        messages_feed = ChatMessage.objects.filter(sender=request.user).order_by('-timestamp')

    context = {
        'messages_feed': messages_feed,
        'is_staff': is_staff
    }
    
    return render(request, 'home/support_hub.html', context)