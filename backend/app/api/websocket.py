"""
WebSocket endpoints for real-time notifications and live updates.
Provides real-time analytics, event streaming, and system notifications.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from jose import JWTError, jwt
from typing import List, Set, Dict, Optional
import logging
import json
from datetime import datetime

from app.core.config import settings
from app.core.rbac import Role, normalize_role
from app.core.security import ALGORITHM
from app.db.session import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections for broadcasting real-time updates.
    """
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[str, Set[WebSocket]] = {}  # topic -> set of connections
    
    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Unregister a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from all subscriptions
        for topic_subscriptions in self.subscriptions.values():
            topic_subscriptions.discard(websocket)
        
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")
    
    def subscribe(self, websocket: WebSocket, topic: str):
        """Subscribe a connection to a specific topic"""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = set()
        self.subscriptions[topic].add(websocket)
        logger.info(f"Client subscribed to topic: {topic}")
    
    def unsubscribe(self, websocket: WebSocket, topic: str):
        """Unsubscribe a connection from a topic"""
        if topic in self.subscriptions:
            self.subscriptions[topic].discard(websocket)
    
    async def broadcast(self, message: dict, topic: str = None):
        """
        Broadcast a message to all connected clients or to a specific topic.
        
        Args:
            message: Message dict to broadcast
            topic: If specified, only send to subscribers of this topic
        """
        message["timestamp"] = datetime.utcnow().isoformat()
        message_json = json.dumps(message)
        
        if topic:
            # Send to topic subscribers
            connections = self.subscriptions.get(topic, set())
        else:
            # Send to all connections
            connections = self.active_connections
        
        disconnected = []
        for connection in connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    def get_active_connections_count(self) -> int:
        """Get total number of active connections"""
        return len(self.active_connections)
    
    def get_topic_subscribers_count(self, topic: str) -> int:
        """Get number of subscribers for a topic"""
        return len(self.subscriptions.get(topic, set()))


# Global connection manager
manager = ConnectionManager()


def tenant_topic(tenant_id: Optional[int], topic: str) -> str:
    return f"tenant:{tenant_id or 0}:{topic}"


async def get_websocket_user(websocket: WebSocket) -> Optional[User]:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_tenant_id = payload.get("tenant_id")
        if not email:
            raise JWTError("Missing token subject")
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if (
            not user
            or (token_tenant_id is not None and user.tenant_id is not None and user.tenant_id != token_tenant_id)
            or normalize_role(user.role) not in {Role.admin.value, Role.analyst.value, Role.viewer.value}
        ):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
        return user
    finally:
        db.close()


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket, topic: str = Query("general")):
    """
    WebSocket endpoint for real-time notifications.
    
    Connect with: ws://localhost:8000/ws/notifications?topic=analytics
    
    Topics:
    - general: General system notifications
    - analytics: Real-time analytics updates
    - alerts: Security and warning alerts
    - events: Event stream
    """
    current_user = await get_websocket_user(websocket)
    if not current_user:
        return
    await manager.connect(websocket)
    manager.subscribe(websocket, tenant_topic(current_user.tenant_id, topic))
    
    try:
        while True:
            # Receive heartbeat or commands from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "subscribe":
                    new_topic = message.get("topic")
                    if new_topic:
                        manager.subscribe(websocket, tenant_topic(current_user.tenant_id, new_topic))
                        await websocket.send_json({
                            "type": "subscription_confirmed",
                            "topic": new_topic,
                            "status": "ok"
                        })
                
                elif message.get("type") == "unsubscribe":
                    old_topic = message.get("topic")
                    if old_topic:
                        manager.unsubscribe(websocket, tenant_topic(current_user.tenant_id, old_topic))
                        await websocket.send_json({
                            "type": "unsubscription_confirmed",
                            "topic": old_topic,
                            "status": "ok"
                        })
                
                elif message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            except json.JSONDecodeError:
                # Invalid JSON, send error
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid message format"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.websocket("/ws/analytics")
async def websocket_analytics(websocket: WebSocket):
    """
    WebSocket endpoint for live analytics dashboard.
    
    Streams real-time statistics like:
    - Active user count
    - Events per second
    - Current scenario metrics
    """
    current_user = await get_websocket_user(websocket)
    if not current_user:
        return
    await manager.connect(websocket)
    manager.subscribe(websocket, tenant_topic(current_user.tenant_id, "analytics"))
    
    try:
        while True:
            data = await websocket.receive_text()
            # Process any control messages
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket, scenario_id: str = Query(None)):
    """
    WebSocket endpoint for real-time event stream.
    
    Receives live events like:
    - Email opens
    - Link clicks
    - Phishing reports
    """
    current_user = await get_websocket_user(websocket)
    if not current_user:
        return
    await manager.connect(websocket)
    
    if scenario_id:
        manager.subscribe(websocket, tenant_topic(current_user.tenant_id, f"scenario_{scenario_id}"))
    else:
        manager.subscribe(websocket, tenant_topic(current_user.tenant_id, "events"))
    
    try:
        while True:
            data = await websocket.receive_text()
            # Process control messages
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Helper functions for broadcasting events


async def broadcast_event(event_type: str, event_data: dict, tenant_id: Optional[int]):
    """Broadcast an event to all connected clients"""
    message = {
        "type": event_type,
        "data": event_data,
    }
    await manager.broadcast(message, topic=tenant_topic(tenant_id, "events"))


async def broadcast_analytics_update(metrics: dict, tenant_id: Optional[int]):
    """Broadcast analytics update to subscribers"""
    message = {
        "type": "analytics_update",
        "metrics": metrics,
    }
    await manager.broadcast(message, topic=tenant_topic(tenant_id, "analytics"))


async def broadcast_alert(alert_type: str, title: str, description: str, tenant_id: Optional[int]):
    """Broadcast security alert to all clients"""
    message = {
        "type": "alert",
        "alert_type": alert_type,
        "title": title,
        "description": description,
    }
    await manager.broadcast(message, topic=tenant_topic(tenant_id, "alerts"))


async def send_notification(websocket: WebSocket, notification_type: str, content: dict):
    """Send a notification to a specific client"""
    message = {
        "type": notification_type,
        "content": content,
    }
    try:
        await websocket.send_json(message)
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
