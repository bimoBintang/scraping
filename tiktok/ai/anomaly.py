"""
Anomaly Detection Module for TikTok AI
Bot detection, spam detection, fake follower detection
"""

import math
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import Counter
import re

try:
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    import numpy as np
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


# ==================== DATA CLASSES ====================

@dataclass
class AccountHealth:
    """Overall account health assessment"""
    username: str
    bot_probability: float  # 0-1
    spam_score: float  # 0-1
    fake_follower_pct: float  # 0-100
    authenticity_score: float  # 0-1
    risk_factors: List[str] = field(default_factory=list)
    confidence: float = 0.0
    analysis_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BotIndicators:
    """Specific bot behavior indicators"""
    posting_regularity: float  # 0-1, higher = more regular (bot-like)
    engagement_ratio: float  # likes+comments / followers
    comment_similarity: float  # 0-1, higher = more similar comments
    following_ratio: float  # following / followers
    account_age_days: int
    avg_posts_per_day: float
    activity_hours: List[int]  # Hours of day when active
    
    def get_score(self) -> float:
        """Calculate overall bot score"""
        score = 0.0
        
        # Highly regular posting is suspicious
        if self.posting_regularity > 0.9:
            score += 0.3
        
        # Abnormal engagement ratio
        if self.engagement_ratio > 0.5 or self.engagement_ratio < 0.001:
            score += 0.2
        
        # High comment similarity
        if self.comment_similarity > 0.7:
            score += 0.3
        
        # Extreme following ratio
        if self.following_ratio > 10:
            score += 0.2
        
        # New account with high activity
        if self.account_age_days < 30 and self.avg_posts_per_day > 10:
            score += 0.2
        
        # 24/7 activity
        if len(self.activity_hours) > 20:
            score += 0.2
        
        return min(1.0, score)


@dataclass
class SpamIndicators:
    """Spam behavior indicators"""
    link_frequency: float  # Links per post
    promo_word_frequency: float  # Promotional words per post
    hashtag_stuffing: float  # Avg hashtags per post
    duplicate_content_ratio: float  # % of duplicate posts
    mention_frequency: float  # Mentions per post
    
    def get_score(self) -> float:
        """Calculate spam score"""
        score = 0.0
        
        if self.link_frequency > 0.5:
            score += 0.25
        
        if self.promo_word_frequency > 0.3:
            score += 0.25
        
        if self.hashtag_stuffing > 15:
            score += 0.2
        
        if self.duplicate_content_ratio > 0.3:
            score += 0.2
        
        if self.mention_frequency > 3:
            score += 0.1
        
        return min(1.0, score)


@dataclass
class FakeFollowerIndicators:
    """Fake follower indicators"""
    no_profile_pic_pct: float
    no_bio_pct: float
    no_posts_pct: float
    suspicious_names_pct: float
    recent_creation_pct: float
    
    def get_score(self) -> float:
        """Estimate fake follower percentage"""
        weights = [0.1, 0.15, 0.3, 0.25, 0.2]
        values = [
            self.no_profile_pic_pct,
            self.no_bio_pct,
            self.no_posts_pct,
            self.suspicious_names_pct,
            self.recent_creation_pct
        ]
        
        return sum(w * v for w, v in zip(weights, values))


@dataclass
class BotCluster:
    """Group of accounts suspected to be coordinated bots"""
    id: int
    accounts: List[str]
    similarity_score: float
    shared_behaviors: List[str]
    detected_at: datetime = field(default_factory=datetime.now)


# ==================== BOT DETECTOR ====================

class BotDetector:
    """
    Detect bot accounts using behavioral analysis
    Uses Isolation Forest for anomaly detection
    """
    
    # Promo words that indicate spam/bot
    PROMO_WORDS = {
        'free', 'win', 'click', 'link', 'bio', 'dm', 'buy', 'sale', 'discount',
        'promo', 'offer', 'limited', 'exclusive', 'now', 'hurry', 'shop',
        'gratis', 'beli', 'murah', 'diskon', 'promo', 'klik', 'order'
    }
    
    def __init__(self, contamination: float = 0.1):
        """
        Args:
            contamination: Expected proportion of bots (0.1 = 10%)
        """
        self.contamination = contamination
        self._model = None
        self._scaler = None
    
    def analyze_account(self, profile: Dict, posts: List[Dict] = None) -> BotIndicators:
        """Analyze single account for bot indicators"""
        posts = posts or []
        
        # Calculate indicators
        posting_regularity = self._calc_posting_regularity(posts)
        engagement_ratio = self._calc_engagement_ratio(profile, posts)
        comment_similarity = 0.0  # Would need comments data
        following_ratio = self._calc_following_ratio(profile)
        account_age = self._calc_account_age(profile)
        posts_per_day = len(posts) / max(account_age, 1)
        activity_hours = self._get_activity_hours(posts)
        
        return BotIndicators(
            posting_regularity=posting_regularity,
            engagement_ratio=engagement_ratio,
            comment_similarity=comment_similarity,
            following_ratio=following_ratio,
            account_age_days=account_age,
            avg_posts_per_day=posts_per_day,
            activity_hours=activity_hours
        )
    
    def detect_bots(
        self, 
        profiles: List[Dict],
        confidence_threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        Detect bots from a list of profiles
        Returns list of (username, bot_probability)
        """
        if not HAS_SKLEARN or len(profiles) < 10:
            # Fallback to simple scoring
            return self._simple_bot_detection(profiles)
        
        # Extract features
        features = []
        usernames = []
        
        for profile in profiles:
            feat = self._extract_features(profile)
            if feat:
                features.append(feat)
                usernames.append(profile.get('username', 'unknown'))
        
        if not features:
            return []
        
        # Scale features
        X = np.array(features)
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)
        
        # Train isolation forest
        self._model = IsolationForest(
            contamination=self.contamination,
            random_state=42,
            n_estimators=100
        )
        
        # Predict (-1 = anomaly/bot, 1 = normal)
        predictions = self._model.fit_predict(X_scaled)
        scores = self._model.decision_function(X_scaled)
        
        # Convert to probabilities
        results = []
        for username, pred, score in zip(usernames, predictions, scores):
            # Convert score to probability (lower score = more likely bot)
            probability = 1 / (1 + np.exp(score * 5))  # Sigmoid transform
            
            if probability >= confidence_threshold:
                results.append((username, float(probability)))
        
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def _extract_features(self, profile: Dict) -> Optional[List[float]]:
        """Extract numerical features from profile"""
        try:
            followers = profile.get('follower_count', 0)
            following = profile.get('following_count', 0)
            likes = profile.get('total_likes', 0)
            videos = profile.get('video_count', 0)
            
            # Derived features
            follower_ratio = following / max(followers, 1)
            engagement_rate = likes / max(followers * videos, 1)
            videos_per_follower = videos / max(followers, 1)
            
            return [
                math.log1p(followers),
                math.log1p(following),
                math.log1p(videos),
                follower_ratio,
                engagement_rate,
                videos_per_follower,
                1 if profile.get('is_verified', False) else 0,
                1 if profile.get('has_bio', True) else 0
            ]
        except:
            return None
    
    def _simple_bot_detection(self, profiles: List[Dict]) -> List[Tuple[str, float]]:
        """Simple rule-based bot detection"""
        results = []
        
        for profile in profiles:
            score = 0.0
            
            followers = profile.get('follower_count', 0)
            following = profile.get('following_count', 0)
            
            # High following to follower ratio
            if following > 0 and followers > 0:
                ratio = following / followers
                if ratio > 10:
                    score += 0.3
                elif ratio > 5:
                    score += 0.15
            
            # No profile picture or bio
            if not profile.get('avatar_url'):
                score += 0.2
            if not profile.get('bio'):
                score += 0.15
            
            # Suspicious username pattern
            username = profile.get('username', '')
            if re.match(r'.*\d{5,}.*', username):  # Many numbers
                score += 0.2
            
            # Very new with high following
            if following > 1000 and followers < 100:
                score += 0.25
            
            if score >= 0.5:
                results.append((username, min(score, 1.0)))
        
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def _calc_posting_regularity(self, posts: List[Dict]) -> float:
        """Calculate how regular posting times are"""
        if len(posts) < 2:
            return 0.0
        
        timestamps = []
        for post in posts:
            ts = post.get('create_time')
            if ts:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts)
                    except:
                        continue
                timestamps.append(ts)
        
        if len(timestamps) < 2:
            return 0.0
        
        # Calculate intervals
        timestamps.sort()
        intervals = [(timestamps[i+1] - timestamps[i]).total_seconds() 
                    for i in range(len(timestamps)-1)]
        
        if not intervals:
            return 0.0
        
        # Calculate coefficient of variation (lower = more regular)
        mean_interval = sum(intervals) / len(intervals)
        if mean_interval == 0:
            return 1.0
        
        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        cv = math.sqrt(variance) / mean_interval
        
        # Convert to regularity score (lower CV = more regular = more bot-like)
        return max(0, 1 - cv)
    
    def _calc_engagement_ratio(self, profile: Dict, posts: List[Dict]) -> float:
        """Calculate engagement ratio"""
        followers = profile.get('follower_count', 1)
        
        total_likes = sum(p.get('like_count', 0) for p in posts)
        total_comments = sum(p.get('comment_count', 0) for p in posts)
        
        return (total_likes + total_comments) / max(followers * len(posts), 1)
    
    def _calc_following_ratio(self, profile: Dict) -> float:
        """Calculate following to followers ratio"""
        followers = profile.get('follower_count', 1)
        following = profile.get('following_count', 0)
        return following / max(followers, 1)
    
    def _calc_account_age(self, profile: Dict) -> int:
        """Calculate account age in days"""
        created = profile.get('create_time')
        if not created:
            return 365  # Assume 1 year if unknown
        
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except:
                return 365
        
        return (datetime.now() - created).days
    
    def _get_activity_hours(self, posts: List[Dict]) -> List[int]:
        """Get unique hours of activity"""
        hours = set()
        for post in posts:
            ts = post.get('create_time')
            if ts:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts)
                    except:
                        continue
                hours.add(ts.hour)
        return list(hours)


# ==================== SPAM DETECTOR ====================

class SpamDetector:
    """
    Detect spam content and accounts
    """
    
    SPAM_PATTERNS = [
        r'(?i)(click|tap)\s*(here|link|bio)',
        r'(?i)dm\s*(me|for)',
        r'(?i)free\s*(money|gift|iphone)',
        r'(?i)make\s*\$?\d+',
        r'(?i)(binary|crypto|forex)\s*trading',
        r'(?i)become\s*rich',
        r'https?://\S+\s*https?://\S+',  # Multiple links
    ]
    
    def __init__(self):
        self._patterns = [re.compile(p) for p in self.SPAM_PATTERNS]
    
    def analyze_content(self, texts: List[str]) -> SpamIndicators:
        """Analyze content for spam indicators"""
        if not texts:
            return SpamIndicators(
                link_frequency=0, promo_word_frequency=0,
                hashtag_stuffing=0, duplicate_content_ratio=0,
                mention_frequency=0
            )
        
        total_links = 0
        total_promo = 0
        total_hashtags = 0
        total_mentions = 0
        
        for text in texts:
            total_links += len(re.findall(r'https?://\S+', text))
            total_promo += sum(1 for word in BotDetector.PROMO_WORDS if word in text.lower())
            total_hashtags += len(re.findall(r'#\w+', text))
            total_mentions += len(re.findall(r'@\w+', text))
        
        n = len(texts)
        
        # Detect duplicates
        unique_texts = set(texts)
        duplicate_ratio = 1 - len(unique_texts) / n
        
        return SpamIndicators(
            link_frequency=total_links / n,
            promo_word_frequency=total_promo / n,
            hashtag_stuffing=total_hashtags / n,
            duplicate_content_ratio=duplicate_ratio,
            mention_frequency=total_mentions / n
        )
    
    def is_spam_text(self, text: str) -> Tuple[bool, List[str]]:
        """Check if text is spam"""
        matches = []
        
        for pattern in self._patterns:
            if pattern.search(text):
                matches.append(pattern.pattern)
        
        # Additional checks
        hashtag_count = len(re.findall(r'#\w+', text))
        if hashtag_count > 20:
            matches.append("excessive_hashtags")
        
        return len(matches) > 0, matches
    
    def detect_spam_accounts(
        self,
        profiles: List[Dict],
        posts_by_user: Dict[str, List[str]],
        threshold: float = 0.5
    ) -> List[Tuple[str, float]]:
        """Detect spam accounts"""
        results = []
        
        for profile in profiles:
            username = profile.get('username', '')
            posts = posts_by_user.get(username, [])
            
            if not posts:
                continue
            
            indicators = self.analyze_content(posts)
            score = indicators.get_score()
            
            if score >= threshold:
                results.append((username, score))
        
        return sorted(results, key=lambda x: x[1], reverse=True)


# ==================== FAKE FOLLOWER DETECTOR ====================

class FakeFollowerDetector:
    """
    Estimate percentage of fake followers
    """
    
    # Patterns suggesting fake/bot username
    SUSPICIOUS_NAME_PATTERNS = [
        r'^user\d{6,}$',
        r'^\w+\d{6,}$',
        r'^[a-z]{2,3}\d{8,}$',
        r'.*_bot$',
        r'^bot_.*',
    ]
    
    def __init__(self):
        self._patterns = [re.compile(p, re.I) for p in self.SUSPICIOUS_NAME_PATTERNS]
    
    def analyze_followers(self, followers: List[Dict]) -> FakeFollowerIndicators:
        """Analyze followers for fake accounts"""
        if not followers:
            return FakeFollowerIndicators(
                no_profile_pic_pct=0, no_bio_pct=0, no_posts_pct=0,
                suspicious_names_pct=0, recent_creation_pct=0
            )
        
        n = len(followers)
        
        no_pic = sum(1 for f in followers if not f.get('avatar_url'))
        no_bio = sum(1 for f in followers if not f.get('bio'))
        no_posts = sum(1 for f in followers if f.get('video_count', 0) == 0)
        suspicious = sum(1 for f in followers if self._is_suspicious_name(f.get('username', '')))
        recent = sum(1 for f in followers if self._is_recent_account(f))
        
        return FakeFollowerIndicators(
            no_profile_pic_pct=no_pic / n * 100,
            no_bio_pct=no_bio / n * 100,
            no_posts_pct=no_posts / n * 100,
            suspicious_names_pct=suspicious / n * 100,
            recent_creation_pct=recent / n * 100
        )
    
    def _is_suspicious_name(self, username: str) -> bool:
        """Check if username matches suspicious pattern"""
        return any(p.match(username) for p in self._patterns)
    
    def _is_recent_account(self, profile: Dict) -> bool:
        """Check if account was created recently"""
        created = profile.get('create_time')
        if not created:
            return False
        
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except:
                return False
        
        return (datetime.now() - created).days < 30


# ==================== ACCOUNT HEALTH ANALYZER ====================

class AccountHealthAnalyzer:
    """
    Combined account health analysis
    """
    
    def __init__(self):
        self.bot_detector = BotDetector()
        self.spam_detector = SpamDetector()
        self.fake_detector = FakeFollowerDetector()
    
    def analyze(
        self,
        profile: Dict,
        posts: List[Dict] = None,
        followers: List[Dict] = None
    ) -> AccountHealth:
        """Full account health analysis"""
        posts = posts or []
        followers = followers or []
        
        username = profile.get('username', 'unknown')
        risk_factors = []
        
        # Bot analysis
        bot_indicators = self.bot_detector.analyze_account(profile, posts)
        bot_prob = bot_indicators.get_score()
        
        if bot_prob > 0.5:
            risk_factors.append("High bot probability")
        if bot_indicators.posting_regularity > 0.9:
            risk_factors.append("Suspiciously regular posting")
        if bot_indicators.following_ratio > 10:
            risk_factors.append("Abnormal following/follower ratio")
        
        # Spam analysis
        texts = [p.get('description', '') for p in posts if p.get('description')]
        spam_indicators = self.spam_detector.analyze_content(texts)
        spam_score = spam_indicators.get_score()
        
        if spam_score > 0.5:
            risk_factors.append("Spam-like content")
        if spam_indicators.link_frequency > 0.5:
            risk_factors.append("Excessive links")
        if spam_indicators.hashtag_stuffing > 15:
            risk_factors.append("Hashtag stuffing")
        
        # Fake follower analysis
        fake_indicators = self.fake_detector.analyze_followers(followers)
        fake_pct = fake_indicators.get_score()
        
        if fake_pct > 30:
            risk_factors.append("High fake follower percentage")
        
        # Calculate authenticity score
        authenticity = 1 - (bot_prob * 0.4 + spam_score * 0.3 + fake_pct/100 * 0.3)
        
        # Confidence based on data availability
        confidence = 0.5
        if posts:
            confidence += 0.2
        if followers:
            confidence += 0.2
        if len(posts) > 10:
            confidence += 0.1
        
        return AccountHealth(
            username=username,
            bot_probability=bot_prob,
            spam_score=spam_score,
            fake_follower_pct=fake_pct,
            authenticity_score=max(0, authenticity),
            risk_factors=risk_factors,
            confidence=min(1.0, confidence)
        )
    
    def detect_bot_network(
        self,
        profiles: List[Dict],
        similarity_threshold: float = 0.8
    ) -> List[BotCluster]:
        """Detect coordinated bot networks"""
        if len(profiles) < 5:
            return []
        
        # Extract features for clustering
        clusters = []
        
        # Simple clustering by similar behavior patterns
        bot_scores = {}
        for profile in profiles:
            username = profile.get('username', '')
            indicators = self.bot_detector.analyze_account(profile, [])
            bot_scores[username] = indicators.get_score()
        
        # Group high-scoring bots
        high_score_bots = [u for u, s in bot_scores.items() if s > 0.6]
        
        if len(high_score_bots) >= 3:
            clusters.append(BotCluster(
                id=0,
                accounts=high_score_bots,
                similarity_score=0.8,
                shared_behaviors=["High bot probability", "Similar behavior patterns"]
            ))
        
        return clusters


# ==================== MAIN ANOMALY DETECTOR ====================

class AnomalyDetector:
    """
    Unified anomaly detection interface
    """
    
    def __init__(self):
        self.account_analyzer = AccountHealthAnalyzer()
    
    def analyze_account(
        self,
        profile: Dict,
        posts: List[Dict] = None,
        followers: List[Dict] = None
    ) -> AccountHealth:
        """Analyze single account"""
        return self.account_analyzer.analyze(profile, posts, followers)
    
    def analyze_batch(
        self,
        profiles: List[Dict],
        posts_by_user: Dict[str, List[Dict]] = None,
        followers_by_user: Dict[str, List[Dict]] = None
    ) -> List[AccountHealth]:
        """Analyze multiple accounts"""
        posts_by_user = posts_by_user or {}
        followers_by_user = followers_by_user or {}
        
        results = []
        for profile in profiles:
            username = profile.get('username', '')
            posts = posts_by_user.get(username, [])
            followers = followers_by_user.get(username, [])
            
            result = self.analyze_account(profile, posts, followers)
            results.append(result)
        
        return results
    
    def detect_all_anomalies(
        self,
        profiles: List[Dict],
        posts_by_user: Dict[str, List[Dict]] = None
    ) -> Dict[str, Any]:
        """Detect all types of anomalies"""
        posts_by_user = posts_by_user or {}
        
        # Analyze all accounts
        health_results = self.analyze_batch(profiles, posts_by_user)
        
        # Detect bots
        bots = [(h.username, h.bot_probability) for h in health_results if h.bot_probability > 0.6]
        
        # Detect spam
        spammers = [(h.username, h.spam_score) for h in health_results if h.spam_score > 0.5]
        
        # Detect bot networks
        bot_networks = self.account_analyzer.detect_bot_network(profiles)
        
        # Summary
        return {
            "total_analyzed": len(profiles),
            "suspected_bots": bots,
            "suspected_spammers": spammers,
            "bot_networks": bot_networks,
            "average_authenticity": sum(h.authenticity_score for h in health_results) / len(health_results) if health_results else 0,
            "high_risk_accounts": [h for h in health_results if h.authenticity_score < 0.5]
        }
