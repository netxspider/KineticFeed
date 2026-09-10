"""
Kinetic Feed - Platform Session & Authentication Verifier
Performs deterministic checks against stored browser cookies and DOM elements.
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import config

SESSION_CACHE = {
    "instagram": {"logged_in": False, "username": None, "checked_at": 0, "status": "UNCHECKED", "details": "Not checked yet"},
    "twitter": {"logged_in": False, "username": None, "checked_at": 0, "status": "UNCHECKED", "details": "Not checked yet"},
    "threads": {"logged_in": False, "username": None, "checked_at": 0, "status": "UNCHECKED", "details": "Not checked yet"},
}

def verify_instagram_session() -> dict:
    user_dir = str(config.USER_DATA_INSTAGRAM)
    if not Path(user_dir).exists():
        res = {
            "logged_in": False,
            "username": None,
            "checked_at": time.time(),
            "status": "NOT_LOGGED_IN",
            "details": "No local browser profile found. Run login first."
        }
        SESSION_CACHE["instagram"] = res
        return res

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"]
            )

            # 1. Check all cookies in context for sessionid (Instagram / Meta)
            cookies = context.cookies()
            session_cookie = next((c for c in cookies if c["name"] == "sessionid" and c.get("value") and ("instagram" in c.get("domain", "") or "facebook" in c.get("domain", ""))), None)
            if not session_cookie:
                session_cookie = next((c for c in cookies if c["name"] == "sessionid" and c.get("value")), None)

            if not session_cookie:
                context.close()
                res = {
                    "logged_in": False,
                    "username": None,
                    "checked_at": time.time(),
                    "status": "NOT_LOGGED_IN",
                    "details": "No active sessionid cookie. Please log in to Instagram."
                }
                SESSION_CACHE["instagram"] = res
                return res

            # 2. Session cookie exists, verify live page access & extract username
            page = context.new_page()
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)

            current_url = page.url
            login_box = page.locator("input[name='username'], button:has-text('Log In'), a[href*='/accounts/login']").first
            if "/accounts/login" in current_url or (login_box.count() > 0 and login_box.is_visible()):
                res = {
                    "logged_in": False,
                    "username": None,
                    "checked_at": time.time(),
                    "status": "NOT_LOGGED_IN",
                    "details": "Session expired or rejected by Instagram."
                }
            else:
                # Extract username from profile picture alt or side rail link
                username = None
                img_profile = page.locator("img[alt*=\"'s profile picture\"], img[alt*=\"profile picture\"]").first
                if img_profile.count() > 0:
                    alt = img_profile.get_attribute("alt") or ""
                    if "'s profile picture" in alt:
                        username = alt.split("'s profile picture")[0].strip()

                if not username:
                    # Look for profile nav link in side rail
                    links = page.locator("a[href^='/']").all()
                    for l in links:
                        href = l.get_attribute("href") or ""
                        clean = href.strip("/")
                        if clean and "/" not in clean and clean not in ["explore", "reels", "direct", "stories", "popular", "about", "legal", "terms"]:
                            if l.locator("svg, img").count() > 0 and (l.inner_text().strip().lower() == "profile" or "profile" in href):
                                username = clean
                                break

                res = {
                    "logged_in": True,
                    "username": f"@{username}" if username else "Active Account",
                    "checked_at": time.time(),
                    "status": "LOGGED_IN",
                    "details": f"Authenticated session confirmed{': @' + username if username else ''}."
                }

            context.close()
        except Exception as e:
            res = {
                "logged_in": False,
                "username": None,
                "checked_at": time.time(),
                "status": "NOT_LOGGED_IN",
                "details": f"Check error: {str(e)[:70]}"
            }

    SESSION_CACHE["instagram"] = res
    return res

def verify_twitter_session() -> dict:
    user_dir = str(config.USER_DATA_TWITTER)
    if not Path(user_dir).exists():
        res = {
            "logged_in": False,
            "username": None,
            "checked_at": time.time(),
            "status": "NOT_LOGGED_IN",
            "details": "No local browser profile found. Run login first."
        }
        SESSION_CACHE["twitter"] = res
        return res

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage"
                ],
                ignore_default_args=["--enable-automation"]
            )

            # Check cookies for auth_token / twid
            cookies = context.cookies()
            auth_token = next((c for c in cookies if c["name"] == "auth_token" and c.get("value")), None)
            twid = next((c for c in cookies if c["name"] == "twid" and c.get("value")), None)

            if not auth_token and not twid:
                context.close()
                res = {
                    "logged_in": False,
                    "username": None,
                    "checked_at": time.time(),
                    "status": "NOT_LOGGED_IN",
                    "details": "No active auth_token cookie. Please log in to X/Twitter."
                }
                SESSION_CACHE["twitter"] = res
                return res

            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            try:
                page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=12000)
                time.sleep(2)
            except Exception:
                pass

            current_url = page.url
            login_el = page.locator("a[href*='/login'], a[data-testid='loginButton']").first
            if "/login" in current_url or "/i/flow/login" in current_url or (login_el.count() > 0 and login_el.is_visible()):
                res = {
                    "logged_in": False,
                    "username": None,
                    "checked_at": time.time(),
                    "status": "NOT_LOGGED_IN",
                    "details": "Redirected to Twitter login flow."
                }
            else:
                account_switcher = page.locator("[data-testid='SideNav_AccountSwitcher_Button']").first
                username = None
                if account_switcher.count() > 0:
                    for line in account_switcher.inner_text().split("\n"):
                        if line.startswith("@"):
                            username = line.strip()
                            break

                res = {
                    "logged_in": True,
                    "username": username or "Active Account",
                    "checked_at": time.time(),
                    "status": "LOGGED_IN",
                    "details": f"Authenticated Twitter session confirmed{': ' + username if username else ''}."
                }

            context.close()
        except Exception as e:
            res = {
                "logged_in": False,
                "username": None,
                "checked_at": time.time(),
                "status": "NOT_LOGGED_IN",
                "details": f"Check error: {str(e)[:70]}"
            }

    SESSION_CACHE["twitter"] = res
    return res

def verify_threads_session() -> dict:
    user_dir = str(config.USER_DATA_THREADS)
    if not Path(user_dir).exists():
        res = {
            "logged_in": False,
            "username": None,
            "checked_at": time.time(),
            "status": "NOT_LOGGED_IN",
            "details": "No local browser profile found. Run login first."
        }
        SESSION_CACHE["threads"] = res
        return res

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"]
            )

            # Check all cookies in context for sessionid (across .threads.net, .threads.com, .instagram.com)
            cookies = context.cookies()
            session_cookie = next((c for c in cookies if c["name"] == "sessionid" and c.get("value") and any(d in c.get("domain", "") for d in ["threads", "instagram"])), None)
            if not session_cookie:
                session_cookie = next((c for c in cookies if c["name"] == "sessionid" and c.get("value")), None)

            if not session_cookie:
                context.close()
                res = {
                    "logged_in": False,
                    "username": None,
                    "checked_at": time.time(),
                    "status": "NOT_LOGGED_IN",
                    "details": "No active sessionid cookie. Please log in to Threads."
                }
                SESSION_CACHE["threads"] = res
                return res

            page = context.new_page()
            page.goto("https://www.threads.com/", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)

            current_url = page.url
            login_btn = page.locator("a[href*='/login'], div[role='button']:has-text('Log in')").first
            if "/login" in current_url or (login_btn.count() > 0 and login_btn.is_visible()):
                res = {
                    "logged_in": False,
                    "username": None,
                    "checked_at": time.time(),
                    "status": "NOT_LOGGED_IN",
                    "details": "Redirected to Threads login screen."
                }
            else:
                profile_nav = page.locator("a[href^='/@']").first
                username = None
                if profile_nav.count() > 0:
                    href = profile_nav.get_attribute("href") or ""
                    if "@" in href:
                        username = href.split("@")[-1].strip("/")

                res = {
                    "logged_in": True,
                    "username": f"@{username}" if username else "Active Account",
                    "checked_at": time.time(),
                    "status": "LOGGED_IN",
                    "details": f"Authenticated Threads session confirmed{': @' + username if username else ''}."
                }

            context.close()
        except Exception as e:
            res = {
                "logged_in": False,
                "username": None,
                "checked_at": time.time(),
                "status": "NOT_LOGGED_IN",
                "details": f"Check error: {str(e)[:70]}"
            }

    SESSION_CACHE["threads"] = res
    return res

def check_platform(platform: str) -> dict:
    p = platform.lower().strip()
    if p in ["instagram", "ig"]:
        return verify_instagram_session()
    elif p in ["twitter", "x"]:
        return verify_twitter_session()
    elif p == "threads":
        return verify_threads_session()
    elif p == "all":
        return {
            "instagram": verify_instagram_session(),
            "twitter": verify_twitter_session(),
            "threads": verify_threads_session(),
        }
    return {"error": f"Unknown platform: {platform}"}

def get_cached_sessions() -> dict:
    return SESSION_CACHE
