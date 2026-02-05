# TikTok Advanced Scraper v2.0

# TikTok Advanced Scraper v3.0

Advanced TikTok profile scraper menggunakan Playwright dengan fitur lengkap.

## ✨ Features

### Scraping
- 📊 Profile scraping (followers, following, likes, bio)
- 👥 Following/Followers list
- 🍪 Cookie injection untuk authenticated sessions

### Graph Algorithms
- 🔍 **BFS** - Breadth-first crawling (level by level)
- 🌲 **DFS** - Depth-first crawling (deep exploration)
- ⭐ **A\* Search** - Find influencers dengan heuristic
- ↔️ **Bidirectional** - Find shortest path antara 2 user
- 🎲 **Random Walk** - Sampling representatif dari network
- 📈 **Influence Score** - PageRank-style ranking
- 👥 **Community Detection** - Label propagation clustering

### Export
- 📁 CSV, Excel, JSON Lines
- 🕸️ GraphML, GEXF (untuk Gephi)
- 📊 Statistics generation

### Anti-Detection
- 🔄 User-Agent rotation (18+ browsers)
- 🌐 Proxy rotation dengan health check
- ⏱️ Smart delays dengan jitter
- 📡 API request sniffing

## 🚀 Installation

```bash
pip install playwright
playwright install chromium
```

## 📖 Usage

### Basic
```bash
# Profile saja
python main.py username

# Save ke JSON
python main.py username --save
```

### Social Features (perlu cookies)
```bash
# Following/Followers
python main.py username --followers --cookies cookies.json
python main.py username --following --cookies cookies.json
```

### Graph Algorithms
```bash
# BFS/DFS crawling
python main.py username --bfs --depth 2 --cookies cookies.json
python main.py username --dfs --depth 3 --cookies cookies.json

# A* Search (cari influencer)
python main.py username --astar --depth 3 --cookies cookies.json

# Find path antara 2 user
python main.py user1 --bidirectional user2 --cookies cookies.json

# Random walk sampling
python main.py username --random-walk --walks 10 --steps 20 --cookies cookies.json

# Influence scoring
python main.py username --influence --max 100 --cookies cookies.json

# Community detection
python main.py username --community --max 100 --cookies cookies.json
```

### Export Options
```bash
# Export ke CSV
python main.py username --bfs --export csv --cookies cookies.json

# Export ke Excel
python main.py username --bfs --export excel --cookies cookies.json

# Export ke GraphML (untuk Gephi)
python main.py username --bfs --export graphml --cookies cookies.json

# Dengan statistics
python main.py username --bfs --export csv --stats --cookies cookies.json
```

### Anti-Detection
```bash
# Dengan proxy
python main.py username --proxy-file proxies.txt

# Delay modes: aggressive, normal, cautious, stealth
python main.py username --delay cautious
```

## 🍪 Cookie Setup

1. Install browser extension "Cookie-Editor"
2. Login ke TikTok
3. Export cookies sebagai JSON
4. Simpan sebagai `cookies.json`

## 📁 Project Structure

```
tiktok/
├── __init__.py      # Package exports
├── models.py        # TikTokProfile dataclass
├── browser.py       # Playwright browser manager
├── scraper.py       # Core scraping logic
├── algorithms.py    # BFS, DFS, A*, Bidirectional, etc
├── export.py        # CSV, Excel, GraphML export
├── rotation.py      # UA & Proxy rotation
├── delays.py        # Smart delays
├── parsers.py       # HTML/JSON parsers
└── sniffer.py       # API interception
```

## 📄 License

MIT
