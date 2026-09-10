"""
Kinetic Feed - Algorithm Cracking & Viral Intelligence Engine
Evaluates social media post metrics (velocity, likes, replies, views, age),
calculates the Viral Index (0-100), filters out low-engagement/dead posts,
and generates algorithm-ranked hashtag recommendations.
"""

import re
import time
from typing import Dict, List, Optional, Tuple

# Algorithm-Cracked Hashtag Matrix organized by high-velocity niches
HASHTAG_MATRIX = {
    "tech": [
        {"tag": "#AIRevolution", "viral_score": 98, "volume": "2.4M/mo", "competition": "Optimal"},
        {"tag": "#ArtificialIntelligence", "viral_score": 96, "volume": "5.1M/mo", "competition": "High"},
        {"tag": "#TechTrends", "viral_score": 95, "volume": "1.8M/mo", "competition": "Optimal"},
        {"tag": "#MachineLearning", "viral_score": 93, "volume": "3.2M/mo", "competition": "Moderate"},
        {"tag": "#GenerativeAI", "viral_score": 96, "volume": "2.9M/mo", "competition": "High Velocity"},
        {"tag": "#BuildInPublic", "viral_score": 94, "volume": "850K/mo", "competition": "Blue Ocean"},
        {"tag": "#DevCommunity", "viral_score": 91, "volume": "1.2M/mo", "competition": "Optimal"},
        {"tag": "#CyberSecurity", "viral_score": 89, "volume": "950K/mo", "competition": "Moderate"},
        {"tag": "#SaaS", "viral_score": 92, "volume": "1.1M/mo", "competition": "High ROI"}
    ],
    "growth": [
        {"tag": "#GrowthHacking", "viral_score": 97, "volume": "1.6M/mo", "competition": "Optimal"},
        {"tag": "#DigitalMarketing", "viral_score": 94, "volume": "6.8M/mo", "competition": "High"},
        {"tag": "#CreatorEconomy", "viral_score": 96, "volume": "2.1M/mo", "competition": "Breakout"},
        {"tag": "#SocialMediaStrategy", "viral_score": 93, "volume": "1.9M/mo", "competition": "Moderate"},
        {"tag": "#ViralGrowth", "viral_score": 95, "volume": "980K/mo", "competition": "Blue Ocean"},
        {"tag": "#MarketingTips", "viral_score": 92, "volume": "3.4M/mo", "competition": "High"},
        {"tag": "#PersonalBranding", "viral_score": 94, "volume": "1.5M/mo", "competition": "Optimal"}
    ],
    "business": [
        {"tag": "#EntrepreneurLife", "viral_score": 95, "volume": "4.2M/mo", "competition": "High"},
        {"tag": "#StartupGrind", "viral_score": 93, "volume": "1.4M/mo", "competition": "Optimal"},
        {"tag": "#EcommerceTips", "viral_score": 92, "volume": "890K/mo", "competition": "Blue Ocean"},
        {"tag": "#ProductivityHacks", "viral_score": 94, "volume": "1.7M/mo", "competition": "Optimal"},
        {"tag": "#FinTech", "viral_score": 91, "volume": "1.3M/mo", "competition": "Moderate"},
        {"tag": "#OnlineBusiness", "viral_score": 90, "volume": "3.1M/mo", "competition": "High"}
    ],
    "general": [
        {"tag": "#TrendingNow", "viral_score": 96, "volume": "8.5M/mo", "competition": "Peak"},
        {"tag": "#ViralPost", "viral_score": 94, "volume": "4.1M/mo", "competition": "High"},
        {"tag": "#ExplorePage", "viral_score": 93, "volume": "12M/mo", "competition": "Massive"},
        {"tag": "#MindsetShift", "viral_score": 91, "volume": "1.1M/mo", "competition": "Optimal"},
        {"tag": "#DailyInspiration", "viral_score": 89, "volume": "5.3M/mo", "competition": "High"}
    ]
}

def parse_metric_number(val) -> int:
    """Parses strings like '1.2K', '350', '2.5M' into exact integers."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip().upper().replace(",", "")
    if not s:
        return 0
    
    m = re.match(r"^([\d\.]+)\s*([KMB]?)$", s)
    if not m:
        digits = re.findall(r"\d+", s)
        return int("".join(digits)) if digits else 0
    
    num_str, suffix = m.groups()
    try:
        num = float(num_str)
    except ValueError:
        return 0
    
    if suffix == "K":
        return int(num * 1000)
    elif suffix == "M":
        return int(num * 1_000_000)
    elif suffix == "B":
        return int(num * 1_000_000_000)
    return int(num)

def evaluate_post_metrics(
    platform: str,
    metrics: Dict,
    min_likes_threshold: int = None,
    max_comments_saturation: int = 250
) -> Tuple[bool, int, str, Dict]:
    """
    Cracks platform engagement algorithms:
    - Calculates hourly velocity (likes / post age).
    - Checks minimum engagement floor (avoids dead posts with 0-10 likes).
    - Checks comment saturation (avoids posts with 300+ comments where our reply gets buried).
    - Returns: (is_worthy, viral_score, reason, normalized_metrics)
    """
    platform = platform.lower().strip()
    
    likes = parse_metric_number(metrics.get("likes", 0))
    comments = parse_metric_number(metrics.get("comments", metrics.get("replies", 0)))
    views = parse_metric_number(metrics.get("views", metrics.get("impressions", 0)))
    reposts = parse_metric_number(metrics.get("reposts", metrics.get("retweets", 0)))
    hours_old = float(metrics.get("hours_old", 1.0))
    hours_old = max(0.1, hours_old)

    # Set platform-tailored minimum engagement floors
    if min_likes_threshold is None:
        if platform == "twitter":
            min_likes_threshold = 15
        elif platform == "instagram":
            min_likes_threshold = 25
        elif platform == "threads":
            min_likes_threshold = 10
        else:
            min_likes_threshold = 15

    # 1. Floor Filter: Reject dead posts
    if likes < min_likes_threshold and views < 150:
        reason = f"Low engagement floor (Likes: {likes}, Views: {views}) — Below threshold of {min_likes_threshold}."
        return False, 35, reason, {"likes": likes, "comments": comments, "views": views, "velocity": 0}

    # 2. Saturation Filter: Reject oversaturated comment sections
    if comments > max_comments_saturation:
        reason = f"Oversaturated comment section ({comments} comments) — Comment would be deprioritized by algorithm."
        return False, 45, reason, {"likes": likes, "comments": comments, "views": views, "velocity": int(likes / hours_old)}

    # 3. Viral Velocity Calculation
    velocity = likes / hours_old
    if reposts > 0:
        velocity += (reposts * 1.5) / hours_old

    # 4. Viral Index Calculation (0 - 100)
    score = 65

    # Velocity Bonus
    if velocity >= 300:
        score += 22
    elif velocity >= 100:
        score += 16
    elif velocity >= 40:
        score += 10
    elif velocity >= 15:
        score += 5

    # Early Adopter Placement Advantage
    if comments < 30 and velocity >= 25:
        score += 10

    # Views / Impressions Ratio Bonus
    if views > 1000:
        ratio = (likes / views) if views > 0 else 0
        if ratio > 0.05:
            score += 6

    # Saturation Penalty if approaching limit
    if comments > 120:
        score -= 8

    final_score = min(99, max(50, int(score)))

    # Algorithmic decision
    if final_score >= 68:
        is_worthy = True
        reason = f"High viral velocity ({int(velocity)} likes/hr, {comments} replies, {views} views) — Score {final_score}/100."
    else:
        is_worthy = False
        reason = f"Sub-optimal viral score ({final_score}/100, velocity: {int(velocity)} likes/hr)."

    return is_worthy, final_score, reason, {
        "likes": likes,
        "comments": comments,
        "views": views,
        "reposts": reposts,
        "velocity": int(velocity),
        "viral_score": final_score
    }

def get_suggested_hashtags(platform: str = "instagram", topic_or_niche: str = "") -> List[Dict]:
    """
    Returns ranked, algorithm-cracked hashtag suggestions tailored to platform and niche.
    """
    topic = (topic_or_niche or "").lower().strip().replace("#", "")
    
    cluster = "general"
    if any(k in topic for k in ["ai", "tech", "code", "dev", "software", "machine", "cyber", "saas", "data"]):
        cluster = "tech"
    elif any(k in topic for k in ["growth", "market", "social", "viral", "scale", "creator", "brand"]):
        cluster = "growth"
    elif any(k in topic for k in ["biz", "business", "startup", "finance", "money", "shop", "ecommerce", "crypto"]):
        cluster = "business"
    else:
        combined = HASHTAG_MATRIX["tech"][:3] + HASHTAG_MATRIX["growth"][:3] + HASHTAG_MATRIX["business"][:2]
        return sorted(combined, key=lambda x: x["viral_score"], reverse=True)

    results = list(HASHTAG_MATRIX.get(cluster, HASHTAG_MATRIX["general"]))
    
    if len(results) < 6:
        results.extend(HASHTAG_MATRIX["general"][:3])

    return sorted(results, key=lambda x: x["viral_score"], reverse=True)
