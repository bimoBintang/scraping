"""
Cross-Modal Fusion Module for TikTok AI
Combine vision, audio, and text features for unified analysis
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
class ModalityFeatures:
    """Features from a single modality"""
    modality: str  # 'vision', 'audio', 'text'
    features: List[float]
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FusedFeatures:
    """Combined features from all modalities"""
    combined_vector: List[float]
    modalities_used: List[str]
    fusion_method: str
    confidence: float = 0.0
    attention_weights: Dict[str, float] = field(default_factory=dict)


@dataclass
class CrossModalResult:
    """Cross-modal analysis result"""
    fused_features: FusedFeatures
    consistency_score: float  # How consistent are modalities
    dominant_modality: str
    cross_correlations: Dict[Tuple[str, str], float] = field(default_factory=dict)
    insights: List[str] = field(default_factory=list)


# ==================== FEATURE EXTRACTORS ====================

class VisionFeatureExtractor:
    """Extract normalized features from vision analysis"""
    
    FEATURE_SIZE = 64
    
    def extract(self, vision_result: Dict) -> ModalityFeatures:
        """Extract vision features"""
        features = []
        
        # Object-based features
        objects = vision_result.get('objects', [])
        object_counts = {}
        for obj in objects:
            label = obj.get('label', 'unknown')
            object_counts[label] = object_counts.get(label, 0) + 1
        
        # Top object categories (normalized)
        top_objects = ['person', 'face', 'phone', 'food', 'animal']
        for obj_type in top_objects:
            features.append(min(object_counts.get(obj_type, 0) / 10.0, 1.0))
        
        # Face features
        face_count = vision_result.get('face_count', 0)
        features.append(min(face_count / 5.0, 1.0))
        
        # Scene features (simplified)
        scene = vision_result.get('primary_scene', 'unknown')
        scene_encoding = {
            'indoor': 0.2, 'outdoor': 0.4, 'nature': 0.6,
            'studio': 0.8, 'unknown': 0.5
        }
        features.append(scene_encoding.get(scene, 0.5))
        
        # Has text overlay
        features.append(1.0 if vision_result.get('has_text', False) else 0.0)
        
        # Pad to fixed size
        while len(features) < self.FEATURE_SIZE:
            features.append(0.0)
        
        return ModalityFeatures(
            modality='vision',
            features=features[:self.FEATURE_SIZE],
            confidence=0.8,
            metadata={'object_count': len(objects), 'face_count': face_count}
        )


class AudioFeatureExtractor:
    """Extract normalized features from audio analysis"""
    
    FEATURE_SIZE = 64
    
    def extract(self, audio_result: Dict) -> ModalityFeatures:
        """Extract audio features"""
        features = []
        
        # Has music
        features.append(1.0 if audio_result.get('has_music', False) else 0.0)
        
        # Has speech
        features.append(1.0 if audio_result.get('has_speech', False) else 0.0)
        
        # Tempo (normalized)
        tempo = audio_result.get('tempo', 120) / 200.0
        features.append(min(tempo, 1.0))
        
        # Energy level
        energy = audio_result.get('energy', 0.5)
        features.append(energy)
        
        # Pad to fixed size
        while len(features) < self.FEATURE_SIZE:
            features.append(0.0)
        
        return ModalityFeatures(
            modality='audio',
            features=features[:self.FEATURE_SIZE],
            confidence=0.7 if audio_result else 0.3,
            metadata=audio_result
        )


class TextFeatureExtractor:
    """Extract normalized features from NLP analysis"""
    
    FEATURE_SIZE = 64
    
    def extract(self, nlp_result: Dict) -> ModalityFeatures:
        """Extract text features"""
        features = []
        
        # Sentiment (normalized -1 to 1 → 0 to 1)
        sentiment = nlp_result.get('sentiment_score', 0)
        features.append((sentiment + 1) / 2)
        
        # Hashtag count (normalized)
        hashtag_count = len(nlp_result.get('hashtags', []))
        features.append(min(hashtag_count / 10.0, 1.0))
        
        # Has trending hashtags
        features.append(1.0 if nlp_result.get('has_trending', False) else 0.0)
        
        # Caption length (normalized)
        caption_len = nlp_result.get('caption_length', 0)
        features.append(min(caption_len / 150.0, 1.0))
        
        # Topic diversity
        topic_count = len(nlp_result.get('topics', []))
        features.append(min(topic_count / 5.0, 1.0))
        
        # Pad to fixed size
        while len(features) < self.FEATURE_SIZE:
            features.append(0.0)
        
        return ModalityFeatures(
            modality='text',
            features=features[:self.FEATURE_SIZE],
            confidence=0.9,
            metadata={'hashtags': hashtag_count, 'sentiment': sentiment}
        )


# ==================== FUSION METHODS ====================

class EarlyFusion:
    """
    Early fusion: concatenate all features
    Simple but preserves all information
    """
    
    def fuse(self, features: List[ModalityFeatures]) -> FusedFeatures:
        """Concatenate all feature vectors"""
        combined = []
        modalities = []
        
        for f in features:
            combined.extend(f.features)
            modalities.append(f.modality)
        
        # Average confidence
        avg_confidence = sum(f.confidence for f in features) / len(features)
        
        return FusedFeatures(
            combined_vector=combined,
            modalities_used=modalities,
            fusion_method='early',
            confidence=avg_confidence
        )


class LateFusion:
    """
    Late fusion: average predictions from each modality
    Good for when modalities are independent
    """
    
    def fuse(self, features: List[ModalityFeatures]) -> FusedFeatures:
        """Average feature vectors"""
        if not HAS_NUMPY:
            return self._simple_fuse(features)
        
        # Pad all to same length
        max_len = max(len(f.features) for f in features)
        padded = []
        
        for f in features:
            vec = f.features + [0.0] * (max_len - len(f.features))
            padded.append(vec)
        
        # Weighted average by confidence
        weights = [f.confidence for f in features]
        weight_sum = sum(weights)
        
        combined = np.zeros(max_len)
        for vec, weight in zip(padded, weights):
            combined += np.array(vec) * weight / weight_sum
        
        return FusedFeatures(
            combined_vector=combined.tolist(),
            modalities_used=[f.modality for f in features],
            fusion_method='late',
            confidence=sum(weights) / len(weights),
            attention_weights={f.modality: w/weight_sum for f, w in zip(features, weights)}
        )
    
    def _simple_fuse(self, features: List[ModalityFeatures]) -> FusedFeatures:
        """Simple fusion without numpy"""
        max_len = max(len(f.features) for f in features)
        combined = [0.0] * max_len
        
        for f in features:
            for i, v in enumerate(f.features):
                combined[i] += v / len(features)
        
        return FusedFeatures(
            combined_vector=combined,
            modalities_used=[f.modality for f in features],
            fusion_method='late',
            confidence=0.7
        )


if HAS_TORCH:
    class AttentionFusion(nn.Module):
        """
        Attention-based fusion
        Learns importance of each modality
        """
        
        def __init__(self, feature_size: int = 64, num_modalities: int = 3):
            super().__init__()
            
            # Attention layers
            self.attention = nn.Sequential(
                nn.Linear(feature_size, 32),
                nn.ReLU(),
                nn.Linear(32, 1)
            )
            
            # Output projection
            self.output = nn.Linear(feature_size * num_modalities, feature_size)
        
        def forward(self, features: List[torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor]:
            """
            Args:
                features: List of [batch, feature_size] tensors
            Returns:
                fused: [batch, feature_size]
                attention_weights: [batch, num_modalities]
            """
            # Calculate attention scores
            scores = []
            for f in features:
                score = self.attention(f)
                scores.append(score)
            
            # Softmax over modalities
            scores = torch.cat(scores, dim=1)
            weights = torch.softmax(scores, dim=1)
            
            # Weighted sum
            stacked = torch.stack(features, dim=2)  # [batch, features, modalities]
            weighted = stacked * weights.unsqueeze(1)
            fused = weighted.sum(dim=2)
            
            return fused, weights


# ==================== CROSS-MODAL ENGINE ====================

class CrossModalFusionEngine:
    """
    Main cross-modal fusion engine
    """
    
    def __init__(self, fusion_method: str = 'late'):
        self.fusion_method = fusion_method
        
        # Feature extractors
        self.vision_extractor = VisionFeatureExtractor()
        self.audio_extractor = AudioFeatureExtractor()
        self.text_extractor = TextFeatureExtractor()
        
        # Fusion methods
        self.early_fusion = EarlyFusion()
        self.late_fusion = LateFusion()
        self.attention_fusion = None
        
        if HAS_TORCH:
            self.attention_fusion = AttentionFusion()
    
    def fuse(
        self,
        vision_result: Optional[Dict] = None,
        audio_result: Optional[Dict] = None,
        nlp_result: Optional[Dict] = None
    ) -> CrossModalResult:
        """Fuse results from all modalities"""
        features = []
        
        # Extract features from available modalities
        if vision_result:
            features.append(self.vision_extractor.extract(vision_result))
        
        if audio_result:
            features.append(self.audio_extractor.extract(audio_result))
        
        if nlp_result:
            features.append(self.text_extractor.extract(nlp_result))
        
        if not features:
            return CrossModalResult(
                fused_features=FusedFeatures([], [], 'none', 0.0),
                consistency_score=0.0,
                dominant_modality='none'
            )
        
        # Apply fusion
        if self.fusion_method == 'early':
            fused = self.early_fusion.fuse(features)
        elif self.fusion_method == 'attention' and self.attention_fusion:
            fused = self._attention_fuse(features)
        else:
            fused = self.late_fusion.fuse(features)
        
        # Calculate cross-modal correlations
        correlations = self._calculate_correlations(features)
        
        # Determine dominant modality
        dominant = max(features, key=lambda f: f.confidence).modality
        
        # Calculate consistency
        consistency = self._calculate_consistency(correlations)
        
        # Generate insights
        insights = self._generate_insights(features, correlations)
        
        return CrossModalResult(
            fused_features=fused,
            consistency_score=consistency,
            dominant_modality=dominant,
            cross_correlations=correlations,
            insights=insights
        )
    
    def _attention_fuse(self, features: List[ModalityFeatures]) -> FusedFeatures:
        """Attention-based fusion using PyTorch"""
        tensors = [torch.tensor([f.features], dtype=torch.float32) for f in features]
        
        with torch.no_grad():
            fused_tensor, weights = self.attention_fusion(tensors)
        
        weight_dict = {
            f.modality: float(weights[0, i])
            for i, f in enumerate(features)
        }
        
        return FusedFeatures(
            combined_vector=fused_tensor[0].tolist(),
            modalities_used=[f.modality for f in features],
            fusion_method='attention',
            confidence=max(f.confidence for f in features),
            attention_weights=weight_dict
        )
    
    def _calculate_correlations(
        self, 
        features: List[ModalityFeatures]
    ) -> Dict[Tuple[str, str], float]:
        """Calculate pairwise correlations between modalities"""
        correlations = {}
        
        for i, f1 in enumerate(features):
            for f2 in features[i+1:]:
                # Simple correlation: cosine similarity
                if HAS_NUMPY:
                    v1 = np.array(f1.features)
                    v2 = np.array(f2.features)
                    
                    # Ensure same length
                    min_len = min(len(v1), len(v2))
                    v1, v2 = v1[:min_len], v2[:min_len]
                    
                    norm1 = np.linalg.norm(v1)
                    norm2 = np.linalg.norm(v2)
                    
                    if norm1 > 0 and norm2 > 0:
                        corr = np.dot(v1, v2) / (norm1 * norm2)
                    else:
                        corr = 0.0
                else:
                    corr = 0.5  # Default
                
                correlations[(f1.modality, f2.modality)] = float(corr)
        
        return correlations
    
    def _calculate_consistency(self, correlations: Dict) -> float:
        """Calculate overall consistency score"""
        if not correlations:
            return 1.0
        
        # Average of all pairwise correlations
        return sum(correlations.values()) / len(correlations)
    
    def _generate_insights(
        self,
        features: List[ModalityFeatures],
        correlations: Dict
    ) -> List[str]:
        """Generate human-readable insights"""
        insights = []
        
        # Check modality availability
        modalities = [f.modality for f in features]
        
        if len(modalities) == 1:
            insights.append(f"Only {modalities[0]} modality available")
        elif len(modalities) == 3:
            insights.append("Full multimodal analysis available")
        
        # Check correlations
        for (m1, m2), corr in correlations.items():
            if corr > 0.8:
                insights.append(f"High consistency between {m1} and {m2}")
            elif corr < 0.3:
                insights.append(f"Low consistency between {m1} and {m2} - may indicate mixed content")
        
        # Check confidence levels
        low_conf = [f.modality for f in features if f.confidence < 0.5]
        if low_conf:
            insights.append(f"Low confidence in {', '.join(low_conf)} analysis")
        
        return insights


# ==================== VALIDATION ====================

class CrossModalValidator:
    """
    Validate consistency across modalities
    """
    
    def validate(
        self,
        vision_result: Optional[Dict],
        audio_result: Optional[Dict],
        nlp_result: Optional[Dict]
    ) -> Dict[str, Any]:
        """Validate cross-modal consistency"""
        issues = []
        
        # Check video-audio sync
        if vision_result and audio_result:
            if vision_result.get('has_speech') and not audio_result.get('has_speech'):
                issues.append("Video shows speaking but audio has no speech detected")
        
        # Check text-vision consistency
        if vision_result and nlp_result:
            vision_objects = set(o.get('label', '') for o in vision_result.get('objects', []))
            text_entities = set(nlp_result.get('entities', []))
            
            # Look for obvious mismatches
            if 'person' in vision_objects and nlp_result.get('sentiment_score', 0) < -0.5:
                issues.append("Negative text sentiment may not match visible content")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "modalities_checked": [
                m for m, v in [
                    ('vision', vision_result),
                    ('audio', audio_result),
                    ('text', nlp_result)
                ] if v
            ]
        }
