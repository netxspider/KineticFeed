"""
Kinetic Feed - Twitter (X) AI Vision & Context Engagement Engine
Targets trending tweets and For You algorithmic posts on X, visually inspects media with Gemini Vision,
and submits punchy high-reach replies.
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
from datetime import datetime

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-features=IsolateOrigins,site-per-process"
]

def get_gemini_client():
    if config.GEMINI_API_KEY:
        try:
            return genai.Client(api_key=config.GEMINI_API_KEY)
        except Exception as e:
            print(f"[Kinetic Feed] Gemini Client init warning: {e}")
    return None

def is_promoted_tweet(article) -> bool:
    """Detects promoted/sponsored ads on X."""
    try:
        if article.locator("[data-testid='placementTracking']").count() > 0:
            return True
        text = article.inner_text().lower()
        if "promoted" in text or " ad\n" in text or "sponsored" in text:
            return True
    except Exception:
        pass
    return False

def generate_twitter_comment(screenshot_bytes: bytes, author: str, tweet_snippet: str = "", client=None, on_error=None) -> Optional[str]:
    """Uses Gemini Vision to produce sharp, high-engagement Twitter replies."""
    if not client:
        client = get_gemini_client()

    if not client:
        err = "Gemini API key is not configured. Please set a valid GEMINI_API_KEY in .env."
        if on_error:
            on_error(err)
        return None

    prompt = f"""
You are an active Twitter/X user reacting to a tweet by @{author}.
Tweet Context: {tweet_snippet[:200] if tweet_snippet else 'See visual context.'}

Analyze the visual image, meme, chart, screenshot, or text in the provided tweet screenshot.
Write a natural, authentic reply native to Twitter/X culture:
- Sarcastic / witty / dry humor (e.g. "bro really thought we wouldn't notice 💀", "the accuracy hurts 😂")
- Casual / relatable internet banter (e.g. "nah this is actually wild 😭", "wait who let them cook 😭", "felt this fr")
- Pure emoji reaction (e.g. "💀😭", "🔥🔥", "👀🍿", "😂👏") if the visual speaks for itself!
- Short punchy observation (3 to 8 words max).
CRITICAL: NEVER sound like an AI, marketer, or brand. Do NOT say "Great tweet!" or generic corporate praise.
Return ONLY the reply text or emojis without quotes.
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
        print(f"[Gemini Twitter Error] {err_msg}")
        if on_error:
            on_error(err_msg)
        return None

def submit_twitter_reply(page, reply_text: str, tweet_locator=None) -> bool:
    """Locates the reply button, inputs the text into the composer, and posts."""
    try:
        # 1. Click reply trigger
        clicked = False
        if tweet_locator:
            try:
                btn = tweet_locator.locator("[data-testid='reply']").first
                if btn.count() > 0 and btn.is_visible():
                    btn.click(timeout=2500)
                    time.sleep(0.8)
                    clicked = True
            except Exception:
                pass

        if not clicked:
            try:
                reply_btn = page.locator("[data-testid='reply']").first
                if reply_btn.count() > 0 and reply_btn.is_visible():
                    reply_btn.click(timeout=2500)
                    time.sleep(0.8)
            except Exception:
                pass

        # 2. Locate composer textarea (dialog modal or inline drawer)
        composer_selectors = [
            "div[role='dialog'] div[data-testid='tweetTextarea_0']",
            "div[data-testid='tweetTextarea_0']",
            "div[role='textbox'][contenteditable='true']"
        ]
        composer = None
        for sel in composer_selectors:
            box = page.locator(sel).first
            if box.count() > 0 and box.is_visible():
                composer = box
                break

        if not composer:
            print("  -> Could not locate Twitter reply composer.")
            return False

        composer.click()
        time.sleep(0.3)
        page.keyboard.type(reply_text, delay=random.randint(15, 25))
        time.sleep(0.6)

        # 3. Click Tweet / Reply button
        send_selectors = [
            "button[data-testid='tweetButton']",
            "button[data-testid='tweetButtonInline']",
            "div[role='dialog'] button[data-testid='tweetButton']",
            "button:has-text('Reply')"
        ]
        posted = False
        for s in send_selectors:
            send_btn = page.locator(s).first
            if send_btn.count() > 0 and send_btn.is_visible():
                send_btn.click(timeout=2000)
                time.sleep(1.0)
                posted = True
                break

        if not posted:
            page.keyboard.press("Meta+Enter")
            page.keyboard.press("Control+Enter")
            time.sleep(1.0)

        return True
    except Exception as e:
        print(f"  -> Error posting Twitter reply: {e}")
        return False

def run_twitter_campaign(
    target_comments: int = None,
    mode: str = "trending",  # "trending", "for_you", or custom topic
    topic: str = None,
    target_urls: list = None,
    exclude_post_ids: set = None,
    on_event = None,
    stop_event = None
):
    """Executes Twitter (X) engagement campaign with real-time event broadcasting."""
    if target_urls:
        target_comments = len(target_urls)
    elif target_comments is None:
        target_comments = config.TARGET_COMMENTS

    client = get_gemini_client()
    user_dir = str(config.USER_DATA_TWITTER)
    Path(user_dir).mkdir(parents=True, exist_ok=True)

    def emit(event_type: str, data: dict):
        if on_event:
            payload = {"platform": "twitter", "type": event_type, "timestamp": time.time(), **data}
            on_event(payload)

    def handle_api_error(err_str: str):
        emit("api_error", {
            "error": err_str,
            "message": f"Gemini API Error: {err_str[:120]}"
        })
        emit("log", {"message": f"[API ERROR] Gemini Vision failed: {err_str[:100]}"})

    # Initialize seen_tweets with previously commented post IDs
    seen_tweets = set(exclude_post_ids) if exclude_post_ids else set()
    try:
        with open(config.BASE_DIR / "stats.json", "r", encoding="utf-8") as f:
            sj = json.load(f)
            for h in sj.get("history", []):
                if h.get("platform") == "twitter" and h.get("postId"):
                    seen_tweets.add(str(h["postId"]).strip())
    except Exception:
        pass

    emit("campaign_started", {"target": target_comments, "mode": "direct_links" if target_urls else mode, "topic": topic, "urlsCount": len(target_urls) if target_urls else 0})

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=False,
                channel="chrome",
                args=STEALTH_ARGS,
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1280, "height": 850}
            )
        except Exception:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=False,
                args=STEALTH_ARGS,
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1280, "height": 850}
            )

        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        # Handle direct post URLs
        if target_urls:
            emit("log", {"message": f"Targeting {len(target_urls)} custom Twitter/X URLs directly."})
            replied_count = 0
            for idx, tweet_url in enumerate(target_urls):
                if stop_event and stop_event.is_set():
                    emit("log", {"message": "Direct link campaign stopped by user."})
                    break

                tweet_url = tweet_url.strip()
                if not tweet_url:
                    continue

                status_id = tweet_url.split("/status/")[-1].split("?")[0].split("/")[0] if "/status/" in tweet_url else f"tweet_{idx+1}"
                if status_id in seen_tweets:
                    emit("log", {"message": f"Skipping already commented direct tweet: {status_id}"})
                    continue

                seen_tweets.add(status_id)
                emit("log", {"message": f"[{idx+1}/{len(target_urls)}] Opening tweet: {tweet_url}"})

                try:
                    page.goto(tweet_url, wait_until="domcontentloaded")
                    time.sleep(3.5)

                    tweet_el = page.locator("article[data-testid='tweet']").first
                    if tweet_el.count() == 0:
                        tweet_el = page

                    author = "user"
                    user_el = page.locator("[data-testid='User-Name']").first
                    if user_el.count() > 0:
                        user_text = user_el.inner_text()
                        for part in user_text.split():
                            if part.startswith("@"):
                                author = part.replace("@", "")
                                break

                    tweet_text = ""
                    text_el = page.locator("[data-testid='tweetText']").first
                    if text_el.count() > 0:
                        tweet_text = text_el.inner_text()

                    emit("post_found", {"postId": status_id, "author": author, "url": tweet_url})
                    try:
                        screenshot_bytes = tweet_el.screenshot(timeout=3000)
                    except Exception:
                        screenshot_bytes = page.screenshot(timeout=3000)

                    reply_text = generate_twitter_comment(screenshot_bytes, author, tweet_text, client, on_error=handle_api_error)
                    if not reply_text:
                        emit("log", {"message": "Halting campaign due to Gemini API error. Please update your API key."})
                        emit("campaign_completed", {"totalCommented": replied_count, "target": len(target_urls), "error": "API_KEY_ERROR"})
                        break

                    reach_score = config.calculate_reach_score(reply_text)
                    emit("comment_generated", {"postId": status_id, "author": author, "comment": reply_text, "reachScore": reach_score})

                    success = submit_twitter_reply(page, reply_text, tweet_locator=tweet_el)
                    if success:
                        replied_count += 1
                        emit("comment_posted", {
                            "postId": status_id,
                            "author": author,
                            "comment": reply_text,
                            "progress": replied_count,
                            "target": len(target_urls),
                            "reachScore": reach_score,
                            "url": tweet_url
                        })
                    else:
                        emit("comment_failed", {"postId": status_id, "author": author})

                    if idx < len(target_urls) - 1:
                        delay = random.randint(config.MIN_DELAY, config.MAX_DELAY)
                        emit("delay", {"seconds": delay})
                        time.sleep(delay)
                except Exception as e:
                    err_msg = str(e).lower()
                    emit("log", {"message": f"Error on direct tweet {tweet_url}: {e}"})
                    if "closed" in err_msg or "target" in err_msg:
                        break
                    continue

            emit("campaign_completed", {"totalCommented": replied_count, "target": len(target_urls)})
            context.close()
            return replied_count

        if mode == "trending":
            target_url = "https://x.com/explore/tabs/trending"
        elif mode == "for_you":
            target_url = "https://x.com/home"
        elif mode == "feed":
            target_url = "https://x.com/home"
        elif topic:
            target_url = f"https://x.com/search?q={topic}&f=top"
        else:
            target_url = "https://x.com/home"

        print(f"[Kinetic Feed] Connecting to Twitter/X ({target_url}) in {mode.upper()} mode...")
        emit("log", {"message": f"Connecting to Twitter/X in {mode.upper()} mode: {target_url}"})
        page.goto(target_url, wait_until="domcontentloaded")
        time.sleep(3.5)

        # Tab alignment for home feed modes
        if mode == "for_you":
            try:
                for_you_tab = page.locator("div[role='tab']:has-text('For you')").first
                if for_you_tab.count() > 0 and for_you_tab.is_visible():
                    for_you_tab.click()
                    time.sleep(1.5)
            except Exception:
                pass
        elif mode == "feed":
            try:
                following_tab = page.locator("div[role='tab']:has-text('Following')").first
                if following_tab.count() > 0 and following_tab.is_visible():
                    following_tab.click()
                    time.sleep(1.5)
            except Exception:
                pass

        seen_tweets = set()
        replied_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 60

        while replied_count < target_comments and scroll_attempts < max_scroll_attempts:
            if stop_event and stop_event.is_set():
                emit("log", {"message": "Campaign stopped by user."})
                break

            tweets = page.locator("article[data-testid='tweet']").all()
            found_new = False

            for tweet in tweets:
                if stop_event and stop_event.is_set():
                    break

                try:
                    if is_promoted_tweet(tweet):
                        continue

                    # Extract tweet ID and author
                    tweet_link = tweet.locator("a[href*='/status/']").first
                    if tweet_link.count() == 0:
                        continue

                    href = tweet_link.get_attribute("href")
                    if not href:
                        continue

                    status_id = href.split("/status/")[-1].split("?")[0].split("/")[0]
                    if not status_id or status_id in seen_tweets:
                        continue

                    seen_tweets.add(status_id)
                    found_new = True

                    try:
                        tweet.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass
                    time.sleep(0.3)

                    # Extract author handle
                    author = "user"
                    user_el = tweet.locator("[data-testid='User-Name']").first
                    if user_el.count() > 0:
                        user_text = user_el.inner_text()
                        for part in user_text.split():
                            if part.startswith("@"):
                                author = part.replace("@", "")
                                break

                    tweet_text = ""
                    text_el = tweet.locator("[data-testid='tweetText']").first
                    if text_el.count() > 0:
                        tweet_text = text_el.inner_text()

                    # ==========================================
                    # ALGORITHM CRACKING: EXTRACT REAL METRICS
                    # ==========================================
                    replies_text = "0"
                    likes_text = "0"
                    retweets_text = "0"
                    views_text = "0"
                    hours_old = 1.0

                    try:
                        rep_el = tweet.locator("[data-testid='reply']").first
                        if rep_el.count() > 0:
                            replies_text = rep_el.inner_text() or "0"
                    except Exception:
                        pass

                    try:
                        ret_el = tweet.locator("[data-testid='retweet']").first
                        if ret_el.count() > 0:
                            retweets_text = ret_el.inner_text() or "0"
                    except Exception:
                        pass

                    try:
                        lik_el = tweet.locator("[data-testid='like']").first
                        if lik_el.count() > 0:
                            likes_text = lik_el.inner_text() or "0"
                    except Exception:
                        pass

                    try:
                        view_el = tweet.locator("a[href*='/analytics'], [data-testid='app-text-transition-container']").first
                        if view_el.count() > 0:
                            views_text = view_el.inner_text() or "0"
                    except Exception:
                        pass

                    try:
                        time_el = tweet.locator("time").first
                        if time_el.count() > 0:
                            dt_str = time_el.get_attribute("datetime")
                            if dt_str:
                                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                                diff_hours = (datetime.now(dt.tzinfo) - dt).total_seconds() / 3600.0
                                hours_old = max(0.1, diff_hours)
                    except Exception:
                        pass

                    raw_metrics = {
                        "likes": likes_text,
                        "replies": replies_text,
                        "retweets": retweets_text,
                        "views": views_text,
                        "hours_old": hours_old
                    }

                    is_worthy, viral_score, eval_reason, norm_metrics = algo_engine.evaluate_post_metrics(
                        "twitter", raw_metrics
                    )

                    emit("post_found", {
                        "postId": status_id,
                        "author": author,
                        "url": f"https://x.com/{author}/status/{status_id}",
                        "viralScore": viral_score,
                        "metrics": norm_metrics
                    })

                    # Filter out non-viral or oversaturated posts
                    if not is_worthy:
                        emit("log", {
                            "message": f"[ALGO CRACKER] ⏭ Skipped @{author} ({status_id}): {eval_reason}"
                        })
                        continue

                    emit("log", {
                        "message": f"[ALGO CRACKER] 🚀 High-Velocity Viral Candidate Found! @{author} (Score: {viral_score}/100, Velocity: ~{norm_metrics['velocity']} likes/hr)"
                    })
                    print(f"\n[Twitter/X] [{replied_count + 1}/{target_comments}] Viral Post by @{author} ({status_id}) | Score: {viral_score}")

                    # Take screenshot of tweet element
                    try:
                        screenshot_bytes = tweet.screenshot(timeout=3000)
                    except Exception:
                        screenshot_bytes = page.screenshot(timeout=3000)

                    post_tweet_url = f"https://x.com/{author}/status/{status_id}" if author and author != "user" else f"https://x.com/i/status/{status_id}"
                    reply_text = generate_twitter_comment(screenshot_bytes, author, tweet_text, client, on_error=handle_api_error)
                    if not reply_text:
                        emit("log", {"message": "Halting campaign due to Gemini API error. Please update your API key."})
                        emit("campaign_completed", {"totalCommented": replied_count, "target": target_comments, "error": "API_KEY_ERROR"})
                        break

                    reach_score = config.calculate_reach_score(reply_text)
                    
                    print(f"Reply: \"{reply_text}\" (Reach Score: {reach_score})")
                    emit("comment_generated", {"postId": status_id, "author": author, "comment": reply_text, "reachScore": reach_score, "viralScore": viral_score})

                    # Submit reply
                    success = submit_twitter_reply(page, reply_text, tweet_locator=tweet)
                    if not success:
                        # Try navigating to tweet directly
                        tweet_url = post_tweet_url
                        try:
                            page.goto(tweet_url, wait_until="domcontentloaded", timeout=12000)
                            time.sleep(2)
                            success = submit_twitter_reply(page, reply_text)
                            page.goto(target_url, wait_until="domcontentloaded", timeout=12000)
                            time.sleep(2)
                        except Exception:
                            pass

                    if success:
                        replied_count += 1
                        emit("comment_posted", {
                            "postId": status_id,
                            "author": author,
                            "comment": reply_text,
                            "progress": replied_count,
                            "target": target_comments,
                            "reachScore": reach_score,
                            "viralScore": viral_score,
                            "url": post_tweet_url
                        })
                        print(f"--> [Twitter/X] Replied successfully! [{replied_count}/{target_comments}]")
                    else:
                        emit("comment_failed", {"postId": status_id, "author": author})

                    # Advance feed so new tweets load
                    page.mouse.wheel(0, 850)
                    page.keyboard.press("PageDown")
                    time.sleep(1.5)

                    if replied_count < target_comments:
                        delay = random.randint(config.MIN_DELAY, config.MAX_DELAY)
                        emit("delay", {"seconds": delay})
                        time.sleep(delay)

                    break

                except Exception as e:
                    err_msg = str(e).lower()
                    emit("log", {"message": f"Error handling tweet: {e}"})
                    if "closed" in err_msg or "target" in err_msg:
                        emit("log", {"message": "Twitter browser session closed. Terminating loop."})
                        break
                    continue

            if not found_new:
                emit("log", {"message": "Scanning for more trending tweets..."})
                page.mouse.wheel(0, 1200)
                page.keyboard.press("PageDown")
                time.sleep(1.8)
                scroll_attempts += 1

        emit("campaign_completed", {"totalCommented": replied_count, "target": target_comments})
        context.close()
        return replied_count

if __name__ == "__main__":
    run_twitter_campaign()
