# Kinetic Feed

Kinetic Feed is a local dashboard and automation engine for Instagram, X (Twitter), and Threads. It uses Playwright for browser automation and Google Gemini Vision to generate context-aware comments from post screenshots.

## What It Includes

- Local dashboard with live status, campaign controls, and Server-Sent Events (SSE).
- Persistent browser profiles under `user_data/` for each platform.
- Platform login helpers for Instagram, X, and Threads.
- Gemini Vision comment generation with fallback comments when no API client is available.
- Campaign metrics persisted in `stats.json`.

## Requirements

- Python 3.9 or newer
- Chrome or Chromium
- A Google Gemini API key for AI-generated comments
- Platform accounts that are permitted to use automated interactions

## Quick Start

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
cp .env.example .env
```

Edit `.env` and set `GEMINI_API_KEY` to a valid key. Then launch the dashboard:

```bash
python3 server.py
```

Open [http://localhost:5050](http://localhost:5050) in a browser.

For a previously configured environment, the quick launch command is:

```bash
python3 server.py
```

The port can be changed with `DASHBOARD_PORT` in `.env`.

## First-Time Platform Login

Run each helper once, complete login and 2FA in the opened browser, then press Enter in the terminal:

```bash
python3 login_instagram.py
python3 login_twitter.py
python3 login_threads.py
```

Sessions are stored locally in `user_data/` and are ignored by git. The dashboard can also trigger login and session verification.

## Configuration

`.env.example` contains the supported settings:

```env
GEMINI_API_KEY="your_gemini_api_key_here"
GEMINI_MODEL="gemini-3.6-flash"
TARGET_COMMENTS=6
MIN_DELAY=3
MAX_DELAY=6
DASHBOARD_PORT=5050
```

`GEMINI_API_KEY` is required for Gemini-generated comments. The dashboard and login helpers can still be started without it.

## Standalone Campaigns

Campaign workers can be run without the dashboard:

```bash
python3 gemini_vision_commenter.py
python3 twitter_vision_commenter.py
python3 threads_vision_commenter.py
```

The dashboard is the recommended entry point because it coordinates campaigns, session checks, live events, and persisted metrics.

## Project Layout

| Path | Purpose |
| --- | --- |
| `server.py` | Local HTTP dashboard and SSE server |
| `engine.py` | Campaign orchestration and event broadcasting |
| `config.py` | Environment loading and runtime settings |
| `*_vision_commenter.py` | Platform-specific campaign workers |
| `login_*.py` | Persistent browser login helpers |
| `session_checker.py` | Platform session verification |
| `static/` | Dashboard HTML, CSS, and JavaScript |
| `requirements.txt` | Python dependencies |

## Safety and Privacy

Browser profiles, API keys, campaign metrics, and generated screenshots are local runtime data and are excluded by `.gitignore`. Review each platform's terms and applicable laws before enabling automated interactions. Use conservative quotas and delays, and keep credentials out of source control.
