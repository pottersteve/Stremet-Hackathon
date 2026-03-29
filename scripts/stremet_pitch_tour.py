#!/usr/bin/env python3
"""
Stremet pitch demo: migrate, seed demo data, start Django, then drive the UI with Playwright.

See also: STREMET_DEMO_DATA.md (seed scope, demo users, STREMET_SEED_PASSWORD).

Use the project virtual environment so Django, gpt4all, and Playwright match this repo:

  python -m venv .venv
  .venv\\Scripts\\activate          # Windows
  pip install -r requirements.txt -r requirements-dev.txt
  python -m playwright install chromium

Django preloads GPT4All at startup (see home.apps). Migrate/seed/runserver may each take
a long time on first run while the model loads; the script waits for HTTP only after
runserver starts. Increase --server-ready-timeout if your machine is slower.
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

# Demo users (seed_stremet_demo)
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


def beat_pause(label: str, interactive: bool) -> None:
    if interactive:
        input(f"\n>>> {label}\n    Press Enter to continue… ")
    else:
        time.sleep(2.5)


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
    order_id = args.order_id or f"SO-2026-DEMO-{int(time.time())}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=args.slow_mo)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        try:
            # --- Beat 1: customer login + quote page ---
            do_login(page, base, USER_CUSTOMER, pw, delay_ms)
            page.wait_for_url(re.compile(r".*/request-quote/.*"), timeout=15000)
            beat_pause("Customer: quote request form (presenter can introduce the portal)", args.interactive)
            after_action(page, delay_ms)

            # --- Beat 2: fill quote ---
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
            page.locator('textarea[name="admin_notes"]').fill("Pitch demo quote — automated tour.")
            after_action(page, delay_ms)

            beat_pause("Customer: about to submit the quote request", args.interactive)
            page.locator('button[name="create_customer_order"]').click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Customer: quote submitted (success message)", args.interactive)

            # --- Beat 3: customer portal + chat ---
            page.goto(f"{base}/customer/", wait_until="domcontentloaded")
            after_action(page, delay_ms)
            page.locator('input[name="order_id"]').fill(order_id)
            after_action(page, delay_ms)
            page.get_by_role("button", name=re.compile(r"^Track$")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Customer: order tracking and progress area", args.interactive)

            page.get_by_role("button", name=re.compile(r"Live Support")).click()
            after_action(page, delay_ms)
            page.locator("#chat-message-input").fill(
                "Hello — this is our pitch demo. When can we expect feedback on this quote?"
            )
            after_action(page, delay_ms)
            page.locator("#send-chat-btn").click()
            page.wait_for_timeout(800)
            after_action(page, delay_ms)
            beat_pause("Customer: support message sent", args.interactive)

            # --- Beat 4: admin support + AI ---
            do_logout(page, base, delay_ms)
            do_login(page, base, USER_ADMIN, pw, delay_ms)
            page.goto(f"{base}/support/", wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Support hub: message thread for the demo order", args.interactive)

            msg_cards = page.locator(".message-card").filter(has_text=order_id)
            if msg_cards.count() == 0:
                raise RuntimeError(f"No support thread found for order {order_id!r}.")
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
                    "\n[warn] AI suggestion did not fill in time "
                    f"({args.ai_timeout_sec}s). Is GPT4All running? Using fallback reply text.\n",
                    file=sys.stderr,
                )

            beat_pause("Support: AI draft in reply box (or empty if model offline)", args.interactive)
            reply_ta.fill(
                reply_ta.input_value().strip()
                or "Thank you for your message. Our team is reviewing your quote and will respond shortly."
            )
            after_action(page, delay_ms)
            card_loc.get_by_role("button", name=re.compile(r"^Send Reply$")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Support: reply sent", args.interactive)

            # --- Beat 5: designer ---
            do_logout(page, base, delay_ms)
            do_login(page, base, USER_DESIGNER, pw, delay_ms)
            page.goto(f"{base}/designer/", wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)

            order_card = page.locator(".order-card").filter(has_text=order_id).first
            order_card.get_by_role("link", name=re.compile(r"^Open Plan$")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Designer: manufacturing plan editor", args.interactive)

            page.locator('button[data-bs-target="#addStepModal"]').click()
            after_action(page, delay_ms)
            page.locator("#addStepModal").locator('input[name="name"]').fill(
                "Laser cut — demo panel"
            )
            after_action(page, delay_ms)
            beat_pause("Designer: about to add a manufacturing step", args.interactive)
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
            beat_pause("Designer: step details — add BOM and optional quality check", args.interactive)

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

            beat_pause("Designer: saving step (creates warehouse pickup from BOM)", args.interactive)
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
            beat_pause("Designer: plan set to Ready — save metadata", args.interactive)
            page.get_by_role("button", name=re.compile(r"Save plan")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Designer: plan saved — manufacturer queue will unlock", args.interactive)

            # --- Beat 6: warehouse pickup ---
            do_logout(page, base, delay_ms)
            do_login(page, base, USER_WAREHOUSE, pw, delay_ms)
            page.goto(f"{base}/warehouse/pickup/", wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Warehouse: pickup queue", args.interactive)

            wh_card = page.locator(".wh-card").filter(has_text=order_id).first
            wh_card.get_by_role("link", name=re.compile(r"Open pickup")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Warehouse: confirm pickup (consumes stock)", args.interactive)
            page.get_by_role(
                "button", name=re.compile(r"Confirm pickup", re.I)
            ).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Warehouse: pickup complete", args.interactive)

            # --- Beat 7: manufacturer ---
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
            beat_pause("Manufacturer: production queue", args.interactive)

            mfg_card = page.locator(".mfg-order-card").filter(has_text=order_id).first
            mfg_card.get_by_role("link", name=re.compile(r"Open step")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Manufacturer: step execution and quality checklist", args.interactive)

            page.locator("#id_status").select_option("completed")
            after_action(page, delay_ms)
            qc0 = page.locator('[name="qc-0-result_status"]')
            if qc0.count() > 0:
                qc0.select_option("pass")
                after_action(page, delay_ms)
            page.get_by_role("button", name=re.compile(r"Save progress")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Manufacturer: progress and quality saved", args.interactive)

            # --- Beat 8: customer progress (guest) ---
            do_logout(page, base, delay_ms)
            page.goto(f"{base}/customer/", wait_until="domcontentloaded")
            after_action(page, delay_ms)
            page.locator('input[name="order_id"]').fill(order_id)
            after_action(page, delay_ms)
            page.get_by_role("button", name=re.compile(r"^Track$")).click()
            page.wait_for_load_state("networkidle")
            after_action(page, delay_ms)
            beat_pause("Customer: final progress view — end of tour", args.interactive)

            print(f"\nDemo order id (for reference): {order_id}\n")
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Stremet pitch tour (Playwright + Django seed/server).")
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
        help="Quote order id (default: SO-2026-DEMO-<unix_ts>)",
    )
    parser.add_argument(
        "--delivery-date",
        default="",
        help="target_delivery for quote (YYYY-MM-DD). Default: 30 days from today.",
    )
    parser.add_argument(
        "--password",
        default="",
        help="Login password for all demo users (default: STREMET_SEED_PASSWORD env or built-in demo password)",
    )
    parser.add_argument(
        "--action-delay-ms",
        type=int,
        default=1000,
        help="Pause after each simulated UI action (default 1000 ms)",
    )
    parser.add_argument(
        "--slow-mo",
        type=int,
        default=350,
        help="Playwright slow_mo in ms (default 350)",
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
        help="Use short automatic delays instead of Press Enter between beats",
    )
    parser.add_argument(
        "--server-ready-timeout",
        type=float,
        default=900.0,
        metavar="SEC",
        help=(
            "Max seconds to wait for HTTP after runserver starts "
            "(default 900; allow time for GPT4All preload at startup)"
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
            print("Seeding demo data (seed_stremet_demo)…")
            run_manage("seed_stremet_demo")

        if not args.no_server:
            print(
                f"Starting Django runserver on {args.host}:{args.port}… "
                f"(GPT4All preloads at startup; waiting up to {args.server_ready_timeout:.0f}s for HTTP)…"
            )
            _server_proc = start_runserver(args.host, args.port)
            wait_for_http_ok(
                f"{args.base_url.rstrip('/')}/",
                timeout_sec=args.server_ready_timeout,
            )
            print("Server is up.")
        else:
            print(f"Using existing server at {args.base_url} — verifying…")
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
