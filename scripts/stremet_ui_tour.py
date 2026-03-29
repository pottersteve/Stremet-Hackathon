#!/usr/bin/env python3
"""
Automated UI walkthrough: migrate, seed sample data, start Django, drive the app with Playwright.

Credentials and seed scope: STREMET_DEMO_DATA.md (STREMET_SEED_PASSWORD).

Use a project virtual environment:

  python -m venv .venv
  .venv\\Scripts\\activate          # Windows
  pip install -r requirements.txt -r requirements-dev.txt
  python -m playwright install chromium

Django preloads GPT4All at startup (see home.apps). Migrate, seed, and runserver can take
a long time on first run while the model loads. Increase --server-ready-timeout if needed.
"""

from __future__ import annotations

import argparse
import atexit
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
MANAGE_DIR = REPO_ROOT / "my_django_setup" / "myproject"
DEFAULT_SEED_PASSWORD = "StremetTrain2026!"

# Accounts created by seed_stremet_demo (see STREMET_DEMO_DATA.md)
USER_CUSTOMER = "makinen.eero"
USER_ADMIN = "virtanen.mikko"
USER_DESIGNER = "nieminen.laura"
USER_WAREHOUSE = "lehtonen.sanna"
USER_MANUFACTURER = "koskinen.jukka"
CLIENT_COMPANY = "Pohjan Lift Components Oy"
CLIENT_EMAIL = "eero.makinen@pohjanlift.fi"

_server_proc: subprocess.Popen | None = None


def _manage_py() -> list[str]:
    return [sys.executable, str(MANAGE_DIR / "manage.py")]


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
    return env


def run_manage(*args: str, check: bool = True) -> None:
    subprocess.run(
        _manage_py() + list(args),
        cwd=str(MANAGE_DIR),
        env=_subprocess_env(),
        check=check,
    )


def wait_for_http_ok(url: str, timeout_sec: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_sec
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if 200 <= resp.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
        time.sleep(0.4)
    raise RuntimeError(f"Server at {url} did not respond in time: {last_err!r}")


def start_runserver(host: str, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        _manage_py() + ["runserver", f"{host}:{port}", "--noreload"],
        cwd=str(MANAGE_DIR),
        env=_subprocess_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )


def stop_server() -> None:
    global _server_proc
    if _server_proc is None:
        return
    if _server_proc.poll() is not None:
        _server_proc = None
        return
    _server_proc.terminate()
    try:
        _server_proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        _server_proc.kill()
    _server_proc = None


def beat_pause(label: str, args: argparse.Namespace) -> None:
    if args.interactive:
        input(f"\n>>> {label}\n    Press Enter to continue… ")
    else:
        time.sleep(args.action_delay_ms / 1000.0)


def after_action(page, delay_ms: int) -> None:
    if delay_ms > 0:
        page.wait_for_timeout(delay_ms)


def do_login(page, base: str, username: str, password: str, delay_ms: int) -> None:
    page.goto(f"{base}/login/", wait_until="domcontentloaded")
    after_action(page, delay_ms)
    page.get_by_label("Username", exact=False).fill(username)
    after_action(page, delay_ms)
    page.get_by_label("Password", exact=False).fill(password)
    after_action(page, delay_ms)
    page.get_by_role("button", name=re.compile(r"^Log In$", re.I)).click()
    page.wait_for_load_state("networkidle")
    after_action(page, delay_ms)


def do_logout(page, base: str, delay_ms: int) -> None:
    page.goto(f"{base}/logout/", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    after_action(page, delay_ms)


def run_tour(args: argparse.Namespace) -> None:
    from playwright.sync_api import sync_playwright

    base = args.base_url.rstrip("/")
    delay_ms = args.action_delay_ms
    pw = args.password or os.environ.get("STREMET_SEED_PASSWORD") or DEFAULT_SEED_PASSWORD
    order_id = args.order_id or f"SO-2026-{int(time.time())}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=args.slow_mo)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            # Customer: login and quote request
            page.goto(f"{base}/login/", wait_until="domcontentloaded")
            beat_pause("Login form", args)
            do_login(page, base, USER_CUSTOMER, pw, delay_ms)
            page.wait_for_url(re.compile(r".*/request-quote/.*"), timeout=15000)
            beat_pause("Quote request form", args)
            after_action(page, delay_ms)

            page.locator('input[name="order_id"]').fill(order_id)
            after_action(page, delay_ms)
            page.locator('input[name="company_name"]').fill(CLIENT_COMPANY)
            after_action(page, delay_ms)
            page.locator('input[name="client_email"]').fill(CLIENT_EMAIL)
            after_action(page, delay_ms)
            page.locator('input[name="target_delivery"]').fill(args.delivery_date)
            after_action(page, delay_ms)
            page.locator('input[name="dim_thickness"]').fill("2")
            after_action(page, delay_ms)
            page.locator('input[name="dim_width"]').fill("600")
            after_action(page, delay_ms)
            page.locator('input[name="dim_length"]').fill("1200")
            after_action(page, delay_ms)
            page.locator('input[name="quantity_tons"]').fill("0.5")
            after_action(page, delay_ms)
            page.locator('textarea[name="admin_notes"]').fill(
                "Bracket set for cab frame revision 2026-Q2. Match existing powder RAL7035 batch from last delivery."
            )
            after_action(page, delay_ms)

            beat_pause("Submit quote request", args)
            page.locator('button[name="create_customer_order"]').click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Quote confirmation", args)

            # Customer portal: track order and chat
            page.goto(f"{base}/customer/", wait_until="domcontentloaded")
            after_action(page, delay_ms)
            page.locator('input[name="order_id"]').fill(order_id)
            after_action(page, delay_ms)
            page.get_by_role("button", name=re.compile(r"^Track$")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Order status", args)

            page.get_by_role("button", name=re.compile(r"Live Support")).click()
            after_action(page, delay_ms)
            page.locator("#chat-message-input").fill(
                "Hi, could you confirm lead time for this order? We need parts on site by month-end if possible."
            )
            after_action(page, delay_ms)
            page.locator("#send-chat-btn").click()
            after_action(page, delay_ms)
            beat_pause("Message sent", args)

            # Support: AI-assisted reply
            do_logout(page, base, delay_ms)
            do_login(page, base, USER_ADMIN, pw, delay_ms)
            page.goto(f"{base}/support/", wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Support inbox", args)

            msg_cards = page.locator(".message-card").filter(has_text=order_id)
            if msg_cards.count() == 0:
                raise RuntimeError(f"No thread found for order {order_id!r}.")
            card_loc = msg_cards.first
            card_loc.get_by_role(
                "button", name=re.compile(r"Suggest AI", re.I)
            ).click()
            after_action(page, delay_ms)

            reply_ta = card_loc.locator('textarea[name="chat_message"]').first
            deadline = time.monotonic() + args.ai_timeout_sec
            while time.monotonic() < deadline:
                val = reply_ta.input_value()
                if val and len(val.strip()) > 25:
                    break
                page.wait_for_timeout(500)
            else:
                print(
                    "\n[warn] AI suggestion did not complete within "
                    f"{args.ai_timeout_sec}s. Check GPT4All; using fallback reply text.\n",
                    file=sys.stderr,
                )

            beat_pause("Support reply draft", args)
            reply_ta.fill(
                reply_ta.input_value().strip()
                or "Thank you for your message. Our team is reviewing your quote and will respond shortly."
            )
            after_action(page, delay_ms)
            card_loc.get_by_role("button", name=re.compile(r"^Send Reply$")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Reply sent", args)

            # Designer: plan and BOM
            do_logout(page, base, delay_ms)
            do_login(page, base, USER_DESIGNER, pw, delay_ms)
            page.goto(f"{base}/designer/", wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)

            order_card = page.locator(".order-card").filter(has_text=order_id).first
            order_card.get_by_role("link", name=re.compile(r"^Open Plan$")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Manufacturing plan", args)

            page.locator('button[data-bs-target="#addStepModal"]').click()
            after_action(page, delay_ms)
            page.locator("#addStepModal").locator('input[name="name"]').fill(
                "Laser cut — cab bracket blanks"
            )
            after_action(page, delay_ms)
            beat_pause("Add manufacturing step", args)
            page.locator("#addStepModal").get_by_role(
                "button", name=re.compile(r"^Add Step$")
            ).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)

            page.locator(".list-group-item").filter(
                has_text=re.compile(r"Laser cut", re.I)
            ).filter(has_not_text=re.compile(r"Pick materials", re.I)).get_by_role(
                "link", name=re.compile(r"^Edit$")
            ).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Step details and BOM", args)

            mat_sel = page.locator("#id_material-0-item_reservation")
            mat_sel.wait_for(state="visible", timeout=10000)
            try:
                mat_sel.select_option(label=re.compile(r"SHE-DC01", re.I))
            except Exception:
                mat_sel.select_option(index=1)
            after_action(page, delay_ms)
            page.locator("#id_material-0-quantity").fill("1")
            after_action(page, delay_ms)
            page.locator("#id_material-0-unit").fill("sheet")
            after_action(page, delay_ms)

            page.locator("#id_quality-0-description").fill("Edge burr check")
            after_action(page, delay_ms)
            page.locator("#id_quality-0-expected_result").fill("No sharp burrs")
            after_action(page, delay_ms)

            beat_pause("Save step", args)
            page.get_by_role("button", name=re.compile(r"^Save Step$")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)

            page.get_by_role("link", name=re.compile(r"Back to Plan")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)

            page.locator("#plan-update-form").locator('select[name="status"]').select_option(
                "ready"
            )
            after_action(page, delay_ms)
            beat_pause("Set plan to Ready", args)
            page.get_by_role("button", name=re.compile(r"Save plan")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Plan saved", args)

            # Warehouse pickup
            do_logout(page, base, delay_ms)
            do_login(page, base, USER_WAREHOUSE, pw, delay_ms)
            page.goto(f"{base}/warehouse/pickup/", wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Pickup queue", args)

            wh_card = page.locator(".wh-card").filter(has_text=order_id).first
            wh_card.get_by_role("link", name=re.compile(r"Open pickup")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Confirm pickup", args)
            page.get_by_role(
                "button", name=re.compile(r"Confirm pickup", re.I)
            ).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Pickup done", args)

            # Manufacturer
            do_logout(page, base, delay_ms)
            do_login(page, base, USER_MANUFACTURER, pw, delay_ms)
            page.goto(f"{base}/manufacturer/", wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            page.locator('input[name="q"]').fill(order_id)
            after_action(page, delay_ms)
            page.get_by_role("button", name=re.compile(r"^Search$")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Production queue", args)

            mfg_card = page.locator(".mfg-order-card").filter(has_text=order_id).first
            mfg_card.get_by_role("link", name=re.compile(r"Open step")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Shop floor step", args)

            page.locator("#id_status").select_option("completed")
            after_action(page, delay_ms)
            qc0 = page.locator('[name="qc-0-result_status"]')
            if qc0.count() > 0:
                qc0.select_option("pass")
                after_action(page, delay_ms)
            page.get_by_role("button", name=re.compile(r"Save progress")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Production saved", args)

            # Customer: check progress again
            do_logout(page, base, delay_ms)
            page.goto(f"{base}/customer/", wait_until="domcontentloaded")
            after_action(page, delay_ms)
            page.locator('input[name="order_id"]').fill(order_id)
            after_action(page, delay_ms)
            page.get_by_role("button", name=re.compile(r"^Track$")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Updated order status", args)

            print(f"\nOrder id: {order_id}\n")
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stremet UI walkthrough: Playwright + migrate, seed, runserver.",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="App origin, e.g. http://127.0.0.1:8000 (default: derived from --host/--port)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="runserver bind address")
    parser.add_argument("--port", type=int, default=8000, help="runserver port")
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Do not spawn runserver (use an already-running Django instance).",
    )
    parser.add_argument(
        "--skip-migrate", action="store_true", help="Skip manage.py migrate"
    )
    parser.add_argument(
        "--skip-seed", action="store_true", help="Skip manage.py seed_stremet_demo"
    )
    parser.add_argument(
        "--order-id",
        default="",
        help="Quote order id (default: SO-2026-<unix_ts>)",
    )
    parser.add_argument(
        "--delivery-date",
        default="",
        help="target_delivery for quote (YYYY-MM-DD). Default: 30 days from today.",
    )
    parser.add_argument(
        "--password",
        default="",
        help="Password for seeded users (STREMET_SEED_PASSWORD env or built-in default)",
    )
    parser.add_argument(
        "--action-delay-ms",
        type=int,
        default=250,
        help="Pause after each automated UI action and between beats when --no-pause (default 250 ms)",
    )
    parser.add_argument(
        "--slow-mo",
        type=int,
        default=0,
        help="Playwright slow_mo in ms (default 0)",
    )
    parser.add_argument(
        "--ai-timeout-sec",
        type=int,
        default=120,
        help="Max seconds to wait for AI reply textarea to fill",
    )
    parser.add_argument(
        "--no-pause",
        action="store_true",
        dest="no_pause",
        help="No Enter between steps; use --action-delay-ms between beats",
    )
    parser.add_argument(
        "--server-ready-timeout",
        type=float,
        default=900.0,
        metavar="SEC",
        help=(
            "Max seconds to wait for HTTP after runserver starts "
            "(default 900; GPT4All preload at startup)"
        ),
    )
    args = parser.parse_args()
    args.interactive = not args.no_pause

    if not args.delivery_date:
        from datetime import date, timedelta

        args.delivery_date = (date.today() + timedelta(days=30)).isoformat()

    if not args.base_url:
        args.base_url = f"http://{args.host}:{args.port}"

    if not (MANAGE_DIR / "manage.py").is_file():
        print(
            f"Could not find manage.py at {MANAGE_DIR / 'manage.py'}",
            file=sys.stderr,
        )
        return 1

    global _server_proc
    atexit.register(stop_server)

    try:
        if not args.skip_migrate:
            print("Running migrations…")
            run_manage("migrate", "--noinput")

        if not args.skip_seed:
            print("Running seed_stremet_demo…")
            run_manage("seed_stremet_demo")

        if not args.no_server:
            print(
                f"Starting runserver on {args.host}:{args.port} "
                f"(waiting up to {args.server_ready_timeout:.0f}s for HTTP after GPT4All startup)…"
            )
            _server_proc = start_runserver(args.host, args.port)
            wait_for_http_ok(
                f"{args.base_url.rstrip('/')}/",
                timeout_sec=args.server_ready_timeout,
            )
            print("Server is up.")
        else:
            print(f"Checking server at {args.base_url}…")
            wait_for_http_ok(
                f"{args.base_url.rstrip('/')}/",
                timeout_sec=args.server_ready_timeout,
            )

        run_tour(args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}", file=sys.stderr)
        return e.returncode or 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        stop_server()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
