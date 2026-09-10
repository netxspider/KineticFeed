"""
Kinetic Feed - Twitter (X) Authentication Helper
Launches an anti-detection persistent browser session for manual login,
automatically monitoring for authentication cookies (auth_token / twid),
and saving session cookies to user_data/twitter.
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import config

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-features=IsolateOrigins,site-per-process"
]

def save_twitter_session(interactive: bool = True):
    user_dir = str(config.USER_DATA_TWITTER)
    Path(user_dir).mkdir(parents=True, exist_ok=True)
    
    print(f"\n[Kinetic Feed] Launching Twitter (X) browser session with stealth flags...")
    print(f"[Kinetic Feed] Session path: {user_dir}")

    with sync_playwright() as p:
        # Attempt to launch with Google Chrome channel, fallback to bundled chromium
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=False,
                channel="chrome",
                args=STEALTH_ARGS,
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1280, "height": 850}
            )
        except Exception as e:
            print(f"[Kinetic Feed] Chrome channel launch note ({e}), using bundled Chromium...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=False,
                args=STEALTH_ARGS,
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1280, "height": 850}
            )

        page = context.pages[0] if context.pages else context.new_page()

        # Remove navigator.webdriver anti-bot flag
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.navigator.chrome = { runtime: {} };
        """)

        print("\n" + "="*60)
        print("--> 1. Log into your X / Twitter account in the opened window.")
        print("--> 2. Complete any 2FA/Confirmation codes if required.")
        print("--> 3. The engine automatically detects when login is complete!")
        print("    (You can also close the browser window or press Enter).")
        print("="*60 + "\n")

        try:
            page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            print(f"[Kinetic Feed] Navigation warning ({e}), falling back to direct flow...")
            try:
                page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=20000)
            except Exception:
                pass

        # Intelligent monitoring loop (up to 300s / 5 minutes)
        max_wait_seconds = 300
        start_time = time.time()
        logged_in = False

        while time.time() - start_time < max_wait_seconds:
            # Check if user closed the window manually
            try:
                if page.is_closed() or len(context.pages) == 0:
                    print("[Kinetic Feed] Browser window closed by user. Verifying captured cookies...")
                    break
            except Exception:
                break

            # Inspect cookies for auth_token or twid
            try:
                cookies = context.cookies()
                has_auth = any(
                    c["name"] in ["auth_token", "twid"] and bool(c.get("value"))
                    for c in cookies
                )
                current_url = page.url.lower()

                # If auth cookie exists or we navigated into home / explore feed
                if has_auth or ("/home" in current_url or "/explore" in current_url) and "/login" not in current_url:
                    print("\n[Kinetic Feed] ✨ Active Twitter (X) login detected! Saving session...")
                    time.sleep(3)  # Allow cookies and storage to flush to disk
                    logged_in = True
                    break
            except Exception:
                pass

            time.sleep(2)

        try:
            context.close()
        except Exception:
            pass

        if logged_in:
            print("[Kinetic Feed] ✅ Twitter (X) session cookies and credentials successfully saved!\n")
        else:
            print("[Kinetic Feed] Notice: Twitter window finished. Running session verification...\n")

if __name__ == "__main__":
    save_twitter_session()
