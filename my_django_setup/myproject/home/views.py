import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import Order, Client, OrderImage, OrderItem, ChatMessage
from .auth_utils import ensure_user_profile, get_profile_role
from designer.models import ManufacturingPlan


def _get_role_redirect(user):
    """Return the URL name to redirect to based on user role."""
    ensure_user_profile(user)
    role = get_profile_role(user)
    if role == 'designer':
        return 'designer_dashboard'
    if role == 'manufacturer':
        return 'manufacturer_dashboard'
    if role == 'customer':
        return 'customer_request_quote'
    return 'staff_dashboard'


def _create_order_from_post(request):
    """
    Create Order, ManufacturingPlan, and optional images from POST.
    Returns (order, None) on success or (None, error_message) on failure.
    """
    try:
        company_name = request.POST.get('company_name')
        client_email = (request.POST.get('client_email') or '').strip() or (request.user.email or '')
        if not client_email:
            return None, 'Contact email is required.'

        client, created = Client.objects.get_or_create(
            email=client_email,
            defaults={'company_name': company_name},
        )
        if not created and company_name and client.company_name != company_name:
            client.company_name = company_name
            client.save(update_fields=['company_name'])

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
            admin_notes=request.POST.get('admin_notes'),
        )

        images = request.FILES.getlist('reference_images')
        for img in images:
            if img:
                OrderImage.objects.create(order=new_order, image=img)

        ManufacturingPlan.objects.create(
            order=new_order,
            name=f"Plan for {new_order.order_id}",
        )

        return new_order, None
    except Exception as e:
        return None, f'Error saving order: {e}'


def _can_use_customer_quote_portal(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = get_profile_role(user)
    return role in ('customer', 'admin')


def staff_login(request):
    """Handles authentication for all internal staff."""
    if request.user.is_authenticated:
        return redirect(_get_role_redirect(request.user))

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(_get_role_redirect(user))
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'home/staff_login.html')
def staff_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('staff_login')

def dashboard(request):
    """Renders the main landing page."""
    return render(request, 'home/index.html')

# ==========================================
# UNIFIED AUTHENTICATION
# ==========================================

def login_view(request):
    """Handles login for EVERYONE (Customers, Admins, Manufacturers, Designers)."""
    if request.user.is_authenticated:
        return redirect(_get_role_redirect(request.user))

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(_get_role_redirect(user))
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


@login_required(login_url='/login/')
def customer_request_quote(request):
    """Logged-in customers (and admins testing) submit manufacturing quote requests."""
    ensure_user_profile(request.user)
    if not _can_use_customer_quote_portal(request.user):
        role = get_profile_role(request.user)
        if role == 'manufacturer':
            return redirect('manufacturer_dashboard')
        if role == 'designer':
            return redirect('designer_dashboard')
        messages.error(request, 'You do not have access to this page.')
        return redirect('home_dashboard')

    if request.method == 'POST' and 'create_customer_order' in request.POST:
        new_order, err = _create_order_from_post(request)
        if err:
            messages.error(request, err)
        else:
            messages.success(
                request,
                f'Quote request {new_order.order_id} submitted. Our team will review it shortly.',
            )
            return redirect('customer_request_quote')

    return render(request, 'home/customer_request_quote.html', {
        'default_client_email': request.user.email or '',
    })


# ==========================================
# UNIFIED STAFF DASHBOARD
# ==========================================

@login_required(login_url='/login/')
def staff_dashboard(request):
    """
    Unified view: Checks user roles from UserProfile to show the correct features.
    Admins see order creation; Manufacturers see production tracking.
    """
    ensure_user_profile(request.user)
    role = get_profile_role(request.user)

    if role == 'customer' and not request.user.is_superuser:
        return redirect('customer_request_quote')

    if role == 'manufacturer' and not request.user.is_superuser:
        return redirect('manufacturer_dashboard')

    # 1. IDENTIFY USER ROLES USING OUR NEW DATABASE MODEL!
    is_admin = False
    is_mfg = False

    if role is not None:
        is_admin = (role == 'admin') or request.user.is_superuser
        is_mfg = (role == 'manufacturer') or request.user.is_superuser
    elif request.user.is_superuser:
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
            new_order, err = _create_order_from_post(request)
            if err:
                messages.error(request, err)
            else:
                messages.success(request, f"Order {new_order.order_id} successfully created!")
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