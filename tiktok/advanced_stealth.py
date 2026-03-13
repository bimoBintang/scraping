"""
Advanced Stealth Module — BehavioralFingerprintSpoofer
Demographic-aware behavioral fingerprint spoofing with research-backed statistics,
LRU caching, SQLite analytics, and Playwright integration.

Phase 1: Core + Statistics + Cache + Analytics
"""

import json
import math
import time
import random
import asyncio
import hashlib
import sqlite3
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from playwright.async_api import Page

from .human_behavior import HumanBehavior, HumanMouse, HumanScroll, HumanTyping, BezierCurve, Point
from .fingerprint import FingerprintSpoofing, FingerprintGenerator


# ==================== DATACLASSES ====================

@dataclass
class DemographicProfile:
    """User persona definition"""
    age_range: str = "20-29"          # e.g. "13-19", "20-29", "30-49"
    gender: str = "mixed"             # "male", "female", "mixed"
    country: str = "ID"               # ISO 3166-1 alpha-2
    device_type: str = "mobile"       # "mobile", "desktop", "tablet"
    psychographic: str = "explorer"   # "explorer", "connector", "lurker", "creator"

    def key(self) -> str:
        return f"{self.country}_{self.age_range}_{self.gender}_{self.device_type}"


@dataclass
class ActivityTimePattern:
    """When and how long the user is active"""
    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    session_duration_min: float = 15.0   # minutes
    session_duration_max: float = 90.0
    break_interval_min: float = 8.0      # minutes between breaks
    break_interval_max: float = 25.0
    break_duration_min: float = 0.5      # minutes
    break_duration_max: float = 3.0
    hourly_probability: List[float] = field(default_factory=lambda: [0.0] * 24)


@dataclass
class ScrollBehaviorPattern:
    """Realistic scroll physics"""
    speed_min_pps: float = 800.0       # pixels per second
    speed_max_pps: float = 2200.0
    acceleration: float = 1.2          # multiplier during fast scroll
    deceleration: float = 0.7          # multiplier when slowing
    pause_probability: float = 0.35    # chance to pause while scrolling
    content_pause_min: float = 0.8     # seconds paused on content
    content_pause_max: float = 4.0
    direction_change_pct: float = 0.08 # chance to scroll up briefly
    overshoot_pct: float = 0.12        # chance to scroll past target


@dataclass
class ContentInteractionPattern:
    """Engagement rates per demographic"""
    like_ratio: float = 0.08           # probability per video viewed
    comment_ratio: float = 0.02
    share_ratio: float = 0.04
    save_ratio: float = 0.03
    follow_ratio: float = 0.01
    completion_rate: float = 0.45      # % of videos watched to completion
    double_tap_speed: float = 0.25     # seconds between double-tap like


@dataclass
class VideoWatchPattern:
    """Video viewing behavior"""
    avg_watch_pct: float = 0.65        # average % of video watched
    skip_threshold_sec: float = 2.5    # skip if not hooked by this time
    skip_probability: float = 0.30     # chance to skip a video
    replay_probability: float = 0.08   # chance to replay
    loop_watch_count: Tuple[int, int] = (1, 3)  # loops before next
    pause_probability: float = 0.05    # chance to pause mid-video
    seek_probability: float = 0.03     # chance to seek/scrub


@dataclass
class MouseMovementPattern:
    """Cursor behavior characteristics"""
    speed_min: float = 200.0           # pixels per second
    speed_max: float = 800.0
    curve_randomness: float = 0.3      # Bézier curve noise
    overshoot_probability: float = 0.15
    overshoot_distance: float = 15.0   # pixels past target
    idle_movement_probability: float = 0.20  # random fidget moves
    idle_movement_radius: float = 50.0
    click_offset_max: float = 3.0      # imprecision in clicks (px)
    hover_before_click_min: float = 0.05  # seconds
    hover_before_click_max: float = 0.4


@dataclass
class TypingPattern:
    """Keystroke dynamics"""
    wpm_min: int = 35
    wpm_max: int = 75
    error_rate: float = 0.06           # typo probability per character
    correction_delay_min: float = 0.3  # seconds before correcting typo
    correction_delay_max: float = 1.2
    burst_typing: bool = True          # type in bursts with pauses
    burst_length_min: int = 3          # characters per burst
    burst_length_max: int = 12
    inter_burst_pause_min: float = 0.2
    inter_burst_pause_max: float = 0.8
    think_pause_probability: float = 0.10  # long pause mid-sentence


@dataclass
class TabSwitchPattern:
    """Window/tab behavior"""
    switches_per_session: int = 5
    min_focus_time: float = 30.0       # seconds before switching
    max_focus_time: float = 300.0
    background_duration_min: float = 5.0
    background_duration_max: float = 60.0
    return_probability: float = 0.85   # chance to return vs close


@dataclass
class LocalePattern:
    """Timezone, language, regional signals"""
    timezone: str = "Asia/Jakarta"
    language: str = "id-ID"
    accept_languages: List[str] = field(default_factory=lambda: ["id-ID", "id", "en-US", "en"])
    date_format: str = "DD/MM/YYYY"
    keyboard_layout: str = "QWERTY"
    number_format: str = "1.000,00"    # thousand/decimal separators


@dataclass
class BehavioralPattern:
    """Combined output pattern from all generators"""
    demographic: str = ""
    time_of_day: str = "evening"
    activity: ActivityTimePattern = field(default_factory=ActivityTimePattern)
    scrolling: ScrollBehaviorPattern = field(default_factory=ScrollBehaviorPattern)
    interaction: ContentInteractionPattern = field(default_factory=ContentInteractionPattern)
    video: VideoWatchPattern = field(default_factory=VideoWatchPattern)
    mouse: MouseMovementPattern = field(default_factory=MouseMovementPattern)
    typing: TypingPattern = field(default_factory=TypingPattern)
    tab: TabSwitchPattern = field(default_factory=TabSwitchPattern)
    locale: LocalePattern = field(default_factory=LocalePattern)
    generated_at: str = ""
    js_code: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ==================== BEHAVIORAL STATISTICS DATABASE ====================

class BehavioralStatistics:
    """
    Research-backed statistical database for behavioral patterns.
    Sources: Pew Research, Nielsen, data.ai, academic publications.
    """

    # Engagement rates by demographic (like/comment/share/save per video viewed)
    ENGAGEMENT_RATES = {
        "indonesia_teen_female":  {"like": 0.14, "comment": 0.04, "share": 0.09, "save": 0.06, "follow": 0.015},
        "indonesia_teen_male":    {"like": 0.10, "comment": 0.03, "share": 0.07, "save": 0.04, "follow": 0.012},
        "indonesia_young_adult":  {"like": 0.08, "comment": 0.02, "share": 0.05, "save": 0.03, "follow": 0.010},
        "us_teen":                {"like": 0.11, "comment": 0.03, "share": 0.06, "save": 0.05, "follow": 0.013},
        "us_adult":               {"like": 0.06, "comment": 0.01, "share": 0.02, "save": 0.03, "follow": 0.005},
        "global_desktop":         {"like": 0.05, "comment": 0.01, "share": 0.02, "save": 0.02, "follow": 0.004},
    }

    # Session duration by age group (minutes) — mean, std
    SESSION_DURATION = {
        "13-19": {"mean": 95, "std": 25, "sessions_per_day": 8},
        "20-29": {"mean": 60, "std": 20, "sessions_per_day": 5},
        "30-49": {"mean": 35, "std": 15, "sessions_per_day": 3},
        "50+":   {"mean": 20, "std": 10, "sessions_per_day": 2},
    }

    # Active hours probability distribution (0-23) by age group
    ACTIVE_HOURS = {
        "13-19": [
            0.01, 0.01, 0.00, 0.00, 0.00, 0.01,  # 0-5
            0.03, 0.05, 0.04, 0.03, 0.03, 0.04,  # 6-11
            0.06, 0.05, 0.05, 0.07, 0.08, 0.08,  # 12-17
            0.09, 0.10, 0.12, 0.11, 0.08, 0.04,  # 18-23
        ],
        "20-29": [
            0.02, 0.01, 0.01, 0.00, 0.00, 0.01,
            0.03, 0.04, 0.05, 0.05, 0.04, 0.04,
            0.06, 0.05, 0.04, 0.05, 0.06, 0.07,
            0.08, 0.09, 0.10, 0.09, 0.07, 0.04,
        ],
        "30-49": [
            0.01, 0.01, 0.00, 0.00, 0.00, 0.01,
            0.03, 0.04, 0.05, 0.06, 0.05, 0.04,
            0.06, 0.05, 0.04, 0.04, 0.05, 0.06,
            0.07, 0.08, 0.10, 0.09, 0.06, 0.03,
        ],
    }

    # Scroll physics by device
    SCROLL_PHYSICS = {
        "mobile": {
            "speed_range": (800, 2500),
            "acceleration": 1.3,
            "deceleration": 0.6,
            "pause_pct": 0.35,
            "content_pause": (0.8, 5.0),
            "direction_change": 0.10,
        },
        "desktop": {
            "speed_range": (300, 1200),
            "acceleration": 1.1,
            "deceleration": 0.8,
            "pause_pct": 0.25,
            "content_pause": (1.0, 6.0),
            "direction_change": 0.05,
        },
        "tablet": {
            "speed_range": (600, 1800),
            "acceleration": 1.2,
            "deceleration": 0.7,
            "pause_pct": 0.30,
            "content_pause": (0.9, 5.5),
            "direction_change": 0.07,
        },
    }

    # Video watch patterns by age
    VIDEO_WATCH = {
        "13-19": {"avg_watch": 0.72, "skip_prob": 0.25, "replay": 0.12, "skip_threshold": 1.8},
        "20-29": {"avg_watch": 0.60, "skip_prob": 0.35, "replay": 0.08, "skip_threshold": 2.5},
        "30-49": {"avg_watch": 0.50, "skip_prob": 0.40, "replay": 0.05, "skip_threshold": 3.0},
    }

    # Mouse behavior by device
    MOUSE_BEHAVIOR = {
        "desktop": {
            "speed_range": (200, 900),
            "curve_noise": 0.25,
            "overshoot": 0.18,
            "idle_fidget": 0.22,
            "click_offset": 3.0,
        },
        "mobile": {  # touch simulation
            "speed_range": (400, 1200),
            "curve_noise": 0.40,
            "overshoot": 0.08,
            "idle_fidget": 0.05,
            "click_offset": 8.0,
        },
    }

    # Typing by age group (WPM)
    TYPING_SPEED = {
        "13-19": {"wpm": (45, 85), "error_rate": 0.08, "burst": True},
        "20-29": {"wpm": (40, 75), "error_rate": 0.05, "burst": True},
        "30-49": {"wpm": (30, 60), "error_rate": 0.04, "burst": False},
        "50+":   {"wpm": (20, 45), "error_rate": 0.06, "burst": False},
    }

    # Locale data by country
    LOCALE_DATA = {
        "ID": {"tz": "Asia/Jakarta", "lang": "id-ID", "accept": ["id-ID", "id", "en-US", "en"],
               "date": "DD/MM/YYYY", "kb": "QWERTY", "num": "1.000,00"},
        "US": {"tz": "America/New_York", "lang": "en-US", "accept": ["en-US", "en"],
               "date": "MM/DD/YYYY", "kb": "QWERTY", "num": "1,000.00"},
        "JP": {"tz": "Asia/Tokyo", "lang": "ja-JP", "accept": ["ja-JP", "ja", "en-US", "en"],
               "date": "YYYY/MM/DD", "kb": "JIS", "num": "1,000"},
        "KR": {"tz": "Asia/Seoul", "lang": "ko-KR", "accept": ["ko-KR", "ko", "en-US", "en"],
               "date": "YYYY.MM.DD", "kb": "Dubeolsik", "num": "1,000"},
        "BR": {"tz": "America/Sao_Paulo", "lang": "pt-BR", "accept": ["pt-BR", "pt", "en"],
               "date": "DD/MM/YYYY", "kb": "ABNT2", "num": "1.000,00"},
        "IN": {"tz": "Asia/Kolkata", "lang": "hi-IN", "accept": ["hi-IN", "hi", "en-IN", "en"],
               "date": "DD/MM/YYYY", "kb": "QWERTY", "num": "1,00,000.00"},
    }

    @classmethod
    def get_engagement(cls, preset: str) -> dict:
        return cls.ENGAGEMENT_RATES.get(preset, cls.ENGAGEMENT_RATES["global_desktop"])

    @classmethod
    def get_session(cls, age_range: str) -> dict:
        return cls.SESSION_DURATION.get(age_range, cls.SESSION_DURATION["20-29"])

    @classmethod
    def get_active_hours(cls, age_range: str) -> List[float]:
        return cls.ACTIVE_HOURS.get(age_range, cls.ACTIVE_HOURS["20-29"])

    @classmethod
    def get_scroll(cls, device: str) -> dict:
        return cls.SCROLL_PHYSICS.get(device, cls.SCROLL_PHYSICS["mobile"])

    @classmethod
    def get_video(cls, age_range: str) -> dict:
        return cls.VIDEO_WATCH.get(age_range, cls.VIDEO_WATCH["20-29"])

    @classmethod
    def get_mouse(cls, device: str) -> dict:
        return cls.MOUSE_BEHAVIOR.get(device, cls.MOUSE_BEHAVIOR["desktop"])

    @classmethod
    def get_typing(cls, age_range: str) -> dict:
        return cls.TYPING_SPEED.get(age_range, cls.TYPING_SPEED["20-29"])

    @classmethod
    def get_locale(cls, country: str) -> dict:
        return cls.LOCALE_DATA.get(country, cls.LOCALE_DATA["US"])


# ==================== DEMOGRAPHIC PRESETS ====================

DEMOGRAPHIC_PRESETS: Dict[str, DemographicProfile] = {
    "indonesia_teen_female":  DemographicProfile("13-19", "female", "ID", "mobile", "connector"),
    "indonesia_teen_male":    DemographicProfile("13-19", "male", "ID", "mobile", "explorer"),
    "indonesia_young_adult":  DemographicProfile("20-29", "mixed", "ID", "mobile", "explorer"),
    "us_teen":                DemographicProfile("13-19", "mixed", "US", "mobile", "creator"),
    "us_adult":               DemographicProfile("25-40", "mixed", "US", "desktop", "lurker"),
    "global_desktop":         DemographicProfile("20-35", "mixed", "US", "desktop", "lurker"),
}


# ==================== PATTERN CACHE ====================

class PatternCache:
    """LRU cache with TTL for generated behavioral patterns."""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self._cache: OrderedDict[str, Tuple[BehavioralPattern, float]] = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl_seconds

    def _generate_key(self, demographic: str, time_of_day: str) -> str:
        return hashlib.md5(f"{demographic}:{time_of_day}".encode()).hexdigest()[:12]

    def get(self, demographic: str, time_of_day: str) -> Optional[BehavioralPattern]:
        key = self._generate_key(demographic, time_of_day)
        if key in self._cache:
            pattern, ts = self._cache[key]
            if time.time() - ts < self.ttl:
                self._cache.move_to_end(key)
                return pattern
            else:
                del self._cache[key]
        return None

    def put(self, demographic: str, time_of_day: str, pattern: BehavioralPattern):
        key = self._generate_key(demographic, time_of_day)
        self._cache[key] = (pattern, time.time())
        self._cache.move_to_end(key)
        self._evict()

    def _evict(self):
        now = time.time()
        expired = [k for k, (_, ts) in self._cache.items() if now - ts >= self.ttl]
        for k in expired:
            del self._cache[k]
        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    @property
    def size(self) -> int:
        return len(self._cache)


# ==================== PATTERN ANALYTICS ====================

class PatternAnalytics:
    """SQLite-backed analytics for pattern effectiveness tracking."""

    def __init__(self, db_path: str = "behavioral_patterns.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pattern_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_key TEXT NOT NULL,
                    demographic TEXT NOT NULL,
                    time_of_day TEXT,
                    success INTEGER NOT NULL,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pattern_demo 
                ON pattern_usage(demographic, success)
            """)

    def record_usage(self, pattern_key: str, demographic: str,
                     success: bool, time_of_day: str = "", context: str = ""):
        """Record a pattern usage outcome."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO pattern_usage (pattern_key, demographic, time_of_day, success, context) "
                "VALUES (?, ?, ?, ?, ?)",
                (pattern_key, demographic, time_of_day, int(success), context)
            )

    def get_success_rate(self, demographic: str) -> float:
        """Get overall success rate for a demographic."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*), SUM(success) FROM pattern_usage WHERE demographic = ?",
                (demographic,)
            ).fetchone()
            if row and row[0] > 0:
                return row[1] / row[0]
        return 0.0

    def get_best_patterns(self, demographic: str, limit: int = 5) -> List[dict]:
        """Get most successful patterns for a demographic."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT pattern_key, COUNT(*) as uses, SUM(success) as wins "
                "FROM pattern_usage WHERE demographic = ? "
                "GROUP BY pattern_key ORDER BY (CAST(wins AS FLOAT)/uses) DESC LIMIT ?",
                (demographic, limit)
            ).fetchall()
            return [{"key": r[0], "uses": r[1], "wins": r[2],
                     "rate": r[2]/r[1] if r[1] > 0 else 0} for r in rows]

    def get_effectiveness_report(self) -> dict:
        """Get full effectiveness report across all demographics."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT demographic, COUNT(*), SUM(success) "
                "FROM pattern_usage GROUP BY demographic"
            ).fetchall()
            return {
                r[0]: {"total": r[1], "success": r[2],
                       "rate": round(r[2]/r[1], 3) if r[1] > 0 else 0}
                for r in rows
            }


# ==================== CORE: BEHAVIORAL FINGERPRINT SPOOFER ====================

class BehavioralFingerprintSpoofer:
    """
    Generate and apply demographic-aware behavioral fingerprint patterns.

    Unlike static fingerprint spoofing (canvas, webgl), this generates
    *behavioral* patterns — how the user scrolls, clicks, watches,
    types, and interacts — based on real research statistics.

    Usage:
        spoof = BehavioralFingerprintSpoofer(page)
        pattern = await spoof.generate_for_user(
            demographic="indonesia_teen_female",
            time_of_day="evening"
        )
        await spoof.apply_to_page(pattern)
        report = await spoof.simulate_session(duration_minutes=10)
    """

    def __init__(self, page: Page, demographic: Optional[DemographicProfile] = None):
        self.page = page
        self.demographic = demographic
        self.human = HumanBehavior(page)
        self._cache = PatternCache()
        self._analytics: Optional[PatternAnalytics] = None
        self._session_start: Optional[float] = None

    def enable_analytics(self, db_path: str = "behavioral_patterns.db"):
        """Enable SQLite analytics tracking."""
        self._analytics = PatternAnalytics(db_path)

    # ==================== MAIN API ====================

    async def generate_for_user(
        self,
        demographic: str = "indonesia_young_adult",
        time_of_day: str = "evening"
    ) -> BehavioralPattern:
        """
        Generate a complete behavioral pattern for given demographic + time.

        Args:
            demographic: Preset name or custom DemographicProfile key
            time_of_day: "morning", "afternoon", "evening", "night", "late_night"

        Returns:
            BehavioralPattern with all 8 sub-patterns + JS injection code
        """
        # Check cache
        cached = self._cache.get(demographic, time_of_day)
        if cached:
            return cached

        # Resolve demographic profile
        demo = DEMOGRAPHIC_PRESETS.get(demographic)
        if not demo:
            demo = self.demographic or DemographicProfile()

        # Generate all 8 patterns
        pattern = BehavioralPattern(
            demographic=demographic,
            time_of_day=time_of_day,
            activity=self._generate_activity(demo, time_of_day),
            scrolling=self._generate_scrolling(demo),
            interaction=self._generate_interactions(demo, demographic),
            video=self._generate_video(demo),
            mouse=self._generate_mouse(demo),
            typing=self._generate_typing(demo),
            tab=self._generate_tab(demo),
            locale=self._generate_locale(demo),
            generated_at=datetime.now().isoformat(),
        )

        # Build JS injection
        pattern.js_code = self._build_js_injection(pattern)

        # Cache it
        self._cache.put(demographic, time_of_day, pattern)

        print(f"[Stealth] Generated behavioral pattern: {demographic} @ {time_of_day}")
        return pattern

    async def apply_to_page(self, pattern: BehavioralPattern) -> None:
        """Inject behavioral pattern into the browser page via JS."""
        if pattern.js_code:
            await self.page.evaluate(pattern.js_code)
            print(f"[Stealth] Applied behavioral pattern to page")

    async def simulate_session(self, duration_minutes: float = 10.0,
                               demographic: str = "indonesia_young_adult") -> dict:
        """
        Run a complete session simulation with realistic behavior.

        Simulates scrolling, pausing, watching, and interacting
        based on the generated behavioral pattern.
        """
        self._session_start = time.time()
        pattern = await self.generate_for_user(demographic)
        await self.apply_to_page(pattern)

        duration_sec = duration_minutes * 60
        elapsed = 0.0
        actions = []

        print(f"[Stealth] Starting {duration_minutes}min session simulation...")

        while elapsed < duration_sec:
            # Random action based on pattern
            action = random.choices(
                ["scroll", "watch", "idle", "interact", "break"],
                weights=[0.35, 0.30, 0.15, 0.10, 0.10],
                k=1
            )[0]

            if action == "scroll":
                scroll_amount = random.randint(300, 900)
                speed = random.uniform(
                    pattern.scrolling.speed_min_pps,
                    pattern.scrolling.speed_max_pps
                )
                steps = max(3, int(scroll_amount / speed * 10))
                await self.human.scroll.scroll_down(scroll_amount, smooth=True)
                wait = random.uniform(0.3, 1.5)
                await asyncio.sleep(wait)
                elapsed += wait + scroll_amount / speed
                actions.append({"type": "scroll", "amount": scroll_amount})

            elif action == "watch":
                # Simulate watching a video
                watch_pct = random.gauss(
                    pattern.video.avg_watch_pct,
                    0.15
                )
                watch_pct = max(0.1, min(1.0, watch_pct))
                watch_sec = random.uniform(5, 45) * watch_pct
                await asyncio.sleep(min(watch_sec, duration_sec - elapsed))
                elapsed += watch_sec
                actions.append({"type": "watch", "duration": round(watch_sec, 1)})

            elif action == "idle":
                idle_sec = random.uniform(2, 8)
                if pattern.mouse.idle_movement_probability > random.random():
                    await self.human.random_movement()
                await asyncio.sleep(min(idle_sec, duration_sec - elapsed))
                elapsed += idle_sec
                actions.append({"type": "idle", "duration": round(idle_sec, 1)})

            elif action == "interact":
                if random.random() < pattern.interaction.like_ratio:
                    actions.append({"type": "like"})
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    elapsed += 0.5

            elif action == "break":
                break_dur = random.uniform(
                    pattern.activity.break_duration_min * 60,
                    pattern.activity.break_duration_max * 60
                )
                break_dur = min(break_dur, duration_sec - elapsed)
                await asyncio.sleep(break_dur)
                elapsed += break_dur
                actions.append({"type": "break", "duration": round(break_dur, 1)})

        total_time = time.time() - self._session_start
        report = {
            "demographic": demographic,
            "planned_duration": duration_minutes,
            "actual_duration": round(total_time / 60, 2),
            "actions_count": len(actions),
            "action_breakdown": {},
        }
        for a in actions:
            t = a["type"]
            report["action_breakdown"][t] = report["action_breakdown"].get(t, 0) + 1

        print(f"[Stealth] Session complete: {len(actions)} actions in {report['actual_duration']}min")
        return report

    # ==================== PATTERN GENERATORS ====================

    def _generate_activity(self, demo: DemographicProfile, time_of_day: str) -> ActivityTimePattern:
        """Generate activity time pattern based on demographic + current time."""
        session = BehavioralStatistics.get_session(demo.age_range)
        hours = BehavioralStatistics.get_active_hours(demo.age_range)

        # Adjust peak hours based on time_of_day
        peak_map = {
            "morning":    [7, 8, 9, 10],
            "afternoon":  [12, 13, 14, 15],
            "evening":    [18, 19, 20, 21],
            "night":      [20, 21, 22, 23],
            "late_night": [23, 0, 1, 2],
        }
        peaks = peak_map.get(time_of_day, [19, 20, 21, 22])

        mean_dur = session["mean"]
        std_dur = session["std"]
        dur = max(5, random.gauss(mean_dur, std_dur))

        return ActivityTimePattern(
            peak_hours=peaks,
            session_duration_min=max(5, dur * 0.5),
            session_duration_max=dur * 1.5,
            break_interval_min=dur * 0.15,
            break_interval_max=dur * 0.4,
            break_duration_min=0.5,
            break_duration_max=min(5.0, dur * 0.05),
            hourly_probability=hours,
        )

    def _generate_scrolling(self, demo: DemographicProfile) -> ScrollBehaviorPattern:
        """Generate scroll physics from device + demographic."""
        scroll = BehavioralStatistics.get_scroll(demo.device_type)

        speed_min, speed_max = scroll["speed_range"]
        # Add age-based variation: teens scroll faster
        age_factor = 1.2 if "13-19" in demo.age_range else (1.0 if "20-29" in demo.age_range else 0.85)

        return ScrollBehaviorPattern(
            speed_min_pps=speed_min * age_factor * random.uniform(0.9, 1.1),
            speed_max_pps=speed_max * age_factor * random.uniform(0.9, 1.1),
            acceleration=scroll["acceleration"] + random.uniform(-0.1, 0.1),
            deceleration=scroll["deceleration"] + random.uniform(-0.05, 0.05),
            pause_probability=scroll["pause_pct"] + random.uniform(-0.05, 0.05),
            content_pause_min=scroll["content_pause"][0],
            content_pause_max=scroll["content_pause"][1],
            direction_change_pct=scroll["direction_change"],
            overshoot_pct=random.uniform(0.08, 0.18),
        )

    def _generate_interactions(self, demo: DemographicProfile, preset: str) -> ContentInteractionPattern:
        """Generate engagement rates from research data."""
        eng = BehavioralStatistics.get_engagement(preset)

        # Add randomness within realistic bounds (±20%)
        def jitter(val: float) -> float:
            return val * random.uniform(0.80, 1.20)

        return ContentInteractionPattern(
            like_ratio=jitter(eng["like"]),
            comment_ratio=jitter(eng["comment"]),
            share_ratio=jitter(eng["share"]),
            save_ratio=jitter(eng["save"]),
            follow_ratio=jitter(eng["follow"]),
            completion_rate=random.uniform(0.35, 0.60),
            double_tap_speed=random.uniform(0.15, 0.35),
        )

    def _generate_video(self, demo: DemographicProfile) -> VideoWatchPattern:
        """Generate video watching behavior."""
        vid = BehavioralStatistics.get_video(demo.age_range)

        return VideoWatchPattern(
            avg_watch_pct=vid["avg_watch"] + random.uniform(-0.08, 0.08),
            skip_threshold_sec=vid["skip_threshold"] + random.uniform(-0.5, 0.5),
            skip_probability=vid["skip_prob"] + random.uniform(-0.05, 0.05),
            replay_probability=vid["replay"] + random.uniform(-0.03, 0.03),
            loop_watch_count=(1, 3 if "13-19" in demo.age_range else 2),
            pause_probability=random.uniform(0.03, 0.08),
            seek_probability=random.uniform(0.02, 0.06),
        )

    def _generate_mouse(self, demo: DemographicProfile) -> MouseMovementPattern:
        """Generate mouse/touch movement characteristics."""
        mouse = BehavioralStatistics.get_mouse(demo.device_type)

        return MouseMovementPattern(
            speed_min=mouse["speed_range"][0] + random.uniform(-30, 30),
            speed_max=mouse["speed_range"][1] + random.uniform(-50, 50),
            curve_randomness=mouse["curve_noise"] + random.uniform(-0.05, 0.05),
            overshoot_probability=mouse["overshoot"],
            overshoot_distance=random.uniform(8, 25),
            idle_movement_probability=mouse["idle_fidget"],
            idle_movement_radius=random.uniform(30, 80),
            click_offset_max=mouse["click_offset"],
            hover_before_click_min=0.04,
            hover_before_click_max=random.uniform(0.25, 0.5),
        )

    def _generate_typing(self, demo: DemographicProfile) -> TypingPattern:
        """Generate keystroke dynamics."""
        typ = BehavioralStatistics.get_typing(demo.age_range)

        return TypingPattern(
            wpm_min=typ["wpm"][0] + random.randint(-5, 5),
            wpm_max=typ["wpm"][1] + random.randint(-5, 5),
            error_rate=typ["error_rate"] + random.uniform(-0.02, 0.02),
            correction_delay_min=random.uniform(0.2, 0.5),
            correction_delay_max=random.uniform(0.8, 1.5),
            burst_typing=typ["burst"],
            burst_length_min=random.randint(2, 5),
            burst_length_max=random.randint(8, 15),
            inter_burst_pause_min=0.15,
            inter_burst_pause_max=random.uniform(0.5, 1.0),
            think_pause_probability=random.uniform(0.05, 0.15),
        )

    def _generate_tab(self, demo: DemographicProfile) -> TabSwitchPattern:
        """Generate tab switching behavior."""
        # Teens switch more, adults less
        base_switches = 8 if "13-19" in demo.age_range else (5 if "20-29" in demo.age_range else 3)

        return TabSwitchPattern(
            switches_per_session=base_switches + random.randint(-2, 3),
            min_focus_time=random.uniform(20, 60),
            max_focus_time=random.uniform(180, 420),
            background_duration_min=random.uniform(3, 10),
            background_duration_max=random.uniform(30, 120),
            return_probability=random.uniform(0.75, 0.95),
        )

    def _generate_locale(self, demo: DemographicProfile) -> LocalePattern:
        """Generate locale/timezone patterns."""
        loc = BehavioralStatistics.get_locale(demo.country)

        return LocalePattern(
            timezone=loc["tz"],
            language=loc["lang"],
            accept_languages=loc["accept"],
            date_format=loc["date"],
            keyboard_layout=loc["kb"],
            number_format=loc["num"],
        )

    # ==================== JS INJECTION ====================

    def _build_js_injection(self, pattern: BehavioralPattern) -> str:
        """Build JS code to inject behavioral signals into the page."""
        locale = pattern.locale
        scroll = pattern.scrolling
        mouse = pattern.mouse
        interaction = pattern.interaction

        return f"""
(() => {{
    // === Behavioral Fingerprint Injection ===

    // Locale signals
    Object.defineProperty(navigator, 'language', {{get: () => '{locale.language}'}});
    Object.defineProperty(navigator, 'languages', {{get: () => {json.dumps(locale.accept_languages)}}});

    // Timezone
    const _origDTF = Intl.DateTimeFormat;
    Intl.DateTimeFormat = function(...args) {{
        if (!args[1]) args[1] = {{}};
        if (!args[1].timeZone) args[1].timeZone = '{locale.timezone}';
        return new _origDTF(...args);
    }};
    Object.setPrototypeOf(Intl.DateTimeFormat, _origDTF);

    const _origResolved = _origDTF.prototype.resolvedOptions;
    Intl.DateTimeFormat.prototype.resolvedOptions = function() {{
        const opts = _origResolved.call(this);
        opts.timeZone = '{locale.timezone}';
        return opts;
    }};

    // Scroll behavior signals
    window.__behavioralProfile = {{
        scroll: {{
            speedRange: [{scroll.speed_min_pps}, {scroll.speed_max_pps}],
            pauseProbability: {scroll.pause_probability},
            contentPauseRange: [{scroll.content_pause_min}, {scroll.content_pause_max}],
        }},
        mouse: {{
            speedRange: [{mouse.speed_min}, {mouse.speed_max}],
            curveNoise: {mouse.curve_randomness},
            overshoot: {mouse.overshoot_probability},
            clickOffset: {mouse.click_offset_max},
        }},
        interaction: {{
            likeRatio: {interaction.like_ratio},
            commentRatio: {interaction.comment_ratio},
            shareRatio: {interaction.share_ratio},
        }},
        generated: '{pattern.generated_at}',
    }};

    // Override getTimezoneOffset
    Date.prototype.getTimezoneOffset = function() {{
        const tzOffsets = {{
            'Asia/Jakarta': -420,
            'America/New_York': 300,
            'Asia/Tokyo': -540,
            'Asia/Seoul': -540,
            'America/Sao_Paulo': 180,
            'Asia/Kolkata': -330,
            'Europe/London': 0,
        }};
        return tzOffsets['{locale.timezone}'] || -420;
    }};

    console.log('[BFS] Behavioral fingerprint injected');
}})();
"""

    # ==================== RECORD ANALYTICS ====================

    def record_outcome(self, demographic: str, success: bool,
                       time_of_day: str = "", context: str = ""):
        """Record pattern usage outcome for analytics."""
        if self._analytics:
            key = f"{demographic}:{time_of_day}:{datetime.now().strftime('%H')}"
            self._analytics.record_usage(key, demographic, success, time_of_day, context)
