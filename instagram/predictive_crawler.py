"""
Predictive Crawling Berdasarkan Posting Pattern — Algorithm 7

Menganalisis pola temporal postingan historis user untuk memprediksi
kapan mereka akan posting lagi. Scraper hanya crawl pada window waktu
probabilitas tinggi → hemat resource + kurangi risiko detection.

Usage:
    from instagram.predictive_crawler import PatternAnalyzer, CrawlScheduler
    
    # Analyze posting pattern
    analyzer = PatternAnalyzer()
    pattern = analyzer.analyze(posts)
    
    # Check if now is a good time to crawl
    scheduler = CrawlScheduler()
    if scheduler.should_crawl_now(pattern):
        # Execute scraping
        ...
    
    # Get next optimal crawl time
    next_time = scheduler.get_next_crawl_time(pattern)
    
    # Generate 24-hour schedule
    schedule = scheduler.generate_schedule(pattern, hours_ahead=24)
"""

import json
import math
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median, stdev
from typing import Dict, List, Optional, Tuple

from .models import InstagramPost


# ==================== CONSTANTS ====================

# Regularity thresholds
REGULARITY_HIGH = 0.6     # Very predictable poster
REGULARITY_MED = 0.3      # Semi-regular
# Below 0.3 = random poster

# Hot window detection
HOT_WINDOW_SIGMA = 0.5    # Mean + 0.5*stddev to count as "hot"
MIN_POSTS_FOR_ANALYSIS = 5  # Need at least this many posts

# Default crawl intervals for random posters (hours)
DEFAULT_INTERVAL_HOURS = 6
MAX_INTERVAL_HOURS = 24
MIN_INTERVAL_HOURS = 1

# Cache settings
PATTERN_CACHE_TTL_HOURS = 48  # Re-analyze every 48 hours


# ==================== POSTING PATTERN ====================

@dataclass
class PostingPattern:
    """Temporal posting pattern for a single user"""
    username: str
    
    # Histograms (probabilities, sum to ~1.0)
    hourly_histogram: List[float] = field(default_factory=lambda: [0.0] * 24)
    daily_histogram: List[float] = field(default_factory=lambda: [0.0] * 7)
    
    # Raw counts for display
    hourly_counts: List[int] = field(default_factory=lambda: [0] * 24)
    daily_counts: List[int] = field(default_factory=lambda: [0] * 7)
    
    # Interval stats (hours)
    avg_interval_hours: float = 0.0
    median_interval_hours: float = 0.0
    stddev_interval_hours: float = 0.0
    
    # Analysis results
    regularity_score: float = 0.0    # 0 = random, 1 = predictable
    hot_hours: List[int] = field(default_factory=list)   # e.g., [9, 15, 21]
    hot_days: List[int] = field(default_factory=list)     # 0=Mon, 6=Sun
    
    # Predictions
    next_predicted: Optional[float] = None  # Unix timestamp
    last_post_time: Optional[float] = None
    
    # Metadata
    total_posts_analyzed: int = 0
    analyzed_at: float = 0.0
    
    @property
    def user_type(self) -> str:
        if self.regularity_score >= REGULARITY_HIGH:
            return "regular"
        elif self.regularity_score >= REGULARITY_MED:
            return "semi-regular"
        return "random"
    
    @property
    def peak_hour(self) -> int:
        if not self.hourly_histogram:
            return 12
        return self.hourly_histogram.index(max(self.hourly_histogram))
    
    @property
    def peak_day(self) -> int:
        if not self.daily_histogram:
            return 0
        return self.daily_histogram.index(max(self.daily_histogram))
    
    @property
    def peak_day_name(self) -> str:
        days = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
        return days[self.peak_day]
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['user_type'] = self.user_type
        d['peak_hour'] = self.peak_hour
        d['peak_day_name'] = self.peak_day_name
        return d
    
    def print_pattern(self):
        """Print visual posting pattern"""
        days = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min']
        
        print(f"""
╔══════════════════════════════════════════════════╗
║   📊 Posting Pattern: @{self.username:<24}║
╠══════════════════════════════════════════════════╣
║  Type:         {self.user_type:<35}║
║  Regularity:   {self.regularity_score:.0%} {'█' * int(self.regularity_score * 20)}{'░' * (20 - int(self.regularity_score * 20)):<20}║
║  Posts:         {self.total_posts_analyzed:<34}║
║  Avg Interval: {self.avg_interval_hours:.1f}h (±{self.stddev_interval_hours:.1f}h)             ║
║  Peak Hour:    {self.peak_hour:02d}:00                              ║
║  Peak Day:     {self.peak_day_name:<35}║
╠══════════════════════════════════════════════════╣""")
        
        # Hourly heatmap
        print("║  Hourly Pattern (24h):                           ║")
        max_h = max(self.hourly_histogram) if max(self.hourly_histogram) > 0 else 1
        for row in range(4, -1, -1):
            line = "║  "
            for h in range(24):
                level = int((self.hourly_histogram[h] / max_h) * 4)
                if level >= row:
                    line += "█"
                else:
                    line += " "
            hot = " ← hot" if row == 4 else ""
            print(f"{line}  {hot:<20}║")
        print(f"║  {''.join(f'{h%10}' for h in range(24))}  (hour)              ║")
        
        # Hot windows
        if self.hot_hours:
            hot_str = ', '.join(f'{h:02d}:00' for h in sorted(self.hot_hours))
            print(f"║  🔥 Hot hours: {hot_str:<34}║")
        if self.hot_days:
            hot_days_str = ', '.join(days[d] for d in sorted(self.hot_days))
            print(f"║  🔥 Hot days:  {hot_days_str:<34}║")
        
        # Prediction
        if self.next_predicted:
            pred_dt = datetime.fromtimestamp(self.next_predicted)
            print(f"║  🎯 Next post: ~{pred_dt.strftime('%Y-%m-%d %H:%M'):<32}║")
        
        print("╚══════════════════════════════════════════════════╝")


# ==================== PATTERN ANALYZER ====================

class PatternAnalyzer:
    """
    Analyze temporal posting patterns from historical post data.
    
    Extracts hourly/daily histograms, calculates regularity score
    via normalized entropy, and identifies hot posting windows.
    """
    
    def analyze(self, posts: List[InstagramPost], username: str = "") -> PostingPattern:
        """
        Analyze a list of posts and return the posting pattern.
        
        Args:
            posts: List of InstagramPost with timestamps
            username: Instagram username
            
        Returns:
            PostingPattern with histograms, regularity, and predictions
        """
        pattern = PostingPattern(username=username)
        
        # Filter posts with valid timestamps
        valid_posts = [p for p in posts if p.timestamp > 0]
        
        if len(valid_posts) < MIN_POSTS_FOR_ANALYSIS:
            print(f"  [!] Not enough posts for analysis ({len(valid_posts)}/{MIN_POSTS_FOR_ANALYSIS})")
            pattern.regularity_score = 0.0
            pattern.avg_interval_hours = DEFAULT_INTERVAL_HOURS
            pattern.total_posts_analyzed = len(valid_posts)
            return pattern
        
        # Sort by timestamp (oldest first)
        valid_posts.sort(key=lambda p: p.timestamp)
        
        # Build histograms
        hourly_counts, hourly_hist = self._build_hourly_histogram(valid_posts)
        daily_counts, daily_hist = self._build_daily_histogram(valid_posts)
        
        # Calculate intervals
        intervals = self._calculate_intervals(valid_posts)
        avg_interval = sum(intervals) / len(intervals) if intervals else DEFAULT_INTERVAL_HOURS
        med_interval = median(intervals) if intervals else DEFAULT_INTERVAL_HOURS
        std_interval = stdev(intervals) if len(intervals) > 1 else 0.0
        
        # Regularity score
        regularity = self._calculate_regularity(hourly_hist, daily_hist, intervals)
        
        # Hot windows
        hot_hours = self._find_hot_windows(hourly_hist)
        hot_days = self._find_hot_windows(daily_hist)
        
        # Predict next post
        last_ts = valid_posts[-1].timestamp
        next_predicted = self._predict_next_post(
            last_ts, med_interval, hot_hours, hourly_hist
        )
        
        # Build pattern
        pattern.hourly_histogram = hourly_hist
        pattern.daily_histogram = daily_hist
        pattern.hourly_counts = hourly_counts
        pattern.daily_counts = daily_counts
        pattern.avg_interval_hours = avg_interval
        pattern.median_interval_hours = med_interval
        pattern.stddev_interval_hours = std_interval
        pattern.regularity_score = regularity
        pattern.hot_hours = hot_hours
        pattern.hot_days = hot_days
        pattern.next_predicted = next_predicted
        pattern.last_post_time = last_ts
        pattern.total_posts_analyzed = len(valid_posts)
        pattern.analyzed_at = time.time()
        
        return pattern
    
    def _build_hourly_histogram(self, posts: List[InstagramPost]) -> Tuple[List[int], List[float]]:
        """Build 24-bin histogram of posting hours"""
        counts = [0] * 24
        for post in posts:
            dt = datetime.fromtimestamp(post.timestamp)
            counts[dt.hour] += 1
        
        total = sum(counts)
        hist = [c / total for c in counts] if total > 0 else [0.0] * 24
        return counts, hist
    
    def _build_daily_histogram(self, posts: List[InstagramPost]) -> Tuple[List[int], List[float]]:
        """Build 7-bin histogram of posting days (0=Monday)"""
        counts = [0] * 7
        for post in posts:
            dt = datetime.fromtimestamp(post.timestamp)
            counts[dt.weekday()] += 1
        
        total = sum(counts)
        hist = [c / total for c in counts] if total > 0 else [0.0] * 7
        return counts, hist
    
    def _calculate_intervals(self, posts: List[InstagramPost]) -> List[float]:
        """Calculate intervals between consecutive posts (in hours)"""
        intervals = []
        for i in range(1, len(posts)):
            delta = posts[i].timestamp - posts[i - 1].timestamp
            hours = delta / 3600.0
            if hours > 0:
                intervals.append(hours)
        return intervals
    
    def _calculate_regularity(
        self,
        hourly_hist: List[float],
        daily_hist: List[float],
        intervals: List[float],
    ) -> float:
        """
        Calculate regularity score (0=random, 1=predictable).
        
        Uses normalized Shannon entropy — lower entropy means more
        concentrated (predictable) posting pattern.
        
        Components:
        - Hourly entropy (weight 0.50): how concentrated in specific hours
        - Interval consistency (weight 0.35): coefficient of variation
        - Daily entropy (weight 0.15): how concentrated in specific days
        
        Hourly concentration dominates because a user posting at the same
        hours daily is highly predictable even if they post every day.
        """
        # Hourly entropy (max = log2(24) ≈ 4.585)
        h_entropy = self._shannon_entropy(hourly_hist)
        max_h_entropy = math.log2(24)
        hourly_regularity = 1.0 - (h_entropy / max_h_entropy) if max_h_entropy > 0 else 0
        
        # Daily entropy (max = log2(7) ≈ 2.807)
        d_entropy = self._shannon_entropy(daily_hist)
        max_d_entropy = math.log2(7)
        daily_regularity = 1.0 - (d_entropy / max_d_entropy) if max_d_entropy > 0 else 0
        
        # Interval consistency (coefficient of variation)
        if intervals and len(intervals) > 1:
            mean_int = sum(intervals) / len(intervals)
            std_int = stdev(intervals)
            cv = std_int / mean_int if mean_int > 0 else 1.0
            interval_regularity = max(0.0, 1.0 - min(cv, 2.0) / 2.0)
        else:
            interval_regularity = 0.0
        
        # Weighted combination
        score = (
            0.50 * hourly_regularity +
            0.35 * interval_regularity +
            0.15 * daily_regularity
        )
        
        return round(min(1.0, max(0.0, score)), 3)
    
    @staticmethod
    def _shannon_entropy(probabilities: List[float]) -> float:
        """Calculate Shannon entropy of a probability distribution"""
        entropy = 0.0
        for p in probabilities:
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy
    
    def _find_hot_windows(self, histogram: List[float]) -> List[int]:
        """Find bins above mean + HOT_WINDOW_SIGMA * stddev"""
        if not histogram or max(histogram) == 0:
            return []
        
        non_zero = [v for v in histogram if v > 0]
        if not non_zero:
            return []
        
        mean_val = sum(histogram) / len(histogram)
        
        if len(non_zero) > 1:
            variance = sum((v - mean_val) ** 2 for v in histogram) / len(histogram)
            std_val = math.sqrt(variance)
        else:
            std_val = 0.0
        
        threshold = mean_val + HOT_WINDOW_SIGMA * std_val
        
        return [i for i, v in enumerate(histogram) if v >= threshold]
    
    def _predict_next_post(
        self,
        last_ts: float,
        median_interval: float,
        hot_hours: List[int],
        hourly_hist: List[float],
    ) -> float:
        """
        Predict the next posting time.
        
        Strategy:
        1. Start from last_post + median_interval
        2. Snap to nearest hot hour if available
        3. If result is in the past, advance to next hot window
        """
        # Base prediction: last post + median interval
        base_prediction = last_ts + (median_interval * 3600)
        pred_dt = datetime.fromtimestamp(base_prediction)
        now = datetime.now()
        
        if not hot_hours:
            # No hot hours — just use interval
            if pred_dt < now:
                # If prediction is in the past, use now + interval
                return time.time() + (median_interval * 3600)
            return base_prediction
        
        # Snap to nearest hot hour
        pred_hour = pred_dt.hour
        
        # Find closest hot hour on or after pred_hour
        future_hot = [h for h in hot_hours if h >= pred_hour]
        if future_hot:
            snap_hour = future_hot[0]
        else:
            # Wrap to next day's first hot hour
            snap_hour = hot_hours[0]
            pred_dt += timedelta(days=1)
        
        # Apply snapped hour
        snapped = pred_dt.replace(
            hour=snap_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        
        # If snapped time is in the past, advance to next occurrence
        if snapped < now:
            # Find next hot hour from current time
            current_hour = now.hour
            future_hot_now = [h for h in sorted(hot_hours) if h > current_hour]
            if future_hot_now:
                snapped = now.replace(
                    hour=future_hot_now[0], minute=0, second=0, microsecond=0
                )
            else:
                # Tomorrow's first hot hour
                snapped = (now + timedelta(days=1)).replace(
                    hour=sorted(hot_hours)[0], minute=0, second=0, microsecond=0
                )
        
        return snapped.timestamp()


# ==================== CRAWL SCHEDULER ====================

class CrawlScheduler:
    """
    Decides when to crawl based on posting patterns.
    
    Provides should_crawl_now(), get_next_crawl_time(), and
    generates optimal crawl schedules.
    """
    
    def __init__(
        self,
        cache_file: Optional[str] = None,
        window_margin_minutes: int = 30,
    ):
        self.cache_file = Path(cache_file) if cache_file else None
        self.window_margin = window_margin_minutes
        self._patterns: Dict[str, PostingPattern] = {}
        
        if self.cache_file:
            self._load_cache()
    
    def should_crawl_now(self, pattern: PostingPattern) -> bool:
        """
        Check if current time falls within a hot posting window.
        
        Strategy based on user type:
        - Regular: only crawl during hot hours ± margin
        - Semi-regular: hot hours + 1 random interval check
        - Random: always True (use interval-based scheduling)
        
        Returns:
            True if now is a good time to crawl
        """
        now = datetime.now()
        current_hour = now.hour
        current_day = now.weekday()
        
        if pattern.user_type == "random":
            # Random posters: check interval
            if pattern.last_post_time:
                hours_since = (time.time() - pattern.last_post_time) / 3600
                return hours_since >= max(
                    MIN_INTERVAL_HOURS,
                    pattern.median_interval_hours * 0.8
                )
            return True
        
        # Check hot hours (with margin)
        in_hot_hour = False
        margin_hours = self.window_margin / 60.0
        
        for hot_h in pattern.hot_hours:
            lower = hot_h - margin_hours
            upper = hot_h + 1 + margin_hours  # +1 because hour is a range
            # Handle float comparison with current time
            current_float = current_hour + now.minute / 60.0
            if lower <= current_float <= upper:
                in_hot_hour = True
                break
        
        # Check hot days
        in_hot_day = not pattern.hot_days or current_day in pattern.hot_days
        
        if pattern.user_type == "regular":
            return in_hot_hour and in_hot_day
        
        # Semi-regular: hot hour OR interval exceeded
        if in_hot_hour and in_hot_day:
            return True
        
        # Fallback: check if enough time has passed
        if pattern.last_post_time:
            hours_since = (time.time() - pattern.last_post_time) / 3600
            return hours_since >= pattern.median_interval_hours * 1.5
        
        return True
    
    def get_next_crawl_time(self, pattern: PostingPattern) -> datetime:
        """
        Get the next optimal time to crawl this user.
        
        Returns:
            datetime of next recommended crawl
        """
        now = datetime.now()
        
        if pattern.user_type == "random":
            # Next interval
            interval = max(
                MIN_INTERVAL_HOURS,
                min(MAX_INTERVAL_HOURS, pattern.median_interval_hours)
            )
            return now + timedelta(hours=interval)
        
        # Find next hot window
        if pattern.hot_hours:
            current_hour = now.hour
            current_minute = now.minute
            
            # Sort hot hours
            sorted_hours = sorted(pattern.hot_hours)
            
            # Find next hot hour today
            for h in sorted_hours:
                candidate = now.replace(hour=h, minute=0, second=0, microsecond=0)
                if candidate > now:
                    # Check if it's a hot day too
                    if not pattern.hot_days or now.weekday() in pattern.hot_days:
                        return candidate
            
            # No more hot hours today — find next hot day
            for day_offset in range(1, 8):
                future_day = now + timedelta(days=day_offset)
                if not pattern.hot_days or future_day.weekday() in pattern.hot_days:
                    return future_day.replace(
                        hour=sorted_hours[0],
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
        
        # Fallback: next interval
        interval = pattern.median_interval_hours or DEFAULT_INTERVAL_HOURS
        return now + timedelta(hours=interval)
    
    def generate_schedule(
        self,
        pattern: PostingPattern,
        hours_ahead: int = 24,
    ) -> List[Dict]:
        """
        Generate a crawl schedule for the next N hours.
        
        Returns:
            List of {time: datetime, priority: str, reason: str}
        """
        schedule = []
        now = datetime.now()
        end = now + timedelta(hours=hours_ahead)
        
        if pattern.user_type == "random":
            # Evenly-spaced intervals
            interval = max(
                MIN_INTERVAL_HOURS,
                min(MAX_INTERVAL_HOURS, pattern.median_interval_hours),
            )
            current = now + timedelta(hours=interval)
            while current < end:
                schedule.append({
                    'time': current.strftime('%Y-%m-%d %H:%M'),
                    'priority': 'normal',
                    'reason': f'interval ({interval:.1f}h)',
                })
                current += timedelta(hours=interval)
            return schedule
        
        # iterate through hours in the window
        current = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        while current < end:
            hour = current.hour
            day = current.weekday()
            
            is_hot_hour = hour in pattern.hot_hours
            is_hot_day = not pattern.hot_days or day in pattern.hot_days
            
            if is_hot_hour and is_hot_day:
                prob = pattern.hourly_histogram[hour] if hour < len(pattern.hourly_histogram) else 0
                schedule.append({
                    'time': current.strftime('%Y-%m-%d %H:%M'),
                    'priority': 'high' if prob > 0.1 else 'medium',
                    'reason': f'hot window (prob={prob:.0%})',
                })
            elif pattern.user_type == "semi-regular" and is_hot_day:
                # Add one midday check for semi-regular
                if hour == 12 and not any(
                    s['time'].endswith('12:00') and
                    s['time'].startswith(current.strftime('%Y-%m-%d'))
                    for s in schedule
                ):
                    schedule.append({
                        'time': current.strftime('%Y-%m-%d %H:%M'),
                        'priority': 'low',
                        'reason': 'semi-regular check',
                    })
            
            current += timedelta(hours=1)
        
        return schedule
    
    # ==================== PATTERN CACHE ====================
    
    def save_pattern(self, pattern: PostingPattern):
        """Save a pattern to cache"""
        self._patterns[pattern.username] = pattern
        if self.cache_file:
            self._save_cache()
    
    def get_cached_pattern(self, username: str) -> Optional[PostingPattern]:
        """Get a cached pattern if not expired"""
        pattern = self._patterns.get(username)
        if not pattern:
            return None
        
        # Check TTL
        age_hours = (time.time() - pattern.analyzed_at) / 3600
        if age_hours > PATTERN_CACHE_TTL_HOURS:
            return None  # Expired
        
        return pattern
    
    def _save_cache(self):
        """Save all patterns to JSON file"""
        try:
            data = {}
            for username, pattern in self._patterns.items():
                data[username] = pattern.to_dict()
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def _load_cache(self):
        """Load patterns from JSON file"""
        if not self.cache_file or not self.cache_file.exists():
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for username, pdata in data.items():
                pattern = PostingPattern(
                    username=username,
                    hourly_histogram=pdata.get('hourly_histogram', [0.0] * 24),
                    daily_histogram=pdata.get('daily_histogram', [0.0] * 7),
                    hourly_counts=pdata.get('hourly_counts', [0] * 24),
                    daily_counts=pdata.get('daily_counts', [0] * 7),
                    avg_interval_hours=pdata.get('avg_interval_hours', 0),
                    median_interval_hours=pdata.get('median_interval_hours', 0),
                    stddev_interval_hours=pdata.get('stddev_interval_hours', 0),
                    regularity_score=pdata.get('regularity_score', 0),
                    hot_hours=pdata.get('hot_hours', []),
                    hot_days=pdata.get('hot_days', []),
                    next_predicted=pdata.get('next_predicted'),
                    last_post_time=pdata.get('last_post_time'),
                    total_posts_analyzed=pdata.get('total_posts_analyzed', 0),
                    analyzed_at=pdata.get('analyzed_at', 0),
                )
                self._patterns[username] = pattern
            
            if self._patterns:
                print(f"  [+] Loaded {len(self._patterns)} cached patterns")
        except Exception:
            pass
    
    def print_schedule(self, pattern: PostingPattern, hours_ahead: int = 24):
        """Print a formatted schedule"""
        schedule = self.generate_schedule(pattern, hours_ahead)
        
        if not schedule:
            print("  [!] No scheduled crawls")
            return
        
        print(f"\n  📅 Crawl Schedule for @{pattern.username} (next {hours_ahead}h):")
        print(f"  {'Time':<20} {'Priority':<10} {'Reason'}")
        print(f"  {'-'*55}")
        
        priority_icons = {'high': '🔴', 'medium': '🟡', 'normal': '🟢', 'low': '⚪'}
        
        for entry in schedule:
            icon = priority_icons.get(entry['priority'], '⚪')
            print(f"  {entry['time']:<20} {icon} {entry['priority']:<8} {entry['reason']}")
        
        print(f"\n  Total: {len(schedule)} crawl{'s' if len(schedule) != 1 else ''}")
