"""
Virality Prediction Module for TikTok AI
Deep learning model for predicting viral potential
"""

import math
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ==================== DATA CLASSES ====================

@dataclass
class ViralityFeatures:
    """Features extracted for virality prediction"""
    # Content features
    video_duration: float = 0.0
    has_music: bool = False
    has_text_overlay: bool = False
    face_count: int = 0
    object_diversity: int = 0
    
    # Engagement pattern features
    early_like_rate: float = 0.0  # Likes in first hour
    early_comment_rate: float = 0.0
    early_share_rate: float = 0.0
    
    # Account features
    follower_count: int = 0
    following_count: int = 0
    total_likes: int = 0
    video_count: int = 0
    avg_engagement_rate: float = 0.0
    
    # Temporal features
    hour_of_day: int = 0
    day_of_week: int = 0
    is_trending_time: bool = False
    
    # Content quality features
    caption_length: int = 0
    hashtag_count: int = 0
    mention_count: int = 0
    has_call_to_action: bool = False
    sentiment_score: float = 0.0
    
    def to_vector(self) -> List[float]:
        """Convert to feature vector"""
        return [
            self.video_duration,
            1.0 if self.has_music else 0.0,
            1.0 if self.has_text_overlay else 0.0,
            float(self.face_count),
            float(self.object_diversity),
            self.early_like_rate,
            self.early_comment_rate,
            self.early_share_rate,
            math.log1p(self.follower_count),
            math.log1p(self.following_count),
            math.log1p(self.total_likes),
            float(self.video_count),
            self.avg_engagement_rate,
            float(self.hour_of_day) / 24.0,
            float(self.day_of_week) / 7.0,
            1.0 if self.is_trending_time else 0.0,
            float(self.caption_length) / 150.0,  # Normalize to typical max
            float(self.hashtag_count) / 10.0,
            float(self.mention_count) / 5.0,
            1.0 if self.has_call_to_action else 0.0,
            (self.sentiment_score + 1) / 2.0  # Normalize -1 to 1 → 0 to 1
        ]


@dataclass
class ViralityScore:
    """Virality prediction result"""
    probability: float  # 0-1
    confidence: float  # 0-1
    tier: str  # 'low', 'medium', 'high', 'viral'
    key_factors: List[Tuple[str, float]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    @classmethod
    def from_probability(cls, prob: float, features: ViralityFeatures) -> 'ViralityScore':
        """Create score from probability"""
        if prob >= 0.8:
            tier = "viral"
        elif prob >= 0.5:
            tier = "high"
        elif prob >= 0.25:
            tier = "medium"
        else:
            tier = "low"
        
        # Determine key factors
        key_factors = []
        if features.face_count > 0:
            key_factors.append(("face_presence", 0.1))
        if features.has_music:
            key_factors.append(("trending_audio", 0.15))
        if features.early_like_rate > 0.1:
            key_factors.append(("early_engagement", 0.2))
        if features.hashtag_count >= 3:
            key_factors.append(("hashtag_optimization", 0.1))
        
        # Generate suggestions
        suggestions = []
        if not features.has_music:
            suggestions.append("Add trending audio/music")
        if features.hashtag_count < 3:
            suggestions.append("Use 3-5 relevant hashtags")
        if features.video_duration > 60:
            suggestions.append("Consider shorter videos (15-30s)")
        if not features.has_call_to_action:
            suggestions.append("Add call-to-action in caption")
        
        return cls(
            probability=prob,
            confidence=0.7,  # Base confidence
            tier=tier,
            key_factors=key_factors,
            suggestions=suggestions
        )


# ==================== NEURAL NETWORK MODEL ====================

if HAS_TORCH:
    class ViralityNetwork(nn.Module):
        """Neural network for virality prediction"""
        
        def __init__(self, input_size: int = 21):
            super().__init__()
            
            self.network = nn.Sequential(
                nn.Linear(input_size, 256),
                nn.BatchNorm1d(256),
                nn.ReLU(),
                nn.Dropout(0.3),
                
                nn.Linear(256, 128),
                nn.BatchNorm1d(128),
                nn.ReLU(),
                nn.Dropout(0.3),
                
                nn.Linear(128, 64),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                
                nn.Linear(64, 1),
                nn.Sigmoid()
            )
        
        def forward(self, x):
            return self.network(x)


# ==================== FEATURE EXTRACTOR ====================

class FeatureExtractor:
    """
    Extract virality features from video and metadata
    """
    
    # Call-to-action patterns
    CTA_PATTERNS = [
        'follow', 'like', 'share', 'comment', 'duet', 'stitch',
        'tag', 'subscribe', 'click', 'link in bio', 'dm',
        'ikuti', 'suka', 'bagikan', 'komentar'
    ]
    
    # Peak TikTok hours (UTC)
    TRENDING_HOURS = [11, 12, 13, 19, 20, 21, 22]
    
    def extract(
        self,
        video_metadata: Dict,
        profile: Dict,
        vision_result: Optional[Dict] = None,
        nlp_result: Optional[Dict] = None
    ) -> ViralityFeatures:
        """Extract all features"""
        now = datetime.now()
        
        features = ViralityFeatures(
            # Video features
            video_duration=video_metadata.get('duration', 0),
            has_music=bool(video_metadata.get('music_id')),
            
            # Account features
            follower_count=profile.get('follower_count', 0),
            following_count=profile.get('following_count', 0),
            total_likes=profile.get('total_likes', 0),
            video_count=profile.get('video_count', 0),
            
            # Temporal
            hour_of_day=now.hour,
            day_of_week=now.weekday(),
            is_trending_time=now.hour in self.TRENDING_HOURS,
            
            # Caption analysis
            caption_length=len(video_metadata.get('description', '')),
            hashtag_count=len(video_metadata.get('hashtags', [])),
            mention_count=video_metadata.get('description', '').count('@'),
            has_call_to_action=self._has_cta(video_metadata.get('description', ''))
        )
        
        # Calculate engagement rate
        if features.follower_count > 0 and features.video_count > 0:
            features.avg_engagement_rate = features.total_likes / (features.follower_count * features.video_count)
        
        # Add vision features if available
        if vision_result:
            features.face_count = vision_result.get('face_count', 0)
            features.object_diversity = vision_result.get('unique_objects', 0)
            features.has_text_overlay = vision_result.get('has_text', False)
        
        # Add NLP features if available
        if nlp_result:
            features.sentiment_score = nlp_result.get('sentiment_score', 0)
        
        return features
    
    def _has_cta(self, text: str) -> bool:
        """Check if text contains call-to-action"""
        text_lower = text.lower()
        return any(cta in text_lower for cta in self.CTA_PATTERNS)


# ==================== VIRALITY PREDICTOR ====================

class ViralityPredictor:
    """
    Predict virality potential using ML or heuristics
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self._model = None
        self._initialized = False
        self.feature_extractor = FeatureExtractor()
    
    def _initialize(self):
        """Load model"""
        if self._initialized:
            return
        
        if HAS_TORCH and self.model_path:
            try:
                self._model = ViralityNetwork()
                self._model.load_state_dict(torch.load(self.model_path))
                self._model.eval()
                print(f"[VIRALITY] Loaded model: {self.model_path}")
            except Exception as e:
                print(f"[VIRALITY] Failed to load model: {e}")
        
        self._initialized = True
    
    def predict(
        self,
        video_metadata: Dict,
        profile: Dict,
        vision_result: Optional[Dict] = None,
        nlp_result: Optional[Dict] = None
    ) -> ViralityScore:
        """Predict virality for a video"""
        self._initialize()
        
        # Extract features
        features = self.feature_extractor.extract(
            video_metadata, profile, vision_result, nlp_result
        )
        
        # Use model if available
        if self._model is not None and HAS_TORCH:
            return self._ml_predict(features)
        else:
            return self._heuristic_predict(features)
    
    def _ml_predict(self, features: ViralityFeatures) -> ViralityScore:
        """ML-based prediction"""
        feature_vector = features.to_vector()
        
        with torch.no_grad():
            x = torch.tensor([feature_vector], dtype=torch.float32)
            probability = self._model(x).item()
        
        return ViralityScore.from_probability(probability, features)
    
    def _heuristic_predict(self, features: ViralityFeatures) -> ViralityScore:
        """Heuristic-based prediction when model unavailable"""
        score = 0.2  # Base score
        
        # Content factors
        if features.has_music:
            score += 0.1
        if 15 <= features.video_duration <= 30:
            score += 0.1
        elif 30 < features.video_duration <= 60:
            score += 0.05
        if features.face_count > 0:
            score += 0.1
        if features.has_text_overlay:
            score += 0.05
        
        # Caption optimization
        if 3 <= features.hashtag_count <= 5:
            score += 0.1
        if features.has_call_to_action:
            score += 0.05
        if 50 <= features.caption_length <= 150:
            score += 0.05
        
        # Account strength
        if features.follower_count > 10000:
            score += 0.15
        elif features.follower_count > 1000:
            score += 0.1
        elif features.follower_count > 100:
            score += 0.05
        
        if features.avg_engagement_rate > 0.1:
            score += 0.1
        
        # Timing
        if features.is_trending_time:
            score += 0.05
        
        # Sentiment
        if features.sentiment_score > 0.5:
            score += 0.05
        
        probability = min(1.0, score)
        return ViralityScore.from_probability(probability, features)
    
    def predict_batch(
        self,
        videos: List[Dict],
        profile: Dict
    ) -> List[ViralityScore]:
        """Predict virality for multiple videos"""
        return [
            self.predict(video, profile)
            for video in videos
        ]
    
    def compare_videos(
        self,
        videos: List[Dict],
        profile: Dict
    ) -> Dict[str, Any]:
        """Compare virality potential across videos"""
        scores = self.predict_batch(videos, profile)
        
        ranked = sorted(
            zip(videos, scores),
            key=lambda x: x[1].probability,
            reverse=True
        )
        
        return {
            "ranking": [
                {
                    "video_id": v.get('id', i),
                    "probability": s.probability,
                    "tier": s.tier
                }
                for i, (v, s) in enumerate(ranked)
            ],
            "best": ranked[0] if ranked else None,
            "average_probability": sum(s.probability for s in scores) / len(scores) if scores else 0
        }


# ==================== TRAINING UTILITIES ====================

class ViralityTrainer:
    """
    Train virality prediction model
    """
    
    def __init__(self, learning_rate: float = 0.001):
        self.learning_rate = learning_rate
        self.model = None
        self.feature_extractor = FeatureExtractor()
    
    def prepare_training_data(
        self,
        videos: List[Dict],
        profiles: Dict[str, Dict],
        labels: List[int]  # 0 = not viral, 1 = viral
    ) -> Tuple[List[List[float]], List[int]]:
        """Prepare training data"""
        X = []
        y = []
        
        for video, label in zip(videos, labels):
            username = video.get('author', {}).get('username', '')
            profile = profiles.get(username, {})
            
            features = self.feature_extractor.extract(video, profile)
            X.append(features.to_vector())
            y.append(label)
        
        return X, y
    
    def train(
        self,
        X: List[List[float]],
        y: List[int],
        epochs: int = 100,
        batch_size: int = 32
    ) -> Dict[str, float]:
        """Train the model"""
        if not HAS_TORCH:
            print("[VIRALITY] PyTorch required for training")
            return {}
        
        # Convert to tensors
        X_tensor = torch.tensor(X, dtype=torch.float32)
        y_tensor = torch.tensor(y, dtype=torch.float32).unsqueeze(1)
        
        # Create model
        self.model = ViralityNetwork(input_size=len(X[0]))
        
        # Training setup
        criterion = nn.BCELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        
        # Training loop
        self.model.train()
        losses = []
        
        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = self.model(X_tensor)
            loss = criterion(outputs, y_tensor)
            loss.backward()
            optimizer.step()
            
            losses.append(loss.item())
            
            if epoch % 10 == 0:
                print(f"[TRAIN] Epoch {epoch}, Loss: {loss.item():.4f}")
        
        return {
            "final_loss": losses[-1],
            "epochs": epochs,
            "samples": len(X)
        }
    
    def save_model(self, path: str):
        """Save trained model"""
        if self.model and HAS_TORCH:
            torch.save(self.model.state_dict(), path)
            print(f"[VIRALITY] Model saved: {path}")
    
    def evaluate(self, X: List[List[float]], y: List[int]) -> Dict[str, float]:
        """Evaluate model"""
        if not self.model or not HAS_TORCH:
            return {}
        
        self.model.eval()
        X_tensor = torch.tensor(X, dtype=torch.float32)
        
        with torch.no_grad():
            predictions = self.model(X_tensor).numpy().flatten()
        
        # Calculate metrics
        binary_preds = (predictions > 0.5).astype(int)
        accuracy = (binary_preds == y).mean()
        
        # Precision, recall
        true_pos = ((binary_preds == 1) & (y == 1)).sum()
        pred_pos = (binary_preds == 1).sum()
        actual_pos = (y == 1).sum()
        
        precision = true_pos / pred_pos if pred_pos > 0 else 0
        recall = true_pos / actual_pos if actual_pos > 0 else 0
        
        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1": 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0
        }
