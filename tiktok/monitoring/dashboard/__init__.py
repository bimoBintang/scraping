"""
Dashboard Package for TikTok Monitoring
FastAPI-based web dashboard with real-time updates
"""

from .app import DashboardServer, create_app

__all__ = [
    'DashboardServer',
    'create_app',
]
