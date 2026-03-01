"""
MCP-D1: AI Context Analyzer - Analisis Konteks Cerdas
Uses Ollama (local LLM) to analyze page intelligence and provide
framework detection, anti-bot analysis, data location mapping,
and bypass recommendations.
"""

import json
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

try:
    import requests as http_requests
except ImportError:
    http_requests = None

from playwright.async_api import Page


# ==================== DATA CLASSES ====================

@dataclass
class AnalysisResult:
    """Structured result from AI analysis"""
    framework_detected: str = "unknown"
    anti_bot_mechanisms: List[str] = field(default_factory=list)
    data_locations: Dict[str, Any] = field(default_factory=dict)
    bypass_recommendations: List[str] = field(default_factory=list)
    detection_risks: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    raw_analysis: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ==================== PAGE INTELLIGENCE COLLECTOR ====================

class PageIntelligenceCollector:
    """
    Collect comprehensive page intelligence via JS injection.
    Gathers: DOM structure, scripts, frameworks, storage, anti-bot markers,
    network patterns.
    """

    def __init__(self, page: Page):
        self.page = page

    async def collect(self) -> Dict[str, Any]:
        """Collect all page intelligence"""
        print("[MCP-D1] Collecting page intelligence...")

        intelligence = {}

        # Collect in parallel
        intelligence['dom'] = await self._collect_dom_structure()
        intelligence['scripts'] = await self._collect_scripts()
        intelligence['framework'] = await self._detect_framework()
        intelligence['storage'] = await self._collect_storage()
        intelligence['antibot'] = await self._detect_antibot()
        intelligence['network'] = await self._collect_network_info()
        intelligence['meta'] = await self._collect_meta()

        print(f"[MCP-D1] Intelligence collected: {len(json.dumps(intelligence))} bytes")
        return intelligence

    async def _collect_dom_structure(self) -> dict:
        """Collect DOM structure summary"""
        try:
            return await self.page.evaluate("""
            (() => {
                const all = document.querySelectorAll('*');
                const tagCounts = {};
                let maxDepth = 0;
                let hiddenCount = 0;
                let interactiveCount = 0;

                for (const el of all) {
                    const tag = el.tagName.toLowerCase();
                    tagCounts[tag] = (tagCounts[tag] || 0) + 1;

                    // Calculate depth
                    let depth = 0, node = el;
                    while (node.parentElement) { depth++; node = node.parentElement; }
                    if (depth > maxDepth) maxDepth = depth;

                    // Hidden elements
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') hiddenCount++;

                    // Interactive elements
                    if (['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) interactiveCount++;
                }

                return {
                    total_elements: all.length,
                    tag_distribution: Object.entries(tagCounts).sort((a,b) => b[1]-a[1]).slice(0, 20).reduce((o,[k,v]) => ({...o,[k]:v}), {}),
                    max_depth: maxDepth,
                    hidden_elements: hiddenCount,
                    interactive_elements: interactiveCount,
                    shadow_roots: document.querySelectorAll('*').length > 0 ? [...all].filter(e => e.shadowRoot).length : 0,
                    iframes: document.querySelectorAll('iframe').length,
                    custom_elements: [...all].filter(e => e.tagName.includes('-')).length,
                    forms: document.querySelectorAll('form').length,
                    data_attributes: [...all].filter(e => Object.keys(e.dataset).length > 0).length
                };
            })()
            """)
        except:
            return {}

    async def _collect_scripts(self) -> dict:
        """Collect loaded scripts info"""
        try:
            return await self.page.evaluate("""
            (() => {
                const scripts = document.querySelectorAll('script');
                const result = { total: scripts.length, inline: 0, external: 0, sources: [], has_nonce: false, has_integrity: false };

                for (const s of scripts) {
                    if (s.src) {
                        result.external++;
                        result.sources.push(s.src.substring(0, 150));
                    } else {
                        result.inline++;
                    }
                    if (s.getAttribute('nonce')) result.has_nonce = true;
                    if (s.getAttribute('integrity')) result.has_integrity = true;
                }

                // Limit sources
                result.sources = result.sources.slice(0, 15);
                return result;
            })()
            """)
        except:
            return {}

    async def _detect_framework(self) -> dict:
        """Detect frontend framework"""
        try:
            return await self.page.evaluate("""
            (() => {
                const result = { name: 'unknown', version: null, evidence: [] };

                // React
                const reactRoot = document.querySelector('[data-reactroot]') || document.getElementById('__next') || document.getElementById('root');
                if (reactRoot) {
                    const keys = Object.keys(reactRoot);
                    const fiberKey = keys.find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
                    if (fiberKey) {
                        result.name = 'react';
                        result.evidence.push('fiber_key: ' + fiberKey.substring(0, 30));
                    }
                }

                // Next.js
                if (document.getElementById('__NEXT_DATA__')) {
                    result.name = 'next.js (react)';
                    result.evidence.push('__NEXT_DATA__ found');
                }

                // Vue
                if ([...document.querySelectorAll('*')].some(e => e.__vue__ || e.__vue_app__)) {
                    result.name = 'vue';
                    result.evidence.push('__vue__ instance found');
                }

                // Angular
                if (document.querySelector('[ng-version]') || window.ng) {
                    result.name = 'angular';
                    const ver = document.querySelector('[ng-version]')?.getAttribute('ng-version');
                    if (ver) result.version = ver;
                }

                // SIGI (TikTok)
                if (document.querySelector('script[id*="SIGI"]') || document.querySelector('script[id*="sigi"]')) {
                    result.name = 'sigi (tiktok custom)';
                    result.evidence.push('SIGI_STATE found');
                }

                // Webpack
                if (window.webpackJsonp || window.__webpack_modules__) {
                    result.evidence.push('webpack detected');
                }

                return result;
            })()
            """)
        except:
            return {}

    async def _collect_storage(self) -> dict:
        """Collect storage contents summary"""
        try:
            return await self.page.evaluate("""
            (() => {
                const result = { localStorage: {}, sessionStorage: {}, indexedDB: [], cookies_count: 0 };

                // localStorage
                try {
                    result.localStorage.count = localStorage.length;
                    result.localStorage.keys = [];
                    for (let i = 0; i < Math.min(localStorage.length, 20); i++) {
                        const key = localStorage.key(i);
                        const val = localStorage.getItem(key);
                        result.localStorage.keys.push({
                            key: key,
                            size: val?.length || 0,
                            has_user_data: (key + (val||'')).toLowerCase().includes('user') || (key + (val||'')).toLowerCase().includes('follow')
                        });
                    }
                } catch (e) {}

                // sessionStorage
                try {
                    result.sessionStorage.count = sessionStorage.length;
                    result.sessionStorage.keys = [];
                    for (let i = 0; i < Math.min(sessionStorage.length, 20); i++) {
                        const key = sessionStorage.key(i);
                        result.sessionStorage.keys.push({ key: key, size: sessionStorage.getItem(key)?.length || 0 });
                    }
                } catch (e) {}

                // IndexedDB
                try {
                    if (window.indexedDB) {
                        const dbs = indexedDB.databases ? 'supported' : 'not_enumerable';
                        result.indexedDB = dbs;
                    }
                } catch (e) {}

                // Cookies
                try { result.cookies_count = document.cookie.split(';').filter(c => c.trim()).length; } catch (e) {}

                return result;
            })()
            """)
        except:
            return {}

    async def _detect_antibot(self) -> dict:
        """Detect anti-bot mechanisms"""
        try:
            return await self.page.evaluate("""
            (() => {
                const result = { mechanisms: [], csp: null, fingerprint_scripts: [], monitoring: [] };

                // CSP
                const cspMeta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
                if (cspMeta) result.csp = cspMeta.getAttribute('content')?.substring(0, 300);

                // Known anti-bot scripts
                const scripts = document.querySelectorAll('script[src]');
                const antibotPatterns = ['captcha', 'recaptcha', 'hcaptcha', 'turnstile', 'fingerprint', 'bot-detect', 'akamai', 'cloudflare', 'datadome', 'kasada', 'perimeterx', 'distil', 'imperva'];

                for (const s of scripts) {
                    const src = s.src.toLowerCase();
                    for (const pattern of antibotPatterns) {
                        if (src.includes(pattern)) {
                            result.fingerprint_scripts.push({ src: s.src.substring(0, 150), pattern: pattern });
                            result.mechanisms.push(pattern);
                        }
                    }
                }

                // Check for common anti-bot markers
                if (document.querySelector('.captcha, [class*="captcha"], [id*="captcha"]')) result.mechanisms.push('captcha_element');
                if (document.querySelector('[data-cf-beacon]')) result.mechanisms.push('cloudflare_beacon');
                if (window.__POWERED_BY_CLOUDFLARE !== undefined) result.mechanisms.push('cloudflare');

                // Check for navigator property tampering detection
                try {
                    const props = Object.getOwnPropertyDescriptor(navigator, 'webdriver');
                    if (props) result.mechanisms.push('webdriver_detection');
                } catch (e) {}

                // Check for DevTools detection
                if (window.__DEVTOOLS_DETECTED !== undefined) result.mechanisms.push('devtools_detection');

                return result;
            })()
            """)
        except:
            return {}

    async def _collect_network_info(self) -> dict:
        """Collect network request patterns"""
        try:
            return await self.page.evaluate("""
            (() => {
                const result = { performance_entries: [], api_endpoints: [], websockets: false };

                // Performance API
                try {
                    const entries = performance.getEntriesByType('resource');
                    const apiEntries = entries.filter(e => e.name.includes('/api/') || e.name.includes('/v1/') || e.name.includes('/v2/'));

                    result.performance_entries = apiEntries.slice(0, 20).map(e => ({
                        url: e.name.substring(0, 200),
                        type: e.initiatorType,
                        duration: Math.round(e.duration),
                        size: e.transferSize || 0
                    }));

                    result.api_endpoints = [...new Set(apiEntries.map(e => {
                        try { return new URL(e.name).pathname; } catch (err) { return e.name.substring(0, 100); }
                    }))].slice(0, 15);
                } catch (e) {}

                // WebSocket detection
                try {
                    result.websockets = !!window.WebSocket;
                } catch (e) {}

                return result;
            })()
            """)
        except:
            return {}

    async def _collect_meta(self) -> dict:
        """Collect page meta information"""
        try:
            return await self.page.evaluate("""
            (() => {
                return {
                    url: location.href,
                    title: document.title,
                    charset: document.characterSet,
                    lang: document.documentElement.lang,
                    viewport: document.querySelector('meta[name="viewport"]')?.content || null
                };
            })()
            """)
        except:
            return {}


# ==================== AI CONTEXT ANALYZER ====================

class AIContextAnalyzer:
    """
    MCP-D1: Analisis Konteks Cerdas
    Uses Ollama (local LLM) to analyze page intelligence and provide
    bypass recommendations.
    """

    OLLAMA_URL = "http://localhost:11434/api/generate"
    DEFAULT_MODEL = "llama3"

    def __init__(self, page: Page, model: str = None):
        self.page = page
        self.collector = PageIntelligenceCollector(page)
        self.model = model or self.DEFAULT_MODEL

    async def execute(self) -> Dict[str, Any]:
        """Execute AI context analysis"""
        print("[MCP-D1] AI Context Analysis (Ollama)...")

        try:
            # Phase 1: Collect intelligence
            intelligence = await self.collector.collect()

            # Phase 2: Check Ollama availability
            if not await self._check_ollama():
                print("[MCP-D1] ⚠ Ollama not available, returning raw intelligence only")
                return {
                    'algorithm': 'MCP-D1_AIContext',
                    'success': True,
                    'ollama_available': False,
                    'intelligence': intelligence,
                    'analysis': None,
                    'message': 'Ollama not available. Install: curl -fsSL https://ollama.com/install.sh | sh && ollama pull llama3'
                }

            # Phase 3: Build prompt
            prompt = self._build_prompt(intelligence)

            # Phase 4: Query Ollama
            print(f"[MCP-D1] Querying Ollama ({self.model})...")
            raw_response = await self._query_ollama(prompt)

            # Phase 5: Parse response
            analysis = self._parse_response(raw_response, intelligence)

            print(f"[MCP-D1] Analysis complete:")
            print(f"  Framework: {analysis.framework_detected}")
            print(f"  Anti-bot: {len(analysis.anti_bot_mechanisms)} mechanisms")
            print(f"  Bypass recommendations: {len(analysis.bypass_recommendations)}")
            print(f"  Confidence: {analysis.confidence_score:.0%}")

            return {
                'algorithm': 'MCP-D1_AIContext',
                'success': True,
                'ollama_available': True,
                'intelligence': intelligence,
                'analysis': analysis.to_dict(),
                'follow_data': []
            }

        except Exception as e:
            print(f"[MCP-D1] Error: {e}")
            return {
                'algorithm': 'MCP-D1_AIContext',
                'success': False,
                'error': str(e),
                'follow_data': []
            }

    async def _check_ollama(self) -> bool:
        """Check if Ollama is running"""
        if http_requests is None:
            print("[MCP-D1] 'requests' library not installed. pip install requests")
            return False

        try:
            resp = http_requests.get("http://localhost:11434/api/tags", timeout=3)
            if resp.status_code == 200:
                models = resp.json().get('models', [])
                model_names = [m.get('name', '').split(':')[0] for m in models]
                print(f"[MCP-D1] Ollama OK, models: {model_names}")

                if self.model not in model_names and f"{self.model}:latest" not in [m.get('name','') for m in models]:
                    print(f"[MCP-D1] Model '{self.model}' not found. Available: {model_names}")
                    if model_names:
                        self.model = model_names[0]
                        print(f"[MCP-D1] Using fallback model: {self.model}")
                    else:
                        return False
                return True
        except Exception as e:
            print(f"[MCP-D1] Ollama connection failed: {e}")
        return False

    def _build_prompt(self, intelligence: dict) -> str:
        """Build analysis prompt for LLM"""
        # Truncate intelligence to fit context window
        intel_str = json.dumps(intelligence, indent=2, default=str)
        if len(intel_str) > 6000:
            intel_str = intel_str[:6000] + "\n... [truncated]"

        return f"""Anda adalah security researcher yang menganalisis halaman web untuk menemukan cara terbaik mengekstrak data.

Analisis data intelligence berikut dari halaman web:

```json
{intel_str}
```

Berikan analisis dalam format JSON berikut (HANYA JSON, tanpa teks lain):
{{
    "framework_detected": "nama framework (react/vue/angular/next.js/unknown)",
    "anti_bot_mechanisms": ["list mekanisme anti-bot yang terdeteksi"],
    "data_locations": {{
        "dom": "deskripsi data di DOM",
        "state_management": "deskripsi state management",
        "storage": "deskripsi data di storage",
        "api": "deskripsi API endpoints"
    }},
    "bypass_recommendations": [
        "rekomendasi bypass spesifik 1",
        "rekomendasi bypass spesifik 2"
    ],
    "detection_risks": [
        "risiko deteksi 1",
        "risiko deteksi 2"
    ],
    "confidence_score": 0.85,
    "best_algorithm": "D1-D15 yang paling efektif untuk halaman ini"
}}"""

    async def _query_ollama(self, prompt: str) -> str:
        """Query Ollama API"""
        def _do_request():
            resp = http_requests.post(
                self.OLLAMA_URL,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 2000
                    }
                },
                timeout=120
            )
            if resp.status_code != 200:
                raise Exception(f"Ollama returned {resp.status_code}: {resp.text[:200]}")
            return resp.json().get('response', '')

        # Run blocking request in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_request)

    def _parse_response(self, raw: str, intelligence: dict) -> AnalysisResult:
        """Parse LLM response into structured result"""
        result = AnalysisResult(raw_analysis=raw)

        # Try to extract JSON from response
        try:
            # Find JSON block in response
            json_start = raw.find('{')
            json_end = raw.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(raw[json_start:json_end])

                result.framework_detected = data.get('framework_detected', 'unknown')
                result.anti_bot_mechanisms = data.get('anti_bot_mechanisms', [])
                result.data_locations = data.get('data_locations', {})
                result.bypass_recommendations = data.get('bypass_recommendations', [])
                result.detection_risks = data.get('detection_risks', [])
                result.confidence_score = float(data.get('confidence_score', 0.5))

                return result
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: extract from intelligence directly
        fw = intelligence.get('framework', {})
        result.framework_detected = fw.get('name', 'unknown')

        antibot = intelligence.get('antibot', {})
        result.anti_bot_mechanisms = antibot.get('mechanisms', [])

        result.confidence_score = 0.3  # Low confidence for fallback
        result.bypass_recommendations = [
            "LLM response could not be parsed, using raw intelligence",
            f"Framework: {result.framework_detected}",
            f"Anti-bot: {', '.join(result.anti_bot_mechanisms) or 'none detected'}"
        ]

        return result


# ==================== MCP-D2: ADAPTIVE STRATEGY SELECTOR ====================

@dataclass
class StrategyStep:
    """Single step in the adaptive strategy"""
    algorithm: str  # e.g. 'd12', 'd1', 'd3'
    priority: int  # 1 = highest
    reason: str
    params: Dict[str, Any] = field(default_factory=dict)
    fallback: str = ""
    delay_ms: int = 500
    # Filled after execution
    executed: bool = False
    result: Dict[str, Any] = field(default_factory=dict)
    success: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class AdaptiveStrategySelector:
    """
    MCP-D2: Pemilihan Strategi Adaptif
    Uses MCP-D1 analysis to select optimal D1-D15 execution order.
    AI evaluates each step's result and adapts the remaining strategy in real-time.
    """

    OLLAMA_URL = "http://localhost:11434/api/generate"
    DEFAULT_MODEL = "llama3"

    # Algorithm descriptions for AI context
    ALGORITHM_CATALOG = {
        'd1': 'Shadow DOM Penetration - access shadow roots',
        'd2': 'IFrame Bridging - cross-origin iframe access',
        'd3': 'Virtual DOM Reconstruction - extract React/Vue state',
        'd4': 'DOM Cloning & Deep Serialization - full DOM snapshot',
        'd5': 'Event Loop Interception - capture async data',
        'd6': 'Mutation History Tracking - track DOM changes over time',
        'd7': 'Pseudo-Element Extraction - CSS pseudo content',
        'd8': 'Canvas & WebGL Capture - rendered text extraction',
        'd9': 'SVG & ForeignObject Parsing - SVG embedded data',
        'd10': 'Web Component State - custom element internals',
        'd11': 'Lazy-Loading Force - trigger all lazy content',
        'd12': 'DOM Fingerprint Detection - bypass anti-tampering',
        'd13': 'JS Context Isolation Bypass - cross-context access',
        'd14': 'CSP Bypass - content security policy workaround',
        'd15': 'Service Worker Interception - cached data extraction',
    }

    def __init__(self, page, model: str = None):
        self.page = page
        self.model = model or self.DEFAULT_MODEL
        self.strategy: List[StrategyStep] = []
        self.execution_log: List[Dict[str, Any]] = []
        self.total_users_found = 0

    async def execute(self, mcp_d1_result: dict = None) -> Dict[str, Any]:
        """Execute adaptive strategy selection and run algorithms"""
        print("\n[MCP-D2] Adaptive Strategy Selector...")

        try:
            # Phase 1: Get MCP-D1 analysis or run it
            if mcp_d1_result and mcp_d1_result.get('analysis'):
                analysis = mcp_d1_result
                print("[MCP-D2] Using existing MCP-D1 analysis")
            else:
                print("[MCP-D2] Running MCP-D1 first...")
                analyzer = AIContextAnalyzer(self.page, self.model)
                analysis = await analyzer.execute()

            # Phase 2: Build initial strategy via Ollama
            ollama_ok = await self._check_ollama()
            if ollama_ok:
                self.strategy = await self._ai_build_strategy(analysis)
            else:
                self.strategy = self._heuristic_build_strategy(analysis)

            if not self.strategy:
                print("[MCP-D2] No strategy steps generated, using defaults")
                self.strategy = self._default_strategy()

            # Print strategy
            print(f"\n[MCP-D2] Strategy ({len(self.strategy)} steps):")
            for i, step in enumerate(self.strategy):
                print(f"  {i+1}. {step.algorithm.upper()}: {step.reason}")
                if step.fallback:
                    print(f"     ↳ fallback: {step.fallback}")

            # Phase 3: Execute strategy with real-time adaptation
            from tiktok.dom_algorithms import DOMAlgorithmOrchestrator
            orchestrator = DOMAlgorithmOrchestrator(self.page)

            all_users = []
            for i, step in enumerate(self.strategy):
                print(f"\n[MCP-D2] Step {i+1}/{len(self.strategy)}: {step.algorithm.upper()}")

                # Execute algorithm
                try:
                    result = await orchestrator.run_single(step.algorithm)
                    step.executed = True
                    step.success = result.success
                    step.result = result.data

                    users = result.data.get('follow_data', [])
                    all_users.extend(users)
                    self.total_users_found += len(users)

                    self.execution_log.append({
                        'step': i + 1,
                        'algorithm': step.algorithm,
                        'success': result.success,
                        'nodes': result.nodes_found,
                        'users': len(users)
                    })

                    print(f"  → {'✅' if result.success else '❌'} nodes:{result.nodes_found} users:{len(users)}")

                except Exception as e:
                    print(f"  → ❌ Error: {e}")
                    step.executed = True
                    step.success = False
                    self.execution_log.append({
                        'step': i + 1,
                        'algorithm': step.algorithm,
                        'success': False,
                        'error': str(e)
                    })

                    # Try fallback
                    if step.fallback:
                        print(f"  → Trying fallback: {step.fallback}")
                        try:
                            fb_result = await orchestrator.run_single(step.fallback)
                            users = fb_result.data.get('follow_data', [])
                            all_users.extend(users)
                            self.execution_log[-1]['fallback_used'] = step.fallback
                            self.execution_log[-1]['fallback_success'] = fb_result.success
                        except Exception:
                            pass

                # Phase 4: Mid-execution adaptation (every 3 steps)
                if ollama_ok and (i + 1) % 3 == 0 and i + 1 < len(self.strategy):
                    adapted = await self._ai_adapt_strategy(i + 1)
                    if adapted:
                        print(f"  🔄 Strategy adapted: {len(self.strategy) - i - 1} steps remaining")

                # Delay between steps
                if step.delay_ms > 0 and i + 1 < len(self.strategy):
                    await asyncio.sleep(step.delay_ms / 1000)

            # Deduplicate users
            seen = set()
            unique_users = []
            for user in all_users:
                uname = user.get('username', '')
                if uname and uname not in seen:
                    seen.add(uname)
                    unique_users.append(user)

            # Summary
            succeeded = sum(1 for s in self.strategy if s.success)
            print(f"\n[MCP-D2] === Strategy Complete ===")
            print(f"  Steps: {succeeded}/{len(self.strategy)} succeeded")
            print(f"  Users: {len(unique_users)} unique extracted")

            return {
                'algorithm': 'MCP-D2_AdaptiveStrategy',
                'success': True,
                'strategy': [s.to_dict() for s in self.strategy],
                'execution_log': self.execution_log,
                'users_extracted': unique_users,
                'total_unique_users': len(unique_users),
                'steps_succeeded': succeeded,
                'steps_total': len(self.strategy),
                'follow_data': unique_users
            }

        except Exception as e:
            print(f"[MCP-D2] Error: {e}")
            return {
                'algorithm': 'MCP-D2_AdaptiveStrategy',
                'success': False,
                'error': str(e),
                'follow_data': []
            }

    async def _check_ollama(self) -> bool:
        """Check Ollama availability"""
        if http_requests is None:
            return False
        try:
            resp = http_requests.get("http://localhost:11434/api/tags", timeout=3)
            return resp.status_code == 200
        except:
            return False

    async def _ai_build_strategy(self, analysis: dict) -> List[StrategyStep]:
        """Use AI to build optimal strategy based on MCP-D1 analysis"""
        print("[MCP-D2] AI building strategy...")

        intel = analysis.get('intelligence', {})
        ai_analysis = analysis.get('analysis', {})

        context = json.dumps({
            'framework': intel.get('framework', {}),
            'antibot': intel.get('antibot', {}),
            'dom': {k: intel.get('dom', {}).get(k, 0) for k in
                    ['shadow_roots', 'iframes', 'custom_elements', 'hidden_elements', 'total_elements']},
            'scripts': {'total': intel.get('scripts', {}).get('total', 0),
                        'has_nonce': intel.get('scripts', {}).get('has_nonce', False)},
            'ai_analysis': ai_analysis if isinstance(ai_analysis, dict) else {},
            'algorithms_available': self.ALGORITHM_CATALOG
        }, indent=2, default=str)

        if len(context) > 4000:
            context = context[:4000] + "\n..."

        prompt = f"""Anda adalah AI strategist untuk web scraping.
Berdasarkan analisis halaman berikut, tentukan urutan algoritma D1-D15 yang OPTIMAL.

{context}

Berikan response dalam format JSON ARRAY (HANYA JSON, tanpa teks lain):
[
  {{"algorithm": "d12", "priority": 1, "reason": "alasan singkat", "delay_ms": 500, "fallback": "d4"}},
  {{"algorithm": "d1", "priority": 2, "reason": "alasan singkat", "delay_ms": 300, "fallback": ""}},
  ...
]

Aturan:
- Pilih 5-10 algoritma yang PALING RELEVAN (tidak harus semua)
- Urutkan berdasarkan efisiensi dan keamanan
- Selalu mulai dengan D12 (anti-tampering detection) jika ada anti-bot
- Prioritaskan D3 (Virtual DOM) untuk React/Vue
- Prioritaskan D1 (Shadow DOM) jika ada custom elements
- Include D11 (lazy loading) jika halaman punya banyak konten
- Sertakan fallback untuk setiap langkah penting"""

        try:
            raw = await self._query_ollama(prompt)

            # Parse JSON array
            json_start = raw.find('[')
            json_end = raw.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                steps_data = json.loads(raw[json_start:json_end])
                steps = []
                for s in steps_data:
                    steps.append(StrategyStep(
                        algorithm=s.get('algorithm', 'd4'),
                        priority=s.get('priority', len(steps) + 1),
                        reason=s.get('reason', 'AI selected'),
                        delay_ms=s.get('delay_ms', 500),
                        fallback=s.get('fallback', ''),
                        params=s.get('params', {})
                    ))
                return steps
        except Exception as e:
            print(f"[MCP-D2] AI strategy build failed: {e}")

        return self._heuristic_build_strategy(analysis)

    def _heuristic_build_strategy(self, analysis: dict) -> List[StrategyStep]:
        """Fallback: build strategy using heuristics from intelligence"""
        print("[MCP-D2] Building heuristic strategy...")

        intel = analysis.get('intelligence', {})
        dom = intel.get('dom', {})
        framework = intel.get('framework', {})
        antibot = intel.get('antibot', {})

        steps = []

        # Always start with anti-tampering detection
        if antibot.get('mechanisms'):
            steps.append(StrategyStep('d12', 1, 'Anti-bot detected, neutralize first', fallback='d14'))
            steps.append(StrategyStep('d14', 2, 'CSP bypass after anti-tamper', delay_ms=300))

        # Framework-specific
        fw_name = framework.get('name', 'unknown').lower()
        if 'react' in fw_name or 'next' in fw_name or 'sigi' in fw_name:
            steps.append(StrategyStep('d3', len(steps)+1, f'Virtual DOM for {fw_name}', fallback='d4'))
        if 'vue' in fw_name:
            steps.append(StrategyStep('d3', len(steps)+1, f'Virtual DOM for Vue', fallback='d4'))

        # DOM structure-based
        if dom.get('shadow_roots', 0) > 0:
            steps.append(StrategyStep('d1', len(steps)+1, f"{dom['shadow_roots']} shadow roots found"))
        if dom.get('iframes', 0) > 0:
            steps.append(StrategyStep('d2', len(steps)+1, f"{dom['iframes']} iframes found"))
        if dom.get('custom_elements', 0) > 0:
            steps.append(StrategyStep('d10', len(steps)+1, f"{dom['custom_elements']} custom elements"))

        # Always useful
        steps.append(StrategyStep('d11', len(steps)+1, 'Force lazy-loaded content'))
        steps.append(StrategyStep('d5', len(steps)+1, 'Intercept event loop data'))
        steps.append(StrategyStep('d6', len(steps)+1, 'Track DOM mutations'))
        steps.append(StrategyStep('d15', len(steps)+1, 'Check service worker caches'))

        # Context isolation & deep extraction
        steps.append(StrategyStep('d13', len(steps)+1, 'Context isolation bypass'))
        steps.append(StrategyStep('d4', len(steps)+1, 'Deep DOM clone as final sweep', delay_ms=300))

        return steps

    def _default_strategy(self) -> List[StrategyStep]:
        """Default strategy when nothing else works"""
        return [
            StrategyStep('d12', 1, 'Anti-tampering detection', fallback='d14'),
            StrategyStep('d3', 2, 'Virtual DOM reconstruction', fallback='d4'),
            StrategyStep('d11', 3, 'Force lazy loading'),
            StrategyStep('d1', 4, 'Shadow DOM penetration'),
            StrategyStep('d5', 5, 'Event loop interception'),
            StrategyStep('d4', 6, 'Deep DOM clone'),
            StrategyStep('d15', 7, 'Service worker cache'),
        ]

    async def _ai_adapt_strategy(self, completed_steps: int) -> bool:
        """Ask AI to adapt remaining strategy based on results so far"""
        try:
            log_summary = json.dumps(self.execution_log[-3:], default=str)
            remaining = [s.algorithm for s in self.strategy[completed_steps:]]

            prompt = f"""Berdasarkan hasil eksekusi terbaru:
{log_summary}

Total users ditemukan sejauh ini: {self.total_users_found}
Remaining steps: {remaining}

Haruskah urutan sisanya diubah? Jika ya, berikan JSON array baru untuk remaining steps.
Jika tidak, jawab: {{"keep": true}}

Format: [{{"algorithm": "dX", "priority": N, "reason": "..."}}]"""

            raw = await self._query_ollama(prompt)

            # Check if keep
            if '"keep"' in raw and 'true' in raw:
                return False

            # Parse new order
            json_start = raw.find('[')
            json_end = raw.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                new_steps = json.loads(raw[json_start:json_end])
                adapted = []
                for s in new_steps:
                    adapted.append(StrategyStep(
                        algorithm=s.get('algorithm', 'd4'),
                        priority=s.get('priority', len(adapted)+1),
                        reason=s.get('reason', 'AI adapted'),
                        delay_ms=s.get('delay_ms', 500),
                        fallback=s.get('fallback', '')
                    ))
                if adapted:
                    self.strategy = self.strategy[:completed_steps] + adapted
                    return True

        except Exception:
            pass
        return False

    async def _query_ollama(self, prompt: str) -> str:
        """Query Ollama API"""
        def _do_request():
            resp = http_requests.post(
                self.OLLAMA_URL,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 1500}
                },
                timeout=90
            )
            if resp.status_code != 200:
                raise Exception(f"Ollama {resp.status_code}")
            return resp.json().get('response', '')

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_request)

