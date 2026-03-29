import json
import os
import sys
import threading
import time

from django.contrib import messages
from django.contrib.auth import authenticate, logout
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponse,
    HttpResponseNotAllowed,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render

from .auth_utils import ensure_user_profile, get_profile_role
from .models import ChatMessage, Client, Order, OrderImage
from .services import (
    apply_flowchart_step_update,
    create_chat_message_from_request,
    create_order_from_post,
    lookup_order_with_chats,
    parse_flowchart_status_post,
)

from gpt4all import GPT4All


# Grounded in Stremet Oy (https://stremet.fi); output must read as a real Stremet support email.
STREMET_SUPPORT_SYSTEM_PROMPT = """You write AS Stremet customer support sending the next message to the client.

Stremet (Stremet Oy) is a Finnish industrial sheet-metal and steel partner (since 1995, Salo region): punching, laser cutting, bending, welding, surface treatment, assembly, design support. Values: quality, reliable lead times, sustainability, long-term industrial relationships.

You receive structured facts from our database (order, customer contact, full message thread, and who is replying on our side). Use those facts naturally—greet and refer using real names, company, and order id when provided. Do not invent exact dates, prices, tonnages, or legal commitments that are not in the data; if something is missing, say you will confirm with production/sales and follow up.

Tone: warm, professional, calm, concise. If the customer is upset, acknowledge it briefly and stay constructive. No harassment, discrimination, or abuse. Refuse harmful or illegal requests briefly and redirect to legitimate order support.

CRITICAL OUTPUT RULES:
- Your entire output is ONLY the outbound reply text the customer will read (like an email body). 
- Do NOT prefix with assistant chatter: no "Sure!", "Here is a draft", "You could write", "Below is", no markdown code fences, no bullet list of instructions to yourself.
- Do NOT role-play explaining what you are doing. Start as the support person would (e.g. greeting or direct answer).
- Use real names/sign-offs consistent with the "You are replying as" section when appropriate (e.g. first name + Stremet / team).
- Match the customer's language when the thread is clearly in one language; otherwise use clear professional English.

Follow these rules on every response."""


def _load_gpt4all_model():
    """
    Load Orca Mini with GPU when possible.

    Override with env:
      GPT4ALL_DEVICE=cuda|kompute|cpu|gpu  (gpu → try CUDA then Kompute on Windows/Linux)
      GPT4ALL_NGL=100  (layers offloaded to GPU; Vulkan/CUDA)

    On macOS, default None uses Metal on Apple Silicon (per GPT4All).
    """
    common_kw = dict(
        model_name="orca-mini-3b-gguf2-q4_0.gguf",
        n_ctx=2048,
        n_threads=os.cpu_count() or 4,
    )
    ngl = int(os.environ.get("GPT4ALL_NGL", "100"))
    override = os.environ.get("GPT4ALL_DEVICE", "").strip()
    if override.lower() == "gpu" and sys.platform != "darwin":
        # On Windows/Linux, GPT4All maps "gpu" inconsistently; use CUDA → Kompute auto-detect.
        override = ""

    if override.lower() == "cpu":
        print("Loading AI Model (CPU only; GPT4ALL_DEVICE=cpu)...")
        return GPT4All(**common_kw, device="cpu")

    if override:
        print(f"Loading AI Model (GPT4ALL_DEVICE={override!r})...")
        kwargs = {**common_kw, "device": override}
        if override.lower() != "cpu":
            kwargs["ngl"] = ngl
        return GPT4All(**kwargs)

    if sys.platform == "darwin":
        try:
            print("Loading AI Model (default backend; Metal on Apple Silicon)...")
            return GPT4All(**common_kw, ngl=ngl)
        except Exception as e:
            print(f"GPU/default backend failed: {e}")
        print("Loading AI Model (CPU fallback)...")
        return GPT4All(**common_kw, device="cpu")

    for dev, label in (("cuda", "NVIDIA CUDA"), ("kompute", "Kompute (Vulkan GPU)")):
        try:
            print(f"Loading AI Model (trying {label})...")
            return GPT4All(**common_kw, device=dev, ngl=ngl)
        except Exception as e:
            print(f"{label} unavailable: {e}")
    print("Loading AI Model (CPU fallback)...")
    return GPT4All(**common_kw, device="cpu")


try:
    ai_model = _load_gpt4all_model()
    print("AI Model loaded successfully!")
except Exception as e:
    print(f"Failed to load AI: {e}")
    ai_model = None

# GPT4All instances are not safe for concurrent generate(); serialize access.
_ai_generate_lock = threading.Lock()


def _warmup_ai_model_delayed():
    """Prime llama runtime after a short delay so the server can bind first."""
    if ai_model is None:
        return
    time.sleep(1.0)
    try:
        with _ai_generate_lock:
            with ai_model.chat_session(system_prompt=STREMET_SUPPORT_SYSTEM_PROMPT):
                # One greedy token warms the same path as live streaming.
                for _ in ai_model.generate(
                    "ok",
                    max_tokens=1,
                    temp=0.0,
                    top_k=1,
                    top_p=1.0,
                    streaming=True,
                    n_batch=128,
                ):
                    break
    except Exception as exc:
        print(f"AI warm-up skipped: {exc}")


if ai_model is not None:
    threading.Thread(
        target=_warmup_ai_model_delayed,
        name="gpt4all-warmup",
        daemon=True,
    ).start()


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


# Keep thread excerpt within model context (2048 tokens total with system + template).
_AI_THREAD_MAX_CHARS = 5000


def _user_can_access_order_for_ai(user, order):
    if _user_is_support_staff(user):
        return True
    uemail = (user.email or "").strip().lower()
    if uemail and (order.client.email or "").strip().lower() == uemail:
        return True
    return ChatMessage.objects.filter(order=order, sender=user).exists()


def _display_name(user):
    if user is None:
        return "Guest"
    full = (user.get_full_name() or "").strip()
    if full:
        return f"{full} ({user.username})"
    return user.username or "Unknown"


def _message_role_line(msg):
    if msg.sender_id is None:
        return "Guest / unidentified portal sender"
    role = get_profile_role(msg.sender)
    if role == "customer":
        return "Customer"
    if role == "admin":
        return "Stremet team — administrator"
    if role == "manufacturer":
        return "Stremet team — manufacturing"
    if role == "designer":
        return "Stremet team — designer"
    return f"Portal user — {role or 'unknown'}"


def _format_order_facts(order):
    lines = [
        f"Order ID: {order.order_id}",
        f"Production stage (system field): {order.get_status_display()}",
        f"Material / grade: {order.steel_grade}",
        f"Dimensions: {order.dimensions}",
        f"Quantity (tons): {order.quantity_tons}",
        f"Target delivery date: {order.target_delivery}",
        f"Order record created: {order.created_at.isoformat(timespec='minutes')}",
    ]
    if order.product_form:
        lines.append(f"Product form: {order.product_form}")
    if order.surface_finish:
        lines.append(f"Surface finish: {order.surface_finish}")
    extras = []
    if order.heat_treatment:
        extras.append("heat treatment requested")
    if order.ultrasonic_test:
        extras.append("ultrasonic test requested")
    if order.mill_certificate:
        extras.append("mill certificate requested")
    if extras:
        lines.append("Options: " + "; ".join(extras))
    lines.append(f"Client company: {order.client.company_name}")
    lines.append(f"Client email (CRM): {order.client.email}")
    if order.client.name:
        lines.append(f"Client contact name: {order.client.name}")
    items = list(order.items.all()[:15])
    if items:
        lines.append("Line items:")
        for it in items:
            lines.append(
                f"  - {it.item_name} × {it.quantity} "
                f"(shop floor status: {it.current_status})"
            )
    return "\n".join(lines)


def _format_replying_user(user):
    role = get_profile_role(user)
    name = (user.get_full_name() or "").strip() or user.username
    return (
        f"Sign or speak as: {name}\n"
        f"Username: {user.username}\n"
        f"Email: {user.email or '—'}\n"
        f"Portal role: {role or '—'}"
    )


def _build_thread_transcript(order):
    msgs = list(
        ChatMessage.objects.filter(order=order)
        .order_by("timestamp")
        .select_related("sender")
    )
    blocks = []
    for i, msg in enumerate(msgs, start=1):
        ts = msg.timestamp.isoformat(sep=" ", timespec="minutes")
        who = _display_name(msg.sender) if msg.sender_id else "Guest (not logged in)"
        role_line = _message_role_line(msg)
        step = f"\nFlow / step context: {msg.step_context}" if msg.step_context else ""
        att = "\n[Portal note: file attachment on this message]" if msg.attachment else ""
        blocks.append(
            f"--- Message {i} | {ts} ---\n"
            f"From: {who} | Role: {role_line}{step}\n"
            f"{msg.message}{att}"
        )
    text = "\n\n".join(blocks)
    if len(text) > _AI_THREAD_MAX_CHARS:
        text = (
            "[Older messages truncated. Most recent part of the thread follows.]\n\n"
            + text[-_AI_THREAD_MAX_CHARS:]
        )
    return text or "(No messages yet in this order thread.)"


def _build_support_ai_user_context(order, replying_user):
    return (
        "=== ORDER (from database) ===\n"
        f"{_format_order_facts(order)}\n\n"
        "=== CUSTOMER / CLIENT CONTACT (from database) ===\n"
        f"Company: {order.client.company_name}\n"
        f"Contact email: {order.client.email}\n"
        f"Contact name on file: {order.client.name or '—'}\n\n"
        "=== YOU ARE REPLYING AS (logged-in user; be consistent with this identity) ===\n"
        f"{_format_replying_user(replying_user)}\n\n"
        "=== FULL SUPPORT THREAD FOR THIS ORDER (oldest first) ===\n"
        f"{_build_thread_transcript(order)}\n\n"
        "Write the next Stremet support reply to the customer, continuing this conversation. "
        "Use the facts above. Output only the outgoing message body—no preamble or meta."
    )


@login_required(login_url="login")
def generate_ai_suggestion(request):
    """Stream an AI draft from full order thread + DB facts (plain text, not auto-sent)."""
    ensure_user_profile(request.user)

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        return HttpResponse(
            "Invalid JSON body.",
            status=400,
            content_type="text/plain; charset=utf-8",
        )

    order_id = (data.get("order_id") or "").strip()
    if not order_id:
        return HttpResponse(
            "order_id is required.",
            status=400,
            content_type="text/plain; charset=utf-8",
        )

    if not ai_model:
        return HttpResponse(
            "AI model is offline or loading.",
            status=503,
            content_type="text/plain; charset=utf-8",
        )

    order = (
        Order.objects.filter(order_id=order_id)
        .select_related("client")
        .prefetch_related("items")
        .first()
    )
    if order is None:
        return HttpResponse(
            "Order not found.",
            status=404,
            content_type="text/plain; charset=utf-8",
        )
    if not _user_can_access_order_for_ai(request.user, order):
        return HttpResponse(
            "You do not have access to AI suggestions for this order.",
            status=403,
            content_type="text/plain; charset=utf-8",
        )

    user_prompt = _build_support_ai_user_context(order, request.user)

    def token_stream():
        try:
            with _ai_generate_lock:
                with ai_model.chat_session(system_prompt=STREMET_SUPPORT_SYSTEM_PROMPT):
                    stream = ai_model.generate(
                        user_prompt,
                        max_tokens=512,
                        temp=0.6,
                        top_k=40,
                        top_p=0.85,
                        repeat_penalty=1.15,
                        streaming=True,
                        # Larger batches speed up prompt processing (time-to-first-token).
                        n_batch=128,
                    )
                    for token in stream:
                        if isinstance(token, str):
                            yield token.encode("utf-8")
                        else:
                            yield bytes(token)
        except Exception as e:
            yield ("\n\n[Generation stopped: " + str(e) + "]").encode(
                "utf-8", errors="replace"
            )

    response = StreamingHttpResponse(
        token_stream(),
        content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def client_directory(request):
    """Custom interface for Admins to view all clients and their associated orders."""

    is_admin = request.user.is_superuser or (
        hasattr(request.user, "profile") and request.user.profile.role == "admin"
    )
    if not is_admin:
        messages.error(
            request, "Access Denied. You do not have administrator privileges."
        )
        return redirect("home_dashboard")

    clients = Client.objects.prefetch_related("orders").all().order_by("company_name")

    return render(request, "home/client_directory.html", {"clients": clients})


def admin_panel(request):
    """View for the Administrator Portal to create new manufacturing orders."""

    is_admin = request.user.is_superuser or (
        hasattr(request.user, "profile") and request.user.profile.role == "admin"
    )
    if not is_admin:
        messages.error(
            request, "Access Denied. You do not have administrator privileges."
        )
        return redirect("home_dashboard")

    if request.method == "POST":
        try:
            company_name = request.POST.get("company_name")
            client_email = request.POST.get("client_email")

            client, _ = Client.objects.get_or_create(
                email=client_email,
                defaults={"company_name": company_name},
            )

            thickness = request.POST.get("dim_thickness") or "0"
            width = request.POST.get("dim_width") or "0"
            length = request.POST.get("dim_length") or "0"
            dimensions_str = f"{thickness}mm x {width}mm x {length}mm"

            quantity_tons = request.POST.get("quantity_tons")
            if not quantity_tons:
                quantity_tons = 0

            new_order = Order.objects.create(
                order_id=request.POST.get("order_id"),
                client=client,
                target_delivery=request.POST.get("target_delivery"),
                steel_grade=request.POST.get("steel_grade"),
                product_form=request.POST.get("product_form"),
                dimensions=dimensions_str,
                quantity_tons=quantity_tons,
                surface_finish=request.POST.get("surface_finish"),
                heat_treatment=(request.POST.get("heat_treatment") == "yes"),
                ultrasonic_test=(request.POST.get("ultrasonic_test") == "yes"),
                mill_certificate=(request.POST.get("mill_certificate") == "yes"),
                blueprint_file=request.FILES.get("blueprint_file"),
                admin_notes=request.POST.get("admin_notes"),
            )

            images = request.FILES.getlist("reference_images")
            for img in images:
                OrderImage.objects.create(order=new_order, image=img)

            messages.success(
                request,
                f"Manufacturing Order {new_order.order_id} successfully created!",
            )
            return redirect("admin_panel")

        except Exception as e:
            messages.error(request, f"Error saving order: {e}")
            return redirect("admin_panel")

    return render(request, "home/admin_panel.html")


def _get_role_redirect(user):
    """Return the URL name to redirect to based on user role."""
    ensure_user_profile(user)
    role = get_profile_role(user)
    if role == "designer":
        return "designer_dashboard"
    if role == "manufacturer":
        return "manufacturer_dashboard"
    if role == "warehouse":
        return "warehouse_dashboard"
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
        if role == "warehouse":
            return redirect("warehouse_dashboard")
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

    if role == "warehouse" and not request.user.is_superuser:
        return redirect("warehouse_dashboard")

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


