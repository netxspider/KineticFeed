"""
Kinetic Feed - Instagram AI Vision Engagement Engine
Navigates Instagram Feed and Explore/Trending channels, analyzes visual content via Gemini Vision,
and posts context-aware comments to maximize profile reach.
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

def is_sponsored_ad(article) -> bool:
    """Detects sponsored posts and paid advertisements to prevent wasteful interactions."""
    try:
        text = article.inner_text().lower()
        ad_signals = [
            "sponsored", "paid partnership", "shop now",
            "learn more", "install now", "sign up", "order now"
        ]
        if any(signal in text for signal in ad_signals):
            return True
        if article.locator("a[href*='facebook.com/tr/'], a[href*='ad_id']").count() > 0:
            return True
    except Exception:
        pass
    return False

def generate_visual_comment(screenshot_bytes: bytes, author: str, client=None, on_error=None) -> Optional[str]:
    """Submits post visual screenshot to Gemini Vision for zero-DOM context analysis."""
    if not client:
        client = get_gemini_client()

    if not client:
        err = "Gemini API key is not configured. Please set a valid GEMINI_API_KEY in .env."
        if on_error:
            on_error(err)
        return None

    prompt = f"""
You are an active user browsing Instagram posts. Look at this post by @{author}.
Analyze the visual scene, subject matter, mood, text, and humor in the image.

Write a natural, authentic comment that fits one of these styles:
- Sarcastic / witty / dry humor (e.g. "bro really thought we wouldn't notice 💀", "the accuracy hurts 😂")
- Casual / relatable internet humor (e.g. "nah this is actually wild 😭", "felt this deep in my soul", "wait who let them cook 😭")
- Pure emoji reaction (e.g. "💀😭", "🔥🔥", "👀🍿", "😂👏") if the visual speaks for itself!
- Short punchy observational quip (3 to 8 words max).
CRITICAL: NEVER sound like an AI, marketer, or brand. Do NOT say "Great post!", "Love this!", or generic praise.
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
        print(f"[Gemini Vision Error] {err_msg}")
        if on_error:
            on_error(err_msg)
        return None

def open_and_submit_comment(page, comment_text: str) -> bool:
    """Clicks comment trigger, focuses comment input, types with keystroke delays, and submits."""
    comment_btn_selectors = [
        "button:has(svg[aria-label*='omment' i])",
        "div[role='button']:has(svg[aria-label*='omment' i])",
        "svg[aria-label*='omment' i]",
        "svg[aria-label='Comment']",
        "svg[aria-label='टिप्पणी']",
        "section svg[aria-label='Comment']"
    ]

    clicked_icon = False
    for btn_sel in comment_btn_selectors:
        try:
            btn = page.locator(btn_sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=1500)
                time.sleep(0.6)
                clicked_icon = True
                break
        except Exception:
            continue

    input_selectors = [
        "textarea[placeholder*='comment' i]",
        "textarea[aria-label*='comment' i]",
        "div[contenteditable='true'][role='textbox']",
        "div[contenteditable='true']",
        "form textarea"
    ]

    target_box = None
    for sel in input_selectors:
        try:
            box = page.locator(sel).first
            if box.count() > 0 and box.is_visible():
                target_box = box
                break
        except Exception:
            continue

    if not target_box:
        try:
            comment_icon = page.locator("svg[aria-label='Comment'], svg[aria-label='टिप्पणी']").first
            if comment_icon.count() > 0 and comment_icon.is_visible():
                comment_icon.click()
                time.sleep(0.6)
                for sel in input_selectors:
                    box = page.locator(sel).first
                    if box.count() > 0 and box.is_visible():
                        target_box = box
                        break
        except Exception:
            pass

    if not target_box:
        print("  -> Could not locate comment input after opening.")
        return False

    try:
        target_box.click()
        time.sleep(0.3)
        page.keyboard.type(comment_text, delay=random.randint(12, 25))
        time.sleep(0.4)
        page.keyboard.press("Enter")

        post_btn = page.locator(
            "div[role='button']:has-text('Post'), button:has-text('Post'), div:text-is('Post')"
        ).first
        if post_btn.count() > 0 and post_btn.is_visible():
            post_btn.click(timeout=1000)
            time.sleep(0.6)

        return True
    except Exception as e:
        print(f"  -> Error during comment submission: {e}")
        return False

def run_instagram_campaign(
    target_comments: int = None,
    mode: str = "trending",  # "trending", "explore", "feed", or custom topic
    topic: str = None,
    target_urls: list = None,
    exclude_post_ids: set = None,
    on_event = None,
    stop_event = None
):
    """
    Executes Instagram engagement campaign.
    Supports callback hooks for real-time dashboard streaming and direct post URLs.
    """
    if target_urls:
        target_comments = len(target_urls)
    elif target_comments is None:
        target_comments = config.TARGET_COMMENTS

    client = get_gemini_client()
    user_dir = str(config.USER_DATA_INSTAGRAM)
    Path(user_dir).mkdir(parents=True, exist_ok=True)

    def emit(event_type: str, data: dict):
        if on_event:
            payload = {"platform": "instagram", "type": event_type, "timestamp": time.time(), **data}
            on_event(payload)

    def handle_api_error(err_str: str):
        emit("api_error", {
            "error": err_str,
            "message": f"Gemini API Error: {err_str[:120]}"
        })
        emit("log", {"message": f"[API ERROR] Gemini Vision failed: {err_str[:100]}"})

    # Load previously commented posts so we NEVER re-comment on them
    seen_posts = set(exclude_post_ids) if exclude_post_ids else set()
    try:
        with open(config.BASE_DIR / "stats.json", "r", encoding="utf-8") as f:
            sj = json.load(f)
            for h in sj.get("history", []):
                if h.get("platform") == "instagram" and h.get("postId"):
                    seen_posts.add(str(h["postId"]).strip())
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
            emit("log", {"message": "[AUTH ERROR] Instagram is NOT logged in. Please click 'Open Login' in the dashboard first to authenticate."})
            emit("campaign_completed", {"totalCommented": 0, "target": target_comments, "error": "NOT_LOGGED_IN"})
            context.close()
            return 0

        page = context.pages[0] if context.pages else context.new_page()

        # Handle direct URLs targeting mode
        if target_urls:
            emit("log", {"message": f"Targeting {len(target_urls)} custom Instagram URLs directly."})
            commented_count = 0
            for idx, post_url in enumerate(target_urls):
                if stop_event and stop_event.is_set():
                    emit("log", {"message": "Direct link campaign stopped by user."})
                    break

                post_url = post_url.strip()
                if not post_url:
                    continue

                parts = [x for x in post_url.strip("/").split("/") if x]
                post_id = parts[-1] if parts else f"post_{idx+1}"

                if post_id in seen_posts:
                    emit("log", {"message": f"Skipping already commented direct post: {post_id}"})
                    continue

                seen_posts.add(post_id)
                emit("log", {"message": f"[{idx+1}/{len(target_urls)}] Loading post: {post_url}"})
                try:
                    page.goto(post_url, wait_until="domcontentloaded")
                    time.sleep(3)

                    article = page.locator("article").first
                    if article.count() == 0:
                        article = page

                    author = "creator"
                    author_el = page.locator("header a[role='link'], a[role='link']").first
                    if author_el.count() > 0:
                        author = author_el.inner_text().split("\n")[0].strip()

                    emit("post_found", {"postId": post_id, "author": author, "url": post_url})
                    try:
                        screenshot_bytes = article.screenshot(timeout=3000) if article != page else page.screenshot(timeout=3000)
                    except Exception:
                        screenshot_bytes = page.screenshot(timeout=3000)

                    comment_text = generate_visual_comment(screenshot_bytes, author, client, on_error=handle_api_error)
                    if not comment_text:
                        emit("log", {"message": "Halting campaign due to Gemini API error. Please update your API key."})
                        emit("campaign_completed", {"totalCommented": commented_count, "target": len(target_urls), "error": "API_KEY_ERROR"})
                        break

                    reach_score = config.calculate_reach_score(comment_text)
                    emit("comment_generated", {"postId": post_id, "author": author, "comment": comment_text, "reachScore": reach_score})

                    success = open_and_submit_comment(page, comment_text)
                    if success:
                        commented_count += 1
                        emit("comment_posted", {
                            "postId": post_id,
                            "author": author,
                            "comment": comment_text,
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
                    emit("log", {"message": f"Error interacting with direct link {post_url}: {e}"})
                    continue

            emit("campaign_completed", {"totalCommented": commented_count, "target": len(target_urls)})
            context.close()
            return commented_count

        # Decide navigation target based on mode
        if mode == "explore" or mode == "trending":
            target_url = "https://www.instagram.com/explore/"
        elif topic:
            target_url = f"https://www.instagram.com/explore/tags/{topic.strip('#')}/"
        elif mode == "for_you":
            target_url = "https://www.instagram.com/"
        elif mode == "feed":
            target_url = "https://www.instagram.com/"
        else:
            target_url = "https://www.instagram.com/"

        print(f"[Kinetic Feed] Navigating to Instagram {mode.upper()} ({target_url})...")
        emit("log", {"message": f"Navigating to Instagram {mode.upper()} mode: {target_url}"})
        page.goto(target_url, wait_until="domcontentloaded")
        time.sleep(4)

        seen_posts = set()
        commented_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 60

        while commented_count < target_comments and scroll_attempts < max_scroll_attempts:
            if stop_event and stop_event.is_set():
                emit("log", {"message": "Campaign stopped by user."})
                break

            if mode in ["trending", "explore"]:
                # In Explore, posts are grid links (/p/ or /reel/)
                post_links = page.locator("a[href*='/p/'], a[href*='/reel/']").all()
                found_new = False

                for link_el in post_links:
                    if stop_event and stop_event.is_set():
                        break

                    try:
                        href = link_el.get_attribute("href")
                        if not href:
                            continue
                        parts = [x for x in href.strip("/").split("/") if x]
                        post_id = parts[-1] if parts else None
                        if not post_id or post_id in seen_posts:
                            continue

                        seen_posts.add(post_id)
                        found_new = True

                        try:
                            link_el.scroll_into_view_if_needed(timeout=2000)
                        except Exception:
                            pass
                        time.sleep(0.3)

                        # Click into explore post to open modal or page
                        link_el.click()
                        time.sleep(2.5)

                        article = page.locator("article").first
                        if article.count() == 0:
                            article = page

                        # Extract author handle
                        author = "creator"
                        author_el = page.locator("header a[role='link'], a[role='link']").first
                        if author_el.count() > 0:
                            author = author_el.inner_text().split("\n")[0].strip()

                        # ==========================================
                        # ALGORITHM CRACKING: EVALUATE ENGAGEMENT
                        # ==========================================
                        likes_text = "0"
                        try:
                            like_node = article.locator("section span:has-text('likes'), a[href*='/liked_by/'], section button:has-text('likes')").first
                            if like_node.count() > 0:
                                likes_text = like_node.inner_text()
                        except Exception:
                            pass

                        comments_count = 0
                        try:
                            comments_count = article.locator("ul li[role='menuitem'], ul > div > li").count()
                        except Exception:
                            pass

                        is_worthy, viral_score, eval_reason, norm_metrics = algo_engine.evaluate_post_metrics(
                            "instagram", {"likes": likes_text, "comments": comments_count, "hours_old": 2.0}
                        )

                        emit("post_found", {
                            "postId": post_id,
                            "author": author,
                            "url": f"https://www.instagram.com/p/{post_id}/",
                            "viralScore": viral_score,
                            "metrics": norm_metrics
                        })

                        if not is_worthy:
                            emit("log", {"message": f"[ALGO CRACKER] ⏭ Skipped IG post @{author}: {eval_reason}"})
                            try:
                                close_btn = page.locator("svg[aria-label='Close'], div[role='dialog'] svg[aria-label='Close']").first
                                if close_btn.count() > 0 and close_btn.is_visible():
                                    close_btn.click()
                                    time.sleep(0.8)
                                else:
                                    page.keyboard.press("Escape")
                                    time.sleep(0.8)
                            except Exception:
                                pass
                            continue

                        emit("log", {
                            "message": f"[ALGO CRACKER] 🚀 High-Velocity Instagram Post! @{author} (Score: {viral_score}/100, Velocity: ~{norm_metrics['velocity']} likes/hr)"
                        })
                        print(f"\n[Instagram Explore] [{commented_count + 1}/{target_comments}] Post: @{author} ({post_id}) | Score: {viral_score}")

                        # Capture screenshot
                        try:
                            screenshot_bytes = article.screenshot(timeout=3000) if article != page else page.screenshot(timeout=3000)
                        except Exception:
                            screenshot_bytes = page.screenshot(timeout=3000)

                        comment_text = generate_visual_comment(screenshot_bytes, author, client, on_error=handle_api_error)
                        if not comment_text:
                            emit("log", {"message": "Halting campaign due to Gemini API error. Please update your API key."})
                            emit("campaign_completed", {"totalCommented": commented_count, "target": target_comments, "error": "API_KEY_ERROR"})
                            break

                        reach_score = config.calculate_reach_score(comment_text)
                        
                        print(f"Comment: \"{comment_text}\" (Reach Score: {reach_score})")
                        emit("comment_generated", {"postId": post_id, "author": author, "comment": comment_text, "reachScore": reach_score, "viralScore": viral_score})

                        success = open_and_submit_comment(page, comment_text)
                        if success:
                            commented_count += 1
                            emit("comment_posted", {
                                "postId": post_id,
                                "author": author,
                                "comment": comment_text,
                                "progress": commented_count,
                                "target": target_comments,
                                "reachScore": reach_score,
                                "viralScore": viral_score,
                                "url": f"https://www.instagram.com/p/{post_id}/"
                            })
                            print(f"--> [Instagram] Commented successfully! [{commented_count}/{target_comments}]")
                        else:
                            emit("comment_failed", {"postId": post_id, "author": author})

                        # Close post modal / back to explore
                        close_btn = page.locator("svg[aria-label='Close'], div[role='dialog'] svg[aria-label='Close']").first
                        if close_btn.count() > 0 and close_btn.is_visible():
                            close_btn.click()
                            time.sleep(1)
                        else:
                            page.goto("https://www.instagram.com/explore/", wait_until="domcontentloaded")
                            time.sleep(2)

                        if commented_count < target_comments:
                            delay = random.randint(config.MIN_DELAY, config.MAX_DELAY)
                            emit("delay", {"seconds": delay})
                            time.sleep(delay)

                        break
                    except Exception as e:
                        err_msg = str(e).lower()
                        emit("log", {"message": f"Error interacting with explore item: {e}"})
                        if "closed" in err_msg or "target" in err_msg:
                            emit("log", {"message": "Instagram browser session closed. Terminating loop."})
                            break
                        try:
                            page.goto("https://www.instagram.com/explore/", wait_until="domcontentloaded")
                            time.sleep(2)
                        except Exception:
                            break
                        continue

            else:
                # Regular feed flow
                articles = page.locator("article").all()
                found_new = False

                for article in articles:
                    if stop_event and stop_event.is_set():
                        break

                    try:
                        if is_sponsored_ad(article):
                            continue

                        post_link_el = article.locator("a[href*='/p/'], a[href*='/reel/']").first
                        if post_link_el.count() == 0:
                            continue

                        href = post_link_el.get_attribute("href")
                        if not href:
                            continue

                        parts = [x for x in href.strip("/").split("/") if x]
                        post_id = parts[-1] if parts else None

                        if not post_id or post_id in seen_posts:
                            continue

                        seen_posts.add(post_id)
                        found_new = True

                        try:
                            article.scroll_into_view_if_needed(timeout=2000)
                        except Exception:
                            pass
                        time.sleep(0.4)

                        author = "creator"
                        author_el = article.locator("header a[role='link'], a[role='link']").first
                        if author_el.count() > 0:
                            author = author_el.inner_text().split("\n")[0].strip()

                        emit("post_found", {"postId": post_id, "author": author, "url": f"https://www.instagram.com/p/{post_id}/"})
                        try:
                            screenshot_bytes = article.screenshot(timeout=3000)
                        except Exception:
                            screenshot_bytes = page.screenshot(timeout=3000)

                        comment_text = generate_visual_comment(screenshot_bytes, author, client, on_error=handle_api_error)
                        if not comment_text:
                            emit("log", {"message": "Halting campaign due to Gemini API error. Please update your API key."})
                            emit("campaign_completed", {"totalCommented": commented_count, "target": target_comments, "error": "API_KEY_ERROR"})
                            break

                        reach_score = config.calculate_reach_score(comment_text)
                        
                        emit("comment_generated", {"postId": post_id, "author": author, "comment": comment_text, "reachScore": reach_score})

                        post_full_url = f"https://www.instagram.com/p/{post_id}/"
                        page.goto(post_full_url, wait_until="domcontentloaded")
                        time.sleep(2)

                        success = open_and_submit_comment(page, comment_text)
                        if success:
                            commented_count += 1
                            emit("comment_posted", {
                                "postId": post_id,
                                "author": author,
                                "comment": comment_text,
                                "progress": commented_count,
                                "target": target_comments,
                                "reachScore": reach_score,
                                "url": post_full_url
                            })
                        else:
                            emit("comment_failed", {"postId": post_id, "author": author})

                        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
                        time.sleep(1.5)

                        page.mouse.wheel(0, 1200)
                        page.keyboard.press("PageDown")

                        if commented_count < target_comments:
                            delay = random.randint(config.MIN_DELAY, config.MAX_DELAY)
                            emit("delay", {"seconds": delay})
                            time.sleep(delay)

                        break
                    except Exception as e:
                        err_msg = str(e).lower()
                        emit("log", {"message": f"Error handling post: {e}"})
                        if "closed" in err_msg or "target" in err_msg:
                            emit("log", {"message": "Instagram browser session closed. Terminating loop."})
                            break
                        try:
                            page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
                            time.sleep(1.5)
                        except Exception:
                            break
                        continue

            if not found_new:
                emit("log", {"message": "Scanning further down the feed..."})
                page.mouse.wheel(0, 1000)
                page.keyboard.press("PageDown")
                time.sleep(1.8)
                scroll_attempts += 1

        emit("campaign_completed", {"totalCommented": commented_count, "target": target_comments})
        context.close()
        return commented_count

def run_vision_commenter():
    """CLI default launcher."""
    run_instagram_campaign()

if __name__ == "__main__":
    run_vision_commenter()