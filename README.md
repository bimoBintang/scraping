# Social Media Scraping Platform v5.3

🚀 **Enterprise-grade scraping platform** untuk **TikTok**, **Instagram**, & **Shopee** dengan AI/ML integration, advanced stealth, dan distributed processing.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Playwright](https://img.shields.io/badge/playwright-latest-green.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ What's New in v5.3

- 📸 **Instagram Scraper v1.6** — 10 algorithms, Hybrid API + Browser + Mobile API
- 🧠 **Adaptive RL Rate Limiter** — Q-Learning based delay optimization
- 🔄 **Account Rotation** — Consistent hashing, multi-cookie support
- 📅 **Predictive Crawling** — FFT-based posting pattern analysis
- 🌐 **Multi-Proxy Rotation** — Latency-based scoring, EMA, geo-routing
- 📂 **Story Highlights Crawler** — 2-step tray→items API with GraphQL fallback
- 🔀 **Selenium/Playwright Hybrid** — Auto engine selection + difficulty scoring
- 📡 **Real-Time Monitoring** — WebSocket streaming, Telegram alerts, dashboard
- 🤖 **AI/ML Integration** — 11 modules dengan 51+ classes untuk content analysis
- 🥷 **Advanced Stealth** — Browser fingerprint spoofing, human behavior simulation

---

## 🎯 Features

### Platform Support

| Platform      | Package       | Capabilities                                              |
| ------------- | ------------- | --------------------------------------------------------- |
| 📹 **TikTok** | `tiktok/`     | Profile, social network, 7 graph algorithms, AI/ML, stealth |
| 📸 **Instagram** | `instagram/` | 10 algorithms, Hybrid API, RL, proxy rotation, highlights |
| 🛍️ **Shopee** | `shopee/`     | Price tracking, wishlist, API client, browser scraping     |

### Core Scraping (TikTok)

| Feature             | Description                                           |
| ------------------- | ----------------------------------------------------- |
| 📊 Profile Scraping | Followers, following, likes, bio, verification status |
| 👥 Social Network   | Following/followers list extraction                   |
| 🍪 Cookie Injection | Authenticated session support                         |
| 📡 API Interception | Capture internal TikTok API responses                 |

### 📸 Instagram Scraper (v1.6)

```
instagram/
├── hybrid_client.py      # Algo 1: Tri-layer API fallback
├── discovery.py          # Algo 2: GraphQL doc_id auto-discovery
├── parsers.py            # Algo 3: 4-strategy HTML parsing
├── location_cluster.py   # Algo 4: DBSCAN user clustering
├── rate_limiter.py       # Algo 5: Q-Learning adaptive rate limiter
├── account_router.py     # Algo 6: Consistent hashing account rotation
├── predictive_crawler.py # Algo 7: FFT posting pattern analysis
├── proxy_rotator.py      # Algo 8: Multi-proxy latency-based rotation
├── highlights_crawler.py # Algo 9: Story highlights tray→items crawler
├── browser_engine.py     # Algo 10: Selenium/Playwright hybrid engine
├── browser.py            # Playwright scraper (Layer 2)
├── models.py             # Profile, Post, Story, Location
├── exporter.py           # CSV/JSON/Excel export
├── selectors.py          # CSS/DOM selectors
└── utils.py              # Cookies, headers, helpers
```

| #  | Algorithm                           | Description                                                |
|----|-------------------------------------|------------------------------------------------------------|
| 1  | 🔄 **Hybrid Tri-Layer Fallback**    | Web API → Browser → Mobile API, auto-switch + exp backoff  |
| 2  | 🔍 **doc_id Auto-Discovery**        | Parse JS bundles for GraphQL doc_ids, cache 7-day TTL      |
| 3  | 📄 **Multi-Fallback Parsing**       | SharedData → additionalData → `__require` → regex          |
| 4  | 📍 **Location Clustering**          | DBSCAN + Haversine + reverse geocoding (25 cities)         |
| 5  | 🧠 **Adaptive RL Rate Limiter**     | Q-Learning, 5 states × 4 actions, epsilon-greedy           |
| 6  | 🔄 **Account Rotation**             | Consistent hashing ring, health-aware failover             |
| 7  | 📅 **Predictive Crawling**          | FFT posting pattern, optimal crawl scheduling              |
| 8  | 🌐 **Multi-Proxy Rotation**         | Composite scoring, EMA latency, geo-routing, auto-ban      |
| 9  | 📂 **Story Highlights Crawler**     | 2-step tray→items, Mobile API + GraphQL fallback           |
| 10 | 🔀 **Selenium/Playwright Hybrid**   | Difficulty scoring, auto engine selection, fallback         |

### Graph Algorithms

| Algorithm                  | Use Case                           |
| -------------------------- | ---------------------------------- |
| 🔍 **BFS**                 | Level-by-level network exploration |
| 🌲 **DFS**                 | Deep path exploration              |
| ⭐ **A\* Search**          | Find influencers with heuristics   |
| ↔️ **Bidirectional**       | Shortest path between 2 users      |
| 🎲 **Random Walk**         | Representative network sampling    |
| 📈 **Influence Score**     | PageRank-style ranking             |
| 👥 **Community Detection** | Label propagation clustering       |

### 🤖 AI/ML Integration (NEW!)

```
tiktok/ai/
├── preprocessing.py    # Video/audio/text pipeline
├── nlp.py              # Sentiment, topics, hashtags
├── anomaly.py          # Bot/spam/fake detection
├── vision.py           # Object detection (YOLO), OCR
├── virality.py         # Viral prediction ML
├── fusion.py           # Cross-modal analysis
├── explainability.py   # SHAP, counterfactuals
├── monitoring.py       # Metrics, alerts, dashboard
├── orchestrator.py     # Workflow management
├── model_registry.py   # Version control, A/B testing
└── resilience.py       # Circuit breaker, fallbacks
```

| Module       | Capabilities                                                    |
| ------------ | --------------------------------------------------------------- |
| **NLP**      | Sentiment analysis (BERT), topic modeling, hashtag trends       |
| **Vision**   | Object detection, scene classification, face analysis, OCR      |
| **Anomaly**  | Bot detection (Isolation Forest), spam patterns, fake followers |
| **Virality** | Predict viral potential dengan deep learning                    |
| **Fusion**   | Early/late/attention-based multimodal fusion                    |
| **XAI**      | Feature importance, counterfactuals, bias detection             |

### 🥷 Stealth & Anti-Detection

| Feature                     | Description                                            |
| --------------------------- | ------------------------------------------------------ |
| 🖥️ **Fingerprint Spoofing** | Canvas, WebGL, fonts, audio, navigator                 |
| 🖱️ **Human Behavior**       | Bezier curve mouse, natural scrolling, typing patterns |
| 🔐 **Session Isolation**    | Complete context separation, emergency wipe            |
| 🌐 **Proxy Chain**          | Multi-hop routing, residential proxy support           |
| 🔄 **Identity Rotation**    | Automatic identity switching with policies             |

### Export Options

- 📁 CSV, Excel, JSON Lines
- 🕸️ GraphML, GEXF (Gephi compatible)
- 📊 Auto-generated statistics

### 📡 Real-Time Monitoring (NEW!)

```
tiktok/monitoring/
├── events.py           # Pub/sub + LRU cache
├── metrics.py          # EMA smoothing, time windows
├── anomaly.py          # Z-score detection
├── rate_limiter.py     # Token Bucket algorithm
├── websocket_server.py # Delta encoding streaming
├── webhooks.py         # HMAC signatures + retry
├── notifications/      # Telegram + Circuit Breaker
└── dashboard/          # FastAPI + Chart.js
```

| Feature           | Capabilities                                  |
| ----------------- | --------------------------------------------- |
| **WebSocket**     | Real-time streaming, delta encoding, pub/sub  |
| **Metrics**       | EMA smoothing, time-windowed aggregation      |
| **Anomaly**       | Z-score detection, spike/drop alerts          |
| **Notifications** | Telegram alerts with Circuit Breaker          |
| **Dashboard**     | FastAPI + Chart.js, REST API                  |
| **Webhooks**      | HMAC-SHA256, replay protection, SSRF blocking |

### 🔬 Advanced Social Network Analysis (NEW!)

```
tiktok/social_analysis/
├── temporal.py     # Network evolution over time
├── cascade.py      # Influence propagation tracking
├── evolution.py    # Community lifecycle analysis
└── power_law.py    # Statistical distribution analysis
```

| Module        | Key Features                                                                        |
| ------------- | ----------------------------------------------------------------------------------- |
| **Temporal**  | Network snapshots, burstiness coefficient, temporal centrality, persistence metrics |
| **Cascade**   | Structural virality index, propagation speed, super-spreader identification         |
| **Evolution** | Merge/split detection, modularity trajectory, community loyalty, boundary spanners  |
| **Power Law** | α exponent fitting, KS test, Gini inequality, heavy-tailedness, scaling breaks      |

---

## 🚀 Installation

### Basic

```bash
pip install playwright requests
playwright install chromium
```

### Full AI Features

```bash
pip install numpy scikit-learn torch transformers ultralytics opencv-python easyocr
```

### Optional (Instagram)

```bash
pip install openpyxl                  # Excel export
pip install selenium                  # Selenium engine
pip install undetected-chromedriver    # Stealth Selenium (recommended)
```

---

## 📖 Usage

### TikTok — Basic Scraping

```bash
# Profile only
python main.py username

# Save to JSON
python main.py username --save
```

### TikTok — Social Network

```bash
# Following/Followers (requires cookies)
python main.py username --followers --cookies cookies.json
python main.py username --following --cookies cookies.json
```

### TikTok — Graph Algorithms

```bash
# BFS/DFS crawling
python main.py username --bfs --depth 2 --cookies cookies.json
python main.py username --dfs --depth 3 --cookies cookies.json

# A* Search (find influencers)
python main.py username --astar --depth 3 --cookies cookies.json

# Path finding between 2 users
python main.py user1 --bidirectional user2 --cookies cookies.json

# Random walk sampling
python main.py username --random-walk --walks 10 --steps 20 --cookies cookies.json

# PageRank influence scoring
python main.py username --influence --max 100 --cookies cookies.json

# Community detection
python main.py username --community --max 100 --cookies cookies.json
```

### 📸 Instagram — CLI

```bash
# Profile scraping
python instagram_main.py cristiano --save

# Multiple profiles + compare
python instagram_main.py cristiano leomessi neymarjr --compare

# Posts scraping
python instagram_main.py cristiano --posts --count 50

# Followers/Following (requires cookies)
python instagram_main.py cristiano --followers --cookies cookies.json
python instagram_main.py cristiano --following --cookies cookies.json

# Search users
python instagram_main.py --search "photography"

# Location-based clustering
python instagram_main.py user1 user2 user3 --cluster-location

# Discover GraphQL doc_ids
python instagram_main.py --discover-doc-ids

# Force specific layer
python instagram_main.py cristiano --layer browser

# Export
python instagram_main.py cristiano --posts --export csv
python instagram_main.py cristiano --export excel

# RL Rate Limiter
python instagram_main.py cristiano --rl-stats       # Show Q-table stats
python instagram_main.py cristiano --no-rl           # Disable RL

# Account Rotation
python instagram_main.py cristiano --accounts-dir ./accounts
python instagram_main.py cristiano --ring-status     # Show hash ring

# Predictive Crawling
python instagram_main.py cristiano --analyze-pattern --count 50
python instagram_main.py cristiano --analyze-pattern --schedule

# Proxy Rotation
python instagram_main.py cristiano --proxy-file proxies.json
python instagram_main.py cristiano --proxy-status    # Show pool status
python instagram_main.py cristiano --test-proxies    # Latency test all

# Story Highlights
python instagram_main.py cristiano --highlights --cookies cookies.json
python instagram_main.py cristiano --highlights --save

# Selenium/Playwright Engine
python instagram_main.py cristiano --engine auto        # default
python instagram_main.py cristiano --engine selenium    # force stealth
python instagram_main.py cristiano --engine-status      # show engine health
```

### 📸 Instagram — Python API

```python
from instagram import (
    HybridInstagramClient,
    LocationClusterAnalyzer,
    DocIdDiscovery,
    InstagramExporter,
    HybridBrowserEngine,
)

# Profile scraping (auto tri-layer fallback)
client = HybridInstagramClient()
profile = client.get_profile("cristiano")
print(profile)  # Formatted output

# Posts
posts = client.get_posts("cristiano", count=50)

# With cookies for authenticated features
client = HybridInstagramClient(cookies_file="cookies.json")
followers = client.get_followers("cristiano", count=100)

# Story Highlights
highlights = client.get_highlights("cristiano")

# Location clustering
analyzer = LocationClusterAnalyzer(eps_km=50)
for user in ["user1", "user2", "user3"]:
    posts = client.get_posts(user, count=50)
    prediction = analyzer.predict_location(user, posts)
    print(f"@{user}: {prediction['predicted_city']}, {prediction['predicted_country']}")

# Full-featured client
client = HybridInstagramClient(
    cookies_file="cookies.json",
    accounts_dir="./accounts",    # Multi-account rotation
    proxy_file="proxies.json",    # Proxy pool
    engine="auto",                # auto/playwright/selenium
)

# Auto-discover GraphQL doc_ids
discovery = DocIdDiscovery()
doc_ids = discovery.discover_all()
print(doc_ids)  # {"user_posts": "123...", "user_followers": "456...", ...}

# Export
exporter = InstagramExporter(output_dir="output")
exporter.profiles_to_csv(profiles)
exporter.posts_to_json(posts, username="cristiano")
```

### AI Analysis

```python
from tiktok.ai import (
    SentimentAnalyzer,
    BotDetector,
    ViralityPredictor,
    WorkflowOrchestrator
)

# Sentiment Analysis
analyzer = SentimentAnalyzer()
result = analyzer.analyze("I love this video! Amazing! 🔥")
print(f"{result.label}: {result.score:.2f}")  # positive: 1.00

# Bot Detection
detector = BotDetector()
bots = detector.detect_bots(profiles, confidence_threshold=0.7)

# Virality Prediction
predictor = ViralityPredictor()
score = predictor.predict(video_metadata, profile)
print(f"Viral potential: {score.tier} ({score.probability:.1%})")
```

### Stealth Mode

```python
from tiktok import (
    FingerprintSpoofing,
    HumanMouse,
    SessionIsolator,
    AutoRotatingProxy
)

# Apply stealth fingerprint
spoof = FingerprintSpoofing()
await spoof.apply_to_page(page)

# Human-like mouse movement
mouse = HumanMouse(page)
await mouse.move_to(500, 300)
await mouse.click()

# Isolated session with proxy
isolator = SessionIsolator(browser)
async with isolator.create_isolated_context(proxy="socks5://...") as ctx:
    page = await ctx.new_page()
```

### Export

```bash
# Export formats
python main.py username --bfs --export csv --cookies cookies.json
python main.py username --bfs --export excel --cookies cookies.json
python main.py username --bfs --export graphml --cookies cookies.json

# With statistics
python main.py username --bfs --export csv --stats --cookies cookies.json
```

### Real-Time Monitoring

```python
from tiktok.monitoring import (
    EventEmitter, MetricsCollector, AnomalyDetector,
    MonitoringWebSocket, TelegramNotifier, DashboardServer
)

# Setup monitoring
events = EventEmitter()
metrics = MetricsCollector()
anomaly = AnomalyDetector()

# Record scraping metrics
metrics.record_scrape("username", duration_ms=150, success=True)

# Detect anomalies (Z-score)
result = anomaly.add_value("response_time", 5000)  # Spike!
if result and result[1]:  # is_anomaly
    print(f"🚨 Anomaly detected! Z-score: {result[0]:.2f}")

# Start WebSocket server
ws = MonitoringWebSocket(port=8765, event_emitter=events)
await ws.start()

# Start Dashboard
dashboard = DashboardServer(metrics=metrics, port=8080)
await dashboard.start()  # Open http://localhost:8080
```

### Telegram Alerts

```python
from tiktok.monitoring import TelegramNotifier, NotificationManager

telegram = TelegramNotifier(
    bot_token="YOUR_BOT_TOKEN",
    chat_id="YOUR_CHAT_ID"
)

manager = NotificationManager()
manager.add_notifier(telegram)
manager.add_default_rules()  # Auto-alert on errors

await manager.process_event(error_event)
```

### Secure Webhooks

```python
from tiktok.monitoring import WebhookDispatcher, WebhookConfig

dispatcher = WebhookDispatcher()
dispatcher.register(WebhookConfig(
    url="https://your-endpoint.com/webhook",
    secret=WebhookConfig.generate_secret(),  # 64-char secure
    events=["error", "rate_limit"],
    validate_url=True,      # SSRF protection
    sanitize_payload=True,  # Redact sensitive data
))

await dispatcher.start()
await dispatcher.dispatch(event)
```

### Social Network Analysis

```python
from tiktok.social_analysis import (
    TemporalNetworkAnalyzer, InfluenceCascadeTracker,
    CommunityEvolutionAnalyzer, PowerLawAnalyzer
)

# Temporal Analysis
temporal = TemporalNetworkAnalyzer(interval_hours=24)
await temporal.capture_snapshot(["user1"], get_connections)
growth = temporal.get_growth_metrics()
print(f"Burstiness: {growth.burstiness_coefficient}")

# Cascade Tracking
tracker = InfluenceCascadeTracker(max_depth=5)
cascade = await tracker.track_cascade("influencer", get_connections)
stats = tracker.get_cascade_statistics(cascade.cascade_id)
print(f"Structural Virality: {stats.structural_virality}")

# Power Law Analysis
analyzer = PowerLawAnalyzer()
fit = analyzer.fit_power_law(follower_counts)
print(f"Alpha: {fit.alpha}, Gini: {analyzer.get_gini_coefficient(follower_counts)}")
```

### Anti-Detection

```bash
# With proxy rotation
python main.py username --proxy-file proxies.txt

# Delay modes: aggressive, normal, cautious, stealth
python main.py username --delay stealth
```

---

## 🍪 Cookie Setup

### TikTok
1. Install browser extension "Cookie-Editor"
2. Login to TikTok
3. Export cookies as JSON → Save as `cookies.json`

### Instagram
1. Install browser extension "Cookie-Editor" / "EditThisCookie"
2. Login to Instagram
3. Export cookies as JSON → Save as `instagram_cookies.json`
4. Use: `python instagram_main.py username --cookies instagram_cookies.json`

---

## 📁 Project Structure

```
├── main.py                 # TikTok CLI entry point
├── tiktok_playwright.py    # TikTok browser scraper
├── tiktok_scraper.py       # TikTok lightweight scraper
├── instagram_main.py       # Instagram CLI entry point (NEW)
├── instagram_playwright.py # Instagram browser scraper (NEW)
├── shopee_main.py          # Shopee CLI entry point
│
├── tiktok/                 # TikTok Package (v4.2.0)
│   ├── models.py           # TikTokProfile dataclass
│   ├── browser.py          # Playwright browser manager
│   ├── scraper.py          # Core scraping logic
│   ├── algorithms.py       # 7 graph algorithms
│   ├── export.py           # Multi-format export
│   ├── fingerprint.py      # Browser fingerprint spoofing
│   ├── human_behavior.py   # Human-like behavior
│   ├── isolation.py        # Session isolation
│   ├── ai/                 # AI/ML (11 modules, 51+ classes)
│   ├── monitoring/         # Real-time monitoring
│   └── social_analysis/    # Network analysis
│
├── instagram/                # Instagram Package v1.6
│   ├── hybrid_client.py      # Algo 1: Tri-layer fallback
│   ├── discovery.py          # Algo 2: doc_id auto-discovery
│   ├── parsers.py            # Algo 3: 4-strategy parsing
│   ├── location_cluster.py   # Algo 4: DBSCAN clustering
│   ├── rate_limiter.py       # Algo 5: RL rate limiter
│   ├── account_router.py     # Algo 6: Account rotation
│   ├── predictive_crawler.py # Algo 7: Predictive crawling
│   ├── proxy_rotator.py      # Algo 8: Proxy rotation
│   ├── highlights_crawler.py # Algo 9: Story highlights
│   ├── browser_engine.py     # Algo 10: Hybrid browser engine
│   ├── browser.py            # Playwright scraper
│   ├── models.py             # Profile, Post, Story, Location
│   ├── exporter.py           # CSV/JSON/Excel export
│   ├── selectors.py          # CSS/DOM selectors
│   └── utils.py              # Cookies, headers, helpers
│
└── shopee/                 # Shopee Package (v1.0)
    ├── api_client.py       # HTTP API client
    ├── browser.py          # Browser scraper
    ├── price_tracker.py    # Price monitoring
    ├── wishlist.py         # Wishlist management
    ├── models.py           # Product data models
    └── exporter.py         # Export utilities
```

---

---

## 🔧 Dependencies

### Required

- `playwright` - Browser automation
- `numpy` - Numerical operations

### Optional (Enhanced Features)

| Package               | Feature                     |
| --------------------- | --------------------------- |
| `torch`               | Deep learning models        |
| `transformers`        | BERT sentiment analysis     |
| `ultralytics`         | YOLOv8 object detection     |
| `opencv-python`       | Video processing            |
| `easyocr`             | Text extraction from images |
| `scikit-learn`        | ML algorithms               |
| `selenium`            | Browser automation (engine) |
| `undetected-chromedriver` | Stealth Selenium        |
| `websockets`          | Real-time streaming         |
| `fastapi`             | Dashboard backend           |
| `uvicorn`             | ASGI server                 |
| `python-telegram-bot` | Telegram alerts             |
| `aiohttp`             | Async HTTP client           |

---

## 📊 Version History

| Version | Release | Highlights                                                              |
| ------- | ------- | ----------------------------------------------------------------------- |
| v5.3    | 2026-02 | **Instagram v1.6** (10 algorithms, highlights, hybrid engine)          |
| v5.2    | 2026-02 | **Instagram Scraper** (Hybrid API, doc_id discovery, location cluster) |
| v5.1    | 2026-02 | Real-Time Monitoring (WebSocket, Telegram, Dashboard, Webhooks)         |
| v5.0    | 2026-02 | AI/ML Integration (11 modules, 51+ classes)                             |
| v4.2    | 2026-02 | Stealth identity protection                                             |
| v4.1    | 2026-02 | Async utilities, centralized selectors                                  |
| v3.0    | 2026-01 | Graph algorithms, export formats                                        |
| v2.0    | 2025-12 | Social network scraping                                                 |

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Always respect each platform's Terms of Service and rate limits. The developers are not responsible for any misuse of this software.
