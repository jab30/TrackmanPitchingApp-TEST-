"""
login_app.py — KSU Baseball Analytics Portal
Run this file instead of app.py:
    shiny run login_app.py

This wraps the main app with a password-protected login page.

IP TRACKING NOTES:
- Locally: captures real client IP via Starlette request headers
- HuggingFace Spaces: captures X-Forwarded-For (proxy IP, usually HF's own)
  For real visitor IPs on HF, you'd need a custom backend — not available in Spaces.
- All login attempts (success + fail) are written to login_log.csv
"""

import os
import csv
import base64
import datetime
import importlib.util
from pathlib import Path

from shiny import App, ui, reactive, render

# ── Config ────────────────────────────────────────────────────────────────────
PASSWORD  = "FYPM2025!"
BASE_DIR  = Path(__file__).parent
LOGIN_LOG = BASE_DIR / "login_log.csv"
IMG_PATH  = BASE_DIR / "crop.jpg"

# ── Embed background image as base64 ─────────────────────────────────────────
def _load_bg() -> str:
    if IMG_PATH.exists():
        with open(IMG_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/jpeg;base64,{b64}"
    return ""

_BG_DATA_URI = _load_bg()
_BG_CSS_VAL  = f"url('{_BG_DATA_URI}')" if _BG_DATA_URI else "linear-gradient(135deg,#111 0%,#1a1a1a 100%)"

# ── IP logging ────────────────────────────────────────────────────────────────
def _log_attempt(ip: str, success: bool):
    """Log login attempt to stdout (visible in HF Space logs) and login_log.csv."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = "SUCCESS" if success else "FAILED"
    # stdout — always visible in HF Space logs tab
    print(f"[LOGIN] {timestamp} | IP: {ip} | {result}", flush=True)
    # CSV file — persists locally, ephemeral on HF
    write_header = not LOGIN_LOG.exists()
    with open(LOGIN_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["timestamp", "ip", "result"])
        w.writerow([timestamp, ip, result])


def _get_ip(session) -> str:
    """
    Best-effort client IP extraction.
    - Local: real IP from Starlette request
    - Behind reverse proxy (HuggingFace, nginx): X-Forwarded-For header
    """
    try:
        # Access the underlying Starlette request object
        req = session._conn._request
        # Check X-Forwarded-For first (set by reverse proxies)
        xff = req.headers.get("x-forwarded-for", "").strip()
        if xff:
            return xff.split(",")[0].strip()
        if req.client:
            return req.client.host
    except Exception:
        pass
    return "unknown"


# ── Login page UI ─────────────────────────────────────────────────────────────
_CSS = f"""
html, body {{
    margin: 0; padding: 0; height: 100%; width: 100%;
    font-family: 'Inter', 'Helvetica Neue', sans-serif;
    background: #0e0e0e;
}}

#login-bg {{
    position: fixed; inset: 0; z-index: 0;
    background-image: {_BG_CSS_VAL};
    background-size: cover;
    background-position: center 30%;
    filter: brightness(0.38) saturate(0.8);
}}

#login-wrap {{
    position: relative; z-index: 1;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
}}

.login-card {{
    background: rgba(14, 14, 14, 0.90);
    border: 1px solid rgba(245, 200, 66, 0.18);
    border-radius: 18px;
    padding: 52px 48px 44px;
    width: 380px;
    box-shadow: 0 32px 80px rgba(0,0,0,0.75), 0 0 0 1px rgba(255,255,255,0.04);
    text-align: center;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}}

.login-owl {{
    font-size: 3rem;
    margin-bottom: 10px;
    line-height: 1;
}}

.login-title {{
    color: #f5c842;
    font-size: 1.65rem;
    font-weight: 800;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 3px;
}}

.login-sub {{
    color: #888;
    font-size: 0.75rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 36px;
}}

.login-divider {{
    border: none;
    border-top: 1px solid rgba(255,255,255,0.08);
    margin: 0 0 28px;
}}

#pw-input {{
    width: 100%;
    box-sizing: border-box;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 10px;
    color: #f0f0f0;
    font-size: 1.05rem;
    padding: 13px 16px;
    text-align: center;
    letter-spacing: 0.18em;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
}}
#pw-input:focus {{
    border-color: #f5c842;
    box-shadow: 0 0 0 3px rgba(245,200,66,0.15);
}}
#pw-input::placeholder {{
    color: #555;
    letter-spacing: 0.06em;
    font-size: 0.9rem;
}}

#login-btn {{
    margin-top: 16px;
    width: 100%;
    background: #f5c842;
    color: #111111;
    font-weight: 800;
    font-size: 0.95rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    border: none;
    border-radius: 10px;
    padding: 14px 0;
    cursor: pointer;
    transition: background 0.15s, transform 0.1s, box-shadow 0.15s;
    box-shadow: 0 4px 20px rgba(245,200,66,0.25);
}}
#login-btn:hover {{
    background: #ffd84d;
    transform: translateY(-1px);
    box-shadow: 0 6px 24px rgba(245,200,66,0.35);
}}
#login-btn:active {{
    transform: translateY(0);
    box-shadow: none;
}}

.login-error {{
    color: #ff5555;
    font-size: 0.8rem;
    margin-top: 14px;
    min-height: 20px;
    letter-spacing: 0.04em;
}}

.login-footer {{
    color: #444;
    font-size: 0.68rem;
    letter-spacing: 0.08em;
    margin-top: 28px;
    text-transform: uppercase;
}}
"""

_login_page = ui.div(
    ui.tags.style(_CSS),
    # Background layer
    ui.div(id="login-bg"),
    # Card
    ui.div(
        ui.div(
            ui.div("🦉",              class_="login-owl"),
            ui.div("KSU Baseball",    class_="login-title"),
            ui.div("Analytics Portal",class_="login-sub"),
            ui.tags.hr(              class_="login-divider"),
            # Password input (raw HTML so we get the right id)
            ui.tags.input(
                id="pw-input",
                type="password",
                placeholder="Enter password",
                autocomplete="off",
                onkeydown="if(event.key==='Enter'){document.getElementById('login-btn').click();}",
            ),
            ui.input_action_button("login_btn", "Log In"),
            ui.output_ui("error_out"),
            ui.div("Kennesaw State University · Baseball Analytics", class_="login-footer"),
            class_="login-card",
        ),
        id="login-wrap",
    ),
)


# ── Main app UI (imported lazily after auth) ───────────────────────────────────
def _load_main_app_ui():
    """Import app_ui from app.py at runtime."""
    spec = importlib.util.spec_from_file_location("main_app", BASE_DIR / "app.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.app_ui, mod.server


# ── Root UI ───────────────────────────────────────────────────────────────────
app_ui = ui.page_output("root_ui")


def server(input, output, session):
    authed    = reactive.value(False)
    error_msg = reactive.value("")

    # ── Password check ────────────────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.login_btn)
    def _handle_login():
        # Read the raw HTML input value via JS message
        # Shiny doesn't auto-bind raw <input> tags — use session.send_input_message workaround
        # Instead, we use a JS observer to sync it (see tags.script below)
        pw  = input.pw_val() if hasattr(input, "pw_val") else ""
        ip  = _get_ip(session)
        if pw == PASSWORD:
            _log_attempt(ip, True)
            authed.set(True)
            error_msg.set("")
        else:
            _log_attempt(ip, False)
            error_msg.set("⚠ Incorrect password. Please try again.")

    # ── Root page render ──────────────────────────────────────────────────────
    @render.ui
    def root_ui():
        if authed():
            # Dynamically load the main app UI
            try:
                main_ui, main_server = _load_main_app_ui()
                # Register main server logic
                main_server(input, output, session)
                return main_ui
            except Exception as e:
                return ui.div(
                    ui.h3("Error loading app", style="color:red;"),
                    ui.p(str(e)),
                    style="padding:40px; color:white; background:#111; min-height:100vh;"
                )
        # Show login + JS bridge to sync raw input → Shiny reactive
        return ui.div(
            _login_page,
            ui.tags.script("""
                // Sync raw #pw-input value into Shiny input as 'pw_val'
                (function() {
                    function syncPw() {
                        var val = document.getElementById('pw-input');
                        if (val) Shiny.setInputValue('pw_val', val.value, {priority: 'event'});
                    }
                    document.addEventListener('keydown', function(e) {
                        if (e.key === 'Enter') syncPw();
                    });
                    var btn = document.getElementById('login-btn');
                    if (btn) btn.addEventListener('mousedown', syncPw);

                    // Also attach on any click just in case button re-renders
                    document.addEventListener('click', function(e) {
                        if (e.target && e.target.id === 'login-btn') syncPw();
                    });
                })();
            """),
        )

    @render.ui
    def error_out():
        msg = error_msg()
        return ui.div(msg, class_="login-error")


app = App(app_ui, server)
