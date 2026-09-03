"""
ArthAI Dashboard - WebSocket Manager
Handles real-time push to connected clients
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Set, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages all WebSocket connections and broadcasts"""
    
    def __init__(self):
        # All active connections: {client_id: websocket}
        self.connections: Dict[str, WebSocket] = {}
        # Channel subscriptions: {client_id: set of channels}
        self.subscriptions: Dict[str, Set[str]] = {}
        # Message queue for broadcasting
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
    
    async def connect(self, websocket: WebSocket) -> str:
        """Register a new WebSocket connection"""
        client_id = str(uuid.uuid4())[:8]
        self.connections[client_id] = websocket
        self.subscriptions[client_id] = {"all"}  # Default: all channels
        logger.info(f"WS connected: {client_id} | Total: {len(self.connections)}")
        return client_id
    
    def disconnect(self, client_id: str):
        """Remove a disconnected client"""
        self.connections.pop(client_id, None)
        self.subscriptions.pop(client_id, None)
        logger.info(f"WS disconnected: {client_id} | Remaining: {len(self.connections)}")
    
    def subscribe(self, client_id: str, channel: str):
        """Add client to a specific channel"""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].add(channel)
    
    async def broadcast(self, message: dict, channel: str = "all"):
        """
        Broadcast message to all clients subscribed to channel
        Call this from anywhere in ArthAI to push updates
        """
        await self.message_queue.put({
            "message": message,
            "channel": channel,
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_to_client(self, client_id: str, message: dict):
        """Send message to specific client"""
        if client_id in self.connections:
            try:
                await self.connections[client_id].send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to {client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast_loop(self):
        """
        Background task that processes message queue
        Runs continuously, sends to all matching subscribers
        """
        self._running = True
        logger.info("WebSocket broadcast loop started")
        
        while self._running:
            try:
                # Get message from queue (wait up to 1 second)
                try:
                    item = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                message = item["message"]
                channel = item["channel"]
                
                # Add timestamp and channel to message
                message["_channel"] = channel
                message["_timestamp"] = item["timestamp"]
                
                # Send to all subscribed clients
                disconnected = []
                for client_id, websocket in self.connections.items():
                    client_channels = self.subscriptions.get(client_id, {"all"})
                    
                    # Send if subscribed to channel or "all"
                    if channel in client_channels or "all" in client_channels:
                        try:
                            await websocket.send_json(message)
                        except Exception:
                            disconnected.append(client_id)
                
                # Clean up disconnected clients
                for client_id in disconnected:
                    self.disconnect(client_id)
                    
            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        self._running = False
    
    @property
    def connection_count(self) -> int:
        return len(self.connections)
    
    async def broadcast_signal(self, signal: dict):
        """Broadcast new signal to all clients"""
        await self.broadcast({
            "type": "new_signal",
            "data": signal
        }, channel="signals")
    
    async def broadcast_market_mood(self, mood: dict):
        """Broadcast market mood update"""
        await self.broadcast({
            "type": "market_mood_update",
            "data": mood
        }, channel="market_mood")
    
    async def broadcast_trade_update(self, trade: dict):
        """Broadcast paper trade update"""
        await self.broadcast({
            "type": "trade_update",
            "data": trade
        }, channel="paper_trading")
    
    async def broadcast_system_alert(self, alert: dict):
        """Broadcast system-wide alert"""
        await self.broadcast({
            "type": "system_alert",
            "data": alert
        }, channel="all")


# Singleton instance
ws_manager = WebSocketManager()