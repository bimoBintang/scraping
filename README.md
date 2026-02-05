# TikTok Advanced Scraper v2.0

Advanced TikTok scraper dengan BFS/DFS algorithms, proxy rotation, dan API sniffing.

## Features

| Feature | Description |
|---------|-------------|
| **Profile Scraping** | Extract username, followers, likes, bio, etc. |
| **Following/Followers** | Scrape following & followers list (requires cookies) |
| **BFS Crawling** | Breadth-first social network traversal |
| **DFS Crawling** | Depth-first social network traversal |
| **User-Agent Rotation** | 18+ browser fingerprints |
| **Proxy Rotation** | HTTP/SOCKS5 with health checking |
| **Delay + Jitter** | Human-like timing patterns |
| **API Sniffing** | Capture internal TikTok API calls |

## Installation

```bash
pip install playwright
playwright install chromium
```

## Quick Start

```bash
# Basic profile
python main.py username

# Save to JSON
python main.py username --save

# Following/Followers (requires cookies)
python main.py username --followers --cookies cookies.json
python main.py username --following --max 50 --cookies cookies.json
```

## Advanced Usage

```bash
# BFS crawling - level by level
python main.py username --bfs --depth 2 --cookies cookies.json

# DFS crawling - deep first
python main.py username --dfs --depth 2 --cookies cookies.json

# With proxy
python main.py username --proxy-file proxies.txt

# Delay modes: aggressive|normal|cautious|stealth
python main.py username --delay stealth

# Enable API sniffing
python main.py username --sniff --save
```

## Cookie Setup

1. Install [Cookie-Editor](https://cookie-editor.com/) extension
2. Login to TikTok
3. Click Cookie-Editor → Export → JSON
4. Save as `cookies.json`
5. Use: `--cookies cookies.json`

## CLI Options

| Option | Description |
|--------|-------------|
| `--save`, `-s` | Save results to JSON |
| `--cookies`, `-c` | Cookie file path |
| `--max`, `-m` | Max results (default: 100) |
| `--following`, `-f` | Scrape following list |
| `--followers`, `-F` | Scrape followers list |
| `--bfs` | BFS network crawling |
| `--dfs` | DFS network crawling |
| `--depth` | Crawl depth (default: 2) |
| `--proxy-file` | Proxy list file |
| `--delay` | Delay profile |
| `--sniff` | Enable API sniffing |
| `--headless`, `-H` | Headless mode |

## Project Structure

```
tiktok/
├── __init__.py      # Package exports
├── models.py        # TikTokProfile dataclass
├── browser.py       # Browser + rotation + proxy
├── parsers.py       # JSON extraction
├── scraper.py       # Core scraper
├── algorithms.py    # BFS, DFS, Priority Queue
├── rotation.py      # User-Agent & Proxy rotation
├── delays.py        # Delay + jitter
└── sniffer.py       # API interception
```

## Proxy File Format

```
# proxies.txt
http://host:port
socks5://user:pass@host:port
```

## License

MIT
