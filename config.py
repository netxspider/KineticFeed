"""
Kinetic Feed - Central Configuration Module
Loads settings from .env file or environment variables with resilient fallback parsing.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def load_env_file(env_path: Path):
    """Simple, reliable .env parser to avoid strict external dependency requirements."""
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            # Only set if not already present in environment
            if key not in os.environ:
                os.environ[key] = val

# Load from .env
load_env_file(BASE_DIR / ".env")

# Core Settings
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

TARGET_COMMENTS = int(os.environ.get("TARGET_COMMENTS", "6"))
MIN_DELAY = int(os.environ.get("MIN_DELAY", "3"))
MAX_DELAY = int(os.environ.get("MAX_DELAY", "6"))
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "5050"))

# Browser Storage Paths
USER_DATA_BASE = BASE_DIR / "user_data"
USER_DATA_INSTAGRAM = USER_DATA_BASE / "instagram"
USER_DATA_TWITTER = USER_DATA_BASE / "twitter"
USER_DATA_THREADS = USER_DATA_BASE / "threads"

# Legacy fallback
if not USER_DATA_INSTAGRAM.exists() and USER_DATA_BASE.exists() and not (USER_DATA_BASE / "twitter").exists():
    # If old single user_data exists with Default profile
    if (USER_DATA_BASE / "Default").exists():
        USER_DATA_INSTAGRAM = USER_DATA_BASE

# Realistic human fallback comments (sarcastic, witty, funny, casual, and emoji reactions)
FALLBACK_COMMENTS = [
    "nah this is actually wild 😭",
    "💀💀",
    "the accuracy hurts 😂",
    "bro really thought we wouldn't notice 💀",
    "wait who let them cook like this 😭",
    "🔥🔥",
    "not what i was expecting to see today lmao",
    "😭😂",
    "living rent free in my head fr",
    "valid honestly",
    "this is unhinged 💀",
    "👀🍿",
    "felt this deep in my soul",
    "no way 💀",
    "😂👏",
    "how does this make so much sense 😭",
    "peak comedy right here",
    "💯",
    "bro woke up and chose chaos 😭",
    "i can't with this 😂"
]

def calculate_reach_score(comment_text: str) -> int:
    """
    Algorithmic reach optimization calculation based on reply science:
    - Brevity & Hook (punchy 5-65 char comments get top placement in reply rank): +12
    - Reply-bait / curiosity triggers ('?', 'wait', 'who', 'how'): +10
    - Emotion & viral triggers ('nah', 'wild', 'bro', 'fr', 'dead', 'lmao'): +9
    - Emoji richness (💀, 😭, 🔥, 😂, 👀): +5 to +10
    Base score: 65. Max: 99.
    """
    score = 65
    txt = comment_text.strip().lower()

    l = len(txt)
    if 4 <= l <= 65:
        score += 12
    elif l < 4:
        score += 6
    else:
        score += 3

    if "?" in txt or any(w in txt for w in ["who", "how", "why", "wait"]):
        score += 10

    viral_triggers = ["nah", "wild", "bro", "fr", "dead", "actually", "lmao", "valid", "accuracy", "chaos", "cook"]
    if any(vt in txt for vt in viral_triggers):
        score += 9

    emojis = ["💀", "😭", "🔥", "😂", "👀", "💯", "👏", "🤯"]
    emoji_count = sum(txt.count(e) for e in emojis)
    if emoji_count >= 1:
        score += min(10, emoji_count * 5)

    score += (abs(hash(txt)) % 5)
    return min(99, max(75, score))
