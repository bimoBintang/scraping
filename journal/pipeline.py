"""
Algorithm Integration Pipelines

5 combined workflows chaining J1-J5 base algorithms with J6-J18:

  Pipeline 1: Discovery     — J1 (Search) → J8 (Frontier) + J15 (Systematic Review)
  Pipeline 2: Citation       — J2 (Crawler) → J6 (Author Network) + J7 (Intent)
  Pipeline 3: Forecast       — J3 (Trend) → J8 (Frontier) + J14 (Impact)
  Pipeline 4: Recommend      — J4 (Recommender) → J10 (Lit Review) + J18 (Reviewer)
  Pipeline 5: Bulk           — J5 (Harvester) → J13 (OA Check) + J16 (Bibmap)

Usage:
    from journal.pipeline import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()
    report = orchestrator.run('discovery', query='deep learning', n_papers=30)
"""

import time
from typing import Dict, List, Optional

from .models import PipelineReport
from .api_client import OpenAlexClient


class PipelineOrchestrator:
    """
    Orchestrate combined algorithm pipelines.
    """

    PIPELINES = {
        'discovery': {
            'description': 'J1 (Search) → J8 (Frontier) + J15 (Systematic Review)',
            'stages': ['search', 'frontier', 'sysrev'],
        },
        'citation': {
            'description': 'J2 (Citation Crawler) → J6 (Author Network) + J7 (Citation Intent)',
            'stages': ['cite', 'author_network', 'intent'],
        },
        'forecast': {
            'description': 'J3 (Trend) → J8 (Frontier) + J14 (Impact Forecaster)',
            'stages': ['trend', 'frontier', 'impact'],
        },
        'recommend': {
            'description': 'J4 (Recommender) → J10 (Lit Review) + J18 (Reviewer Match)',
            'stages': ['recommend', 'review', 'reviewer'],
        },
        'bulk': {
            'description': 'J5 (Harvester) → J13 (OA Check) + J16 (Bibliometric Map)',
            'stages': ['harvest', 'oa_check', 'bibmap'],
        },
    }

    def __init__(self, openalex: Optional[OpenAlexClient] = None):
        self.oa = openalex or OpenAlexClient()

    def run(
        self,
        pipeline_name: str,
        query: str = "",
        doi: str = "",
        n_papers: int = 30,
        years: str = "",
    ) -> PipelineReport:
        """
        Run a named pipeline.

        Args:
            pipeline_name: One of: discovery, citation, forecast, recommend, bulk
            query: Search query or topic
            doi: DOI (for citation/recommend pipelines)
            n_papers: Number of papers to process
            years: Year range (for forecast pipeline)

        Returns:
            PipelineReport
        """
        if pipeline_name not in self.PIPELINES:
            print(f"  [!] Unknown pipeline: {pipeline_name}")
            print(f"  [!] Available: {', '.join(self.PIPELINES.keys())}")
            return PipelineReport(pipeline_name=pipeline_name, query=query)

        info = self.PIPELINES[pipeline_name]
        print(f"\n  [⚡] Pipeline: {pipeline_name.upper()}")
        print(f"  [·] {info['description']}")
        print(f"  [·] Query: \"{query or doi}\"")

        start = time.time()

        dispatch = {
            'discovery': self._run_discovery,
            'citation': self._run_citation,
            'forecast': self._run_forecast,
            'recommend': self._run_recommend,
            'bulk': self._run_bulk,
        }

        report = dispatch[pipeline_name](
            query=query, doi=doi, n_papers=n_papers, years=years
        )

        report.elapsed_seconds = time.time() - start
        self.print_report(report)
        return report

    # ==================== PIPELINE 1: DISCOVERY ====================

    def _run_discovery(self, query: str, n_papers: int, **kwargs) -> PipelineReport:
        """J1 → J8 + J15"""
        from .search_engine import FederatedSearch
        from .frontier_detector import ResearchFrontierDetector
        from .systematic_review import SystematicReviewAssistant

        report = PipelineReport(pipeline_name='discovery', query=query)
        results = {}

        # Stage 1: Federated Search (J1)
        print(f"\n  [1/3] 🔍 Federated Search...")
        try:
            searcher = FederatedSearch()
            search_result = searcher.search(query, count=min(n_papers, 25))
            results['search'] = {
                'total_found': len(search_result.papers) if search_result else 0,
                'sources': list({p.source_api for p in search_result.papers}) if search_result else [],
            }
            report.total_papers = len(search_result.papers) if search_result else 0
            report.stages_completed.append('J1:FederatedSearch')
            print(f"  [✓] Found {report.total_papers} papers")
        except Exception as e:
            results['search'] = {'error': str(e)}
            print(f"  [!] Search error: {e}")

        # Stage 2: Frontier Detection (J8)
        print(f"\n  [2/3] 🌐 Frontier Detection...")
        try:
            detector = ResearchFrontierDetector()
            frontier = detector.detect(query=query, n_topics=min(n_papers // 3, 10))
            results['frontier'] = {
                'topics_found': len(frontier.frontiers) if frontier and frontier.frontiers else 0,
                'top_topics': [t.topic for t in frontier.frontiers[:3]] if frontier and frontier.frontiers else [],
            }
            report.stages_completed.append('J8:FrontierDetector')
            print(f"  [✓] {results['frontier']['topics_found']} frontier topics")
        except Exception as e:
            results['frontier'] = {'error': str(e)}
            print(f"  [!] Frontier error: {e}")

        # Stage 3: Systematic Review (J15)
        print(f"\n  [3/3] 📋 Systematic Review...")
        try:
            assistant = SystematicReviewAssistant()
            sysrev = assistant.review(query=query, n_papers=min(n_papers, 50))
            results['sysrev'] = {
                'total_found': sysrev.total_found if sysrev else 0,
                'included': sysrev.included if sysrev else 0,
                'excluded': sysrev.excluded if sysrev else 0,
            }
            report.stages_completed.append('J15:SystematicReview')
            print(f"  [✓] Screened: {results['sysrev']['total_found']} papers")
        except Exception as e:
            results['sysrev'] = {'error': str(e)}
            print(f"  [!] Sysrev error: {e}")

        report.results = results
        return report

    # ==================== PIPELINE 2: CITATION INTELLIGENCE ====================

    def _run_citation(self, doi: str, query: str, n_papers: int, **kwargs) -> PipelineReport:
        """J2 → J6 + J7"""
        from .search_engine import CitationCrawler
        from .author_network import AuthorDisambiguator, CollaborationNetwork
        from .citation_analyzer import CitationImpactAnalyzer

        target = doi or query
        report = PipelineReport(pipeline_name='citation', query=target)
        results = {}

        # Stage 1: Citation Crawl (J2)
        print(f"\n  [1/3] 🕸️ Citation Crawling...")
        crawl_data = {}
        papers = []
        try:
            crawler = CitationCrawler()
            crawl_data = crawler.crawl(seed_doi=target, depth=1, max_per_level=min(n_papers, 50))
            papers = crawl_data.get('papers', [])
            results['citation_crawl'] = {
                'papers_found': crawl_data.get('stats', {}).get('total_papers', 0),
                'edges': crawl_data.get('stats', {}).get('total_edges', 0),
            }
            report.total_papers = len(papers)
            report.stages_completed.append('J2:CitationCrawler')
            print(f"  [✓] Crawled {report.total_papers} papers")
        except Exception as e:
            results['citation_crawl'] = {'error': str(e)}
            print(f"  [!] Crawl error: {e}")

        # Stage 2: Author Network (J6) — uses papers from crawl
        print(f"\n  [2/3] 👥 Author Network Analysis...")
        try:
            if papers:
                disambiguator = AuthorDisambiguator()
                disambiguated = disambiguator.disambiguate(papers)
                network = CollaborationNetwork()
                net_report = network.build_and_analyze(papers, disambiguated)
                results['author_network'] = {
                    'authors': net_report.total_authors if net_report else 0,
                    'edges': net_report.total_edges if net_report else 0,
                    'communities': net_report.communities if net_report else 0,
                }
                report.stages_completed.append('J6:AuthorNetwork')
                print(f"  [✓] {results['author_network']['authors']} authors")
            else:
                results['author_network'] = {'note': 'No papers from crawl to analyze'}
                print(f"  [·] No papers available for author analysis")
        except Exception as e:
            results['author_network'] = {'error': str(e)}
            print(f"  [!] Network error: {e}")

        # Stage 3: Citation Intent (J7)
        print(f"\n  [3/3] 🎯 Citation Intent Analysis...")
        try:
            analyzer = CitationImpactAnalyzer()
            impact = analyzer.analyze(doi_or_id=target, limit=min(n_papers, 50))
            results['citation_intent'] = {
                'total_citations': impact.total_citations if impact else 0,
                'quality_score': round(impact.quality_score, 3) if impact else 0,
                'intent_breakdown': impact.intent_breakdown if impact else {},
            }
            report.stages_completed.append('J7:CitationIntent')
            print(f"  [✓] Analyzed {results['citation_intent']['total_citations']} citations")
        except Exception as e:
            results['citation_intent'] = {'error': str(e)}
            print(f"  [!] Intent error: {e}")

        report.results = results
        return report

    # ==================== PIPELINE 3: TREND FORECASTING ====================

    def _run_forecast(self, query: str, n_papers: int, years: str, **kwargs) -> PipelineReport:
        """J3 → J8 + J14"""
        from .search_engine import TrendAnalyzer
        from .frontier_detector import ResearchFrontierDetector
        from .impact_forecaster import ResearchImpactForecaster

        report = PipelineReport(pipeline_name='forecast', query=query)
        results = {}

        # Parse years
        start_year, end_year = 2020, 2026
        if years and '-' in years:
            parts = years.split('-')
            start_year, end_year = int(parts[0]), int(parts[1])

        # Stage 1: Trend Analysis (J3) — returns Dict
        print(f"\n  [1/3] 📈 Trend Analysis ({start_year}-{end_year})...")
        try:
            analyzer = TrendAnalyzer()
            trend = analyzer.analyze(query=query, start_year=start_year, end_year=end_year)
            results['trend'] = {
                'data_points': len(trend.get('trend_points', [])) if trend else 0,
                'direction': trend.get('direction', 'unknown') if trend else 'unknown',
                'total_publications': trend.get('total_publications', 0) if trend else 0,
            }
            report.stages_completed.append('J3:TrendAnalyzer')
            print(f"  [✓] {results['trend']['data_points']} trend points")
        except Exception as e:
            results['trend'] = {'error': str(e)}
            print(f"  [!] Trend error: {e}")

        # Stage 2: Frontier Detection (J8)
        print(f"\n  [2/3] 🌐 Frontier Detection...")
        try:
            detector = ResearchFrontierDetector()
            frontier = detector.detect(query=query, n_topics=min(n_papers // 3, 10))
            results['frontier'] = {
                'topics_found': len(frontier.frontiers) if frontier and frontier.frontiers else 0,
                'top_topics': [t.topic for t in frontier.frontiers[:3]] if frontier and frontier.frontiers else [],
            }
            report.stages_completed.append('J8:FrontierDetector')
            print(f"  [✓] {results['frontier']['topics_found']} frontiers")
        except Exception as e:
            results['frontier'] = {'error': str(e)}
            print(f"  [!] Frontier error: {e}")

        # Stage 3: Impact Forecast (J14)
        print(f"\n  [3/3] 🔮 Impact Forecasting...")
        try:
            forecaster = ResearchImpactForecaster()
            # Get a representative paper DOI
            papers = self.oa.search(query, per_page=1)
            if papers and papers[0].doi:
                forecast = forecaster.forecast(doi=papers[0].doi)
                results['impact'] = {
                    'paper': papers[0].title[:50] if papers[0].title else '',
                    'predicted_impact': forecast.predicted_impact if hasattr(forecast, 'predicted_impact') else 0,
                }
                report.total_papers = 1
                report.stages_completed.append('J14:ImpactForecaster')
                print(f"  [✓] Impact forecast complete")
            else:
                results['impact'] = {'note': 'No DOI found for forecasting'}
                print(f"  [·] No DOI available for forecasting")
        except Exception as e:
            results['impact'] = {'error': str(e)}
            print(f"  [!] Impact error: {e}")

        report.results = results
        return report

    # ==================== PIPELINE 4: RECOMMENDATION ====================

    def _run_recommend(self, doi: str, query: str, n_papers: int, **kwargs) -> PipelineReport:
        """J4 → J10 + J18"""
        from .search_engine import PaperRecommender
        from .review_generator import LiteratureReviewGenerator
        from .reviewer_matcher import ReviewerMatcher

        target = doi or query
        report = PipelineReport(pipeline_name='recommend', query=target)
        results = {}

        # Stage 1: Paper Recommendations (J4) — returns Dict
        print(f"\n  [1/3] 📄 Paper Recommendations...")
        try:
            recommender = PaperRecommender()
            recs = recommender.recommend(doi_or_id=target, count=min(n_papers, 20))
            rec_list = recs.get('recommendations', []) if isinstance(recs, dict) else []
            results['recommendations'] = {
                'papers_recommended': len(rec_list),
                'top_papers': [p.get('title', '')[:40] for p in rec_list[:3]] if rec_list else [],
            }
            report.total_papers = len(rec_list)
            report.stages_completed.append('J4:PaperRecommender')
            print(f"  [✓] {results['recommendations']['papers_recommended']} recommendations")
        except Exception as e:
            results['recommendations'] = {'error': str(e)}
            print(f"  [!] Recommend error: {e}")

        # Stage 2: Literature Review (J10)
        print(f"\n  [2/3] 📝 Literature Review...")
        try:
            generator = LiteratureReviewGenerator()
            search_query = query if query else target
            review = generator.generate(query=search_query, n_papers=min(n_papers, 30))
            results['review'] = {
                'sections': len(review.sections) if review and review.sections else 0,
                'themes': [s.title for s in review.sections[:3]] if review and review.sections else [],
            }
            report.stages_completed.append('J10:LiteratureReview')
            print(f"  [✓] {results['review']['sections']} review sections")
        except Exception as e:
            results['review'] = {'error': str(e)}
            print(f"  [!] Review error: {e}")

        # Stage 3: Reviewer Matching (J18)
        print(f"\n  [3/3] 👥 Reviewer Matching...")
        try:
            matcher = ReviewerMatcher()
            search_query = query if query else target
            match_report = matcher.match(manuscript_text=search_query, n_candidates=5)
            results['reviewers'] = {
                'candidates': len(match_report.candidates) if match_report else 0,
                'top_reviewers': [c.name for c in match_report.candidates[:3]] if match_report and match_report.candidates else [],
            }
            report.stages_completed.append('J18:ReviewerMatcher')
            print(f"  [✓] {results['reviewers']['candidates']} reviewer candidates")
        except Exception as e:
            results['reviewers'] = {'error': str(e)}
            print(f"  [!] Reviewer error: {e}")

        report.results = results
        return report

    # ==================== PIPELINE 5: BULK ANALYSIS ====================

    def _run_bulk(self, query: str, n_papers: int, **kwargs) -> PipelineReport:
        """J5 → J13 + J16"""
        from .search_engine import FederatedSearch
        from .oa_checker import OAComplianceChecker
        from .bibliometric_map import BibliometricMapper

        report = PipelineReport(pipeline_name='bulk', query=query)
        results = {}

        # Stage 1: Bulk Harvest (J5 — via federated search)
        print(f"\n  [1/3] 📦 Bulk Harvest...")
        papers = []
        try:
            searcher = FederatedSearch()
            search_result = searcher.search(query, count=min(n_papers, 50))
            papers = search_result.papers if search_result else []
            results['harvest'] = {
                'papers_harvested': len(papers),
            }
            report.total_papers = len(papers)
            report.stages_completed.append('J5:BulkHarvest')
            print(f"  [✓] Harvested {len(papers)} papers")
        except Exception as e:
            results['harvest'] = {'error': str(e)}
            print(f"  [!] Harvest error: {e}")

        # Stage 2: OA Compliance Check (J13) — sample papers with DOIs
        print(f"\n  [2/3] 🔓 OA Compliance Check...")
        try:
            checker = OAComplianceChecker()
            doi_papers = [p for p in papers if p.doi][:5]
            oa_results = []
            for p in doi_papers:
                try:
                    oa_report = checker.check(doi=p.doi)
                    oa_results.append({
                        'doi': p.doi,
                        'is_oa': oa_report.oa_status.is_oa if oa_report and oa_report.oa_status else False,
                        'status': oa_report.oa_status.status if oa_report and oa_report.oa_status else 'unknown',
                    })
                except Exception:
                    pass

            oa_count = sum(1 for r in oa_results if r.get('is_oa'))
            results['oa_check'] = {
                'checked': len(oa_results),
                'open_access': oa_count,
                'oa_ratio': round(oa_count / len(oa_results), 2) if oa_results else 0,
                'details': oa_results,
            }
            report.stages_completed.append('J13:OAChecker')
            print(f"  [✓] OA: {oa_count}/{len(oa_results)} papers open access")
        except Exception as e:
            results['oa_check'] = {'error': str(e)}
            print(f"  [!] OA error: {e}")

        # Stage 3: Bibliometric Map (J16)
        print(f"\n  [3/3] 🗺️ Bibliometric Mapping...")
        try:
            mapper = BibliometricMapper()
            bmap = mapper.map(query=query, map_type='keyword', n_papers=min(n_papers, 50))
            results['bibmap'] = {
                'nodes': len(bmap.nodes) if bmap else 0,
                'edges': len(bmap.edges) if bmap else 0,
                'clusters': bmap.clusters if bmap else 0,
            }
            report.stages_completed.append('J16:BibliometricMap')
            print(f"  [✓] Map: {results['bibmap']['nodes']} nodes, {results['bibmap']['edges']} edges")
        except Exception as e:
            results['bibmap'] = {'error': str(e)}
            print(f"  [!] Bibmap error: {e}")

        report.results = results
        return report

    # ==================== DISPLAY ====================

    @staticmethod
    def print_report(report: PipelineReport):
        """Print combined pipeline report"""
        print(f"\n{'='*65}")
        print(f"  ⚡ Pipeline Report: {report.pipeline_name.upper()}")
        print(f"{'='*65}")
        print(f"  Query: \"{report.query}\"")
        print(f"  Papers: {report.total_papers}")
        print(f"  Time: {report.elapsed_seconds:.1f}s")

        print(f"\n  📊 Stages ({len(report.stages_completed)}/{len(PipelineOrchestrator.PIPELINES.get(report.pipeline_name, {}).get('stages', []))} completed):")
        for stage in report.stages_completed:
            print(f"    ✓ {stage}")

        if report.results:
            print(f"\n  📋 Results:")
            for key, val in report.results.items():
                if isinstance(val, dict):
                    err = val.get('error')
                    if err:
                        print(f"    ❌ {key}: {err}")
                    else:
                        summary = {k: v for k, v in val.items() if k != 'details'}
                        print(f"    ✓ {key}: {summary}")

        print(f"\n{'='*65}")

    @classmethod
    def list_pipelines(cls):
        """Print available pipelines"""
        print(f"\n  ⚡ Available Pipelines:")
        print(f"  {'─'*55}")
        for name, info in cls.PIPELINES.items():
            print(f"    {name:12s} → {info['description']}")
        print(f"  {'─'*55}")
