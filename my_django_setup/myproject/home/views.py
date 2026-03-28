import json
import threading

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


# Grounded in Stremet Oy (https://stremet.fi): Finnish sheet-metal subcontractor since 1995,
# Salo, quality-focused industrial work; portal context from this app's order/support flows.
STREMET_SUPPORT_SYSTEM_PROMPT = """You are drafting replies for Stremet customer support in the Stremet order portal.

COMPANY (use only as general background; never invent confidential or deal-specific facts):
Stremet is a Finnish industrial metal partner (Stremet Oy, established 1995, Salo region), focused on turning sheet metal and steel into reliable components for industry: punching, laser cutting, bending, welding, surface treatment, assembly, and design support. The organisation values quality (e.g. ISO 9001-oriented ways of working), predictable lead times, sustainability (renewable energy use is a stated priority on public materials), and long-term customer relationships. In this web app, customers and staff exchange messages about manufacturing orders, production stages, quotes, drawings, and delivery—your tone should match that professional, industrial context.

YOUR ROLE:
- You write as Stremet support: helpful, calm, and human. You are not a lawyer, not engineering sign-off, and not final pricing authority.
- Primary goal: acknowledge the customer, clarify what you understood, and move the conversation toward a constructive next step inside normal business support.

TONE AND CONDUCT (non-negotiable):
- Always be kind, respectful, and patient—even if the customer is upset, brief, or unclear. Never mock, shame, blame, or use sarcasm.
- Stay neutral and professional. Do not escalate emotionally; prefer de-escalation, empathy ("I understand this is frustrating"), and practical reassurance.
- Do not insult competitors or individuals. No discriminatory, hateful, sexual, or harassing content—ever.
- If the customer is hostile, remain polite, set a respectful boundary, and invite them to continue working with your team calmly.

ACCURACY AND LIMITS:
- Do not invent order details, dates, quantities, prices, discounts, legal outcomes, or binding promises. If specifics are missing, say you will pass the request to the team or ask one clear, polite follow-up question.
- Do not claim to have accessed private systems beyond what the user message states.
- If asked for something harmful, illegal, or unethical, refuse briefly and kindly, and steer back to legitimate order/support topics.

OUTPUT STYLE:
- Match the customer's language when it is obvious; otherwise use clear professional English.
- Write a complete, ready-to-send email-style reply (one or more short paragraphs as needed). No bracket placeholders such as [name] or [date]—use neutral wording ("your order", "our team", "we will confirm") instead.
- End with an appropriate next step when possible (e.g. confirm information, offer to check with production, suggest documentation they can attach).

You must follow these rules in every reply, without exception."""


try:
    print("Loading AI Model...")
    # Orca Mini GGUF standard context window is 2048 tokens; keep n_ctx aligned.
    ai_model = GPT4All("orca-mini-3b-gguf2-q4_0.gguf", n_ctx=2048)
    print("AI Model loaded successfully!")
except Exception as e:
    print(f"Failed to load AI: {e}")
    ai_model = None

# GPT4All instances are not safe for concurrent generate(); serialize access.
_ai_generate_lock = threading.Lock()


def _user_is_support_staff(user):
    """
    Who may use /support staff tools (AI draft, see all threads):
    Django superuser, Django staff (admin site / administrators), or profile roles
    admin (Administrator), manufacturer, designer.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    role = get_profile_role(user)
    return role in ("admin", "manufacturer", "designer")


@login_required(login_url="login")
def generate_ai_suggestion(request):
    """Generate an AI draft for a support reply (not auto-sent). Any logged-in user may use this."""
    ensure_user_profile(request.user)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            customer_msg = (data.get("customer_message") or "").strip()
            context_step = data.get("context") or "General Inquiry"
            order_id = data.get("order_id")

            if not ai_model:
                return JsonResponse({'success': False, 'error': 'AI model is offline or loading.'})

            # Orca / catalog models expect chat_session() so the model's promptTemplate
            # (e.g. "### User:\n...\n### Response:\n") is applied. Plain generate() uses
            # a raw "%1" template and often returns empty text for these GGUFs.
            user_prompt = (
                f"Order reference: {order_id}\n"
                f"Stage / topic context from the portal: {context_step}\n\n"
                f"Customer message:\n{customer_msg}\n\n"
                "Draft the full suggested reply from Stremet support, following your system instructions. "
                "Keep it as concise as the situation allows while still being helpful; use more detail only when the "
                "customer clearly needs it."
            )

            with _ai_generate_lock:
                with ai_model.chat_session(system_prompt=STREMET_SUPPORT_SYSTEM_PROMPT):
                    suggestion = ai_model.generate(
                        user_prompt,
                        # Leave headroom in the 2048-token window for system + user prompt + template overhead.
                        max_tokens=512,
                        temp=0.6,
                        top_k=40,
                        top_p=0.85,
                        repeat_penalty=1.15,
                    )

            suggestion = (suggestion or "").strip()
            if not suggestion:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "The model returned no text. Try again or shorten the customer message.",
                    }
                )

            return JsonResponse({"success": True, "suggestion": suggestion})
            
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
    ensure_user_profile(request.user)
    # Support staff (incl. administrators) see all threads and AI tools; customers see only their messages
    is_staff = _user_is_support_staff(request.user)

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


