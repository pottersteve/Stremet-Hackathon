"""
Local GPT4All model lifecycle: load and warm up at Django app startup (see home.apps).

Skipped automatically for common management commands and when GPT4ALL_SKIP_PRELOAD is set.
"""

from __future__ import annotations

import os
import sys
import threading

from gpt4all import GPT4All

# Grounded in Stremet Oy (https://stremet.fi); output must read as a real Stremet support email.
STREMET_SUPPORT_SYSTEM_PROMPT = """You write AS Stremet customer support sending the next message to the client.

Stremet (Stremet Oy) is a Finnish industrial sheet-metal and steel partner (since 1995, Salo region): punching, laser cutting, bending, welding, surface treatment, assembly, design support. Values: quality, reliable lead times, sustainability, long-term industrial relationships.

You receive structured facts from our database (order, customer contact, full message thread, and who is replying on our side). Use those facts naturally—greet and refer using real names, company, and order id when provided. Do not invent exact dates, prices, tonnages, or legal commitments that are not in the data; if something is missing, say you will confirm with production/sales and follow up.

Tone: warm, professional, calm, concise. If the customer is upset, acknowledge it briefly and stay constructive. No harassment, discrimination, or abuse. Refuse harmful or illegal requests briefly and redirect to legitimate order support.

CRITICAL OUTPUT RULES:
- Your entire output is ONLY the message body the customer will read—never an email template with headers. Do NOT output To:, From:, Subject:, Date:, time stamps, RE:/FW: lines, or any metadata at the top or bottom.
- Always begin with a short, natural greeting (e.g. "Hi [name]!" / "Hello [name]," / Finnish: "Hei …!" / "Tervehdys …,") using the customer's or thread-appropriate name when you know it; if unknown, use a neutral "Hi!" / "Hello," style opening. Do not jump straight into business without a greeting.
- Always end with a polite closing line and sign-off using the real name (and role/team if natural) from the "You are replying as" section—e.g. "Best regards," then a new line with the person's first name (and "Stremet" or the team if it fits). Acceptable variants: "Kind regards," "Warm regards," or the equivalent in the customer's language (e.g. "Ystävällisin terveisin," + name).
- Do NOT prefix with assistant chatter: no "Sure!", "Here is a draft", "You could write", "Below is", no markdown code fences, no bullet list of instructions to yourself.
- Do NOT role-play explaining what you are doing; write only the support message from greeting through sign-off.
- Match the customer's language when the thread is clearly in one language; otherwise use clear professional English (including greeting and closing in that language).

Follow these rules on every response."""

_ai_model: GPT4All | None = None
_preload_attempted = False
# GPT4All instances are not safe for concurrent generate(); serialize access.
_ai_generate_lock = threading.Lock()

_SKIP_MANAGEMENT_COMMANDS = frozenset(
    {
        "migrate",
        "makemigrations",
        "squashmigrations",
        "flush",
        "collectstatic",
        "test",
        "shell",
        "dbshell",
        "showmigrations",
        "dumpdata",
        "loaddata",
        "check",
        "compilemessages",
        "makemessages",
    }
)


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def should_skip_gpt4all_preload() -> bool:
    if _env_truthy("GPT4ALL_SKIP_PRELOAD"):
        return True
    if len(sys.argv) > 1 and sys.argv[1] in _SKIP_MANAGEMENT_COMMANDS:
        return True
    return False


def get_ai_model() -> GPT4All | None:
    return _ai_model


def get_ai_generate_lock() -> threading.Lock:
    return _ai_generate_lock


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


def _warmup_model(model: GPT4All) -> None:
    """Prime llama runtime on the same path as live streaming."""
    with _ai_generate_lock:
        with model.chat_session(system_prompt=STREMET_SUPPORT_SYSTEM_PROMPT):
            for _ in model.generate(
                "ok",
                max_tokens=1,
                temp=0.0,
                top_k=1,
                top_p=1.0,
                streaming=True,
                n_batch=128,
            ):
                break


def _warmup_model_in_thread(model: GPT4All) -> None:
    def run() -> None:
        try:
            _warmup_model(model)
        except Exception as exc:
            print(f"AI warm-up skipped: {exc}")

    threading.Thread(target=run, name="gpt4all-warmup", daemon=True).start()


def preload_gpt4all_at_startup() -> None:
    """
    Load (and optionally warm) the model once per process during Django startup.

    Warm-up is synchronous by default so the first customer request is not paying cold-start
    latency. Set GPT4ALL_ASYNC_WARMUP=1 to defer warm-up to a background thread.
    """
    global _ai_model, _preload_attempted

    if _preload_attempted:
        return
    _preload_attempted = True

    if should_skip_gpt4all_preload():
        print("GPT4All preload skipped (management command or GPT4ALL_SKIP_PRELOAD).")
        return

    try:
        _ai_model = _load_gpt4all_model()
        print("AI Model loaded successfully!")
    except Exception as e:
        print(f"Failed to load AI: {e}")
        _ai_model = None
        return

    if _ai_model is None:
        return

    if _env_truthy("GPT4ALL_ASYNC_WARMUP"):
        _warmup_model_in_thread(_ai_model)
    else:
        try:
            _warmup_model(_ai_model)
            print("AI Model warm-up complete.")
        except Exception as exc:
            print(f"AI warm-up failed (model is loaded): {exc}")
