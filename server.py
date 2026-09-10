"""
Kinetic Feed - Local Web Dashboard & Real-Time SSE Server
Lightweight, zero-dependency multi-threaded HTTP + SSE server.
"""

import json
import os
import queue
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import config
import algo_engine
from engine import engine

STATIC_DIR = config.BASE_DIR / "static"

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class KineticDashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy default console logging of SSE pings
        if "/api/stream" not in str(args):
            super().log_message(format, *args)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Real-Time Server-Sent Events (SSE) stream
        if path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            q = engine.subscribe()
            try:
                # Send recent buffered events immediately
                with engine.lock:
                    initial_events = list(engine.recent_events[-10:])
                for ev in initial_events:
                    msg = f"data: {json.dumps(ev)}\n\n"
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()

                # Stream live updates
                while True:
                    try:
                        ev = q.get(timeout=15.0)
                        msg = f"data: {json.dumps(ev)}\n\n"
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive heartbeat comment
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                engine.unsubscribe(q)
            return

        # 2. Status API
        if path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status_data = engine.get_status()
            self.wfile.write(json.dumps(status_data).encode("utf-8"))
            return

        # 3. Algorithm-Cracked Hashtags API
        if path == "/api/hashtags/suggest":
            query_params = parse_qs(parsed.query)
            platform = query_params.get("platform", ["instagram"])[0]
            topic = query_params.get("topic", [""])[0]
            suggestions = algo_engine.get_suggested_hashtags(platform, topic)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "hashtags": suggestions}).encode("utf-8"))
            return

        # 4. Static Files
        if path == "/" or path == "/index.html":
            file_path = STATIC_DIR / "index.html"
            content_type = "text/html"
        elif path.startswith("/static/"):
            rel_path = path.replace("/static/", "")
            file_path = STATIC_DIR / rel_path
            if path.endswith(".css"):
                content_type = "text/css"
            elif path.endswith(".js"):
                content_type = "application/javascript"
            elif path.endswith(".svg"):
                content_type = "image/svg+xml"
            else:
                content_type = "text/plain"
        else:
            file_path = STATIC_DIR / path.lstrip("/")
            content_type = "text/plain"

        if file_path.exists() and file_path.is_file():
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        # 1. Start Campaign (Exclusively triggered from Campaign Controller)
        if path == "/api/campaign/start":
            platform = payload.get("platform", "instagram")
            target = int(payload.get("target", 6))
            mode = payload.get("mode", "trending")
            topic = payload.get("topic", "")
            raw_urls = payload.get("urls", [])

            # Handle both list of URLs or multi-line string of URLs
            urls = []
            if isinstance(raw_urls, str):
                urls = [u.strip() for u in raw_urls.splitlines() if u.strip()]
            elif isinstance(raw_urls, list):
                for item in raw_urls:
                    if isinstance(item, str):
                        for sub_u in item.splitlines():
                            sub_u = sub_u.strip()
                            if sub_u:
                                urls.append(sub_u)

            success = engine.start_campaign(platform, target, mode, topic, target_urls=urls if urls else None)
            self.send_response(200 if success else 400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": success,
                "error": None if success else f"Campaign for {platform} is already active or invalid."
            }).encode("utf-8"))
            return

        # 2. Stop Campaign
        if path == "/api/campaign/stop":
            platform = payload.get("platform", "instagram")
            success = engine.stop_campaign(platform)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))
            return

        # 3. Check / Verify Platform Login
        if path == "/api/platform/verify":
            platform = payload.get("platform", "all")
            if platform == "all":
                for p in ["instagram", "twitter", "threads"]:
                    engine.verify_platform(p)
            else:
                engine.verify_platform(platform)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": f"Verification started for {platform}"}).encode("utf-8"))
            return

        # 4. Trigger Browser Login
        if path == "/api/login/trigger":
            platform = payload.get("platform", "instagram")
            success = engine.trigger_login(platform)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))
            return

        # 4. Save Configuration
        if path == "/api/config":
            api_key = payload.get("apiKey")
            model = payload.get("model")
            min_delay = payload.get("minDelay")
            max_delay = payload.get("maxDelay")

            env_path = config.BASE_DIR / ".env"
            lines = []
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            # Update in memory
            if api_key:
                config.GEMINI_API_KEY = api_key
                os.environ["GEMINI_API_KEY"] = api_key
            if model:
                config.GEMINI_MODEL = model
                os.environ["GEMINI_MODEL"] = model
            if min_delay:
                config.MIN_DELAY = int(min_delay)
            if max_delay:
                config.MAX_DELAY = int(max_delay)

            # Write back to .env
            env_content = f"""# Kinetic Feed - Environment Configuration
GEMINI_API_KEY="{config.GEMINI_API_KEY}"
GEMINI_MODEL="{config.GEMINI_MODEL}"
TARGET_COMMENTS={config.TARGET_COMMENTS}
MIN_DELAY={config.MIN_DELAY}
MAX_DELAY={config.MAX_DELAY}
DASHBOARD_PORT={config.DASHBOARD_PORT}
"""
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def run_dashboard_server(port: int = None):
    if port is None:
        port = config.DASHBOARD_PORT

    server_address = ("", port)
    httpd = ThreadedHTTPServer(server_address, KineticDashboardHandler)
    print("\n" + "="*60)
    print(f"🚀 [Kinetic Feed] Dashboard running at: http://localhost:{port}")
    print(f"⚡ Real-time SSE streaming active on: http://localhost:{port}/api/stream")
    print(f"🤖 Gemini Vision model: {config.GEMINI_MODEL}")
    print("="*60 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Kinetic Feed] Shutting down dashboard server...")
        httpd.server_close()

if __name__ == "__main__":
    run_dashboard_server()
