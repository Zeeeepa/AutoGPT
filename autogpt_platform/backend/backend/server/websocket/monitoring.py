"""
WebSocket Monitoring System.

Provides real-time WebSocket endpoints for streaming system metrics, status updates,
and events to monitoring dashboards and clients.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter
import weakref

logger = logging.getLogger(__name__)

# Global connection manager
connection_manager: Optional['WebSocketConnectionManager'] = None


class WebSocketConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        # Use WeakSet to automatically clean up closed connections
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "metrics": set(),
            "health": set(),
            "sessions": set(),
            "scaling": set(),
            "events": set(),
            "all": set()
        }
        
        # Background tasks
        self._broadcast_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Event queue for broadcasting
        self.event_queue: asyncio.Queue = asyncio.Queue()
        
        # Metrics cache
        self.last_metrics: Dict[str, Any] = {}
        self.last_health: Dict[str, Any] = {}
        
    async def start(self):
        """Start the connection manager."""
        logger.info("Starting WebSocket connection manager")
        
        # Start background tasks
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("WebSocket connection manager started")
    
    async def stop(self):
        """Stop the connection manager."""
        logger.info("Stopping WebSocket connection manager")
        
        # Cancel background tasks
        if self._broadcast_task:
            self._broadcast_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Close all connections
        for channel_connections in self.active_connections.values():
            for connection in list(channel_connections):
                try:
                    await connection.close()
                except:
                    pass
        
        logger.info("WebSocket connection manager stopped")
    
    async def connect(self, websocket: WebSocket, channel: str = "all"):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        if channel not in self.active_connections:
            channel = "all"
        
        self.active_connections[channel].add(websocket)
        self.active_connections["all"].add(websocket)
        
        logger.info(f"WebSocket connected to channel '{channel}'. Total connections: {len(self.active_connections['all'])}")
        
        # Send initial data
        await self._send_initial_data(websocket, channel)
    
    def disconnect(self, websocket: WebSocket, channel: str = "all"):
        """Remove a WebSocket connection."""
        for channel_name, connections in self.active_connections.items():
            connections.discard(websocket)
        
        logger.info(f"WebSocket disconnected from channel '{channel}'. Total connections: {len(self.active_connections['all'])}")
    
    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Broadcast a message to all connections in a specific channel."""
        if channel not in self.active_connections:
            return
        
        message_str = json.dumps(message, default=str)
        dead_connections = set()
        
        for connection in list(self.active_connections[channel]):
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                dead_connections.add(connection)
        
        # Remove dead connections
        for connection in dead_connections:
            self.disconnect(connection, channel)
    
    async def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Queue an event for broadcasting."""
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        try:
            self.event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Event queue is full, dropping event")
    
    async def _send_initial_data(self, websocket: WebSocket, channel: str):
        """Send initial data to a newly connected client."""
        try:
            if channel in ["metrics", "all"] and self.last_metrics:
                await websocket.send_text(json.dumps({
                    "type": "metrics",
                    "timestamp": datetime.now().isoformat(),
                    "data": self.last_metrics
                }, default=str))
            
            if channel in ["health", "all"] and self.last_health:
                await websocket.send_text(json.dumps({
                    "type": "health",
                    "timestamp": datetime.now().isoformat(),
                    "data": self.last_health
                }, default=str))
        
        except Exception as e:
            logger.warning(f"Failed to send initial data: {e}")
    
    async def _broadcast_loop(self):
        """Main broadcast loop for processing events."""
        while True:
            try:
                # Wait for events
                event = await self.event_queue.get()
                
                # Broadcast to appropriate channels
                event_type = event.get("type", "unknown")
                
                if event_type == "metrics":
                    self.last_metrics = event["data"]
                    await self.broadcast_to_channel("metrics", event)
                    await self.broadcast_to_channel("all", event)
                
                elif event_type == "health":
                    self.last_health = event["data"]
                    await self.broadcast_to_channel("health", event)
                    await self.broadcast_to_channel("all", event)
                
                elif event_type == "session_update":
                    await self.broadcast_to_channel("sessions", event)
                    await self.broadcast_to_channel("all", event)
                
                elif event_type == "scaling_event":
                    await self.broadcast_to_channel("scaling", event)
                    await self.broadcast_to_channel("all", event)
                
                else:
                    # Broadcast to events channel and all
                    await self.broadcast_to_channel("events", event)
                    await self.broadcast_to_channel("all", event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
                await asyncio.sleep(1)
    
    async def _cleanup_loop(self):
        """Periodic cleanup of dead connections."""
        while True:
            try:
                await asyncio.sleep(30)  # Cleanup every 30 seconds
                
                total_removed = 0
                for channel_name, connections in self.active_connections.items():
                    dead_connections = set()
                    
                    for connection in list(connections):
                        try:
                            # Try to send a ping
                            await connection.send_text(json.dumps({
                                "type": "ping",
                                "timestamp": datetime.now().isoformat()
                            }))
                        except:
                            dead_connections.add(connection)
                    
                    # Remove dead connections
                    for connection in dead_connections:
                        connections.discard(connection)
                        total_removed += 1
                
                if total_removed > 0:
                    logger.info(f"Cleaned up {total_removed} dead WebSocket connections")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")


# WebSocket router
router = APIRouter()


@router.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics."""
    global connection_manager
    if not connection_manager:
        await websocket.close(code=1011, reason="Connection manager not initialized")
        return
    
    try:
        await connection_manager.connect(websocket, "metrics")
        
        while True:
            # Keep connection alive and handle client messages
            try:
                message = await websocket.receive_text()
                # Handle client messages if needed
                data = json.loads(message)
                
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # Ignore invalid JSON
                pass
            except Exception as e:
                logger.warning(f"Error handling WebSocket message: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket metrics error: {e}")
    finally:
        connection_manager.disconnect(websocket, "metrics")


@router.websocket("/ws/health")
async def websocket_health(websocket: WebSocket):
    """WebSocket endpoint for real-time health status."""
    global connection_manager
    if not connection_manager:
        await websocket.close(code=1011, reason="Connection manager not initialized")
        return
    
    try:
        await connection_manager.connect(websocket, "health")
        
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.warning(f"Error handling WebSocket message: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket health error: {e}")
    finally:
        connection_manager.disconnect(websocket, "health")


@router.websocket("/ws/sessions")
async def websocket_sessions(websocket: WebSocket):
    """WebSocket endpoint for real-time session updates."""
    global connection_manager
    if not connection_manager:
        await websocket.close(code=1011, reason="Connection manager not initialized")
        return
    
    try:
        await connection_manager.connect(websocket, "sessions")
        
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.warning(f"Error handling WebSocket message: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket sessions error: {e}")
    finally:
        connection_manager.disconnect(websocket, "sessions")


@router.websocket("/ws/scaling")
async def websocket_scaling(websocket: WebSocket):
    """WebSocket endpoint for real-time scaling events."""
    global connection_manager
    if not connection_manager:
        await websocket.close(code=1011, reason="Connection manager not initialized")
        return
    
    try:
        await connection_manager.connect(websocket, "scaling")
        
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.warning(f"Error handling WebSocket message: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket scaling error: {e}")
    finally:
        connection_manager.disconnect(websocket, "scaling")


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket endpoint for real-time system events."""
    global connection_manager
    if not connection_manager:
        await websocket.close(code=1011, reason="Connection manager not initialized")
        return
    
    try:
        await connection_manager.connect(websocket, "events")
        
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.warning(f"Error handling WebSocket message: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket events error: {e}")
    finally:
        connection_manager.disconnect(websocket, "events")


@router.websocket("/ws/all")
async def websocket_all(websocket: WebSocket):
    """WebSocket endpoint for all real-time updates."""
    global connection_manager
    if not connection_manager:
        await websocket.close(code=1011, reason="Connection manager not initialized")
        return
    
    try:
        await connection_manager.connect(websocket, "all")
        
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.warning(f"Error handling WebSocket message: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket all error: {e}")
    finally:
        connection_manager.disconnect(websocket, "all")


# Utility functions for broadcasting events
async def broadcast_metrics_update(metrics: Dict[str, Any]):
    """Broadcast metrics update to connected clients."""
    global connection_manager
    if connection_manager:
        await connection_manager.broadcast_event("metrics", metrics)


async def broadcast_health_update(health: Dict[str, Any]):
    """Broadcast health update to connected clients."""
    global connection_manager
    if connection_manager:
        await connection_manager.broadcast_event("health", health)


async def broadcast_session_update(session_event: Dict[str, Any]):
    """Broadcast session update to connected clients."""
    global connection_manager
    if connection_manager:
        await connection_manager.broadcast_event("session_update", session_event)


async def broadcast_scaling_event(scaling_event: Dict[str, Any]):
    """Broadcast scaling event to connected clients."""
    global connection_manager
    if connection_manager:
        await connection_manager.broadcast_event("scaling_event", scaling_event)


async def broadcast_system_event(event_type: str, event_data: Dict[str, Any]):
    """Broadcast general system event to connected clients."""
    global connection_manager
    if connection_manager:
        await connection_manager.broadcast_event(event_type, event_data)


# Initialization functions
async def initialize_websocket_monitoring():
    """Initialize the WebSocket monitoring system."""
    global connection_manager
    
    if connection_manager is None:
        connection_manager = WebSocketConnectionManager()
        await connection_manager.start()
        logger.info("WebSocket monitoring system initialized")
    
    return connection_manager


async def shutdown_websocket_monitoring():
    """Shutdown the WebSocket monitoring system."""
    global connection_manager
    
    if connection_manager:
        await connection_manager.stop()
        connection_manager = None
        logger.info("WebSocket monitoring system shutdown")


def get_connection_manager() -> Optional[WebSocketConnectionManager]:
    """Get the global connection manager."""
    return connection_manager
