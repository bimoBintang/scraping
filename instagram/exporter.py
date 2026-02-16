"""
Instagram Data Exporter
Export profiles, posts, and clusters to CSV, JSON, and Excel.
"""

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .models import InstagramProfile, InstagramPost, UserCluster


class InstagramExporter:
    """
    Export Instagram data to multiple formats.
    
    Usage:
        exporter = InstagramExporter(output_dir="output")
        exporter.to_json(profiles, "profiles.json")
        exporter.to_csv(profiles, "profiles.csv")
        exporter.posts_to_csv(posts, "posts.csv")
    """
    
    def __init__(self, output_dir: str = "."):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    # ==================== PROFILE EXPORT ====================
    
    def profiles_to_json(self, profiles: List[InstagramProfile], filename: str = "instagram_profiles.json") -> str:
        """Export profiles to JSON"""
        filepath = self.output_dir / filename
        data = {
            'exported_at': datetime.now().isoformat(),
            'count': len(profiles),
            'profiles': [p.to_dict() for p in profiles],
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  [+] Profiles exported: {filepath}")
        return str(filepath)
    
    def profiles_to_csv(self, profiles: List[InstagramProfile], filename: str = "instagram_profiles.csv") -> str:
        """Export profiles to CSV"""
        filepath = self.output_dir / filename
        
        if not profiles:
            print("  [!] No profiles to export")
            return ""
        
        fieldnames = [
            'username', 'full_name', 'bio', 'followers', 'following',
            'post_count', 'is_private', 'is_verified', 'is_business',
            'category', 'external_url', 'user_id',
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for profile in profiles:
                row = {k: getattr(profile, k, '') for k in fieldnames}
                writer.writerow(row)
        
        print(f"  [+] Profiles CSV exported: {filepath}")
        return str(filepath)
    
    # ==================== POSTS EXPORT ====================
    
    def posts_to_json(self, posts: List[InstagramPost], username: str = "", filename: Optional[str] = None) -> str:
        """Export posts to JSON"""
        if not filename:
            filename = f"instagram_{username}_posts.json" if username else "instagram_posts.json"
        
        filepath = self.output_dir / filename
        data = {
            'exported_at': datetime.now().isoformat(),
            'username': username,
            'count': len(posts),
            'posts': [p.to_dict() for p in posts],
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  [+] Posts exported: {filepath}")
        return str(filepath)
    
    def posts_to_csv(self, posts: List[InstagramPost], username: str = "", filename: Optional[str] = None) -> str:
        """Export posts to CSV"""
        if not filename:
            filename = f"instagram_{username}_posts.csv" if username else "instagram_posts.csv"
        
        filepath = self.output_dir / filename
        
        if not posts:
            print("  [!] No posts to export")
            return ""
        
        fieldnames = [
            'shortcode', 'url', 'post_type', 'caption', 'likes',
            'comments', 'timestamp', 'is_video', 'video_views',
            'hashtags', 'location_name',
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for post in posts:
                row = {
                    'shortcode': post.shortcode,
                    'url': post.url,
                    'post_type': post.post_type,
                    'caption': post.caption[:200] if post.caption else '',
                    'likes': post.likes,
                    'comments': post.comments,
                    'timestamp': post.timestamp,
                    'is_video': post.is_video,
                    'video_views': post.video_views,
                    'hashtags': ', '.join(post.hashtags),
                    'location_name': post.location.get('name', '') if post.location else '',
                }
                writer.writerow(row)
        
        print(f"  [+] Posts CSV exported: {filepath}")
        return str(filepath)
    
    # ==================== CLUSTER EXPORT ====================
    
    def clusters_to_json(self, clusters: List[UserCluster], filename: str = "instagram_clusters.json") -> str:
        """Export location clusters to JSON"""
        filepath = self.output_dir / filename
        data = {
            'exported_at': datetime.now().isoformat(),
            'count': len(clusters),
            'clusters': [c.to_dict() for c in clusters],
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  [+] Clusters exported: {filepath}")
        return str(filepath)
    
    # ==================== COMPARISON REPORT ====================
    
    def comparison_report(self, profiles: List[InstagramProfile], filename: str = "instagram_comparison.txt") -> str:
        """Generate a text comparison report for multiple profiles"""
        filepath = self.output_dir / filename
        
        lines = [
            "=" * 70,
            "  INSTAGRAM PROFILE COMPARISON REPORT",
            f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 70,
            "",
        ]
        
        if not profiles:
            lines.append("  No profiles to compare.")
        else:
            # Header
            lines.append(f"  {'Username':<20} {'Followers':>12} {'Following':>12} {'Posts':>10} {'V':>3} {'P':>3}")
            lines.append("  " + "-" * 65)
            
            for p in sorted(profiles, key=lambda x: x.followers, reverse=True):
                stats = p.formatted_stats()
                v = "✓" if p.is_verified else " "
                priv = "🔒" if p.is_private else " "
                lines.append(f"  @{p.username:<19} {stats['followers']:>12} {stats['following']:>12} {stats['posts']:>10} {v:>3} {priv:>3}")
            
            lines.append("")
            lines.append(f"  Total profiles: {len(profiles)}")
            
            # Top stats
            most_followers = max(profiles, key=lambda x: x.followers)
            most_posts = max(profiles, key=lambda x: x.post_count)
            lines.append(f"  Most followers: @{most_followers.username} ({most_followers.formatted_stats()['followers']})")
            lines.append(f"  Most posts: @{most_posts.username} ({most_posts.formatted_stats()['posts']})")
        
        lines.append("\n" + "=" * 70)
        
        report = "\n".join(lines)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"  [+] Comparison report: {filepath}")
        return str(filepath)
    
    # ==================== EXCEL (OPTIONAL) ====================
    
    def to_excel(self, profiles: List[InstagramProfile], posts: Optional[List[InstagramPost]] = None, filename: str = "instagram_data.xlsx") -> str:
        """Export to Excel with multiple sheets (requires openpyxl)"""
        try:
            from openpyxl import Workbook
        except ImportError:
            print("  [!] openpyxl not installed. Use: pip install openpyxl")
            # Fallback to CSV
            return self.profiles_to_csv(profiles)
        
        filepath = self.output_dir / filename
        wb = Workbook()
        
        # Sheet 1: Profiles
        ws1 = wb.active
        ws1.title = "Profiles"
        headers = ['Username', 'Full Name', 'Followers', 'Following', 'Posts', 'Bio', 'Verified', 'Private', 'Business', 'Category', 'URL']
        ws1.append(headers)
        
        for p in profiles:
            ws1.append([
                p.username, p.full_name, p.followers, p.following,
                p.post_count, p.bio[:100], p.is_verified, p.is_private,
                p.is_business, p.category, p.external_url,
            ])
        
        # Sheet 2: Posts (if provided)
        if posts:
            ws2 = wb.create_sheet("Posts")
            post_headers = ['Shortcode', 'Type', 'Caption', 'Likes', 'Comments', 'Video Views', 'Hashtags', 'URL']
            ws2.append(post_headers)
            
            for post in posts:
                ws2.append([
                    post.shortcode, post.post_type, post.caption[:100],
                    post.likes, post.comments, post.video_views,
                    ', '.join(post.hashtags), post.url,
                ])
        
        wb.save(filepath)
        print(f"  [+] Excel exported: {filepath}")
        return str(filepath)
