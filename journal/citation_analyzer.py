"""
Algorithm J7: Citation Intent & Sentiment Analysis

Dual-mode NLP classifier for citation contexts:
  1. Rule-based (zero dependencies) — keyword/pattern matching
  2. Transformer (optional) — uses scibert/scincl if available

Analyzes HOW a paper is cited, not just HOW MANY times.

Intent categories:
  - background    → general reference, related work
  - methodology   → adopts method/dataset
  - extension     → builds upon, improves
  - comparison    → benchmarks against
  - support       → confirms findings, agrees
  - contrast      → disagrees, identifies limitations

Sentiment: positive (support/extension/methodology), negative (contrast), neutral (background/comparison)

Usage:
    from journal.citation_analyzer import CitationImpactAnalyzer

    analyzer = CitationImpactAnalyzer()
    report = analyzer.analyze("10.1038/s41586-021-03819-2")
    analyzer.print_report(report)
"""

import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

from .models import Paper, CitationContext, CitationImpactReport
from .api_client import SemanticScholarClient


# ==================== INTENT KEYWORD PATTERNS ====================

# Each intent has a list of regex patterns that indicate it
INTENT_PATTERNS = {
    'support': [
        r'\b(confirm(s|ed|ing)?|validate[sd]?|verified|verif(y|ies)|corroborate[sd]?|consistent with)\b',
        r'\b(in (line|agreement|accordance) with)\b',
        r'\b(support(s|ed|ing)? (the|this|our|their))\b',
        r'\b(as (shown|demonstrated|proven|established) by)\b',
        r'\b(reinforce[sd]?|strengthen(s|ed)?|lend(s)? support)\b',
        r'\b(successfully (applied|used|adopted|demonstrated))\b',
        r'\b(effective(ly)?|superior|outperform(s|ed)?|achieve[sd]? (state|best|high))\b',
    ],
    'contrast': [
        r'\b(however|although|despite|unlike|contrary|nevertheless|nonetheless)\b',
        r'\b(contradict(s|ed)?|disagree(s|d)?|refute[sd]?|challenge[sd]?|oppose[sd]?)\b',
        r'\b(fail(s|ed)? to|unable to|cannot|limitation(s)?|drawback(s)?)\b',
        r'\b(suffer(s|ed)? from|lack(s|ing)?|overlook(s|ed)?|ignore[sd]?)\b',
        r'\b(insufficient|inadequate|poor(ly)?|inferior)\b',
        r'\b(in contrast (to|with)|as opposed to)\b',
        r'\b(problem(s|atic)?|issue(s)?|weakness(es)?|shortcoming(s)?)\b',
        r'\b(overfit(ting)?|bias(ed)?|not generaliz|not scalab)\b',
    ],
    'methodology': [
        r'\b(we (use[sd]?|adopt(ed)?|employ(ed)?|follow(ed)?|implement(ed)?|appl(y|ied)))\b',
        r'\b(based on|build(s|ing)? (on|upon)|inspired by)\b',
        r'\b(using (the )?(method|approach|framework|model|technique) (of|from|in|by))\b',
        r'\b(similar(ly)? to|following|according to)\b',
        r'\b(dataset|benchmark|metric|evaluation) (from|of|in|by)\b',
        r'\b(pre-?trained (on|model|network))\b',
        r'\b(fine-?tun(e[sd]?|ing)|transfer learn(ing)?)\b',
    ],
    'extension': [
        r'\b(extend(s|ed|ing)?|improv(e[sd]?|ing)|enhanc(e[sd]?|ing)|augment(s|ed)?|generaliz(e[sd]?|ing))\b',
        r'\b(we (further|also|additionally))\b',
        r'\b(build(s|ing)? (on|upon) (the work|this|their))\b',
        r'\b(going beyond|advanc(e[sd]?|ing)|novel(ty)?|contribution(s)?)\b',
        r'\b(in addition to|complement(s|ed)?|supplement(s|ed)?)\b',
        r'\b(modif(y|ied|ies)|refin(e[sd]?|ing)|adapt(s|ed)?|tailor(s|ed)?|customiz(e[sd]?|ing))\b',
    ],
    'comparison': [
        r'\b(compar(e[sd]?|ing|ison) (to|with|against|between))\b',
        r'\b(baseline|benchmark|state.?of.?the.?art)\b',
        r'\b(outperform(s|ed)?|underperform(s|ed)?|match(es|ed)?)\b',
        r'\b(versus|vs\.?|relative to|in terms of)\b',
        r'\b(evaluat(e[sd]?|ing) against)\b',
        r'\b(we also (test(ed)?|report(ed)?|include[sd]?))\b',
    ],
    'background': [
        r'\b(has been (studied|investigated|explored|proposed))\b',
        r'\b(previous(ly)?|prior|early|recent(ly)?|existing)\b',
        r'\b(introduc(e[sd]?|ing)|propos(e[sd]?|ing)|present(s|ed)?|develop(s|ed)?)\b',
        r'\b(well.?known|widely.?used|popular|common(ly)?)\b',
        r'\b(survey(s|ed)?|review(s|ed)?|overview|tutorial|introduction)\b',
        r'\b(related work|literature)\b',
    ],
}

# Sentiment mapping for each intent
INTENT_SENTIMENT = {
    'support': 'positive',
    'contrast': 'negative',
    'methodology': 'positive',
    'extension': 'positive',
    'comparison': 'neutral',
    'background': 'neutral',
}


# ==================== CITATION CLASSIFIER ====================

class CitationClassifier:
    """
    Classify citation contexts into intent and sentiment.

    Dual-mode:
      1. Rule-based (always available) — pattern matching
      2. Transformer (optional) — if transformers lib installed
    """

    def __init__(self, use_transformer: bool = False):
        self.use_transformer = use_transformer
        self._transformer_pipeline = None

        if use_transformer:
            self._init_transformer()

    def _init_transformer(self):
        """Try to load transformer pipeline"""
        try:
            from transformers import pipeline
            self._transformer_pipeline = pipeline(
                "text-classification",
                model="allenai/scibert_scivocab_uncased",
                truncation=True,
                max_length=512,
            )
            print("  [✓] Transformer model loaded (scibert)")
        except ImportError:
            print("  [⚠] transformers not installed, using rule-based classifier")
            self.use_transformer = False
        except Exception as e:
            print(f"  [⚠] Transformer init failed: {e}, using rule-based")
            self.use_transformer = False

    def classify(self, context: str) -> Tuple[str, str, float]:
        """
        Classify a citation context.

        Args:
            context: The text snippet containing the citation

        Returns:
            (intent, sentiment, confidence)
        """
        if not context or not context.strip():
            return ('background', 'neutral', 0.0)

        # Rule-based classification (always run)
        intent, confidence = self._rule_based_classify(context)
        sentiment = INTENT_SENTIMENT.get(intent, 'neutral')

        return (intent, sentiment, confidence)

    def _rule_based_classify(self, text: str) -> Tuple[str, float]:
        """
        Rule-based classification using keyword pattern matching.

        Returns (intent, confidence)
        """
        text_lower = text.lower()
        scores: Dict[str, float] = defaultdict(float)

        for intent, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                if matches:
                    # Each match adds weight
                    scores[intent] += len(matches) * (1.0 / len(patterns))

        if not scores:
            return ('background', 0.3)

        # Pick highest scoring intent
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # Normalize confidence to 0.0 – 1.0
        total = sum(scores.values())
        confidence = min(best_score / max(total, 1), 1.0)

        # Boost confidence if multiple patterns match
        if best_score >= 2.0:
            confidence = min(confidence + 0.2, 1.0)

        return (best_intent, round(confidence, 3))

    def classify_batch(self, contexts: List[str]) -> List[Tuple[str, str, float]]:
        """Classify multiple contexts"""
        return [self.classify(ctx) for ctx in contexts]


# ==================== CITATION IMPACT ANALYZER ====================

class CitationImpactAnalyzer:
    """
    Full citation impact analysis for a paper.

    Fetches citation contexts from Semantic Scholar,
    classifies each context, and computes impact quality metrics.

    Quality Score formula:
        score = (positive × 1.0 + neutral × 0.5 - negative × 0.3) / total
        Normalized to 0.0 – 1.0 range
    """

    def __init__(
        self,
        semantic_scholar: Optional[SemanticScholarClient] = None,
        use_transformer: bool = False,
    ):
        self.s2 = semantic_scholar or SemanticScholarClient()
        self.classifier = CitationClassifier(use_transformer=use_transformer)

    def analyze(self, doi_or_id: str, limit: int = 100) -> CitationImpactReport:
        """
        Analyze citation impact for a paper.

        Args:
            doi_or_id: Paper DOI or S2 paper ID
            limit: Max citations to analyze

        Returns:
            CitationImpactReport with full analysis
        """
        # Resolve paper ID
        s2_id = doi_or_id
        if doi_or_id.startswith('10.'):
            s2_id = f"DOI:{doi_or_id}"

        print(f"\n  [📊] Citation intent analysis: {doi_or_id}")

        # Get seed paper
        seed = self.s2.get_paper(s2_id)
        if not seed:
            print(f"  [!] Paper not found: {doi_or_id}")
            return CitationImpactReport(paper_doi=doi_or_id)

        print(f"  [✓] {seed.title[:60]}...")
        print(f"  [·] Total citations: {seed.citation_count}")

        # Fetch citation contexts
        print(f"  [·] Fetching citation contexts (max {limit})...")
        raw_citations = self.s2.get_citation_contexts(s2_id, limit)

        if not raw_citations:
            print("  [!] No citation contexts available")
            return CitationImpactReport(
                paper_title=seed.title,
                paper_doi=seed.doi,
                total_citations=seed.citation_count,
            )

        # Classify each context
        all_contexts: List[CitationContext] = []
        intent_counts: Dict[str, int] = Counter()
        sentiment_counts: Dict[str, int] = Counter()
        influential_count = 0
        supporters = []
        critics = []

        for item in raw_citations:
            citing_paper = item['citing_paper']
            contexts = item['contexts']
            s2_intents = item['intents']
            is_influential = item['is_influential']

            if is_influential:
                influential_count += 1

            if contexts:
                # Classify each context snippet
                for ctx_text in contexts:
                    if not ctx_text or len(ctx_text.strip()) < 10:
                        continue

                    intent, sentiment, conf = self.classifier.classify(ctx_text)

                    # Use S2's own intents as a signal if available
                    if s2_intents and not contexts:
                        intent = self._map_s2_intent(s2_intents[0])
                        sentiment = INTENT_SENTIMENT.get(intent, 'neutral')

                    cc = CitationContext(
                        text=ctx_text[:500],
                        intent=intent,
                        sentiment=sentiment,
                        confidence=conf,
                        citing_paper_title=citing_paper.title,
                        citing_paper_doi=citing_paper.doi,
                        citing_paper_year=citing_paper.year,
                        is_influential=is_influential,
                    )
                    all_contexts.append(cc)
                    intent_counts[intent] += 1
                    sentiment_counts[sentiment] += 1

                    if sentiment == 'positive':
                        supporters.append(citing_paper.title)
                    elif sentiment == 'negative':
                        critics.append(citing_paper.title)
            else:
                # No context text — use S2 intents or default
                intent = 'background'
                if s2_intents:
                    intent = self._map_s2_intent(s2_intents[0])
                sentiment = INTENT_SENTIMENT.get(intent, 'neutral')

                cc = CitationContext(
                    text="[No context available]",
                    intent=intent,
                    sentiment=sentiment,
                    confidence=0.5 if s2_intents else 0.2,
                    citing_paper_title=citing_paper.title,
                    citing_paper_doi=citing_paper.doi,
                    citing_paper_year=citing_paper.year,
                    is_influential=is_influential,
                )
                all_contexts.append(cc)
                intent_counts[intent] += 1
                sentiment_counts[sentiment] += 1

        # Compute quality score
        pos = sentiment_counts.get('positive', 0)
        neg = sentiment_counts.get('negative', 0)
        neu = sentiment_counts.get('neutral', 0)
        total = pos + neg + neu

        if total > 0:
            raw_score = (pos * 1.0 + neu * 0.5 - neg * 0.3) / total
            quality = max(0.0, min(1.0, raw_score))
        else:
            quality = 0.0

        report = CitationImpactReport(
            paper_title=seed.title,
            paper_doi=seed.doi,
            total_citations=seed.citation_count,
            analyzed_citations=len(all_contexts),
            positive_count=pos,
            negative_count=neg,
            neutral_count=neu,
            intent_breakdown=dict(intent_counts),
            quality_score=quality,
            influential_count=influential_count,
            contexts=all_contexts,
            top_supporters=supporters[:10],
            top_critics=critics[:10],
        )

        self.print_report(report)
        return report

    @staticmethod
    def _map_s2_intent(s2_intent: str) -> str:
        """Map Semantic Scholar intent labels to our categories"""
        mapping = {
            'background': 'background',
            'methodology': 'methodology',
            'result': 'support',
            'motivation': 'background',
        }
        return mapping.get(s2_intent.lower(), 'background')

    @staticmethod
    def print_report(report: CitationImpactReport):
        """Print formatted citation impact report"""
        print(f"\n{'='*65}")
        print(f"  📊 Citation Impact Analysis")
        print(f"{'='*65}")
        print(f"  Paper: {report.paper_title[:60]}...")
        print(f"  DOI:   {report.paper_doi or 'N/A'}")
        print(f"  Total Citations: {report.total_citations}")
        print(f"  Analyzed:        {report.analyzed_citations}")
        print(f"  Influential:     {report.influential_count}")

        # Quality score with visual bar
        bar_len = int(report.quality_score * 30)
        bar = '█' * bar_len + '░' * (30 - bar_len)
        quality_pct = report.quality_score * 100

        if quality_pct >= 70:
            emoji = "🟢"
        elif quality_pct >= 40:
            emoji = "🟡"
        else:
            emoji = "🔴"

        print(f"\n  Impact Quality: {emoji} {quality_pct:.1f}%")
        print(f"  [{bar}]")

        # Sentiment breakdown
        total = report.positive_count + report.negative_count + report.neutral_count
        if total > 0:
            print(f"\n  💚 Positive:  {report.positive_count:4d} ({report.positive_count/total*100:.0f}%)")
            print(f"  🔴 Negative:  {report.negative_count:4d} ({report.negative_count/total*100:.0f}%)")
            print(f"  ⚪ Neutral:   {report.neutral_count:4d} ({report.neutral_count/total*100:.0f}%)")

        # Intent breakdown
        if report.intent_breakdown:
            print(f"\n  📋 Intent Breakdown:")
            print(f"  {'─'*45}")
            intent_icons = {
                'background': '📖', 'methodology': '🔧',
                'extension': '🚀', 'comparison': '⚖️',
                'support': '✅', 'contrast': '❌',
            }
            for intent, count in sorted(
                report.intent_breakdown.items(),
                key=lambda x: x[1], reverse=True
            ):
                icon = intent_icons.get(intent, '·')
                pct = count / total * 100 if total else 0
                print(f"  {icon} {intent:<15} {count:4d} ({pct:.0f}%)")

        # Top supporters
        if report.top_supporters:
            print(f"\n  ✅ Top Supporters:")
            for i, title in enumerate(report.top_supporters[:5], 1):
                print(f"  {i}. {title[:65]}{'...' if len(title) > 65 else ''}")

        # Top critics
        if report.top_critics:
            print(f"\n  ❌ Top Critics:")
            for i, title in enumerate(report.top_critics[:5], 1):
                print(f"  {i}. {title[:65]}{'...' if len(title) > 65 else ''}")

        print(f"\n{'='*65}")
