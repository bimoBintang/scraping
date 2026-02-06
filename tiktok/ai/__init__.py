"""
TikTok AI Package
Advanced AI/ML integration for content analysis
Version 1.0.0

Modules:
- preprocessing: Video/audio/text preprocessing pipeline
- resilience: Circuit breaker, fallbacks, resource management
- nlp: Sentiment, topic modeling, hashtag analysis
- anomaly: Bot/spam/fake follower detection
- vision: Object detection, scene classification, OCR
- virality: Viral prediction using ML
- orchestrator: Workflow management and parallel execution
- monitoring: Metrics, alerts, dashboards
- fusion: Cross-modal feature fusion
- explainability: SHAP, counterfactuals, bias detection
- model_registry: Version control, A/B testing, rollback
"""

# ==================== PREPROCESSING ====================
from .preprocessing import (
    PreprocessingPipeline,
    VideoDecoder,
    AudioExtractor,
    TextCleaner,
    DataValidator,
    BatchProcessor
)

# ==================== RESILIENCE ====================
from .resilience import (
    CircuitBreaker,
    FallbackChain,
    ResourceManager,
    PartialResultHandler,
    async_retry,
    GracefulDegradation
)

# ==================== NLP ====================
from .nlp import (
    NLPAnalyzer,
    SentimentAnalyzer,
    TopicModeler,
    HashtagAnalyzer
)

# ==================== ANOMALY DETECTION ====================
from .anomaly import (
    AnomalyDetector,
    BotDetector,
    SpamDetector,
    AccountHealthAnalyzer
)

# ==================== COMPUTER VISION ====================
from .vision import (
    VideoAnalyzer,
    ObjectDetector,
    SceneClassifier,
    FaceAnalyzer,
    OCRExtractor
)

# ==================== VIRALITY PREDICTION ====================
from .virality import (
    ViralityPredictor,
    ViralityTrainer,
    FeatureExtractor as ViralityFeatureExtractor
)

# ==================== ORCHESTRATION ====================
from .orchestrator import (
    WorkflowOrchestrator,
    StandardWorkflows,
    PriorityQueue,
    ResultAggregator
)

# ==================== MONITORING ====================
from .monitoring import (
    MonitoringSystem,
    MetricsCollector,
    ModelMonitor,
    ResourceMonitor,
    AlertManager,
    DashboardData
)

# ==================== CROSS-MODAL FUSION ====================
from .fusion import (
    CrossModalFusionEngine,
    EarlyFusion,
    LateFusion,
    CrossModalValidator
)

# ==================== EXPLAINABILITY ====================
from .explainability import (
    ExplainableAI,
    SimpleSHAP,
    CounterfactualGenerator,
    BiasDetector,
    ConfidenceScorer
)

# ==================== MODEL REGISTRY ====================
from .model_registry import (
    ModelRegistry,
    ABTestManager,
    RollbackManager,
    AutoUpdateSystem
)


__all__ = [
    # Preprocessing
    'PreprocessingPipeline',
    'VideoDecoder',
    'AudioExtractor', 
    'TextCleaner',
    'DataValidator',
    'BatchProcessor',
    
    # Resilience
    'CircuitBreaker',
    'FallbackChain',
    'ResourceManager',
    'PartialResultHandler',
    'async_retry',
    'GracefulDegradation',
    
    # NLP
    'NLPAnalyzer',
    'SentimentAnalyzer',
    'TopicModeler',
    'HashtagAnalyzer',
    
    # Anomaly Detection
    'AnomalyDetector',
    'BotDetector',
    'SpamDetector',
    'AccountHealthAnalyzer',
    
    # Vision
    'VideoAnalyzer',
    'ObjectDetector',
    'SceneClassifier',
    'FaceAnalyzer',
    'OCRExtractor',
    
    # Virality
    'ViralityPredictor',
    'ViralityTrainer',
    'ViralityFeatureExtractor',
    
    # Orchestration
    'WorkflowOrchestrator',
    'StandardWorkflows',
    'PriorityQueue',
    'ResultAggregator',
    
    # Monitoring
    'MonitoringSystem',
    'MetricsCollector',
    'ModelMonitor',
    'ResourceMonitor',
    'AlertManager',
    'DashboardData',
    
    # Fusion
    'CrossModalFusionEngine',
    'EarlyFusion',
    'LateFusion',
    'CrossModalValidator',
    
    # Explainability
    'ExplainableAI',
    'SimpleSHAP',
    'CounterfactualGenerator',
    'BiasDetector',
    'ConfidenceScorer',
    
    # Model Registry
    'ModelRegistry',
    'ABTestManager',
    'RollbackManager',
    'AutoUpdateSystem',
]

__version__ = '1.0.0'
