"""
Kinetic Feed - Instagram Authentication Helper
Launches a persistent browser session for manual login, saving session cookies to user_data/instagram.
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import config

def save_instagram_session(interactive: bool = True):
    user_dir = str(config.USER_DATA_INSTAGRAM)
    Path(user_dir).mkdir(parents=True, exist_ok=True)
    
    print(f"\n[Kinetic Feed] Launching Instagram browser session...")
    print(f"[Kinetic Feed] Session path: {user_dir}")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_dir,
            headless=False,
            channel="chrome",
            viewport={"width": 1280, "height": 800}
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        
        print("\n" + "="*50)
        print("--> 1. Log in manually inside the opened browser window.")
        print("--> 2. Complete any 2FA/Security challenges if prompted.")
        print("--> 3. Once your Instagram feed or explore page is visible:")
        print("    Press ENTER in this terminal to save and exit.")
        print("="*50 + "\n")
        
        if interactive:
            try:
                input("Press Enter here when logged in: ")
            except EOFError:
                print("Running non-interactive; waiting 45s for login...")
                time.sleep(45)
        else:
            time.sleep(40)

        context.close()
        print("[Kinetic Feed] Instagram session cookies and credentials successfully saved!\n")

if __name__ == "__main__":
    save_instagram_session()
