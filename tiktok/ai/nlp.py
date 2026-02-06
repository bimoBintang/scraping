"""
NLP Analysis Module for TikTok AI
Sentiment analysis, topic modeling, hashtag trends
"""

import re
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import Counter
from datetime import datetime
import math

# Try importing ML libraries
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


# ==================== DATA CLASSES ====================

@dataclass
class SentimentResult:
    """Sentiment analysis result"""
    text: str
    label: str  # positive, negative, neutral
    score: float  # -1 to 1
    confidence: float  # 0 to 1
    breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class Topic:
    """Identified topic"""
    id: int
    name: str
    keywords: List[str]
    weight: float
    sample_texts: List[str] = field(default_factory=list)


@dataclass
class TopicModelResult:
    """Topic modeling result"""
    topics: List[Topic]
    document_topics: Dict[int, List[Tuple[int, float]]]  # doc_id -> [(topic_id, weight)]
    coherence_score: float = 0.0


@dataclass
class HashtagCluster:
    """Cluster of related hashtags"""
    id: int
    hashtags: List[str]
    central_hashtag: str
    trend_score: float
    growth_rate: float = 0.0


@dataclass
class HashtagTrends:
    """Hashtag trend analysis result"""
    top_hashtags: List[Tuple[str, int]]  # (hashtag, count)
    clusters: List[HashtagCluster]
    emerging: List[str]  # Newly trending
    declining: List[str]  # Losing popularity


@dataclass
class NLPAnalysisResult:
    """Combined NLP analysis result"""
    sentiment: Optional[SentimentResult] = None
    topics: Optional[TopicModelResult] = None
    hashtag_trends: Optional[HashtagTrends] = None
    entities: List[str] = field(default_factory=list)
    language: str = "unknown"
    processing_time_ms: float = 0.0


# ==================== SENTIMENT ANALYZER ====================

class SentimentAnalyzer:
    """
    Multi-method sentiment analysis
    Uses BERT when available, falls back to rule-based
    """
    
    # Simple word lists for rule-based fallback
    POSITIVE_WORDS = {
        'love', 'amazing', 'awesome', 'great', 'excellent', 'beautiful',
        'happy', 'joy', 'wonderful', 'fantastic', 'perfect', 'best',
        'good', 'nice', 'cool', 'incredible', 'brilliant', 'superb',
        'suka', 'bagus', 'keren', 'mantap', 'cantik', 'ganteng', 'top'
    }
    
    NEGATIVE_WORDS = {
        'hate', 'terrible', 'awful', 'bad', 'horrible', 'disgusting',
        'angry', 'sad', 'disappointed', 'worst', 'ugly', 'boring',
        'stupid', 'fail', 'poor', 'wrong', 'annoying', 'frustrating',
        'jelek', 'buruk', 'benci', 'marah', 'sedih', 'kecewa', 'sampah'
    }
    
    def __init__(self, model_name: str = "nlptown/bert-base-multilingual-uncased-sentiment"):
        self.model_name = model_name
        self._pipeline = None
        self._initialized = False
    
    def _initialize(self):
        """Lazy initialization of ML model"""
        if self._initialized:
            return
        
        if HAS_TRANSFORMERS and HAS_TORCH:
            try:
                self._pipeline = pipeline(
                    "sentiment-analysis",
                    model=self.model_name,
                    device=0 if torch.cuda.is_available() else -1
                )
                print(f"[NLP] Loaded sentiment model: {self.model_name}")
            except Exception as e:
                print(f"[NLP] Failed to load model: {e}. Using fallback.")
        
        self._initialized = True
    
    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of text"""
        if not text or not text.strip():
            return SentimentResult(
                text=text,
                label="neutral",
                score=0.0,
                confidence=0.0
            )
        
        self._initialize()
        
        if self._pipeline:
            return self._ml_sentiment(text)
        else:
            return self._rule_based_sentiment(text)
    
    def _ml_sentiment(self, text: str) -> SentimentResult:
        """ML-based sentiment analysis"""
        # Truncate for model
        text_truncated = text[:512]
        
        try:
            result = self._pipeline(text_truncated)[0]
            
            # Convert star rating to score
            label = result['label']
            confidence = result['score']
            
            # nlptown model returns "1 star" to "5 stars"
            if 'star' in label.lower():
                stars = int(label.split()[0])
                score = (stars - 3) / 2  # Convert 1-5 to -1 to 1
                label = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
            else:
                score = confidence if label.lower() == 'positive' else -confidence
            
            return SentimentResult(
                text=text,
                label=label,
                score=score,
                confidence=confidence,
                breakdown={"raw_label": result['label'], "raw_score": result['score']}
            )
            
        except Exception as e:
            print(f"[NLP] ML sentiment failed: {e}. Using fallback.")
            return self._rule_based_sentiment(text)
    
    def _rule_based_sentiment(self, text: str) -> SentimentResult:
        """Simple rule-based sentiment analysis"""
        words = set(text.lower().split())
        
        positive_count = len(words & self.POSITIVE_WORDS)
        negative_count = len(words & self.NEGATIVE_WORDS)
        
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            label = "neutral"
            confidence = 0.3
        else:
            score = (positive_count - negative_count) / total
            label = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"
            confidence = min(0.8, total * 0.1 + 0.3)
        
        return SentimentResult(
            text=text,
            label=label,
            score=score,
            confidence=confidence,
            breakdown={
                "positive_words": positive_count,
                "negative_words": negative_count,
                "method": "rule_based"
            }
        )
    
    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze multiple texts"""
        return [self.analyze(text) for text in texts]
    
    def get_aggregate_sentiment(self, results: List[SentimentResult]) -> Dict[str, Any]:
        """Get aggregate sentiment from multiple results"""
        if not results:
            return {"average_score": 0, "distribution": {}}
        
        scores = [r.score for r in results]
        labels = [r.label for r in results]
        
        return {
            "average_score": sum(scores) / len(scores),
            "distribution": dict(Counter(labels)),
            "most_positive": max(results, key=lambda x: x.score),
            "most_negative": min(results, key=lambda x: x.score)
        }


# ==================== TOPIC MODELER ====================

class TopicModeler:
    """
    Topic modeling using TF-IDF and clustering
    Falls back to simple keyword extraction if ML unavailable
    """
    
    def __init__(self, num_topics: int = 5, max_features: int = 1000):
        self.num_topics = num_topics
        self.max_features = max_features
        self._vectorizer = None
        self._model = None
    
    def fit(self, texts: List[str]) -> TopicModelResult:
        """Fit topic model on texts"""
        if not texts:
            return TopicModelResult(topics=[], document_topics={})
        
        # Clean texts
        cleaned_texts = [self._preprocess(text) for text in texts]
        cleaned_texts = [t for t in cleaned_texts if t]  # Remove empty
        
        if len(cleaned_texts) < self.num_topics:
            return self._simple_topic_extraction(texts)
        
        if HAS_SKLEARN:
            return self._sklearn_topic_model(cleaned_texts, texts)
        else:
            return self._simple_topic_extraction(texts)
    
    def _preprocess(self, text: str) -> str:
        """Preprocess text for topic modeling"""
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove mentions
        text = re.sub(r'@\w+', '', text)
        # Remove hashtags (keep the word)
        text = re.sub(r'#(\w+)', r'\1', text)
        # Remove special chars
        text = re.sub(r'[^\w\s]', ' ', text)
        # Lowercase
        text = text.lower()
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text
    
    def _sklearn_topic_model(self, cleaned_texts: List[str], original_texts: List[str]) -> TopicModelResult:
        """Topic modeling using sklearn"""
        # TF-IDF vectorization
        self._vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        tfidf_matrix = self._vectorizer.fit_transform(cleaned_texts)
        
        # Clustering
        n_clusters = min(self.num_topics, len(cleaned_texts))
        self._model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = self._model.fit_predict(tfidf_matrix)
        
        # Extract topics
        feature_names = self._vectorizer.get_feature_names_out()
        topics = []
        
        for topic_id in range(n_clusters):
            # Get center of cluster
            center = self._model.cluster_centers_[topic_id]
            # Top keywords
            top_indices = center.argsort()[-10:][::-1]
            keywords = [feature_names[i] for i in top_indices]
            
            # Sample texts from this topic
            topic_texts = [
                original_texts[i] for i, c in enumerate(clusters) if c == topic_id
            ][:3]
            
            topics.append(Topic(
                id=topic_id,
                name=keywords[0] if keywords else f"topic_{topic_id}",
                keywords=keywords,
                weight=sum(1 for c in clusters if c == topic_id) / len(clusters),
                sample_texts=topic_texts
            ))
        
        # Document-topic mapping
        doc_topics = {}
        for doc_id, cluster_id in enumerate(clusters):
            doc_topics[doc_id] = [(cluster_id, 1.0)]  # Simple assignment
        
        return TopicModelResult(
            topics=topics,
            document_topics=doc_topics,
            coherence_score=self._estimate_coherence(topics)
        )
    
    def _simple_topic_extraction(self, texts: List[str]) -> TopicModelResult:
        """Simple keyword-based topic extraction"""
        all_words = []
        for text in texts:
            words = self._preprocess(text).split()
            all_words.extend(words)
        
        # Count words
        word_counts = Counter(all_words)
        
        # Remove common words
        common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                       'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                       'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                       'can', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
                       'from', 'or', 'and', 'but', 'not', 'this', 'that', 'it'}
        
        for word in common_words:
            word_counts.pop(word, None)
        
        # Top keywords as topics
        top_words = word_counts.most_common(self.num_topics * 5)
        
        topics = []
        for i in range(min(self.num_topics, len(top_words))):
            start_idx = i * 5
            keywords = [w[0] for w in top_words[start_idx:start_idx+5]]
            
            topics.append(Topic(
                id=i,
                name=keywords[0] if keywords else f"topic_{i}",
                keywords=keywords,
                weight=1.0 / self.num_topics,
                sample_texts=[]
            ))
        
        return TopicModelResult(
            topics=topics,
            document_topics={},
            coherence_score=0.5  # Unknown
        )
    
    def _estimate_coherence(self, topics: List[Topic]) -> float:
        """Estimate topic coherence score"""
        # Simple heuristic based on keyword overlap
        if len(topics) < 2:
            return 1.0
        
        overlaps = []
        for i, t1 in enumerate(topics):
            for t2 in topics[i+1:]:
                overlap = len(set(t1.keywords) & set(t2.keywords))
                overlaps.append(overlap)
        
        # Lower overlap = better coherence
        avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
        return max(0, 1 - avg_overlap / 5)


# ==================== HASHTAG ANALYZER ====================

class HashtagAnalyzer:
    """
    Hashtag trend analysis and clustering
    """
    
    def __init__(self, min_count: int = 2):
        self.min_count = min_count
    
    def analyze(
        self, 
        hashtags: List[str],
        historical: Optional[Dict[str, int]] = None
    ) -> HashtagTrends:
        """Analyze hashtag trends"""
        # Count hashtags
        hashtag_counts = Counter(hashtags)
        
        # Top hashtags
        top = hashtag_counts.most_common(20)
        
        # Cluster similar hashtags
        clusters = self._cluster_hashtags(list(hashtag_counts.keys()))
        
        # Detect emerging/declining if historical data available
        emerging = []
        declining = []
        
        if historical:
            for hashtag, count in hashtag_counts.items():
                old_count = historical.get(hashtag, 0)
                if old_count == 0 and count >= self.min_count:
                    emerging.append(hashtag)
                elif old_count > 0:
                    change = (count - old_count) / old_count
                    if change < -0.5:
                        declining.append(hashtag)
        
        return HashtagTrends(
            top_hashtags=top,
            clusters=clusters,
            emerging=emerging[:10],
            declining=declining[:10]
        )
    
    def _cluster_hashtags(self, hashtags: List[str]) -> List[HashtagCluster]:
        """Cluster similar hashtags by word similarity"""
        if not hashtags:
            return []
        
        clusters = []
        used = set()
        
        for hashtag in hashtags:
            if hashtag in used:
                continue
            
            # Find similar hashtags
            similar = [hashtag]
            for other in hashtags:
                if other != hashtag and other not in used:
                    if self._is_similar(hashtag, other):
                        similar.append(other)
                        used.add(other)
            
            if len(similar) >= 2:
                clusters.append(HashtagCluster(
                    id=len(clusters),
                    hashtags=similar,
                    central_hashtag=hashtag,
                    trend_score=len(similar) / len(hashtags)
                ))
            
            used.add(hashtag)
        
        return clusters
    
    def _is_similar(self, h1: str, h2: str) -> bool:
        """Check if two hashtags are similar"""
        # Check if one contains the other
        h1_lower = h1.lower()
        h2_lower = h2.lower()
        
        if h1_lower in h2_lower or h2_lower in h1_lower:
            return True
        
        # Check character overlap (Jaccard similarity)
        set1 = set(h1_lower)
        set2 = set(h2_lower)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union > 0.7 if union > 0 else False
    
    def get_related_hashtags(self, hashtag: str, all_hashtags: List[str], top_n: int = 5) -> List[str]:
        """Get hashtags that frequently appear with the given hashtag"""
        # This would need co-occurrence data from posts
        # Simple implementation: find similar hashtags
        related = []
        for h in all_hashtags:
            if h != hashtag and self._is_similar(hashtag, h):
                related.append(h)
        return related[:top_n]


# ==================== MAIN NLP ANALYZER ====================

class NLPAnalyzer:
    """
    Combined NLP analysis interface
    """
    
    def __init__(self):
        self.sentiment = SentimentAnalyzer()
        self.topics = TopicModeler()
        self.hashtags = HashtagAnalyzer()
    
    def analyze_text(self, text: str) -> NLPAnalysisResult:
        """Full NLP analysis on single text"""
        start_time = datetime.now()
        
        # Sentiment
        sentiment_result = self.sentiment.analyze(text)
        
        # Extract hashtags
        hashtag_list = re.findall(r'#(\w+)', text)
        hashtag_result = self.hashtags.analyze(hashtag_list) if hashtag_list else None
        
        # Language detection
        language = self._detect_language(text)
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return NLPAnalysisResult(
            sentiment=sentiment_result,
            topics=None,  # Single text doesn't need topic modeling
            hashtag_trends=hashtag_result,
            language=language,
            processing_time_ms=processing_time
        )
    
    def analyze_corpus(self, texts: List[str]) -> NLPAnalysisResult:
        """Full NLP analysis on multiple texts"""
        start_time = datetime.now()
        
        # Aggregate sentiment
        sentiments = self.sentiment.analyze_batch(texts)
        aggregate_sentiment = self.sentiment.get_aggregate_sentiment(sentiments)
        
        avg_sentiment = SentimentResult(
            text=f"[Aggregate of {len(texts)} texts]",
            label=max(aggregate_sentiment['distribution'], key=aggregate_sentiment['distribution'].get) if aggregate_sentiment['distribution'] else 'neutral',
            score=aggregate_sentiment['average_score'],
            confidence=0.8,
            breakdown=aggregate_sentiment
        )
        
        # Topic modeling
        topic_result = self.topics.fit(texts)
        
        # All hashtags
        all_hashtags = []
        for text in texts:
            all_hashtags.extend(re.findall(r'#(\w+)', text))
        hashtag_result = self.hashtags.analyze(all_hashtags)
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return NLPAnalysisResult(
            sentiment=avg_sentiment,
            topics=topic_result,
            hashtag_trends=hashtag_result,
            processing_time_ms=processing_time
        )
    
    def _detect_language(self, text: str) -> str:
        """Detect text language"""
        try:
            from langdetect import detect
            return detect(text)
        except:
            return "unknown"
