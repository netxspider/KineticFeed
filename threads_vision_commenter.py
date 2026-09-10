"""
Kinetic Feed - Threads AI Vision Engagement Engine
Engages with algorithmic 'For You' and trending conversations on Meta Threads using Gemini Vision.
"""

import io
import os
import random
import time
from pathlib import Path
from google import genai
from PIL import Image
from playwright.sync_api import sync_playwright
import config
import algo_engine

def get_gemini_client():
    if config.GEMINI_API_KEY:
        try:
            return genai.Client(api_key=config.GEMINI_API_KEY)
        except Exception as e:
            print(f"[Kinetic Feed] Gemini Client init warning: {e}")
    return None

def generate_threads_comment(screenshot_bytes: bytes, author: str, client=None, on_error=None) -> Optional[str]:
    """Uses Gemini Vision to produce natural, human, funny or emoji comments for Threads."""
    if not client:
        client = get_gemini_client()

    if not client:
        err = "Gemini API key is not configured. Please set a valid GEMINI_API_KEY in .env."
        if on_error:
            on_error(err)
        return None

    prompt = f"""
You are a real human user casually browsing Threads. Look at this post by @{author}.
Analyze the visual scene, text, memes, vibe, or subject matter.

Write a natural, authentic comment that fits one of these styles:
- Sarcastic / witty / dry humor (e.g. "bro really thought we wouldn't notice 💀", "the bar was on the floor and you brought a shovel 😂")
- Casual / relatable internet humor (e.g. "nah this is actually wild 😭", "felt this deep in my soul", "wait who let them cook 😭")
- Pure emoji reaction (e.g. "💀😭", "🔥🔥", "👀🍿", "😂👏") if the visual speaks for itself!
- Short punchy observational quip (3 to 8 words max).
CRITICAL: NEVER sound like an AI, marketer, or brand. Do NOT say "Great post!", "Love the perspective", or generic compliments.
Return ONLY the comment text or emojis without quotes.
"""
    try:
        pil_image = Image.open(io.BytesIO(screenshot_bytes))
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[prompt, pil_image]
        )
        if response and response.text:
            return response.text.strip().replace('"', '').replace('\n', ' ')
        return None
    except Exception as e:
        err_msg = str(e)
        print(f"[Gemini Threads Error] {err_msg}")
        if on_error:
            on_error(err_msg)
        return None
def submit_threads_reply(page, reply_text: str, container=None) -> bool:
    """Clicks reply, types reply text, and submits comment on Threads."""
    try:
        # Click reply button on container or page
        clicked = False
        if container:
            try:
                reply_icon = container.locator("svg[aria-label*='Reply' i], svg[aria-label*='Comment' i]").first
                if reply_icon.count() > 0 and reply_icon.is_visible():
                    reply_icon.click(timeout=2000)
                    time.sleep(0.8)
                    clicked = True
            except Exception:
                pass

        if not clicked:
            try:
                reply_btn = page.locator("svg[aria-label*='Reply' i], svg[aria-label*='Comment' i]").first
                if reply_btn.count() > 0 and reply_btn.is_visible():
                    reply_btn.click(timeout=2000)
                    time.sleep(0.8)
            except Exception:
                pass

        # Locate composer input
        input_selectors = [
            "div[role='dialog'] div[role='textbox']",
            "div[role='textbox'][contenteditable='true']",
            "p[data-placeholder*='Reply' i]",
            "div[data-contents='true']",
            "textarea"
        ]

        target_input = None
        for sel in input_selectors:
            box = page.locator(sel).first
            if box.count() > 0 and box.is_visible():
                target_input = box
                break

        if not target_input:
            print("  -> Could not find Threads reply input box.")
            return False

        target_input.click()
        time.sleep(0.3)
        page.keyboard.type(reply_text, delay=random.randint(15, 25))
        time.sleep(0.5)

        # Click Post button
        post_btn = page.locator("div[role='button']:has-text('Post'), button:has-text('Post')").first
        if post_btn.count() > 0 and post_btn.is_visible():
            post_btn.click(timeout=1500)
            time.sleep(0.8)
            return True
        else:
            page.keyboard.press("Meta+Enter")
            page.keyboard.press("Control+Enter")
            time.sleep(0.8)
            return True
    except Exception as e:
        print(f"  -> Error posting Threads reply: {e}")
        return False

def run_threads_campaign(
    target_comments: int = None,
    mode: str = "for_you",
    topic: str = None,
    target_urls: list = None,
    exclude_post_ids: set = None,
    on_event = None,
    stop_event = None
):
    """Executes Threads engagement campaign."""
    if target_urls:
        target_comments = len(target_urls)
    elif target_comments is None:
        target_comments = config.TARGET_COMMENTS

    client = get_gemini_client()
    user_dir = str(config.USER_DATA_THREADS)
    Path(user_dir).mkdir(parents=True, exist_ok=True)

    def emit(event_type: str, data: dict):
        if on_event:
            payload = {"platform": "threads", "type": event_type, "timestamp": time.time(), **data}
            on_event(payload)

    def handle_api_error(err_str: str):
        emit("api_error", {
            "error": err_str,
            "message": f"Gemini API Error: {err_str[:120]}"
        })
        emit("log", {"message": f"[API ERROR] Gemini Vision failed: {err_str[:100]}"})

    # Initialize seen_threads with previously commented post IDs
    seen_threads = set(exclude_post_ids) if exclude_post_ids else set()
    try:
        with open(config.BASE_DIR / "stats.json", "r", encoding="utf-8") as f:
            sj = json.load(f)
            for h in sj.get("history", []):
                if h.get("platform") == "threads" and h.get("postId"):
                    seen_threads.add(str(h["postId"]).strip())
    except Exception:
        pass

    emit("campaign_started", {"target": target_comments, "mode": "direct_links" if target_urls else mode, "topic": topic, "urlsCount": len(target_urls) if target_urls else 0})

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=False,
                channel="chrome",
                viewport={"width": 1280, "height": 850}
            )
        except Exception:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=False,
                viewport={"width": 1280, "height": 850}
            )

        # Upfront auth check
        cookies = context.cookies()
        if not any(c["name"] == "sessionid" and c.get("value") for c in cookies):
            emit("log", {"message": "[AUTH ERROR] Threads is NOT logged in. Please click 'Open Login' in the dashboard first to authenticate."})
            emit("campaign_completed", {"totalCommented": 0, "target": target_comments, "error": "NOT_LOGGED_IN"})
            context.close()
            return 0

        page = context.pages[0] if context.pages else context.new_page()

        # Handle direct post URLs
        if target_urls:
            emit("log", {"message": f"Targeting {len(target_urls)} custom Threads URLs directly."})
            commented_count = 0
            for idx, post_url in enumerate(target_urls):
                if stop_event and stop_event.is_set():
                    emit("log", {"message": "Direct link campaign stopped by user."})
                    break

                post_url = post_url.strip()
                if not post_url:
                    continue

                post_id = post_url.strip("/").split("/")[-1]
                if post_id in seen_threads:
                    emit("log", {"message": f"Skipping already commented direct thread: {post_id}"})
                    continue

                seen_threads.add(post_id)
                author = "creator"
                for part in post_url.split("/"):
                    if part.startswith("@"):
                        author = part.replace("@", "")
                        break

                emit("log", {"message": f"[{idx+1}/{len(target_urls)}] Opening thread: {post_url}"})
                try:
                    page.goto(post_url, wait_until="domcontentloaded")
                    time.sleep(3.5)

                    container = page.locator("div[data-pressable-container='true'], div[role='article']").first
                    if container.count() == 0:
                        container = page

                    emit("post_found", {"postId": post_id, "author": author, "url": post_url})
                    try:
                        screenshot_bytes = container.screenshot(timeout=3000) if container != page else page.screenshot(timeout=3000)
                    except Exception:
                        screenshot_bytes = page.screenshot(timeout=3000)

                    reply_text = generate_threads_comment(screenshot_bytes, author, client, on_error=handle_api_error)
                    if not reply_text:
                        emit("log", {"message": "Halting campaign due to Gemini API error. Please update your API key."})
                        emit("campaign_completed", {"totalCommented": commented_count, "target": len(target_urls), "error": "API_KEY_ERROR"})
                        break

                    reach_score = config.calculate_reach_score(reply_text)
                    emit("comment_generated", {"postId": post_id, "author": author, "comment": reply_text, "reachScore": reach_score})

                    success = submit_threads_reply(page, reply_text, container=container if container != page else None)
                    if success:
                        commented_count += 1
                        emit("comment_posted", {
                            "postId": post_id,
                            "author": author,
                            "comment": reply_text,
                            "progress": commented_count,
                            "target": len(target_urls),
                            "reachScore": reach_score,
                            "url": post_url
                        })
                    else:
                        emit("comment_failed", {"postId": post_id, "author": author})

                    if idx < len(target_urls) - 1:
                        delay = random.randint(config.MIN_DELAY, config.MAX_DELAY)
                        emit("delay", {"seconds": delay})
                        time.sleep(delay)
                except Exception as e:
                    emit("log", {"message": f"Error on direct thread {post_url}: {e}"})
                    continue

            emit("campaign_completed", {"totalCommented": commented_count, "target": len(target_urls)})
            context.close()
            return commented_count

        if mode == "trending":
            target_url = "https://www.threads.net/trending"
        elif topic:
            clean_topic = topic.strip('#')
            target_url = f"https://www.threads.net/search?q={clean_topic}&filter=trending"
        elif mode == "for_you":
            target_url = "https://www.threads.net/"
        elif mode == "feed":
            target_url = "https://www.threads.net/"
        else:
            target_url = "https://www.threads.net/"

        print(f"[Kinetic Feed] Connecting to Threads ({target_url}) in {mode.upper()} mode...")
        emit("log", {"message": f"Connecting to Threads in {mode.upper()} mode: {target_url}"})
        page.goto(target_url, wait_until="domcontentloaded")
        time.sleep(4)

        commented_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 50

        while commented_count < target_comments and scroll_attempts < max_scroll_attempts:
            if stop_event and stop_event.is_set():
                emit("log", {"message": "Campaign stopped by user."})
                break

            post_containers = page.locator("div[data-pressable-container='true'], div[role='article']").all()
            found_new = False

            for container in post_containers:
                if stop_event and stop_event.is_set():
                    break

                try:
                    # Look strictly for actual post permalink to avoid false matches with user avatars or profile links
                    link_el = container.locator("a[href*='/post/']").first
                    if link_el.count() == 0:
                        continue

                    href = link_el.get_attribute("href") or ""
                    if not href:
                        continue

                    post_id = href.split("/post/")[-1].strip("/").split("?")[0]
                    if not post_id or post_id in seen_threads:
                        continue

                    # Extract author handle
                    author = "creator"
                    for part in href.split("/"):
                        if part.startswith("@"):
                            author = part.replace("@", "")
                            break

                    # Never comment on the logged-in user's own posts
                    if author.lower() in ["unreal.arnav", "_its_spidey__", "popular"]:
                        seen_threads.add(post_id)
                        continue

                    seen_threads.add(post_id)
                    found_new = True

                    try:
                        container.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass
                    time.sleep(0.3)

                    # ==========================================
                    # ALGORITHM CRACKING: THREADS METRICS
                    # ==========================================
                    likes_text = "0"
                    replies_text = "0"
                    try:
                        like_btn = container.locator("svg[aria-label*='Like'], svg[aria-label*='like']").locator("xpath=..").first
                        if like_btn.count() > 0:
                            likes_text = like_btn.inner_text() or "0"
                    except Exception:
                        pass

                    try:
                        rep_btn = container.locator("svg[aria-label*='Reply'], svg[aria-label*='reply']").locator("xpath=..").first
                        if rep_btn.count() > 0:
                            replies_text = rep_btn.inner_text() or "0"
                    except Exception:
                        pass

                    is_worthy, viral_score, eval_reason, norm_metrics = algo_engine.evaluate_post_metrics(
                        "threads", {"likes": likes_text, "replies": replies_text, "hours_old": 1.5}
                    )

                    emit("post_found", {
                        "postId": post_id,
                        "author": author,
                        "url": f"https://www.threads.net{href}" if href.startswith('/') else href,
                        "viralScore": viral_score,
                        "metrics": norm_metrics
                    })

                    if not is_worthy:
                        emit("log", {"message": f"[ALGO CRACKER] ⏭ Skipped Threads post @{author}: {eval_reason}"})
                        continue

                    emit("log", {
                        "message": f"[ALGO CRACKER] 🚀 High-Velocity Threads Post! @{author} (Score: {viral_score}/100, Velocity: ~{norm_metrics['velocity']} likes/hr)"
                    })
                    print(f"\n[Threads] [{commented_count + 1}/{target_comments}] Viral Post by @{author} ({post_id}) | Score: {viral_score}")

                    try:
                        screenshot_bytes = container.screenshot(timeout=3000)
                    except Exception:
                        screenshot_bytes = page.screenshot(timeout=3000)

                    post_full_url = f"https://www.threads.net{href}" if href.startswith('/') else href
                    reply_text = generate_threads_comment(screenshot_bytes, author, client, on_error=handle_api_error)
                    if not reply_text:
                        emit("log", {"message": "Halting campaign due to Gemini API error. Please update your API key."})
                        emit("campaign_completed", {"totalCommented": commented_count, "target": target_comments, "error": "API_KEY_ERROR"})
                        break

                    reach_score = config.calculate_reach_score(reply_text)

                    print(f"Comment: \"{reply_text}\" (Reach Score: {reach_score})")
                    emit("comment_generated", {"postId": post_id, "author": author, "comment": reply_text, "reachScore": reach_score, "viralScore": viral_score})

                    success = submit_threads_reply(page, reply_text, container=container)
                    if success:
                        commented_count += 1
                        emit("comment_posted", {
                            "postId": post_id,
                            "author": author,
                            "comment": reply_text,
                            "progress": commented_count,
                            "target": target_comments,
                            "reachScore": reach_score,
                            "url": post_full_url
                        })
                        print(f"--> [Threads] Replied successfully! [{commented_count}/{target_comments}]")
                    else:
                        emit("comment_failed", {"postId": post_id, "author": author})

                    # Crucial: advance feed so we do not re-encounter the same post!
                    page.mouse.wheel(0, 850)
                    page.keyboard.press("PageDown")
                    time.sleep(1.5)

                    if commented_count < target_comments:
                        delay = random.randint(config.MIN_DELAY, config.MAX_DELAY)
                        emit("delay", {"seconds": delay})
                        time.sleep(delay)

                    break
                except Exception as e:
                    err_msg = str(e).lower()
                    emit("log", {"message": f"Error handling Threads post: {e}"})
                    if "closed" in err_msg or "target" in err_msg:
                        emit("log", {"message": "Threads browser session closed. Terminating loop."})
                        break
                    continue

            if not found_new:
                emit("log", {"message": "Scrolling Threads feed..."})
                page.mouse.wheel(0, 1000)
                page.keyboard.press("PageDown")
                time.sleep(1.8)
                scroll_attempts += 1

        emit("campaign_completed", {"totalCommented": commented_count, "target": target_comments})
        context.close()
        return commented_count

if __name__ == "__main__":
    run_threads_campaign()
