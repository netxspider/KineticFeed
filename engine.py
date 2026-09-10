"""
Kinetic Feed - Orchestration Engine & Real Event Broadcaster
Manages campaigns, tracks real persisted metrics, checks actual platform logins,
and broadcasts live event streams to the Web Dashboard.
"""

import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional
import config

from gemini_vision_commenter import run_instagram_campaign
from twitter_vision_commenter import run_twitter_campaign
from threads_vision_commenter import run_threads_campaign

from login_instagram import save_instagram_session
from login_twitter import save_twitter_session
from login_threads import save_threads_session
import session_checker

STATS_FILE = config.BASE_DIR / "stats.json"

class KineticEngine:
    def __init__(self):
        self.lock = threading.Lock()
        self.event_subscribers: List[queue.Queue] = []
        self.activity_log: List[dict] = []
        self.recent_events: List[dict] = []
        self.max_history = 150

        # Load real persistent stats from disk or initialize to 0
        self.real_stats = self._load_persisted_stats()

        self.platforms = {
            "instagram": {
                "session_exists": config.USER_DATA_INSTAGRAM.exists(),
                "logged_in": False,
                "username": None,
                "status": "UNCHECKED",
                "details": "Click 'Verify Session' to inspect login",
                "active": False,
                "checking": False
            },
            "twitter": {
                "session_exists": config.USER_DATA_TWITTER.exists(),
                "logged_in": False,
                "username": None,
                "status": "UNCHECKED",
                "details": "Click 'Verify Session' to inspect login",
                "active": False,
                "checking": False
            },
            "threads": {
                "session_exists": config.USER_DATA_THREADS.exists(),
                "logged_in": False,
                "username": None,
                "status": "UNCHECKED",
                "details": "Click 'Verify Session' to inspect login",
                "active": False,
                "checking": False
            }
        }

        self.active_tasks: Dict[str, dict] = {}
        self.stop_signals: Dict[str, threading.Event] = {}

    def _load_persisted_stats(self) -> dict:
        if STATS_FILE.exists():
            try:
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {
                        "posts_analyzed": int(data.get("posts_analyzed", 0)),
                        "ai_comments": int(data.get("ai_comments", 0)),
                        "reach_boost": float(data.get("reach_boost", 0.0)),
                        "history": list(data.get("history", []))[-50:]
                    }
            except Exception as e:
                print(f"[Kinetic Feed] Warning loading stats.json: {e}")

        # Fresh default stats - strictly real 0 values
        return {
            "posts_analyzed": 0,
            "ai_comments": 0,
            "reach_boost": 0.0,
            "history": []
        }

    def _save_persisted_stats(self):
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.real_stats, f, indent=2)
        except Exception as e:
            print(f"[Kinetic Feed] Warning saving stats.json: {e}")

    def subscribe(self) -> queue.Queue:
        q = queue.Queue(maxsize=100)
        with self.lock:
            self.event_subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self.lock:
            if q in self.event_subscribers:
                self.event_subscribers.remove(q)

    def broadcast(self, event: dict):
        with self.lock:
            self.recent_events.append(event)
            if len(self.recent_events) > self.max_history:
                self.recent_events.pop(0)

            etype = event.get("type")
            platform = event.get("platform")

            # Update real stats based on actual execution events
            if etype == "post_found":
                self.real_stats["posts_analyzed"] += 1
                self._save_persisted_stats()

            elif etype == "comment_posted":
                self.real_stats["ai_comments"] += 1
                # Organic reach multiplier calculation based on real comments
                self.real_stats["reach_boost"] = round(1.0 + (self.real_stats["ai_comments"] * 0.12), 2)
                
                post_url = event.get("url")
                post_id = event.get("postId")
                author = event.get("author") or ""
                if not post_url:
                    if platform == "instagram" and post_id:
                        post_url = f"https://www.instagram.com/p/{post_id}/"
                    elif platform == "twitter" and post_id:
                        clean_auth = author.replace("@", "") if author and author != "user" else "i"
                        post_url = f"https://x.com/{clean_auth}/status/{post_id}"
                    elif platform == "threads" and post_id:
                        if str(post_id).startswith("@"):
                            post_url = f"https://www.threads.net/{post_id}"
                        else:
                            clean_auth = author.replace("@", "") if author and author != "creator" else "t"
                            post_url = f"https://www.threads.net/@{clean_auth}/post/{post_id}"

                self.real_stats["history"].append({
                    "platform": platform,
                    "postId": post_id,
                    "author": author,
                    "comment": event.get("comment"),
                    "url": post_url,
                    "reachScore": event.get("reachScore"),
                    "timestamp": event.get("timestamp") or time.time()
                })
                if len(self.real_stats["history"]) > 60:
                    self.real_stats["history"].pop(0)
                self._save_persisted_stats()

            elif etype in ["api_error", "error"]:
                # Ensure active campaign is marked as stopped on critical error
                if platform in self.platforms:
                    self.platforms[platform]["active"] = False

            elif etype == "campaign_started" and platform:
                if platform in self.platforms:
                    self.platforms[platform]["active"] = True

            elif etype in ["campaign_completed", "campaign_stopped"] and platform:
                if platform in self.platforms:
                    self.platforms[platform]["active"] = False

            # Broadcast to all live SSE client queues
            dead = []
            for sub in self.event_subscribers:
                try:
                    sub.put_nowait(event)
                except queue.Full:
                    pass
                except Exception:
                    dead.append(sub)
            for d in dead:
                if d in self.event_subscribers:
                    self.event_subscribers.remove(d)

    def on_platform_event(self, event: dict):
        self.broadcast(event)

    def verify_platform(self, platform: str):
        """Asynchronously checks if the platform has an active authenticated session."""
        if platform not in self.platforms:
            return

        with self.lock:
            self.platforms[platform]["checking"] = True

        self.broadcast({
            "type": "verification_started",
            "platform": platform,
            "timestamp": time.time(),
            "message": f"Checking {platform.capitalize()} authenticated session..."
        })

        def worker():
            try:
                res = session_checker.check_platform(platform)
                with self.lock:
                    self.platforms[platform]["checking"] = False
                    self.platforms[platform]["logged_in"] = res.get("logged_in", False)
                    self.platforms[platform]["username"] = res.get("username")
                    self.platforms[platform]["status"] = res.get("status", "UNKNOWN")
                    self.platforms[platform]["details"] = res.get("details", "")

                self.broadcast({
                    "type": "verification_completed",
                    "platform": platform,
                    "timestamp": time.time(),
                    "logged_in": res.get("logged_in", False),
                    "username": res.get("username"),
                    "status": res.get("status"),
                    "details": res.get("details")
                })
            except Exception as e:
                with self.lock:
                    self.platforms[platform]["checking"] = False
                    self.platforms[platform]["status"] = "ERROR"
                    self.platforms[platform]["details"] = str(e)
                self.broadcast({
                    "type": "verification_completed",
                    "platform": platform,
                    "timestamp": time.time(),
                    "logged_in": False,
                    "status": "ERROR",
                    "details": str(e)
                })

        th = threading.Thread(target=worker, daemon=True)
        th.start()

    def get_commented_post_ids(self, platform: str) -> set:
        """Returns set of all post IDs that have already been commented on to avoid re-commenting."""
        with self.lock:
            history = self.real_stats.get("history", [])
            return {
                str(h.get("postId")).strip()
                for h in history
                if h.get("platform") == platform and h.get("postId")
            }

    def start_campaign(
        self,
        platform: str,
        target: int = 6,
        mode: str = "trending",
        topic: str = "",
        target_urls: Optional[List[str]] = None
    ) -> bool:
        """Campaigns can ONLY be launched via this method from the Campaign Controller."""
        if platform in self.active_tasks and self.active_tasks[platform].get("running"):
            return False

        stop_evt = threading.Event()
        self.stop_signals[platform] = stop_evt

        # Normalize URL list if provided
        clean_urls = []
        if target_urls:
            for u in target_urls:
                u = u.strip()
                if u and (u.startswith("http://") or u.startswith("https://")):
                    clean_urls.append(u)

        target_count = len(clean_urls) if clean_urls else target
        commented_ids = self.get_commented_post_ids(platform)

        def worker():
            try:
                if platform == "instagram":
                    run_instagram_campaign(
                        target_comments=target_count,
                        mode=mode,
                        topic=topic,
                        target_urls=clean_urls if clean_urls else None,
                        exclude_post_ids=commented_ids,
                        on_event=self.on_platform_event,
                        stop_event=stop_evt
                    )
                elif platform == "twitter":
                    run_twitter_campaign(
                        target_comments=target_count,
                        mode=mode,
                        topic=topic,
                        target_urls=clean_urls if clean_urls else None,
                        exclude_post_ids=commented_ids,
                        on_event=self.on_platform_event,
                        stop_event=stop_evt
                    )
                elif platform == "threads":
                    run_threads_campaign(
                        target_comments=target_count,
                        mode=mode,
                        topic=topic,
                        target_urls=clean_urls if clean_urls else None,
                        exclude_post_ids=commented_ids,
                        on_event=self.on_platform_event,
                        stop_event=stop_evt
                    )
            except Exception as e:
                self.broadcast({
                    "platform": platform,
                    "type": "error",
                    "timestamp": time.time(),
                    "message": f"Worker encountered an error: {e}"
                })
            finally:
                with self.lock:
                    if platform in self.active_tasks:
                        self.active_tasks[platform]["running"] = False
                    if platform in self.platforms:
                        self.platforms[platform]["active"] = False
                self.broadcast({
                    "platform": platform,
                    "type": "campaign_stopped",
                    "timestamp": time.time()
                })

        th = threading.Thread(target=worker, daemon=True)
        self.active_tasks[platform] = {
            "thread": th,
            "running": True,
            "target": target_count,
            "mode": "direct_urls" if clean_urls else mode,
            "topic": topic,
            "urls": clean_urls,
            "start_time": time.time()
        }
        th.start()
        return True

    def stop_campaign(self, platform: str) -> bool:
        with self.lock:
            if platform in self.stop_signals:
                self.stop_signals[platform].set()
            if platform in self.active_tasks:
                self.active_tasks[platform]["running"] = False
            if platform in self.platforms:
                self.platforms[platform]["active"] = False

        self.broadcast({
            "platform": platform,
            "type": "campaign_stopped",
            "timestamp": time.time()
        })
        return True

    def trigger_login(self, platform: str) -> bool:
        def login_worker():
            self.broadcast({
                "platform": platform,
                "type": "log",
                "timestamp": time.time(),
                "message": f"Launching browser window for {platform.capitalize()} login..."
            })
            try:
                if platform == "instagram":
                    save_instagram_session(interactive=False)
                elif platform == "twitter":
                    save_twitter_session(interactive=False)
                elif platform == "threads":
                    save_threads_session(interactive=False)

                # Trigger automatic re-verification after user login window closes
                self.verify_platform(platform)

                self.broadcast({
                    "platform": platform,
                    "type": "login_completed",
                    "timestamp": time.time(),
                    "message": f"Saved {platform.capitalize()} browser session. Verifying..."
                })
            except Exception as e:
                self.broadcast({
                    "platform": platform,
                    "type": "log",
                    "timestamp": time.time(),
                    "message": f"Login window closed or error: {e}"
                })

        th = threading.Thread(target=login_worker, daemon=True)
        th.start()
        return True

    def get_status(self) -> dict:
        with self.lock:
            active_count = len([k for k, v in self.active_tasks.items() if v.get("running")])

            # Refresh session profile existence
            self.platforms["instagram"]["session_exists"] = config.USER_DATA_INSTAGRAM.exists()
            self.platforms["twitter"]["session_exists"] = config.USER_DATA_TWITTER.exists()
            self.platforms["threads"]["session_exists"] = config.USER_DATA_THREADS.exists()

            return {
                "stats": {
                    "posts_analyzed": self.real_stats["posts_analyzed"],
                    "ai_comments": self.real_stats["ai_comments"],
                    "reach_boost": self.real_stats["reach_boost"],
                    "active_campaigns": active_count,
                    "model": config.GEMINI_MODEL,
                    "api_configured": bool(config.GEMINI_API_KEY)
                },
                "platforms": self.platforms,
                "history": self.real_stats["history"][-20:],
                "activeTasks": {
                    k: {
                        "running": v["running"],
                        "mode": v["mode"],
                        "target": v["target"],
                        "urls_count": len(v.get("urls", []))
                    }
                    for k, v in self.active_tasks.items()
                }
            }

engine = KineticEngine()
