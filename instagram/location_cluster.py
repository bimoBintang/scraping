"""
Instagram Location-Based User Clustering — Algorithm 4

Cluster users by their tagged post locations:
1. Collect location_id + coordinates from user posts
2. Build user → locations frequency map
3. Determine primary location per user (most frequent)
4. DBSCAN clustering on user primary locations
5. Reverse geocode cluster centroids → city/country

Uses Haversine distance (no external geo dependency).
Optional scikit-learn for DBSCAN.
"""

import math
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import InstagramPost, LocationPoint, UserCluster


# ==================== HAVERSINE DISTANCE ====================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points on Earth (km).
    Uses the Haversine formula — no external dependencies.
    """
    R = 6371.0  # Earth radius in km
    
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_r) * math.cos(lat2_r) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


# ==================== KNOWN CITIES DATABASE ====================
# Lightweight reverse-geocoding without external API

KNOWN_CITIES = [
    # Indonesia
    {"name": "Jakarta", "country": "Indonesia", "lat": -6.200, "lng": 106.816},
    {"name": "Surabaya", "country": "Indonesia", "lat": -7.250, "lng": 112.750},
    {"name": "Bandung", "country": "Indonesia", "lat": -6.917, "lng": 107.617},
    {"name": "Medan", "country": "Indonesia", "lat": 3.595, "lng": 98.672},
    {"name": "Semarang", "country": "Indonesia", "lat": -6.967, "lng": 110.417},
    {"name": "Yogyakarta", "country": "Indonesia", "lat": -7.797, "lng": 110.370},
    {"name": "Bali", "country": "Indonesia", "lat": -8.340, "lng": 115.092},
    {"name": "Makassar", "country": "Indonesia", "lat": -5.148, "lng": 119.432},
    {"name": "Palembang", "country": "Indonesia", "lat": -2.976, "lng": 104.775},
    {"name": "Malang", "country": "Indonesia", "lat": -7.979, "lng": 112.630},
    # International
    {"name": "Singapore", "country": "Singapore", "lat": 1.352, "lng": 103.820},
    {"name": "Kuala Lumpur", "country": "Malaysia", "lat": 3.139, "lng": 101.687},
    {"name": "Bangkok", "country": "Thailand", "lat": 13.756, "lng": 100.502},
    {"name": "Tokyo", "country": "Japan", "lat": 35.682, "lng": 139.759},
    {"name": "Seoul", "country": "South Korea", "lat": 37.566, "lng": 126.978},
    {"name": "London", "country": "United Kingdom", "lat": 51.507, "lng": -0.128},
    {"name": "New York", "country": "United States", "lat": 40.713, "lng": -74.006},
    {"name": "Los Angeles", "country": "United States", "lat": 34.052, "lng": -118.244},
    {"name": "Dubai", "country": "UAE", "lat": 25.205, "lng": 55.271},
    {"name": "Paris", "country": "France", "lat": 48.857, "lng": 2.352},
    {"name": "Istanbul", "country": "Turkey", "lat": 41.009, "lng": 28.978},
    {"name": "Sydney", "country": "Australia", "lat": -33.869, "lng": 151.209},
    {"name": "Mumbai", "country": "India", "lat": 19.076, "lng": 72.878},
    {"name": "São Paulo", "country": "Brazil", "lat": -23.551, "lng": -46.633},
    {"name": "Manila", "country": "Philippines", "lat": 14.600, "lng": 120.984},
]


def reverse_geocode_simple(lat: float, lng: float, max_distance_km: float = 100) -> Tuple[str, str]:
    """
    Simple reverse geocoding using known cities database.
    Returns (city_name, country_name) or ("Unknown", "Unknown").
    """
    best_city = None
    best_distance = float('inf')
    
    for city in KNOWN_CITIES:
        dist = haversine_distance(lat, lng, city['lat'], city['lng'])
        if dist < best_distance:
            best_distance = dist
            best_city = city
    
    if best_city and best_distance <= max_distance_km:
        return best_city['name'], best_city['country']
    
    return "Unknown", "Unknown"


# ==================== LOCATION CLUSTER ANALYZER ====================

class LocationClusterAnalyzer:
    """
    Cluster users by their tagged post locations.
    
    Usage:
        analyzer = LocationClusterAnalyzer()
        
        # Analyze single user
        location = analyzer.analyze_user(posts)
        
        # Cluster multiple users
        user_locations = {
            "cristiano": analyzer.analyze_user(cr_posts),
            "leomessi": analyzer.analyze_user(messi_posts),
        }
        clusters = analyzer.cluster_users(user_locations)
        
        # Predict location from posts
        prediction = analyzer.predict_location("username", posts)
    """
    
    def __init__(self, eps_km: float = 50, min_samples: int = 2):
        """
        Args:
            eps_km: DBSCAN epsilon in kilometers (max distance between points in cluster)
            min_samples: Minimum points to form a cluster
        """
        self.eps_km = eps_km
        self.min_samples = min_samples
    
    def extract_locations(self, posts: List[InstagramPost]) -> List[LocationPoint]:
        """Extract location data from posts"""
        locations = []
        
        for post in posts:
            if not post.location:
                continue
            
            loc = post.location
            lat = loc.get('lat', 0) or loc.get('latitude', 0)
            lng = loc.get('lng', 0) or loc.get('longitude', 0)
            
            if lat == 0 and lng == 0:
                continue
            
            point = LocationPoint(
                location_id=str(loc.get('id', '')),
                name=loc.get('name', 'Unknown'),
                latitude=float(lat),
                longitude=float(lng),
                post_count=1,
            )
            locations.append(point)
        
        return locations
    
    def analyze_user(self, posts: List[InstagramPost]) -> Optional[LocationPoint]:
        """
        Determine user's primary location from their posts.
        Returns the most frequently tagged location.
        """
        locations = self.extract_locations(posts)
        
        if not locations:
            return None
        
        # Group by location_id and count frequency
        loc_counter: Dict[str, List[LocationPoint]] = defaultdict(list)
        for loc in locations:
            loc_counter[loc.location_id].append(loc)
        
        # Find most frequent location
        most_frequent_id = max(loc_counter, key=lambda k: len(loc_counter[k]))
        points = loc_counter[most_frequent_id]
        
        primary = LocationPoint(
            location_id=most_frequent_id,
            name=points[0].name,
            latitude=points[0].latitude,
            longitude=points[0].longitude,
            post_count=len(points),
        )
        
        return primary
    
    def cluster_users(
        self,
        user_locations: Dict[str, Optional[LocationPoint]]
    ) -> List[UserCluster]:
        """
        Cluster users by geographic location using DBSCAN.
        
        Args:
            user_locations: Dict of username → LocationPoint (primary location)
            
        Returns:
            List of UserCluster with geographic info
        """
        # Filter out None locations
        valid_users = {
            user: loc for user, loc in user_locations.items()
            if loc is not None and loc.latitude != 0
        }
        
        if not valid_users:
            print("  [!] No valid locations for clustering")
            return []
        
        usernames = list(valid_users.keys())
        points = [(valid_users[u].latitude, valid_users[u].longitude) for u in usernames]
        
        # Try scikit-learn DBSCAN first
        try:
            labels = self._dbscan_sklearn(points)
        except ImportError:
            # Fallback to simple DBSCAN
            labels = self._dbscan_simple(points)
        
        # Build clusters
        clusters_map: Dict[int, List[int]] = defaultdict(list)
        for idx, label in enumerate(labels):
            clusters_map[label].append(idx)
        
        clusters = []
        for cluster_id, indices in sorted(clusters_map.items()):
            if cluster_id == -1:
                continue  # Skip noise
            
            cluster_users = [usernames[i] for i in indices]
            cluster_points = [points[i] for i in indices]
            
            # Calculate centroid
            centroid_lat = sum(p[0] for p in cluster_points) / len(cluster_points)
            centroid_lng = sum(p[1] for p in cluster_points) / len(cluster_points)
            
            # Reverse geocode centroid
            city, country = reverse_geocode_simple(centroid_lat, centroid_lng)
            
            # Calculate confidence
            total_posts = sum(valid_users[u].post_count for u in cluster_users)
            confidence = min(1.0, total_posts / (len(cluster_users) * 3))
            
            cluster = UserCluster(
                cluster_id=cluster_id,
                users=cluster_users,
                centroid=(centroid_lat, centroid_lng),
                city=city,
                country=country,
                confidence=round(confidence, 2),
                location_count=total_posts,
            )
            clusters.append(cluster)
        
        # Handle noise points (unclustered users)
        noise_indices = clusters_map.get(-1, [])
        for idx in noise_indices:
            user = usernames[idx]
            loc = valid_users[user]
            city, country = reverse_geocode_simple(loc.latitude, loc.longitude)
            
            clusters.append(UserCluster(
                cluster_id=-1,
                users=[user],
                centroid=(loc.latitude, loc.longitude),
                city=city,
                country=country,
                confidence=round(min(1.0, loc.post_count / 3), 2),
                location_count=loc.post_count,
            ))
        
        return sorted(clusters, key=lambda c: len(c.users), reverse=True)
    
    def predict_location(
        self,
        username: str,
        posts: List[InstagramPost]
    ) -> Dict:
        """
        Predict user's city/country from their post locations.
        
        Returns:
            Dict with predicted city, country, confidence, and methodology
        """
        locations = self.extract_locations(posts)
        
        if not locations:
            return {
                'username': username,
                'predicted_city': None,
                'predicted_country': None,
                'confidence': 0,
                'methodology': 'No location data available',
            }
        
        # Method 1: Most frequent city
        city_counts: Counter = Counter()
        for loc in locations:
            city, country = reverse_geocode_simple(loc.latitude, loc.longitude)
            if city != "Unknown":
                city_counts[(city, country)] += 1
        
        if not city_counts:
            # Method 2: Average coordinates
            avg_lat = sum(l.latitude for l in locations) / len(locations)
            avg_lng = sum(l.longitude for l in locations) / len(locations)
            city, country = reverse_geocode_simple(avg_lat, avg_lng)
            
            return {
                'username': username,
                'predicted_city': city,
                'predicted_country': country,
                'confidence': round(min(0.5, len(locations) / 10), 2),
                'methodology': 'Average coordinates',
                'data_points': len(locations),
            }
        
        # Most frequent city wins
        (best_city, best_country), count = city_counts.most_common(1)[0]
        total = sum(city_counts.values())
        confidence = round(count / total, 2)
        
        return {
            'username': username,
            'predicted_city': best_city,
            'predicted_country': best_country,
            'confidence': confidence,
            'methodology': 'Frequency-based',
            'data_points': len(locations),
            'top_cities': [
                {'city': c, 'country': co, 'count': n}
                for (c, co), n in city_counts.most_common(5)
            ],
        }
    
    def generate_report(
        self,
        clusters: List[UserCluster],
        user_locations: Dict[str, Optional[LocationPoint]]
    ) -> str:
        """Generate a formatted clustering report"""
        lines = [
            "\n" + "=" * 60,
            "  LOCATION-BASED USER CLUSTERING REPORT",
            "=" * 60,
            f"\n  Total users analyzed: {len(user_locations)}",
            f"  Users with location data: {sum(1 for v in user_locations.values() if v)}",
            f"  Clusters found: {sum(1 for c in clusters if c.cluster_id != -1)}",
            f"  Unclustered users: {sum(1 for c in clusters if c.cluster_id == -1)}",
        ]
        
        for cluster in clusters:
            if cluster.cluster_id == -1:
                label = "UNCLUSTERED"
            else:
                label = f"CLUSTER #{cluster.cluster_id}"
            
            lines.append(f"\n  --- {label} ---")
            lines.append(f"  📍 {cluster.city}, {cluster.country}")
            lines.append(f"  Confidence: {cluster.confidence:.0%}")
            lines.append(f"  Users ({len(cluster.users)}): {', '.join(cluster.users[:10])}")
            if len(cluster.users) > 10:
                lines.append(f"    ... and {len(cluster.users) - 10} more")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
    
    # ==================== DBSCAN IMPLEMENTATIONS ====================
    
    def _dbscan_sklearn(self, points: List[Tuple[float, float]]) -> List[int]:
        """DBSCAN using scikit-learn (preferred if available)"""
        import numpy as np
        from sklearn.cluster import DBSCAN
        
        # Convert to radians for haversine metric
        coords = np.radians(np.array(points))
        
        # DBSCAN with haversine metric
        # eps needs to be in radians: km / Earth_radius
        eps_radians = self.eps_km / 6371.0
        
        db = DBSCAN(
            eps=eps_radians,
            min_samples=self.min_samples,
            metric='haversine',
        )
        
        labels = db.fit_predict(coords)
        return labels.tolist()
    
    def _dbscan_simple(self, points: List[Tuple[float, float]]) -> List[int]:
        """
        Simple DBSCAN implementation using Haversine distance.
        Fallback when scikit-learn is not installed.
        """
        n = len(points)
        labels = [-1] * n
        cluster_id = 0
        visited = set()
        
        for i in range(n):
            if i in visited:
                continue
            
            visited.add(i)
            neighbors = self._get_neighbors(points, i)
            
            if len(neighbors) < self.min_samples:
                continue  # Noise point
            
            # Start new cluster
            labels[i] = cluster_id
            seed_set = list(neighbors)
            
            j = 0
            while j < len(seed_set):
                q = seed_set[j]
                
                if q not in visited:
                    visited.add(q)
                    q_neighbors = self._get_neighbors(points, q)
                    
                    if len(q_neighbors) >= self.min_samples:
                        seed_set.extend(n for n in q_neighbors if n not in visited)
                
                if labels[q] == -1:
                    labels[q] = cluster_id
                
                j += 1
            
            cluster_id += 1
        
        return labels
    
    def _get_neighbors(self, points: List[Tuple[float, float]], idx: int) -> List[int]:
        """Find all points within eps_km of point[idx]"""
        neighbors = []
        lat1, lon1 = points[idx]
        
        for j, (lat2, lon2) in enumerate(points):
            if j == idx:
                continue
            dist = haversine_distance(lat1, lon1, lat2, lon2)
            if dist <= self.eps_km:
                neighbors.append(j)
        
        return neighbors
    
    # ==================== EXPORT ====================
    
    def save_clusters(self, clusters: List[UserCluster], filepath: str):
        """Save clusters to JSON file"""
        data = [c.to_dict() for c in clusters]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  [+] Clusters saved: {filepath}")
