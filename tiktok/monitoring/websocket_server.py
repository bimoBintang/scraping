"""
WebSocket Server for TikTok Monitoring
Real-time streaming with Delta Encoding for efficient data transmission
"""

import asyncio
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = Any

from .events import EventEmitter, ScrapingEvent, EventType


class MessageType(str, Enum):
    """WebSocket message types"""
    SCRAPE_UPDATE = "scrape_update"
    METRICS = "metrics"
    ALERT = "alert"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    CONNECTED = "connected"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


@dataclass
class ClientConnection:
    """Represents a connected WebSocket client"""
    websocket: WebSocketServerProtocol
    client_id: str
    connected_at: datetime = field(default_factory=datetime.now)
    subscriptions: Set[str] = field(default_factory=lambda: {"all"})
    last_state: Dict[str, Any] = field(default_factory=dict)
    message_count: int = 0


class DeltaEncoder:
    """
    Delta Encoding for efficient WebSocket transmission
    
    Only sends changed fields instead of full state,
    reducing bandwidth usage significantly for frequent updates.
    
    Algorithm:
    1. Store previous state for each client
    2. Compare new state with previous
    3. Send only changed fields (delta)
    4. Client applies delta to reconstruct full state
    """
    
    def __init__(self):
        self._previous_states: Dict[str, Dict[str, Any]] = {}
    
    def encode(self, client_id: str, new_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encode state as delta from previous state
        
        Args:
            client_id: Unique client identifier
            new_state: Current full state
            
        Returns:
            Delta dict with only changed fields
        """
        if client_id not in self._previous_states:
            # First message - send full state
            self._previous_states[client_id] = new_state.copy()
            return {"_full": True, **new_state}
        
        prev_state = self._previous_states[client_id]
        delta = self._compute_delta(prev_state, new_state)
        
        # Update stored state
        self._previous_states[client_id] = new_state.copy()
        
        if not delta:
            return {"_unchanged": True}
        
        return {"_delta": True, **delta}
    
    def _compute_delta(
        self,
        prev: Dict[str, Any],
        new: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute difference between two states"""
        delta = {}
        
        # Find changed and new keys
        for key, value in new.items():
            if key not in prev:
                delta[key] = value
            elif prev[key] != value:
                # For nested dicts, could recurse here
                delta[key] = value
        
        # Find removed keys
        removed = [k for k in prev if k not in new]
        if removed:
            delta["_removed"] = removed
        
        return delta
    
    def reset(self, client_id: Optional[str] = None) -> None:
        """Reset state for client or all clients"""
        if client_id:
            self._previous_states.pop(client_id, None)
        else:
            self._previous_states.clear()
    
    @staticmethod
    def decode(current_state: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply delta to reconstruct full state (client-side)
        
        Args:
            current_state: Current client state
            delta: Delta received from server
            
        Returns:
            Updated full state
        """
        if delta.get("_full"):
            # Full state update
            return {k: v for k, v in delta.items() if not k.startswith("_")}
        
        if delta.get("_unchanged"):
            return current_state
        
        if delta.get("_delta"):
            new_state = current_state.copy()
            
            # Apply changes
            for key, value in delta.items():
                if not key.startswith("_"):
                    new_state[key] = value
            
            # Remove deleted keys
            for key in delta.get("_removed", []):
                new_state.pop(key, None)
            
            return new_state
        
        return delta


class MonitoringWebSocket:
    """
    WebSocket server for real-time monitoring
    
    Features:
    - Delta encoding for efficient updates
    - Pub/sub with client subscriptions
    - Heartbeat for connection health
    - Integration with EventEmitter
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        event_emitter: Optional[EventEmitter] = None,
        heartbeat_interval: float = 30.0
    ):
        """
        Args:
            host: Server host
            port: Server port
            event_emitter: Event emitter to subscribe to
            heartbeat_interval: Seconds between heartbeats
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library required. Install with: pip install websockets")
        
        self.host = host
        self.port = port
        self.event_emitter = event_emitter or EventEmitter()
        self.heartbeat_interval = heartbeat_interval
        
        self._clients: Dict[str, ClientConnection] = {}
        self._delta_encoder = DeltaEncoder()
        self._server = None
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # Subscribe to all events
        self.event_emitter.subscribe_all_async(self._on_event)
    
    async def start(self) -> None:
        """Start WebSocket server"""
        self._running = True
        self._server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )
        
        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        print(f"[WebSocket] Server started on ws://{self.host}:{self.port}")
    
    async def stop(self) -> None:
        """Stop WebSocket server"""
        self._running = False
        
        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close all client connections
        for client in list(self._clients.values()):
            await client.websocket.close()
        
        # Stop server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        print("[WebSocket] Server stopped")
    
    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        """Handle new client connection"""
        client_id = self._generate_client_id(websocket)
        client = ClientConnection(
            websocket=websocket,
            client_id=client_id
        )
        self._clients[client_id] = client
        
        print(f"[WebSocket] Client connected: {client_id}")
        
        # Send welcome message
        await self._send_to_client(client, {
            "type": MessageType.CONNECTED.value,
            "client_id": client_id,
            "timestamp": datetime.now().isoformat(),
        })
        
        try:
            async for message in websocket:
                await self._handle_message(client, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # Cleanup
            self._clients.pop(client_id, None)
            self._delta_encoder.reset(client_id)
            print(f"[WebSocket] Client disconnected: {client_id}")
    
    async def _handle_message(self, client: ClientConnection, message: str) -> None:
        """Handle incoming message from client"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == MessageType.SUBSCRIBE.value:
                # Add subscription
                topics = data.get("topics", [])
                client.subscriptions.update(topics)
                await self._send_to_client(client, {
                    "type": "subscribed",
                    "topics": list(client.subscriptions)
                })
            
            elif msg_type == MessageType.UNSUBSCRIBE.value:
                # Remove subscription
                topics = data.get("topics", [])
                client.subscriptions -= set(topics)
                await self._send_to_client(client, {
                    "type": "unsubscribed",
                    "topics": list(client.subscriptions)
                })
            
        except json.JSONDecodeError:
            await self._send_to_client(client, {
                "type": MessageType.ERROR.value,
                "message": "Invalid JSON"
            })
    
    async def _on_event(self, event: ScrapingEvent) -> None:
        """Handle event from EventEmitter"""
        message = {
            "type": MessageType.SCRAPE_UPDATE.value,
            "event": event.to_dict()
        }
        
        await self.broadcast(message, topic=event.event_type.value)
    
    async def broadcast(
        self,
        message: Dict[str, Any],
        topic: str = "all",
        use_delta: bool = True
    ) -> None:
        """
        Broadcast message to all subscribed clients
        
        Args:
            message: Message to send
            topic: Topic for filtering
            use_delta: Whether to use delta encoding
        """
        for client in list(self._clients.values()):
            # Check subscription
            if topic != "all" and topic not in client.subscriptions and "all" not in client.subscriptions:
                continue
            
            await self._send_to_client(client, message, use_delta)
    
    async def broadcast_metrics(self, metrics: Dict[str, Any]) -> None:
        """Broadcast metrics update"""
        await self.broadcast({
            "type": MessageType.METRICS.value,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }, topic="metrics", use_delta=True)
    
    async def broadcast_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "warning",
        data: Optional[Dict] = None
    ) -> None:
        """Broadcast alert to all clients"""
        await self.broadcast({
            "type": MessageType.ALERT.value,
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        }, topic="alerts", use_delta=False)
    
    async def _send_to_client(
        self,
        client: ClientConnection,
        message: Dict[str, Any],
        use_delta: bool = False
    ) -> None:
        """Send message to specific client"""
        try:
            if use_delta and "type" in message and message["type"] == MessageType.METRICS.value:
                # Apply delta encoding for metrics
                encoded = self._delta_encoder.encode(client.client_id, message)
                payload = json.dumps(encoded)
            else:
                payload = json.dumps(message)
            
            await client.websocket.send(payload)
            client.message_count += 1
            
        except Exception as e:
            print(f"[WebSocket] Error sending to {client.client_id}: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats"""
        while self._running:
            await asyncio.sleep(self.heartbeat_interval)
            
            await self.broadcast({
                "type": MessageType.HEARTBEAT.value,
                "timestamp": datetime.now().isoformat(),
                "clients": len(self._clients)
            }, use_delta=False)
    
    def _generate_client_id(self, websocket: WebSocketServerProtocol) -> str:
        """Generate unique client ID"""
        remote = str(websocket.remote_address)
        timestamp = str(datetime.now().timestamp())
        return hashlib.md5(f"{remote}:{timestamp}".encode()).hexdigest()[:12]
    
    @property
    def client_count(self) -> int:
        """Number of connected clients"""
        return len(self._clients)
    
    @property
    def is_running(self) -> bool:
        """Whether server is running"""
        return self._running
    
    def get_client_stats(self) -> List[Dict]:
        """Get stats for all connected clients"""
        return [
            {
                "client_id": c.client_id,
                "connected_at": c.connected_at.isoformat(),
                "subscriptions": list(c.subscriptions),
                "message_count": c.message_count,
            }
            for c in self._clients.values()
        ]
