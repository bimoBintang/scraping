# TikTok Scraper Package v5.1.0

https://chat.deepseek.com/share/vt6phw3j6qo3ra5wse
Advanced TikTok scraper with graph algorithms, 15 DOM bypass algorithms, AI-powered analysis (Ollama), stealth engine, real-time monitoring, and multi-format export.

## Architecture

```mermaid
graph TD
    CLI["_main.py<br/>CLI Entry Point"] --> CORE["Core Layer"]
    CLI --> ALGO["Algorithm Layer"]
    CLI --> DOM["DOM Bypass Layer"]
    CLI --> AI_MCP["AI / MCP Layer"]

    CORE --> scraper["scraper.py"]
    CORE --> browser["browser.py"]
    CORE --> models["models.py"]
    CORE --> parsers["parsers.py"]
    CORE --> selectors["selectors.py"]

    ALGO --> algorithms["algorithms.py<br/>BFS, DFS, A*, Bidirectional,<br/>RandomWalk, Influence, Community"]

    DOM --> recon["reconnaissance.py"]
    DOM --> inject["injection.py"]
    DOM --> maint["maintenance.py"]
    DOM --> dom_algo["dom_algorithms.py<br/>D1-D15 + Orchestrator"]

    AI_MCP --> ai_analyzer["ai_analyzer.py<br/>MCP-D1, MCP-D2"]
    AI_MCP --> ai_pkg["ai/<br/>NLP, Vision, Anomaly,<br/>Virality, Fusion, etc."]

    CLI --> STEALTH["Stealth Layer"]
    STEALTH --> fingerprint["fingerprint.py"]
    STEALTH --> human["human_behavior.py"]
    STEALTH --> isolation["isolation.py"]
    STEALTH --> rotation["rotation.py"]
    STEALTH --> delays["delays.py"]

    CLI --> MON["Monitoring"]
    MON --> mon_pkg["monitoring/<br/>Events, Metrics, WebSocket,<br/>Webhooks, Dashboard"]

    CLI --> SOCIAL["Social Analysis"]
    SOCIAL --> sa_pkg["social_analysis/<br/>Temporal, Cascade,<br/>Evolution, PowerLaw"]

    CLI --> export["export.py<br/>CSV, Excel, JSONL,<br/>GraphML, GEXF"]
    CLI --> sniffer["sniffer.py<br/>API Interceptor"]
```

## Module Reference

### Core

| File | Classes | Description |
|------|---------|-------------|
| `scraper.py` | `TikTokScraper` | Profile, following, followers scraping + manual CAPTCHA handling |
| `browser.py` | `BrowserManager` | Playwright browser lifecycle, cookies, stealth init |
| `models.py` | `TikTokProfile` | Data model (nickname, followers, following, likes, bio) |
| `parsers.py` | — | HTML/JSON profile parser |
| `selectors.py` | — | CSS selectors for TikTok DOM elements |
| `utils.py` | — | Utilities and helpers |

### Graph Algorithms — `algorithms.py`

| Class | Algorithm | Use Case |
|-------|-----------|----------|
| `GraphCrawler` | BFS / DFS / Priority | Network crawling level-by-level or depth-first |
| `AStarCrawler` | A* Search | Find high-value influencers with heuristic |
| `BidirectionalSearch` | Bidirectional BFS | Shortest path between two users |
| `RandomWalkSampler` | Random Walk | Statistical network sampling |
| `InfluenceScorer` | PageRank variant | Calculate influence scores |
| `CommunityDetector` | Label Propagation | Detect community clusters |

### DOM Bypass (4-Phase)

| Phase | File | Class | Description |
|-------|------|-------|-------------|
| 1 | `reconnaissance.py` | `TikTokReconnaissance` | Scan DOM structure, find hidden components |
| 2 | `injection.py` | `TikTokInjector` | Inject JS to intercept/modify behavior |
| 3 | `maintenance.py` | `TikTokMaintenance` | Persistent monitoring, auto-reconnect |
| 4 | `dom_algorithms.py` | `DOMAlgorithmOrchestrator` | Run D1-D15 advanced algorithms |

### Advanced DOM Algorithms (D1-D15) — `dom_algorithms.py`

| # | Class | Technique |
|---|-------|-----------|
| D1 | `ShadowDOMPenetrator` | Force open shadow roots, recursive traversal |
| D2 | `IFrameBridge` | Cross-origin iframe content extraction |
| D3 | `VirtualDOMReconstructor` | Extract React/Vue internal state + fiber tree |
| D4 | `DOMCloner` | Deep DOM serialization with computed styles |
| D5 | `EventLoopInterceptor` | Intercept setTimeout/setInterval/promises |
| D6 | `MutationHistoryTracker` | MutationObserver + historical DOM snapshots |
| D7 | `PseudoElementExtractor` | CSS ::before/::after content extraction |
| D8 | `CanvasWebGLCapture` | Canvas/WebGL rendered text capture |
| D9 | `SVGForeignObjectParser` | SVG embedded HTML/foreignObject parsing |
| D10 | `WebComponentStateAccess` | Custom element internal state access |
| D11 | `LazyLoadingForceTrigger` | Override IntersectionObserver, force all lazy content |
| D12 | `DOMFingerprintDetector` | Detect & bypass anti-tampering |
| D13 | `JSContextIsolationBypass` | Cross-context access, global variable scanning |
| D14 | `CSPBypassInlineHijack` | CSP analysis, nonce reuse, trustedTypes bypass |
| D15 | `ServiceWorkerInterceptor` | Service worker cache inspection |

### AI / MCP — `ai_analyzer.py`

| Algorithm | Class | Description |
|-----------|-------|-------------|
| **MCP-D1** | `AIContextAnalyzer` | Page intelligence → Ollama → framework/anti-bot/bypass report |
| **MCP-D2** | `AdaptiveStrategySelector` | AI-driven D1-D15 ordering + real-time adaptation |

Support class: `PageIntelligenceCollector` (7 collectors: DOM, scripts, framework, storage, anti-bot, network, meta)

### AI/ML Sub-package — `ai/`

| Module | Classes | Description |
|--------|---------|-------------|
| `preprocessing.py` | `PreprocessingPipeline`, `VideoDecoder`, `AudioExtractor`, `TextCleaner` | Data preprocessing |
| `nlp.py` | `NLPAnalyzer`, `SentimentAnalyzer`, `TopicModeler`, `HashtagAnalyzer` | NLP analysis |
| `anomaly.py` | `AnomalyDetector`, `BotDetector`, `SpamDetector` | Anomaly & bot detection |
| `vision.py` | `VideoAnalyzer`, `ObjectDetector`, `SceneClassifier`, `FaceAnalyzer`, `OCRExtractor` | Computer vision |
| `virality.py` | `ViralityPredictor`, `ViralityTrainer` | Viral prediction ML |
| `fusion.py` | `CrossModalFusionEngine`, `EarlyFusion`, `LateFusion` | Multi-modal fusion |
| `explainability.py` | `ExplainableAI`, `SimpleSHAP`, `BiasDetector` | Model explainability |
| `model_registry.py` | `ModelRegistry`, `ABTestManager`, `RollbackManager` | Model versioning |
| `orchestrator.py` | `WorkflowOrchestrator`, `StandardWorkflows` | Workflow management |
| `monitoring.py` | `MonitoringSystem`, `ModelMonitor` | AI metrics monitoring |
| `resilience.py` | `CircuitBreaker`, `FallbackChain`, `GracefulDegradation` | Fault tolerance |

### Stealth Engine

| File | Classes | Description |
|------|---------|-------------|
| `fingerprint.py` | `FingerprintGenerator`, `FingerprintSpoofing`, `IdentityManager` | Canvas, WebGL, navigator, font, audio fingerprint spoofing |
| `human_behavior.py` | `HumanBehavior`, `HumanMouse`, `HumanScroll`, `HumanTyping` | Bézier mouse curves, momentum scroll, realistic typing with typos |
| `isolation.py` | `SessionIsolator`, `EmergencyWipe`, `IdentityRotationPolicy` | Isolated browser contexts, emergency wipe, auto-rotation |
| `rotation.py` | `UserAgentRotator`, `ProxyRotator`, `ProxyChain`, `ResidentialProxyManager` | UA rotation, proxy health checking, multi-hop chains |
| `delays.py` | `DelayManager`, `get_delay_manager` | Configurable delays (aggressive/normal/cautious/stealth) |

### Monitoring — `monitoring/`

| Module | Key Classes | Description |
|--------|-------------|-------------|
| `events.py` | `EventEmitter`, `ScrapingEvent` | Pub/sub event system with LRU cache |
| `metrics.py` | `MetricsCollector`, `ExponentialMovingAverage` | EMA, time-windowed aggregation |
| `anomaly.py` | `AnomalyDetector`, `ZScoreDetector` | Z-score anomaly detection |
| `rate_limiter.py` | `RateLimiter`, `TokenBucket`, `AdaptiveRateLimiter` | Token bucket rate limiting |
| `websocket_server.py` | `MonitoringWebSocket`, `DeltaEncoder` | Real-time streaming with delta encoding |
| `notifications/` | `NotificationManager`, `TelegramNotifier` | Telegram alerts with circuit breaker |
| `webhooks.py` | `WebhookDispatcher` | HMAC-signed webhooks with retry logic |
| `dashboard/` | `DashboardServer` | FastAPI + Chart.js monitoring dashboard |

### Social Analysis — `social_analysis/`

| Module | Key Classes | Description |
|--------|-------------|-------------|
| `temporal.py` | `TemporalNetworkAnalyzer` | Network evolution over time |
| `cascade.py` | `InfluenceCascadeTracker` | Influence propagation tracking |
| `evolution.py` | `CommunityEvolutionAnalyzer` | Community lifecycle analysis |
| `power_law.py` | `PowerLawAnalyzer` | Distribution fitting & heavy-tail metrics |

### Export & Sniffer

| File | Description |
|------|-------------|
| `export.py` | `DataExporter` — CSV, Excel, JSON Lines, GraphML, GEXF |
| `sniffer.py` | `APISniffer` — Intercept TikTok API requests via network layer |
| `async_utils.py` | `with_timeout`, `safe_evaluate`, `async_retry` |

---

## CLI Usage

```bash
# Basic profile
python main.py tiktok username --cookies tiktok_cookies.json

# Following / Followers
python main.py tiktok username --following --cookies tiktok_cookies.json
python main.py tiktok username --followers --cookies tiktok_cookies.json

# Graph algorithms
python main.py tiktok username --bfs --depth 3 --cookies tiktok_cookies.json
python main.py tiktok username --dfs --depth 2 --cookies tiktok_cookies.json
python main.py tiktok username --astar --cookies tiktok_cookies.json
python main.py tiktok username --bidirectional target_user --cookies tiktok_cookies.json
python main.py tiktok username --random-walk --walks 10 --steps 20 --cookies tiktok_cookies.json
python main.py tiktok username --influence --cookies tiktok_cookies.json
python main.py tiktok username --community --cookies tiktok_cookies.json

# DOM bypass
python main.py tiktok username --recon --cookies tiktok_cookies.json
python main.py tiktok username --inject --cookies tiktok_cookies.json
python main.py tiktok username --full-bypass --cookies tiktok_cookies.json
python main.py tiktok username --dom-deep --cookies tiktok_cookies.json

# AI analysis (requires Ollama)
python main.py tiktok username --ai-analyze --cookies tiktok_cookies.json
python main.py tiktok username --ai-strategy --cookies tiktok_cookies.json

# Export
python main.py tiktok username --followers --export csv --cookies tiktok_cookies.json
python main.py tiktok username --bfs --export graphml --cookies tiktok_cookies.json

# Options
python main.py tiktok username --headless          # Headless browser
python main.py tiktok username --max 200           # Max results
python main.py tiktok username --delay stealth     # Delay mode
python main.py tiktok username --proxy-file p.txt  # Proxy rotation
python main.py tiktok username --sniff             # API sniffing
python main.py tiktok username --save              # Save results to JSON
```

## Prerequisites

```bash
pip install playwright requests
python -m playwright install chromium
```

**Optional:**
```bash
pip install openpyxl    # Excel export
pip install pyfiglet    # ASCII banner

# For AI analysis (MCP-D1/D2)
# Install Ollama: https://ollama.com
ollama pull llama3
ollama serve
```

## Configuration

### Cookies
Export cookies dari browser (JSON format) setelah login TikTok:
```bash
python main.py tiktok user --cookies tiktok_cookies.json
```

### Proxy
Buat file proxy (satu per baris):
```
http://user:pass@host:port
socks5://host:port
host:port
```

### Delay Modes

| Mode | Delay Range | Use Case |
|------|-------------|----------|
| `aggressive` | 0.5-1s | Fast but risky |
| `normal` | 1-3s | Default balanced |
| `cautious` | 3-7s | Safer for large scrapes |
| `stealth` | 5-15s | Maximum safety |

---

## File Structure

```
tiktok/
├── __init__.py           # Package exports (v5.1.0)
├── _main.py              # CLI subcommand handler
├── scraper.py            # Core scraper + CAPTCHA handler
├── browser.py            # Playwright browser manager
├── models.py             # Data models
├── parsers.py            # HTML/JSON parsers
├── selectors.py          # CSS selectors
├── utils.py              # Utilities
├── algorithms.py         # Graph algorithms (BFS/DFS/A*/etc)
├── reconnaissance.py     # DOM Phase 1: Recon
├── injection.py          # DOM Phase 2: Injection
├── maintenance.py        # DOM Phase 3: Maintenance
├── dom_algorithms.py     # DOM Phase 4: D1-D15 algorithms
├── ai_analyzer.py        # MCP-D1/D2 AI analysis (Ollama)
├── fingerprint.py        # Browser fingerprint spoofing
├── human_behavior.py     # Human behavior simulation
├── isolation.py          # Session isolation & emergency wipe
├── rotation.py           # UA & proxy rotation
├── delays.py             # Delay management
├── export.py             # Multi-format export
├── sniffer.py            # API request interceptor
├── async_utils.py        # Async helpers
├── ai/                   # AI/ML sub-package (12 modules)
│   ├── preprocessing.py
│   ├── nlp.py
│   ├── anomaly.py
│   ├── vision.py
│   ├── virality.py
│   ├── fusion.py
│   ├── explainability.py
│   ├── model_registry.py
│   ├── orchestrator.py
│   ├── monitoring.py
│   └── resilience.py
├── monitoring/           # Real-time monitoring (7 modules)
│   ├── events.py
│   ├── metrics.py
│   ├── anomaly.py
│   ├── rate_limiter.py
│   ├── websocket_server.py
│   ├── webhooks.py
│   ├── notifications/
│   └── dashboard/
└── social_analysis/      # Social network analysis (4 modules)
    ├── temporal.py
    ├── cascade.py
    ├── evolution.py
    └── power_law.py
```
