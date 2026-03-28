import json

from django.contrib import messages
from django.contrib.auth import authenticate, logout
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .auth_utils import ensure_user_profile, get_profile_role
from .models import ChatMessage, Order
from .services import (
    apply_flowchart_step_update,
    create_chat_message_from_request,
    create_order_from_post,
    lookup_order_with_chats,
    parse_flowchart_status_post,
)

from django.http import JsonResponse
from gpt4all import GPT4All
from .models import Order, ChatMessage


try:
    print("Loading AI Model...")
    ai_model = GPT4All("orca-mini-3b-gguf2-q4_0.gguf")
    print("AI Model loaded successfully!")
except Exception as e:
    print(f"Failed to load AI: {e}")
    ai_model = None

def generate_ai_suggestion(request):
    """Hidden endpoint for staff to generate an AI draft."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_msg = data.get('customer_message')
            context_step = data.get('context', 'General Inquiry')
            order_id = data.get('order_id')

            if not ai_model:
                return JsonResponse({'success': False, 'error': 'AI model is offline or loading.'})

            # Give the AI specific instructions on how to behave
            prompt = f"""You are a helpful support agent for Stremet, a steel manufacturing factory. 
            A customer asked a question about order {order_id}.
            Context: They are asking about the '{context_step}' stage.
            Customer says: "{customer_msg}"
            Write a polite, professional 1-paragraph reply addressing their question. Do not use placeholders."""
            
            # Generate the text
            suggestion = ai_model.generate(prompt, max_tokens=150)
            
            return JsonResponse({'success': True, 'suggestion': suggestion.strip()})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request'})

def _get_role_redirect(user):
    """Return the URL name to redirect to based on user role."""
    ensure_user_profile(user)
    role = get_profile_role(user)
    if role == "designer":
        return "designer_dashboard"
    if role == "manufacturer":
        return "manufacturer_dashboard"
    if role == "customer":
        return "customer_request_quote"
    return "staff_dashboard"


def _can_use_customer_quote_portal(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = get_profile_role(user)
    return role in ("customer", "admin")


def staff_login(request):
    """Handles authentication for all internal staff."""
    if request.user.is_authenticated:
        return redirect(_get_role_redirect(request.user))

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(_get_role_redirect(user))
        messages.error(request, "Invalid username or password.")

    return render(request, "home/staff_login.html")


def staff_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")


def dashboard(request):
    """Renders the main landing page."""
    return render(request, "home/index.html")


def customer_panel(request):
    """View for Customers to track orders via Order ID (same as customer app; URL name may resolve here)."""
    order = None
    chat_msgs = []
    if request.method == "POST":
        order_id = request.POST.get("order_id")
        order, chat_msgs = lookup_order_with_chats(order_id)
        if order is None and order_id:
            messages.error(request, f"Order ID '{order_id}' could not be found.")

    return render(
        request,
        "customer/customer_panel.html",
        {"order": order, "chat_msgs": chat_msgs},
    )


@login_required(login_url="login")
def customer_request_quote(request):
    """Logged-in customers (and admins testing) submit manufacturing quote requests."""
    ensure_user_profile(request.user)
    if not _can_use_customer_quote_portal(request.user):
        role = get_profile_role(request.user)
        if role == "manufacturer":
            return redirect("manufacturer_dashboard")
        if role == "designer":
            return redirect("designer_dashboard")
        messages.error(request, "You do not have access to this page.")
        return redirect("home_dashboard")

    if request.method == "POST" and "create_customer_order" in request.POST:
        new_order, err = create_order_from_post(request)
        if err:
            messages.error(request, err)
        else:
            messages.success(
                request,
                f"Quote request {new_order.order_id} submitted. Our team will review it shortly.",
            )
            return redirect("customer_request_quote")

    return render(
        request,
        "home/customer_request_quote.html",
        {
            "default_client_email": request.user.email or "",
        },
    )


@login_required(login_url="login")
def staff_dashboard(request):
    """
    Unified view: Checks user roles from UserProfile to show the correct features.
    Admins see order creation; Manufacturers see production tracking.
    """
    ensure_user_profile(request.user)
    role = get_profile_role(request.user)

    if role == "customer" and not request.user.is_superuser:
        return redirect("customer_request_quote")

    if role == "manufacturer" and not request.user.is_superuser:
        return redirect("manufacturer_dashboard")

    is_admin = False
    is_mfg = False

    if role is not None:
        is_admin = (role == "admin") or request.user.is_superuser
        is_mfg = (role == "manufacturer") or request.user.is_superuser
    elif request.user.is_superuser:
        is_admin = True
        is_mfg = True

    if is_admin or request.user.is_superuser:
        return render(request, "home/dashboard.html")

    context = {
        "is_admin": is_admin,
        "is_mfg": is_mfg,
    }

    if request.method == "POST":
        if is_admin and "create_order" in request.POST:
            new_order, err = create_order_from_post(request)
            if err:
                messages.error(request, err)
            else:
                messages.success(
                    request, f"Order {new_order.order_id} successfully created!"
                )
            return redirect("staff_dashboard")

        if is_mfg and "search_order" in request.POST:
            search_id = request.POST.get("order_id")
            try:
                order = Order.objects.get(order_id=search_id)
                context["order"] = order
            except Order.DoesNotExist:
                messages.error(request, f"Order ID '{search_id}' could not be found.")

    return render(request, "home/unified_staff_panel.html", context)


@login_required(login_url="login")
def update_item_status(request):
    """Hidden endpoint to update the database via Javascript AJAX."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request"})

    try:
        parsed = parse_flowchart_status_post(request.body)
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"success": False, "error": "Invalid JSON or payload"})

    err = apply_flowchart_step_update(
        parsed["item_id"], parsed["step_number"], parsed["is_done"]
    )
    if err:
        return JsonResponse({"success": False, "error": err})
    return JsonResponse({"success": True})


@login_required(login_url='login')
def support_hub(request):
    """Centralized page for viewing all support messages, contexts, and files."""
    
    # 1. Determine if the user is staff or a customer
    is_staff = False
    if hasattr(request.user, 'profile') and request.user.profile.role in ['admin', 'manufacturer']:
        is_staff = True
    elif request.user.is_superuser:
        is_staff = True

    # --- NEW: HANDLE ADMIN REPLIES DIRECTLY ON THIS PAGE ---
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        chat_message = request.POST.get('chat_message')
        step_context = request.POST.get('step_context')
        chat_attachment = request.FILES.get('chat_attachment')

        try:
            order = Order.objects.get(order_id=order_id)
            # Save the admin's reply to the database
            ChatMessage.objects.create(
                order=order,
                sender=request.user,
                message=chat_message,
                step_context=step_context,
                attachment=chat_attachment
            )
            messages.success(request, f"Reply successfully sent to Order {order_id}!")
        except Order.DoesNotExist:
            messages.error(request, "Error: Could not find that order.")
            
        # Refresh the page to show the new message
        return redirect('support_hub')

    # 2. Fetch the correct messages
    if is_staff:
        messages_feed = ChatMessage.objects.all().order_by('-timestamp')
    else:
        messages_feed = ChatMessage.objects.filter(sender=request.user).order_by('-timestamp')

    context = {
        'messages_feed': messages_feed,
        'is_staff': is_staff
    }
    
    return render(request, 'home/support_hub.html', context)



def send_chat_message(request):
    """AJAX endpoint to receive and save chat messages with files (guests allowed)."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request"})

    payload, err = create_chat_message_from_request(request)
    if err:
        return JsonResponse({"success": False, "error": err})
    return JsonResponse(payload)


