# TikTok Advanced Scraper v5.1

🚀 **Enterprise-grade TikTok scraping platform** dengan AI/ML integration, advanced stealth, dan distributed processing.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Playwright](https://img.shields.io/badge/playwright-latest-green.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ What's New in v5.1

- 📡 **Real-Time Monitoring** - WebSocket streaming, Telegram alerts, dashboard
- 🔐 **Enhanced Webhook Security** - SSRF protection, replay prevention, rate limiting
- 📊 **Advanced Algorithms** - EMA, Z-score anomaly detection, Token Bucket
- 🤖 **AI/ML Integration** - 11 modules dengan 51+ classes untuk content analysis
- 🥷 **Advanced Stealth** - Browser fingerprint spoofing, human behavior simulation
- 🔄 **Session Isolation** - Complete identity rotation dan context management
- 📊 **Monitoring System** - Real-time metrics, alerts, dan dashboards

---

## 🎯 Features

### Core Scraping

| Feature             | Description                                           |
| ------------------- | ----------------------------------------------------- |
| 📊 Profile Scraping | Followers, following, likes, bio, verification status |
| 👥 Social Network   | Following/followers list extraction                   |
| 🍪 Cookie Injection | Authenticated session support                         |
| 📡 API Interception | Capture internal TikTok API responses                 |

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

---

## 🚀 Installation

### Basic

```bash
pip install playwright
playwright install chromium
```

### Full AI Features

```bash
pip install numpy scikit-learn torch transformers ultralytics opencv-python easyocr
```

---

## 📖 Usage

### Basic Scraping

```bash
# Profile only
python main.py username

# Save to JSON
python main.py username --save
```

### Social Network

```bash
# Following/Followers (requires cookies)
python main.py username --followers --cookies cookies.json
python main.py username --following --cookies cookies.json
```

### Graph Algorithms

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

### Anti-Detection

```bash
# With proxy rotation
python main.py username --proxy-file proxies.txt

# Delay modes: aggressive, normal, cautious, stealth
python main.py username --delay stealth
```

---

## 🍪 Cookie Setup

1. Install browser extension "Cookie-Editor"
2. Login to TikTok
3. Export cookies as JSON
4. Save as `cookies.json`

---

## 📁 Project Structure

```
tiktok/
├── __init__.py          # Package exports (v4.2.0)
├── models.py            # TikTokProfile dataclass
├── browser.py           # Playwright browser manager
├── scraper.py           # Core scraping logic
├── algorithms.py        # Graph algorithms
├── export.py            # Multi-format export
├── rotation.py          # UA/Proxy rotation + chains
├── delays.py            # Smart delays with jitter
├── parsers.py           # HTML/JSON parsers
├── sniffer.py           # API interception
│
├── # Stealth Modules (v4.2.0)
├── fingerprint.py       # Browser fingerprint spoofing
├── human_behavior.py    # Human-like behavior simulation
├── isolation.py         # Session isolation & rotation
│
├── # Utility Modules (v4.1.0)
├── selectors.py         # Centralized CSS selectors
├── async_utils.py       # Async utilities & retry logic
│
└── ai/                  # AI/ML Package (v5.0)
    ├── __init__.py      # 51 class exports
    ├── preprocessing.py # Data pipeline
    ├── resilience.py    # Fault tolerance
    ├── nlp.py           # NLP analysis
    ├── anomaly.py       # Bot/spam detection
    ├── vision.py        # Computer vision
    ├── virality.py      # Viral prediction
    ├── orchestrator.py  # Workflow engine
    ├── monitoring.py    # Metrics & alerts
    ├── fusion.py        # Multimodal fusion
    ├── explainability.py # XAI features
    └── model_registry.py # Model versioning
│
└── monitoring/          # Real-Time Monitoring (v5.1)
    ├── __init__.py      # Package exports
    ├── events.py        # EventEmitter + LRU cache
    ├── metrics.py       # EMA, time windows
    ├── anomaly.py       # Z-score detection
    ├── rate_limiter.py  # Token Bucket
    ├── websocket_server.py # Delta encoding
    ├── webhooks.py      # HMAC + SSRF protection
    ├── notifications/   # Telegram + Circuit Breaker
    └── dashboard/       # FastAPI + Chart.js
```

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
| `websockets`          | Real-time streaming         |
| `fastapi`             | Dashboard backend           |
| `uvicorn`             | ASGI server                 |
| `python-telegram-bot` | Telegram alerts             |
| `aiohttp`             | Async HTTP client           |

---

## 📊 Version History

| Version | Release | Highlights                                                      |
| ------- | ------- | --------------------------------------------------------------- |
| v5.1    | 2026-02 | Real-Time Monitoring (WebSocket, Telegram, Dashboard, Webhooks) |
| v5.0    | 2026-02 | AI/ML Integration (11 modules, 51+ classes)                     |
| v4.2    | 2026-02 | Stealth identity protection                                     |
| v4.1    | 2026-02 | Async utilities, centralized selectors                          |
| v3.0    | 2026-01 | Graph algorithms, export formats                                |
| v2.0    | 2025-12 | Social network scraping                                         |

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Always respect TikTok's Terms of Service and rate limits. The developers are not responsible for any misuse of this software.
