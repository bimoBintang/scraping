"""
Algorithm 11: Anomaly Detection for Private Account Patterns

Mendeteksi pola akun private melalui interaksi tidak langsung di postingan publik.
Menganalisis komentar, mentions, dan network graph untuk menginferensi
koneksi dan estimasi follower count akun private.

Pipeline:
  1. CommentScraper     — Fetch comments dari public posts (GraphQL + Mobile API)
  2. MentionExtractor   — Parse @username dari captions + comments
  3. NetworkInferenceEngine — Build graph, estimate followers, score connections
  4. PrivateAccountAnalyzer — Orchestrator: full pipeline + report

Usage:
    from instagram.anomaly_detector import PrivateAccountAnalyzer

    analyzer = PrivateAccountAnalyzer(client)
    report = analyzer.analyze("private_user", depth=2)
    analyzer.print_report(report)
"""

import json
import math
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set, Tuple

import requests

from .models import (
    CommentData,
    InstagramPost,
    InstagramProfile,
    MentionEdge,
    PrivateAccountReport,
)
from .utils import generate_mobile_headers, generate_web_headers, smart_delay


# ==================== CONSTANTS ====================

GRAPHQL_URL = "https://www.instagram.com/graphql/query/"
COMMENTS_MOBILE_URL = "https://i.instagram.com/api/v1/media/{media_id}/comments/"
COMMENTS_DOC_ID = "3742010485902564"  # edge_media_to_parent_comment

COMMENT_FETCH_DELAY = 2.0    # seconds between comment fetches
MAX_COMMENTS_PER_POST = 100  # cap per post
MENTION_REGEX = re.compile(r'@([a-zA-Z0-9._]{1,30})')


# ==================== COMMENT SCRAPER ====================

class CommentScraper:
    """
    Fetch comments from public Instagram posts.

    Supports GraphQL (primary) and Mobile API (fallback).
    Extracts @mentions automatically from comment text.
    """

    def __init__(
        self,
        session: requests.Session,
        make_request: Callable,
        cookies: list,
    ):
        self.session = session
        self.make_request = make_request
        self.cookies = cookies

    def fetch_post_comments(
        self,
        shortcode: str,
        count: int = MAX_COMMENTS_PER_POST,
    ) -> List[CommentData]:
        """
        Fetch comments for a public post.

        Args:
            shortcode: Post shortcode (e.g., "CxY1234")
            count: Max comments to fetch

        Returns:
            List of CommentData with mentions extracted
        """
        comments = self._fetch_comments_graphql(shortcode, count)

        if comments is None:
            comments = self._fetch_comments_mobile(shortcode, count)

        return comments or []

    def fetch_comments_batch(
        self,
        posts: List[InstagramPost],
        count_per_post: int = 50,
    ) -> Dict[str, List[CommentData]]:
        """
        Fetch comments for multiple posts with rate limiting.

        Returns:
            Dict mapping shortcode -> comments list
        """
        all_comments = {}

        for i, post in enumerate(posts):
            if post.comments == 0:
                continue

            print(f"    [{i+1}/{len(posts)}] {post.shortcode} "
                  f"({post.comments} comments)...", end=" ")

            comments = self.fetch_post_comments(post.shortcode, count_per_post)
            all_comments[post.shortcode] = comments
            print(f"fetched {len(comments)}")

            if i < len(posts) - 1:
                smart_delay(COMMENT_FETCH_DELAY, COMMENT_FETCH_DELAY * 1.5)

        return all_comments

    # ─── GraphQL ────────────────────────────────────────────────────

    def _fetch_comments_graphql(
        self,
        shortcode: str,
        count: int,
    ) -> Optional[List[CommentData]]:
        """Fetch comments via GraphQL edge_media_to_parent_comment"""
        headers = generate_web_headers(self.cookies)

        variables = {
            "shortcode": shortcode,
            "first": min(count, 50),
        }

        try:
            response = self.make_request(
                GRAPHQL_URL,
                params={
                    'doc_id': COMMENTS_DOC_ID,
                    'variables': json.dumps(variables),
                },
                headers=headers,
                timeout=15,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            return self._parse_graphql_comments(data, shortcode)

        except Exception as e:
            print(f"  [!] GraphQL comments error: {e}")
            return None

    def _parse_graphql_comments(
        self,
        data: Dict,
        shortcode: str,
    ) -> List[CommentData]:
        """Parse GraphQL comments response"""
        comments = []

        edges = (
            data.get('data', {})
            .get('shortcode_media', data.get('data', {}).get('xdt_shortcode_media', {}))
            .get('edge_media_to_parent_comment', {})
            .get('edges', [])
        )

        for edge in edges:
            node = edge.get('node', {})
            text = node.get('text', '')
            owner = node.get('owner', {})

            comment = CommentData(
                comment_id=str(node.get('id', '')),
                text=text,
                author=owner.get('username', ''),
                author_id=str(owner.get('id', '')),
                timestamp=node.get('created_at', 0),
                likes=node.get('edge_liked_by', {}).get('count', 0),
                post_shortcode=shortcode,
                mentions=MENTION_REGEX.findall(text),
            )
            comments.append(comment)

            # Also parse threaded replies
            reply_edges = (
                node.get('edge_threaded_comments', {})
                .get('edges', [])
            )
            for reply_edge in reply_edges:
                rnode = reply_edge.get('node', {})
                rtext = rnode.get('text', '')
                rowner = rnode.get('owner', {})

                reply = CommentData(
                    comment_id=str(rnode.get('id', '')),
                    text=rtext,
                    author=rowner.get('username', ''),
                    author_id=str(rowner.get('id', '')),
                    timestamp=rnode.get('created_at', 0),
                    likes=rnode.get('edge_liked_by', {}).get('count', 0),
                    post_shortcode=shortcode,
                    mentions=MENTION_REGEX.findall(rtext),
                    is_reply=True,
                    parent_id=str(node.get('id', '')),
                )
                comments.append(reply)

        return comments

    # ─── Mobile API ─────────────────────────────────────────────────

    def _fetch_comments_mobile(
        self,
        shortcode: str,
        count: int,
    ) -> Optional[List[CommentData]]:
        """Fetch comments via Mobile API (fallback)"""
        headers = generate_mobile_headers(self.cookies)

        # Convert shortcode to media_id
        media_id = self._shortcode_to_media_id(shortcode)
        if not media_id:
            return None

        url = COMMENTS_MOBILE_URL.format(media_id=media_id)

        try:
            response = self.make_request(
                url,
                headers=headers,
                timeout=15,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            return self._parse_mobile_comments(data, shortcode)

        except Exception as e:
            print(f"  [!] Mobile comments error: {e}")
            return None

    def _parse_mobile_comments(
        self,
        data: Dict,
        shortcode: str,
    ) -> List[CommentData]:
        """Parse Mobile API comments response"""
        comments = []

        for item in data.get('comments', []):
            text = item.get('text', '')
            user = item.get('user', {})

            comment = CommentData(
                comment_id=str(item.get('pk', '')),
                text=text,
                author=user.get('username', ''),
                author_id=str(user.get('pk', '')),
                timestamp=item.get('created_at', 0),
                likes=item.get('comment_like_count', 0),
                post_shortcode=shortcode,
                mentions=MENTION_REGEX.findall(text),
            )
            comments.append(comment)

        return comments

    @staticmethod
    def _shortcode_to_media_id(shortcode: str) -> Optional[str]:
        """Convert Instagram shortcode to numeric media ID"""
        alphabet = (
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
        )
        media_id = 0
        for char in shortcode:
            idx = alphabet.find(char)
            if idx == -1:
                return None
            media_id = media_id * 64 + idx
        return str(media_id)


# ==================== MENTION EXTRACTOR ====================

class MentionExtractor:
    """
    Parse @mentions from captions and comments.
    Build a mention frequency map: who mentions whom, and how often.
    """

    def __init__(self):
        self.mention_map: Dict[str, Dict[str, MentionEdge]] = defaultdict(dict)

    def extract_mentions(self, text: str) -> List[str]:
        """Extract @username mentions from any text"""
        if not text:
            return []
        return MENTION_REGEX.findall(text)

    def process_posts(
        self,
        posts: List[InstagramPost],
        author: str,
        author_profile: Optional[InstagramProfile] = None,
    ):
        """Extract mentions from post captions"""
        for post in posts:
            mentions = self.extract_mentions(post.caption)
            for mentioned in mentions:
                self._record_mention(
                    source=author,
                    mentioned=mentioned,
                    shortcode=post.shortcode,
                    timestamp=post.timestamp,
                    context=post.caption[:100],
                    source_profile=author_profile,
                )

    def process_comments(
        self,
        comments: List[CommentData],
        author_profiles: Optional[Dict[str, InstagramProfile]] = None,
    ):
        """Extract mentions from collected comments"""
        for comment in comments:
            for mentioned in comment.mentions:
                profile = (author_profiles or {}).get(comment.author)
                self._record_mention(
                    source=comment.author,
                    mentioned=mentioned,
                    shortcode=comment.post_shortcode,
                    timestamp=comment.timestamp,
                    context=comment.text[:100],
                    source_profile=profile,
                )

    def get_edges_for(self, username: str) -> List[MentionEdge]:
        """Get all mention edges where username is mentioned"""
        edges = []
        for source, targets in self.mention_map.items():
            if username in targets:
                edges.append(targets[username])
        return edges

    def get_mentioners(self, username: str) -> List[str]:
        """Get list of users who mention username"""
        mentioners = []
        for source, targets in self.mention_map.items():
            if username in targets:
                mentioners.append(source)
        return mentioners

    def get_total_mentions(self, username: str) -> int:
        """Total times username was mentioned across all sources"""
        total = 0
        for source, targets in self.mention_map.items():
            if username in targets:
                total += targets[username].frequency
        return total

    def _record_mention(
        self,
        source: str,
        mentioned: str,
        shortcode: str,
        timestamp: int,
        context: str,
        source_profile: Optional[InstagramProfile] = None,
    ):
        """Record a single mention event"""
        if source == mentioned:
            return  # Skip self-mentions

        if mentioned not in self.mention_map[source]:
            self.mention_map[source][mentioned] = MentionEdge(
                source_user=source,
                mentioned_user=mentioned,
                frequency=0,
                first_seen=timestamp,
                source_followers=source_profile.followers if source_profile else 0,
                source_is_verified=source_profile.is_verified if source_profile else False,
            )

        edge = self.mention_map[source][mentioned]
        edge.frequency += 1
        edge.last_seen = max(edge.last_seen, timestamp)
        if timestamp > 0 and (edge.first_seen == 0 or timestamp < edge.first_seen):
            edge.first_seen = timestamp
        if context and len(edge.contexts) < 5:
            edge.contexts.append(context)
        if shortcode and shortcode not in edge.post_shortcodes:
            edge.post_shortcodes.append(shortcode)


# ==================== NETWORK INFERENCE ENGINE ====================

class NetworkInferenceEngine:
    """
    Build a network graph from mentions and infer private account properties.

    Uses mention frequency, mentioner follower counts, and network structure
    to estimate follower counts and connection patterns for private accounts.
    """

    def estimate_followers(
        self,
        edges: List[MentionEdge],
        mentioners: List[str],
        mentioner_profiles: Dict[str, InstagramProfile],
    ) -> Tuple[int, float]:
        """
        Estimate follower count for a private account based on
        who mentions them and how often.

        Method: weighted average of mentioner follower counts,
        scaled by mention frequency and network density.

        Returns:
            (estimated_followers, confidence)
        """
        if not edges:
            return 0, 0.0

        # Collect follower counts from mentioners
        follower_counts = []
        weighted_sum = 0.0
        weight_total = 0.0

        for edge in edges:
            profile = mentioner_profiles.get(edge.source_user)
            if profile and profile.followers > 0:
                # Weight by mention frequency (more mentions = closer connection)
                w = edge.frequency
                weighted_sum += profile.followers * w
                weight_total += w
                follower_counts.append(profile.followers)

        if not follower_counts:
            return 0, 0.0

        # Weighted average of mentioner followers
        avg_mentioner_followers = weighted_sum / weight_total

        # Private accounts typically have fewer followers than those
        # who mention them. Apply scaling factor based on network size.
        num_mentioners = len(set(e.source_user for e in edges))

        # Heuristic: private account followers ≈ mentioners * scaling_factor
        # The more diverse the mentioners, the larger the likely following
        scaling_factor = min(num_mentioners * 1.5, 10.0)
        estimated = int(avg_mentioner_followers * 0.3 * scaling_factor / 10)

        # Bound the estimate
        estimated = max(estimated, num_mentioners)
        estimated = min(estimated, int(avg_mentioner_followers * 2))

        # Confidence based on data quality
        confidence = self._calculate_confidence(
            num_edges=len(edges),
            num_mentioners=num_mentioners,
            has_follower_data=len(follower_counts) > 0,
            total_mentions=sum(e.frequency for e in edges),
        )

        return estimated, confidence

    def calculate_network_density(
        self,
        mentioners: List[str],
        mention_map: Dict[str, Dict[str, MentionEdge]],
    ) -> float:
        """
        Calculate how interconnected the mentioners are.

        High density = mentioners also mention each other
        (indicates a tight friend group).

        Returns:
            density score between 0.0 and 1.0
        """
        if len(mentioners) < 2:
            return 0.0

        # Count cross-mentions between mentioners
        cross_mentions = 0
        possible_edges = len(mentioners) * (len(mentioners) - 1)

        mentioner_set = set(mentioners)
        for user in mentioners:
            if user in mention_map:
                for target in mention_map[user]:
                    if target in mentioner_set and target != user:
                        cross_mentions += 1

        return cross_mentions / possible_edges if possible_edges > 0 else 0.0

    def calculate_activity_score(
        self,
        edges: List[MentionEdge],
    ) -> float:
        """
        Score how 'active' a private account appears in the public sphere.

        Based on total mentions, recency, and diversity of mentioners.

        Returns:
            activity score between 0.0 and 1.0
        """
        if not edges:
            return 0.0

        total_mentions = sum(e.frequency for e in edges)
        unique_mentioners = len(set(e.source_user for e in edges))

        # Recency factor: how recent are the mentions?
        now = int(time.time())
        recent_mentions = sum(
            1 for e in edges
            if e.last_seen > 0 and (now - e.last_seen) < 30 * 86400  # within 30 days
        )
        recency_ratio = recent_mentions / len(edges) if edges else 0

        # Normalize components
        mention_score = min(total_mentions / 50, 1.0)
        diversity_score = min(unique_mentioners / 10, 1.0)

        # Weighted combination
        return (mention_score * 0.4 + diversity_score * 0.3 + recency_ratio * 0.3)

    def calculate_ghost_score(
        self,
        total_mentions: int,
        unique_mentioners: int,
    ) -> float:
        """
        Ghost score: 1.0 = no indirect presence, 0.0 = very active.

        Inverse of activity — a high ghost score means the account
        has almost no public footprint despite being mentioned.
        """
        if total_mentions == 0 and unique_mentioners == 0:
            return 1.0

        # More mentions and mentioners = less ghostly
        presence = math.log10(max(total_mentions, 1)) + math.log10(max(unique_mentioners, 1))
        return max(0.0, 1.0 - (presence / 4.0))

    def find_common_hashtags(
        self,
        posts: List[InstagramPost],
        min_frequency: int = 2,
    ) -> List[str]:
        """Find commonly used hashtags across mentioner posts"""
        hashtag_counter = Counter()
        for post in posts:
            for tag in post.hashtags:
                hashtag_counter[tag] += 1

        return [
            tag for tag, count in hashtag_counter.most_common(20)
            if count >= min_frequency
        ]

    def _calculate_confidence(
        self,
        num_edges: int,
        num_mentioners: int,
        has_follower_data: bool,
        total_mentions: int,
    ) -> float:
        """Calculate confidence score for the estimate"""
        score = 0.0

        # More data sources = higher confidence
        if num_mentioners >= 5:
            score += 0.3
        elif num_mentioners >= 2:
            score += 0.15

        # Follower data available?
        if has_follower_data:
            score += 0.25

        # Multiple mentions = more reliable
        if total_mentions >= 10:
            score += 0.25
        elif total_mentions >= 3:
            score += 0.1

        # Multiple independent edges
        if num_edges >= 3:
            score += 0.2
        elif num_edges >= 1:
            score += 0.1

        return min(score, 1.0)


# ==================== PRIVATE ACCOUNT ANALYZER (Orchestrator) ====================

class PrivateAccountAnalyzer:
    """
    Orchestrator: Analyze a private Instagram account via indirect interactions.

    Uses the hybrid client to fetch public data, then builds a network
    graph to infer properties of the private account.
    """

    def __init__(self, client):
        """
        Args:
            client: HybridInstagramClient instance
        """
        self.client = client
        self.comment_scraper = CommentScraper(
            client.session,
            client._make_request,
            client.cookies,
        )
        self.mention_extractor = MentionExtractor()
        self.inference_engine = NetworkInferenceEngine()

    def analyze(
        self,
        target_username: str,
        seed_users: Optional[List[str]] = None,
        depth: int = 2,
        posts_per_user: int = 20,
        comments_per_post: int = 50,
    ) -> PrivateAccountReport:
        """
        Full analysis pipeline for a private account.

        Args:
            target_username: The private account to analyze
            seed_users: Known public accounts connected to target
            depth: How many hops to search (1=direct, 2=friends of friends)
            posts_per_user: Posts to scan per seed user
            comments_per_post: Comments to fetch per post

        Returns:
            PrivateAccountReport with inferred data
        """
        print(f"\n{'='*60}")
        print(f"  🔒 Anomaly Detection: @{target_username}")
        print(f"  Depth: {depth}, Seed users: {len(seed_users) if seed_users else 'auto-discover'}")
        print(f"{'='*60}")

        # Step 1: Check if target is actually private
        print(f"\n  [1/5] Checking target profile...")
        target_profile = self.client.get_profile(target_username)

        is_private = True
        if target_profile:
            is_private = target_profile.is_private
            if not is_private:
                print(f"  [!] @{target_username} is PUBLIC — anomaly detection not needed")
                print(f"  [*] Running analysis anyway for network insights...")

        # Step 2: Discover seed users if not provided
        print(f"\n  [2/5] Discovering connected public accounts...")
        if not seed_users:
            seed_users = self._discover_seed_users(target_username)

        if not seed_users:
            print("  [!] No seed users found. Cannot analyze.")
            return PrivateAccountReport(
                username=target_username,
                is_private=is_private,
                ghost_score=1.0,
            )

        print(f"  [✓] Found {len(seed_users)} seed users: {', '.join(seed_users[:5])}")

        # Step 3: Scrape posts and comments from seed users
        print(f"\n  [3/5] Scraping posts + comments from seed users...")
        all_posts = []
        mentioner_profiles: Dict[str, InstagramProfile] = {}

        for username in seed_users[:10]:  # Cap at 10 seed users
            print(f"\n  ── @{username} ──")

            profile = self.client.get_profile(username)
            if profile:
                mentioner_profiles[username] = profile

            posts = self.client.get_posts(username, count=posts_per_user)
            if not posts:
                continue

            all_posts.extend(posts)

            # Extract mentions from captions
            self.mention_extractor.process_posts(posts, username, profile)

            # Fetch comments for posts that mention target
            relevant_posts = [
                p for p in posts
                if target_username.lower() in (p.caption or '').lower()
                or p.comments > 5
            ]

            if relevant_posts:
                print(f"  [💬] Fetching comments from {len(relevant_posts)} relevant posts...")
                comments_map = self.comment_scraper.fetch_comments_batch(
                    relevant_posts[:5],  # Cap per user
                    count_per_post=comments_per_post,
                )

                all_comments = []
                for shortcode, comments in comments_map.items():
                    all_comments.extend(comments)

                self.mention_extractor.process_comments(
                    all_comments,
                    mentioner_profiles,
                )

            smart_delay(2.0, 4.0)

        # Step 4: Build network and score
        print(f"\n  [4/5] Building network graph...")

        edges = self.mention_extractor.get_edges_for(target_username)
        mentioners = self.mention_extractor.get_mentioners(target_username)
        total_mentions = self.mention_extractor.get_total_mentions(target_username)

        print(f"  [✓] {len(edges)} edges, {len(mentioners)} unique mentioners, "
              f"{total_mentions} total mentions")

        # Estimate followers
        estimated_followers, confidence = self.inference_engine.estimate_followers(
            edges, mentioners, mentioner_profiles,
        )

        # Network density
        network_density = self.inference_engine.calculate_network_density(
            mentioners, self.mention_extractor.mention_map,
        )

        # Activity & ghost scores
        activity_score = self.inference_engine.calculate_activity_score(edges)
        ghost_score = self.inference_engine.calculate_ghost_score(
            total_mentions, len(mentioners),
        )

        # Common hashtags
        common_hashtags = self.inference_engine.find_common_hashtags(all_posts)

        # Step 5: Build report
        print(f"\n  [5/5] Generating report...")

        report = PrivateAccountReport(
            username=target_username,
            is_private=is_private,
            estimated_followers=estimated_followers,
            estimated_following=0,  # harder to infer
            confidence=confidence,
            mentioning_users=mentioners,
            mention_edges=edges,
            total_mentions=total_mentions,
            unique_mentioners=len(mentioners),
            activity_score=activity_score,
            network_density=network_density,
            ghost_score=ghost_score,
            connected_public_accounts=seed_users,
            common_hashtags=common_hashtags,
        )

        self.print_report(report)
        return report

    def _discover_seed_users(self, target_username: str) -> List[str]:
        """
        Auto-discover public accounts that might be connected to the target.

        Strategy: search for the target username and look at related profiles.
        """
        seed_users = []

        # Strategy 1: Search for the username
        try:
            results = self.client.search_users(target_username)
            for result in results:
                username = result.get('username', '')
                is_private = result.get('is_private', True)
                if username and username != target_username and not is_private:
                    seed_users.append(username)
                    if len(seed_users) >= 5:
                        break
        except Exception as e:
            print(f"  [!] Search error: {e}")

        return seed_users

    @staticmethod
    def print_report(report: PrivateAccountReport):
        """Print formatted anomaly detection report"""
        priv_tag = "🔒 PRIVATE" if report.is_private else "🔓 PUBLIC"

        # Confidence indicator
        if report.confidence >= 0.7:
            conf_bar = "████████░░"
            conf_label = "HIGH"
        elif report.confidence >= 0.4:
            conf_bar = "█████░░░░░"
            conf_label = "MEDIUM"
        else:
            conf_bar = "██░░░░░░░░"
            conf_label = "LOW"

        # Ghost indicator
        if report.ghost_score >= 0.8:
            ghost_label = "👻 Ghost (minimal public footprint)"
        elif report.ghost_score >= 0.5:
            ghost_label = "🌫️  Semi-visible"
        else:
            ghost_label = "👀 Active in public sphere"

        print(f"""
╔══════════════════════════════════════════════════════════════╗
║   🔍 Private Account Anomaly Report                         ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Target:   @{report.username:<46} ║
║  Status:   {priv_tag:<47} ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  📊 Inferred Statistics                                      ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Est. Followers:  {report.estimated_followers:<8} (confidence: {report.confidence:.0%})          ║
║  Confidence:      [{conf_bar}] {conf_label:<7}               ║
║                                                              ║
║  Total Mentions:  {report.total_mentions:<40} ║
║  Unique Sources:  {report.unique_mentioners:<40} ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  🕸️  Network Analysis                                        ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Activity Score:  {report.activity_score:.2f}  (0=silent, 1=very active)          ║
║  Network Density: {report.network_density:.2f}  (0=sparse, 1=tight group)         ║
║  Ghost Score:     {report.ghost_score:.2f}  {ghost_label:<27} ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝""")

        # Connected accounts
        if report.connected_public_accounts:
            print(f"\n  🔗 Connected Public Accounts:")
            for user in report.connected_public_accounts[:10]:
                print(f"    → @{user}")

        # Top mentioners with weight
        if report.mention_edges:
            print(f"\n  📢 Top Mentioners:")
            sorted_edges = sorted(report.mention_edges, key=lambda e: e.weight, reverse=True)
            for edge in sorted_edges[:10]:
                bar_len = min(int(edge.weight * 2), 20)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                print(f"    @{edge.source_user:<20} [{bar}] "
                      f"×{edge.frequency} (w={edge.weight:.1f})")

        # Common hashtags
        if report.common_hashtags:
            tags = " ".join(f"#{t}" for t in report.common_hashtags[:10])
            print(f"\n  #️⃣  Common Hashtags: {tags}")

        print()
"""Module for anomaly detection algorithm"""
