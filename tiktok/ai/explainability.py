"""
Explainable AI Module for TikTok AI
SHAP/LIME integration, feature importance, counterfactuals
"""

import math
from typing import List, Dict, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ==================== DATA CLASSES ====================

@dataclass
class FeatureImportance:
    """Single feature importance"""
    name: str
    importance: float  # Positive = contributes positively
    direction: str  # 'positive', 'negative', 'neutral'
    value: Any = None  # Actual feature value


@dataclass
class Explanation:
    """Model prediction explanation"""
    prediction: Any
    confidence: float
    feature_importances: List[FeatureImportance] = field(default_factory=list)
    top_positive: List[str] = field(default_factory=list)
    top_negative: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class Counterfactual:
    """Counterfactual explanation"""
    original_prediction: Any
    target_prediction: Any
    changes_required: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)  # feature -> (from, to)
    feasibility_score: float = 0.0
    explanation: str = ""


@dataclass
class BiasReport:
    """Bias detection report"""
    metric_name: str
    groups: Dict[str, float] = field(default_factory=dict)
    disparity: float = 0.0
    is_biased: bool = False
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ConfidenceBreakdown:
    """Detailed confidence score breakdown"""
    overall: float
    components: Dict[str, float] = field(default_factory=dict)
    uncertainty_sources: List[str] = field(default_factory=list)


# ==================== FEATURE IMPORTANCE CALCULATOR ====================

class FeatureImportanceCalculator:
    """
    Calculate feature importance for predictions
    """
    
    def __init__(self, feature_names: Optional[List[str]] = None):
        self.feature_names = feature_names or []
    
    def calculate_permutation_importance(
        self,
        model_fn: Callable,
        X: List[List[float]],
        y: List[Any],
        n_repeats: int = 5
    ) -> Dict[str, float]:
        """Calculate permutation importance"""
        if not HAS_NUMPY:
            return {}
        
        X = np.array(X)
        y = np.array(y)
        
        # Baseline score
        baseline_preds = [model_fn(x) for x in X]
        baseline_score = self._accuracy(baseline_preds, y)
        
        importances = {}
        
        for i in range(X.shape[1]):
            scores = []
            
            for _ in range(n_repeats):
                X_permuted = X.copy()
                np.random.shuffle(X_permuted[:, i])
                
                preds = [model_fn(x) for x in X_permuted]
                score = self._accuracy(preds, y)
                scores.append(baseline_score - score)
            
            feature_name = self.feature_names[i] if i < len(self.feature_names) else f"feature_{i}"
            importances[feature_name] = np.mean(scores)
        
        return importances
    
    def _accuracy(self, preds: List, y: np.ndarray) -> float:
        """Calculate accuracy"""
        correct = sum(1 for p, actual in zip(preds, y) if p == actual)
        return correct / len(y) if y.size > 0 else 0


# ==================== SHAP-LIKE EXPLAINER ====================

class SimpleSHAP:
    """
    Simplified SHAP-like explainer
    Uses sampling-based approximation
    """
    
    def __init__(self, model_fn: Callable, feature_names: List[str]):
        self.model_fn = model_fn
        self.feature_names = feature_names
        self.background_data = None
    
    def set_background(self, X: List[List[float]]):
        """Set background data for SHAP calculation"""
        if HAS_NUMPY:
            self.background_data = np.array(X)
    
    def explain(self, instance: List[float], num_samples: int = 100) -> Explanation:
        """Explain a single prediction"""
        prediction = self.model_fn(instance)
        
        if not HAS_NUMPY or self.background_data is None:
            return self._simple_explain(instance, prediction)
        
        # Calculate SHAP-like values using sampling
        shap_values = np.zeros(len(instance))
        
        for _ in range(num_samples):
            # Random permutation of features
            perm = np.random.permutation(len(instance))
            
            # Calculate marginal contributions
            for i, idx in enumerate(perm):
                # With feature
                x_with = self._get_masked_instance(instance, perm[:i+1])
                pred_with = self.model_fn(x_with.tolist())
                
                # Without feature
                x_without = self._get_masked_instance(instance, perm[:i])
                pred_without = self.model_fn(x_without.tolist())
                
                # Contribution
                contrib = self._get_numeric_pred(pred_with) - self._get_numeric_pred(pred_without)
                shap_values[idx] += contrib / num_samples
        
        # Create feature importances
        importances = []
        for i, (name, value) in enumerate(zip(self.feature_names, instance)):
            importance = shap_values[i] if i < len(shap_values) else 0
            direction = 'positive' if importance > 0 else 'negative' if importance < 0 else 'neutral'
            
            importances.append(FeatureImportance(
                name=name,
                importance=float(importance),
                direction=direction,
                value=value
            ))
        
        # Sort by absolute importance
        importances.sort(key=lambda x: abs(x.importance), reverse=True)
        
        # Top positive/negative
        top_positive = [f.name for f in importances if f.importance > 0][:3]
        top_negative = [f.name for f in importances if f.importance < 0][:3]
        
        return Explanation(
            prediction=prediction,
            confidence=0.8,  # Placeholder
            feature_importances=importances,
            top_positive=top_positive,
            top_negative=top_negative,
            summary=self._generate_summary(importances, prediction)
        )
    
    def _simple_explain(self, instance: List[float], prediction: Any) -> Explanation:
        """Simple explanation without background data"""
        importances = []
        
        for i, (name, value) in enumerate(zip(self.feature_names, instance)):
            # Simple heuristic: higher values are more important
            importance = value if isinstance(value, (int, float)) else 0
            direction = 'positive' if importance > 0.5 else 'negative' if importance < 0.5 else 'neutral'
            
            importances.append(FeatureImportance(
                name=name,
                importance=float(importance),
                direction=direction,
                value=value
            ))
        
        importances.sort(key=lambda x: abs(x.importance), reverse=True)
        
        return Explanation(
            prediction=prediction,
            confidence=0.5,
            feature_importances=importances,
            top_positive=[f.name for f in importances[:3]],
            top_negative=[],
            summary="Simple explanation (SHAP values not available)"
        )
    
    def _get_masked_instance(self, instance: List[float], included_indices: np.ndarray) -> np.ndarray:
        """Get instance with only some features from original"""
        if self.background_data is None:
            return np.array(instance)
        
        # Sample from background
        bg_sample = self.background_data[np.random.randint(len(self.background_data))]
        
        # Replace included features with actual values
        result = bg_sample.copy()
        for idx in included_indices:
            if idx < len(instance):
                result[idx] = instance[idx]
        
        return result
    
    def _get_numeric_pred(self, pred: Any) -> float:
        """Convert prediction to numeric value"""
        if isinstance(pred, (int, float)):
            return float(pred)
        elif isinstance(pred, str):
            return 1.0 if pred in ['positive', 'high', 'viral'] else 0.0
        return 0.5
    
    def _generate_summary(self, importances: List[FeatureImportance], prediction: Any) -> str:
        """Generate human-readable summary"""
        top = importances[:3]
        
        parts = []
        for f in top:
            if f.direction == 'positive':
                parts.append(f"'{f.name}' increased the prediction")
            elif f.direction == 'negative':
                parts.append(f"'{f.name}' decreased the prediction")
        
        if parts:
            return f"Prediction: {prediction}. " + "; ".join(parts) + "."
        return f"Prediction: {prediction}."


# ==================== COUNTERFACTUAL GENERATOR ====================

class CounterfactualGenerator:
    """
    Generate counterfactual explanations
    """
    
    def __init__(
        self,
        model_fn: Callable,
        feature_names: List[str],
        feature_ranges: Optional[Dict[str, Tuple[float, float]]] = None
    ):
        self.model_fn = model_fn
        self.feature_names = feature_names
        self.feature_ranges = feature_ranges or {}
    
    def generate(
        self,
        instance: List[float],
        target_class: Any,
        max_changes: int = 3
    ) -> Counterfactual:
        """Generate counterfactual for target class"""
        original_pred = self.model_fn(instance)
        
        if original_pred == target_class:
            return Counterfactual(
                original_prediction=original_pred,
                target_prediction=target_class,
                changes_required={},
                feasibility_score=1.0,
                explanation="Already predicting target class"
            )
        
        # Try different feature modifications
        best_cf = None
        best_score = float('inf')
        
        # Simple greedy approach
        for num_changes in range(1, max_changes + 1):
            cf = self._find_counterfactual(instance, target_class, num_changes)
            if cf and self._count_changes(cf) < best_score:
                best_cf = cf
                best_score = self._count_changes(cf)
        
        if best_cf:
            return Counterfactual(
                original_prediction=original_pred,
                target_prediction=target_class,
                changes_required=best_cf,
                feasibility_score=1.0 - len(best_cf) / len(instance),
                explanation=self._explain_changes(best_cf)
            )
        
        return Counterfactual(
            original_prediction=original_pred,
            target_prediction=target_class,
            changes_required={},
            feasibility_score=0.0,
            explanation="Could not find counterfactual"
        )
    
    def _find_counterfactual(
        self,
        instance: List[float],
        target_class: Any,
        num_changes: int
    ) -> Optional[Dict[str, Tuple[Any, Any]]]:
        """Find counterfactual with given number of changes"""
        from itertools import combinations
        
        # Try all combinations of features to change
        for indices in combinations(range(len(instance)), num_changes):
            # Try changing each feature
            modified = instance.copy()
            changes = {}
            
            for idx in indices:
                name = self.feature_names[idx] if idx < len(self.feature_names) else f"feature_{idx}"
                original_val = instance[idx]
                
                # Try different values
                for new_val in self._get_candidate_values(name, original_val):
                    modified[idx] = new_val
                    
                    if self.model_fn(modified) == target_class:
                        changes[name] = (original_val, new_val)
                        return changes
                
                modified[idx] = original_val
        
        return None
    
    def _get_candidate_values(self, feature_name: str, current_value: float) -> List[float]:
        """Get candidate values for a feature"""
        if feature_name in self.feature_ranges:
            low, high = self.feature_ranges[feature_name]
            return [low, high, (low + high) / 2]
        
        # Default candidates
        return [0.0, 0.5, 1.0, current_value * 0.5, current_value * 1.5]
    
    def _count_changes(self, changes: Dict) -> int:
        return len(changes)
    
    def _explain_changes(self, changes: Dict[str, Tuple[Any, Any]]) -> str:
        """Generate explanation for changes"""
        parts = []
        for name, (old, new) in changes.items():
            parts.append(f"Change {name} from {old:.2f} to {new:.2f}")
        return "; ".join(parts)


# ==================== CONFIDENCE SCORER ====================

class ConfidenceScorer:
    """
    Detailed confidence scoring with breakdown
    """
    
    def calculate(
        self,
        prediction: Any,
        model_confidence: float,
        data_quality: float = 1.0,
        model_reliability: Optional[Dict[str, float]] = None
    ) -> ConfidenceBreakdown:
        """Calculate detailed confidence breakdown"""
        components = {
            "model_confidence": model_confidence,
            "data_quality": data_quality
        }
        
        if model_reliability:
            components["model_reliability"] = model_reliability.get("accuracy", 0.8)
        
        # Identify uncertainty sources
        uncertainty_sources = []
        
        if model_confidence < 0.7:
            uncertainty_sources.append("Low model confidence in prediction")
        
        if data_quality < 0.7:
            uncertainty_sources.append("Low quality input data")
        
        if model_reliability and model_reliability.get("accuracy", 1.0) < 0.8:
            uncertainty_sources.append("Model has limited historical accuracy")
        
        # Calculate overall confidence
        weights = [0.5, 0.3, 0.2]
        values = [
            model_confidence,
            data_quality,
            model_reliability.get("accuracy", 0.8) if model_reliability else 0.8
        ]
        
        overall = sum(w * v for w, v in zip(weights, values))
        
        return ConfidenceBreakdown(
            overall=overall,
            components=components,
            uncertainty_sources=uncertainty_sources
        )


# ==================== BIAS DETECTOR ====================

class BiasDetector:
    """
    Detect and report potential biases
    """
    
    def __init__(self, sensitive_features: List[str]):
        self.sensitive_features = sensitive_features
    
    def detect_disparity(
        self,
        predictions: List[Any],
        sensitive_values: List[Any],
        positive_class: Any = 1
    ) -> BiasReport:
        """Detect disparity in predictions across groups"""
        # Group predictions by sensitive value
        groups = {}
        for pred, sensitive in zip(predictions, sensitive_values):
            if sensitive not in groups:
                groups[sensitive] = {"positive": 0, "total": 0}
            
            groups[sensitive]["total"] += 1
            if pred == positive_class:
                groups[sensitive]["positive"] += 1
        
        # Calculate rates per group
        rates = {}
        for group, counts in groups.items():
            rates[str(group)] = counts["positive"] / counts["total"] if counts["total"] > 0 else 0
        
        # Calculate disparity
        if len(rates) < 2:
            disparity = 0.0
        else:
            max_rate = max(rates.values())
            min_rate = min(rates.values())
            disparity = max_rate - min_rate
        
        # Determine if biased (>20% disparity)
        is_biased = disparity > 0.2
        
        # Generate recommendations
        recommendations = []
        if is_biased:
            recommendations.append("Review training data for group imbalance")
            recommendations.append("Consider fairness constraints during training")
            recommendations.append("Monitor predictions across groups in production")
        
        return BiasReport(
            metric_name="demographic_parity",
            groups=rates,
            disparity=disparity,
            is_biased=is_biased,
            recommendations=recommendations
        )


# ==================== MAIN EXPLAINER ====================

class ExplainableAI:
    """
    Main explainable AI interface
    """
    
    def __init__(self, model_fn: Callable, feature_names: List[str]):
        self.model_fn = model_fn
        self.feature_names = feature_names
        
        self.shap = SimpleSHAP(model_fn, feature_names)
        self.counterfactual = CounterfactualGenerator(model_fn, feature_names)
        self.confidence = ConfidenceScorer()
        self.bias = BiasDetector(feature_names)
    
    def explain_prediction(
        self,
        instance: List[float],
        background_data: Optional[List[List[float]]] = None
    ) -> Explanation:
        """Get full explanation for prediction"""
        if background_data:
            self.shap.set_background(background_data)
        
        return self.shap.explain(instance)
    
    def get_counterfactual(
        self,
        instance: List[float],
        target_class: Any
    ) -> Counterfactual:
        """Get counterfactual explanation"""
        return self.counterfactual.generate(instance, target_class)
    
    def get_confidence_breakdown(
        self,
        prediction: Any,
        model_confidence: float,
        data_quality: float = 1.0
    ) -> ConfidenceBreakdown:
        """Get detailed confidence breakdown"""
        return self.confidence.calculate(prediction, model_confidence, data_quality)
    
    def check_bias(
        self,
        predictions: List[Any],
        sensitive_values: List[Any]
    ) -> BiasReport:
        """Check for bias in predictions"""
        return self.bias.detect_disparity(predictions, sensitive_values)
