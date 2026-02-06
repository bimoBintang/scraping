"""
FastAPI Dashboard Application for TikTok Monitoring
Interactive web dashboard with REST API and WebSocket support
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None

from ..events import EventEmitter, ScrapingEvent, EventType
from ..metrics import MetricsCollector


def create_app(
    metrics: Optional[MetricsCollector] = None,
    event_emitter: Optional[EventEmitter] = None,
    title: str = "TikTok Scraper Dashboard"
) -> "FastAPI":
    """
    Create FastAPI application
    
    Args:
        metrics: MetricsCollector instance
        event_emitter: EventEmitter instance
        title: Dashboard title
        
    Returns:
        Configured FastAPI app
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI required. Install with: pip install fastapi uvicorn")
    
    app = FastAPI(
        title=title,
        description="Real-time monitoring dashboard for TikTok Scraper",
        version="1.0.0"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Store instances in app state
    app.state.metrics = metrics or MetricsCollector()
    app.state.event_emitter = event_emitter or EventEmitter()
    app.state.ws_clients: List[WebSocket] = []
    
    # Register routes
    _register_routes(app)
    
    return app


def _register_routes(app: FastAPI) -> None:
    """Register API routes"""
    
    @app.get("/", response_class=HTMLResponse)
    async def get_dashboard():
        """Serve dashboard HTML"""
        return _get_dashboard_html()
    
    @app.get("/api/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "tiktok-scraper-dashboard"
        }
    
    @app.get("/api/stats")
    async def get_stats():
        """Get current statistics"""
        metrics: MetricsCollector = app.state.metrics
        return metrics.get_stats()
    
    @app.get("/api/metrics")
    async def get_metrics(window: int = Query(default=5, ge=1, le=60)):
        """
        Get aggregated metrics for time window
        
        Args:
            window: Time window in minutes
        """
        metrics: MetricsCollector = app.state.metrics
        stats = metrics.get_stats()
        
        return {
            "window_minutes": window,
            "scrapes_per_minute": stats.get("scrapes_per_minute", 0),
            "success_rate": stats.get("success_rate", 1.0),
            "success_rate_ema": stats.get("success_rate_ema", 1.0),
            "response_time_ema": stats.get("response_time_ema", 0),
            "errors_per_minute": stats.get("errors_per_minute", 0),
        }
    
    @app.get("/api/events")
    async def get_events(
        limit: int = Query(default=100, ge=1, le=500),
        event_type: Optional[str] = None
    ):
        """
        Get recent events
        
        Args:
            limit: Maximum number of events
            event_type: Filter by event type
        """
        emitter: EventEmitter = app.state.event_emitter
        
        if event_type:
            try:
                et = EventType(event_type)
                events = emitter.get_events_by_type(et, limit)
            except ValueError:
                raise HTTPException(400, f"Invalid event type: {event_type}")
        else:
            events = emitter.get_recent_events(limit)
        
        return {
            "count": len(events),
            "events": [e.to_dict() for e in events]
        }
    
    @app.get("/api/errors")
    async def get_errors(limit: int = Query(default=50, ge=1, le=200)):
        """Get recent error events"""
        emitter: EventEmitter = app.state.event_emitter
        errors = emitter.get_errors(limit)
        return {
            "count": len(errors),
            "errors": [e.to_dict() for e in errors]
        }
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket for real-time updates"""
        await websocket.accept()
        app.state.ws_clients.append(websocket)
        
        try:
            while True:
                # Send periodic updates
                stats = app.state.metrics.get_stats()
                await websocket.send_json({
                    "type": "stats_update",
                    "data": stats,
                    "timestamp": datetime.now().isoformat()
                })
                await asyncio.sleep(2)  # Update every 2 seconds
        except WebSocketDisconnect:
            app.state.ws_clients.remove(websocket)
        except Exception:
            if websocket in app.state.ws_clients:
                app.state.ws_clients.remove(websocket)


def _get_dashboard_html() -> str:
    """Generate dashboard HTML"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TikTok Scraper Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container { max-width: 1400px; margin: 0 auto; }
        
        header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        
        h1 {
            font-size: 2.5em;
            background: linear-gradient(45deg, #00d4ff, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .status-indicator {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(0,255,136,0.1);
            border-radius: 20px;
            font-size: 0.9em;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            background: #00ff88;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }
        
        .card h3 {
            color: #00d4ff;
            margin-bottom: 20px;
            font-size: 1.1em;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .stat-label {
            color: #aaa;
            font-size: 0.9em;
        }
        
        .stat-change {
            font-size: 0.85em;
            margin-top: 10px;
        }
        
        .stat-change.up { color: #00ff88; }
        .stat-change.down { color: #ff4757; }
        
        .progress-bar {
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 15px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        
        .chart-container {
            height: 250px;
            margin-top: 15px;
        }
        
        .events-list {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .event-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            background: rgba(255,255,255,0.03);
            border-left: 3px solid transparent;
        }
        
        .event-item.error { border-left-color: #ff4757; }
        .event-item.warning { border-left-color: #ffa502; }
        .event-item.info { border-left-color: #00d4ff; }
        
        .event-icon { font-size: 1.5em; }
        .event-details { flex: 1; }
        .event-type { font-weight: 600; }
        .event-time { color: #888; font-size: 0.8em; }
        
        footer {
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 TikTok Scraper Dashboard</h1>
            <div class="status-indicator">
                <span class="status-dot"></span>
                <span id="connection-status">Connecting...</span>
            </div>
        </header>
        
        <div class="grid">
            <div class="card">
                <h3>📊 Total Scrapes</h3>
                <div class="stat-value" id="total-scrapes">0</div>
                <div class="stat-label">profiles scraped</div>
                <div class="stat-change up" id="scrapes-rate">+0/min</div>
            </div>
            
            <div class="card">
                <h3>✅ Success Rate</h3>
                <div class="stat-value" id="success-rate">100%</div>
                <div class="stat-label">successful requests</div>
                <div class="progress-bar">
                    <div class="progress-fill" id="success-bar" style="width: 100%"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>⏱️ Response Time</h3>
                <div class="stat-value" id="response-time">0<small>ms</small></div>
                <div class="stat-label">average (EMA)</div>
            </div>
            
            <div class="card">
                <h3>❌ Errors</h3>
                <div class="stat-value" id="error-count">0</div>
                <div class="stat-label">failed requests</div>
                <div class="stat-change down" id="error-rate">0/min</div>
            </div>
        </div>
        
        <div class="grid">
            <div class="card" style="grid-column: span 2">
                <h3>📈 Scraping Rate</h3>
                <div class="chart-container">
                    <canvas id="rateChart"></canvas>
                </div>
            </div>
            
            <div class="card">
                <h3>📋 Recent Events</h3>
                <div class="events-list" id="events-list">
                    <div class="event-item info">
                        <span class="event-icon">ℹ️</span>
                        <div class="event-details">
                            <div class="event-type">Waiting for events...</div>
                            <div class="event-time">-</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <footer>
            <p>TikTok Scraper Monitoring Dashboard v1.0</p>
        </footer>
    </div>
    
    <script>
        // Chart setup
        const ctx = document.getElementById('rateChart').getContext('2d');
        const rateData = Array(30).fill(0);
        const labels = Array(30).fill('');
        
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Scrapes/min',
                    data: rateData,
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: { 
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#888' }
                    }
                }
            }
        });
        
        // WebSocket connection
        let ws;
        const statusEl = document.getElementById('connection-status');
        
        function connect() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);
            
            ws.onopen = () => {
                statusEl.textContent = 'Connected';
                statusEl.parentElement.style.background = 'rgba(0,255,136,0.1)';
            };
            
            ws.onclose = () => {
                statusEl.textContent = 'Disconnected - Reconnecting...';
                statusEl.parentElement.style.background = 'rgba(255,71,87,0.1)';
                setTimeout(connect, 3000);
            };
            
            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'stats_update') {
                    updateStats(msg.data);
                }
            };
        }
        
        function updateStats(stats) {
            // Update stat cards
            document.getElementById('total-scrapes').textContent = 
                stats.total_scrapes.toLocaleString();
            document.getElementById('scrapes-rate').textContent = 
                `+${stats.scrapes_per_minute.toFixed(1)}/min`;
            
            const successRate = (stats.success_rate * 100).toFixed(1);
            document.getElementById('success-rate').textContent = successRate + '%';
            document.getElementById('success-bar').style.width = successRate + '%';
            
            document.getElementById('response-time').innerHTML = 
                Math.round(stats.response_time_ema) + '<small>ms</small>';
            
            document.getElementById('error-count').textContent = stats.failed_scrapes;
            document.getElementById('error-rate').textContent = 
                stats.errors_per_minute.toFixed(1) + '/min';
            
            // Update chart
            rateData.push(stats.scrapes_per_minute);
            rateData.shift();
            chart.update('none');
        }
        
        // Initial connection
        connect();
        
        // Fetch initial stats
        fetch('/api/stats')
            .then(r => r.json())
            .then(updateStats)
            .catch(console.error);
    </script>
</body>
</html>
"""


class DashboardServer:
    """
    Dashboard server wrapper
    
    Manages FastAPI + Uvicorn server lifecycle
    """
    
    def __init__(
        self,
        metrics: Optional[MetricsCollector] = None,
        event_emitter: Optional[EventEmitter] = None,
        host: str = "0.0.0.0",
        port: int = 8080
    ):
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI required. Install with: pip install fastapi uvicorn")
        
        self.host = host
        self.port = port
        self.metrics = metrics or MetricsCollector()
        self.event_emitter = event_emitter or EventEmitter()
        self._app = create_app(self.metrics, self.event_emitter)
        self._server = None
        self._task: Optional[asyncio.Task] = None
    
    @property
    def app(self) -> FastAPI:
        """Get FastAPI app instance"""
        return self._app
    
    async def start(self) -> None:
        """Start dashboard server asynchronously"""
        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        self._server = uvicorn.Server(config)
        self._task = asyncio.create_task(self._server.serve())
        print(f"[Dashboard] Started on http://{self.host}:{self.port}")
    
    async def stop(self) -> None:
        """Stop dashboard server"""
        if self._server:
            self._server.should_exit = True
            if self._task:
                await self._task
        print("[Dashboard] Stopped")
    
    def run(self) -> None:
        """Run dashboard server (blocking)"""
        uvicorn.run(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
