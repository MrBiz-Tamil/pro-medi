"""
WebSocket Manager for Real-Time Chat
Handles WebSocket connections, rooms, messaging, presence, and typing indicators.
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Set, Optional, List, Any
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types"""
    # Chat messages
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"
    
    # Status messages
    TYPING_START = "typing_start"
    TYPING_STOP = "typing_stop"
    PRESENCE_ONLINE = "presence_online"
    PRESENCE_OFFLINE = "presence_offline"
    
    # Delivery receipts
    DELIVERED = "delivered"
    READ = "read"
    
    # Room events
    JOIN_ROOM = "join_room"
    LEAVE_ROOM = "leave_room"
    ROOM_INFO = "room_info"
    
    # Call events
    CALL_INITIATED = "call_initiated"
    CALL_ACCEPTED = "call_accepted"
    CALL_REJECTED = "call_rejected"
    CALL_ENDED = "call_ended"
    
    # Errors
    ERROR = "error"
    ACK = "ack"


@dataclass
class WebSocketMessage:
    """Structure for WebSocket messages"""
    type: MessageType
    room_id: str
    sender_id: int
    sender_name: str
    sender_role: str  # 'doctor' or 'patient'
    content: Optional[str] = None
    message_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.value if isinstance(self.type, MessageType) else self.type,
            "room_id": self.room_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "sender_role": self.sender_role,
            "content": self.content,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata or {}
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class ConnectedUser:
    """Represents a connected WebSocket user"""
    user_id: int
    user_name: str
    user_role: str
    websocket: WebSocket
    connected_at: datetime = field(default_factory=datetime.utcnow)
    rooms: Set[str] = field(default_factory=set)
    is_typing: bool = False
    last_activity: datetime = field(default_factory=datetime.utcnow)


class WebSocketConnectionManager:
    """
    Manages WebSocket connections for real-time chat functionality.
    Handles:
    - Connection/disconnection
    - Room management
    - Message broadcasting
    - Typing indicators
    - Presence tracking
    - Delivery receipts
    """
    
    def __init__(self):
        # Active connections: user_id -> ConnectedUser
        self.active_connections: Dict[int, ConnectedUser] = {}
        
        # Room members: room_id -> Set[user_id]
        self.rooms: Dict[str, Set[int]] = {}
        
        # Message delivery tracking: message_id -> {delivered_to: [], read_by: []}
        self.message_status: Dict[str, Dict[str, List[int]]] = {}
        
        # Typing status: room_id -> Set[user_id]
        self.typing_users: Dict[str, Set[int]] = {}
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def connect(
        self, 
        websocket: WebSocket, 
        user_id: int, 
        user_name: str, 
        user_role: str
    ) -> ConnectedUser:
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        async with self._lock:
            # Disconnect existing connection for this user if any
            if user_id in self.active_connections:
                old_conn = self.active_connections[user_id]
                try:
                    await old_conn.websocket.close()
                except:
                    pass
            
            # Create new connection
            user = ConnectedUser(
                user_id=user_id,
                user_name=user_name,
                user_role=user_role,
                websocket=websocket
            )
            self.active_connections[user_id] = user
            
            logger.info(f"User {user_id} ({user_name}) connected via WebSocket")
            return user
    
    async def disconnect(self, user_id: int):
        """Handle user disconnection"""
        async with self._lock:
            if user_id not in self.active_connections:
                return
            
            user = self.active_connections[user_id]
            
            # Leave all rooms
            for room_id in list(user.rooms):
                await self._leave_room_internal(user_id, room_id)
            
            # Remove from active connections
            del self.active_connections[user_id]
            
            # Broadcast offline status to relevant rooms
            logger.info(f"User {user_id} disconnected")
    
    async def join_room(self, user_id: int, room_id: str) -> bool:
        """Add user to a chat room"""
        async with self._lock:
            if user_id not in self.active_connections:
                return False
            
            user = self.active_connections[user_id]
            
            # Initialize room if needed
            if room_id not in self.rooms:
                self.rooms[room_id] = set()
            
            # Add user to room
            self.rooms[room_id].add(user_id)
            user.rooms.add(room_id)
            
            logger.info(f"User {user_id} joined room {room_id}")
            
        # Notify other room members
        await self.broadcast_to_room(
            room_id=room_id,
            message=WebSocketMessage(
                type=MessageType.JOIN_ROOM,
                room_id=room_id,
                sender_id=user_id,
                sender_name=user.user_name,
                sender_role=user.user_role,
                content=f"{user.user_name} joined the chat"
            ),
            exclude_user=user_id
        )
        
        # Send room info to the user
        await self.send_room_info(user_id, room_id)
        
        return True
    
    async def _leave_room_internal(self, user_id: int, room_id: str):
        """Internal method to leave room without lock"""
        if room_id in self.rooms and user_id in self.rooms[room_id]:
            self.rooms[room_id].discard(user_id)
            
            # Clean up empty rooms
            if not self.rooms[room_id]:
                del self.rooms[room_id]
                if room_id in self.typing_users:
                    del self.typing_users[room_id]
        
        if user_id in self.active_connections:
            self.active_connections[user_id].rooms.discard(room_id)
    
    async def leave_room(self, user_id: int, room_id: str):
        """Remove user from a chat room"""
        user = self.active_connections.get(user_id)
        if not user:
            return
        
        async with self._lock:
            await self._leave_room_internal(user_id, room_id)
        
        # Notify other room members
        await self.broadcast_to_room(
            room_id=room_id,
            message=WebSocketMessage(
                type=MessageType.LEAVE_ROOM,
                room_id=room_id,
                sender_id=user_id,
                sender_name=user.user_name,
                sender_role=user.user_role,
                content=f"{user.user_name} left the chat"
            ),
            exclude_user=user_id
        )
        
        logger.info(f"User {user_id} left room {room_id}")
    
    async def send_personal_message(self, user_id: int, message: WebSocketMessage):
        """Send message to a specific user"""
        if user_id not in self.active_connections:
            return False
        
        try:
            user = self.active_connections[user_id]
            await user.websocket.send_text(message.to_json())
            return True
        except Exception as e:
            logger.error(f"Error sending message to user {user_id}: {e}")
            await self.disconnect(user_id)
            return False
    
    async def broadcast_to_room(
        self, 
        room_id: str, 
        message: WebSocketMessage, 
        exclude_user: Optional[int] = None
    ):
        """Broadcast message to all users in a room"""
        if room_id not in self.rooms:
            return
        
        disconnected_users = []
        
        for user_id in self.rooms[room_id]:
            if exclude_user and user_id == exclude_user:
                continue
            
            if user_id not in self.active_connections:
                disconnected_users.append(user_id)
                continue
            
            try:
                user = self.active_connections[user_id]
                await user.websocket.send_text(message.to_json())
            except Exception as e:
                logger.error(f"Error broadcasting to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            await self.disconnect(user_id)
    
    async def send_room_info(self, user_id: int, room_id: str):
        """Send room information to a user"""
        if room_id not in self.rooms:
            return
        
        members = []
        for member_id in self.rooms[room_id]:
            if member_id in self.active_connections:
                member = self.active_connections[member_id]
                members.append({
                    "user_id": member.user_id,
                    "user_name": member.user_name,
                    "user_role": member.user_role,
                    "is_online": True
                })
        
        message = WebSocketMessage(
            type=MessageType.ROOM_INFO,
            room_id=room_id,
            sender_id=0,
            sender_name="System",
            sender_role="system",
            metadata={
                "members": members,
                "typing_users": list(self.typing_users.get(room_id, set()))
            }
        )
        
        await self.send_personal_message(user_id, message)
    
    async def set_typing(self, user_id: int, room_id: str, is_typing: bool):
        """Update typing status for a user in a room"""
        if user_id not in self.active_connections:
            return
        
        user = self.active_connections[user_id]
        user.is_typing = is_typing
        
        async with self._lock:
            if room_id not in self.typing_users:
                self.typing_users[room_id] = set()
            
            if is_typing:
                self.typing_users[room_id].add(user_id)
            else:
                self.typing_users[room_id].discard(user_id)
        
        # Broadcast typing status
        message_type = MessageType.TYPING_START if is_typing else MessageType.TYPING_STOP
        await self.broadcast_to_room(
            room_id=room_id,
            message=WebSocketMessage(
                type=message_type,
                room_id=room_id,
                sender_id=user_id,
                sender_name=user.user_name,
                sender_role=user.user_role
            ),
            exclude_user=user_id
        )
    
    async def mark_message_delivered(self, message_id: str, user_id: int, room_id: str):
        """Mark a message as delivered to a user"""
        if message_id not in self.message_status:
            self.message_status[message_id] = {"delivered_to": [], "read_by": []}
        
        if user_id not in self.message_status[message_id]["delivered_to"]:
            self.message_status[message_id]["delivered_to"].append(user_id)
        
        # Notify the sender
        await self.broadcast_to_room(
            room_id=room_id,
            message=WebSocketMessage(
                type=MessageType.DELIVERED,
                room_id=room_id,
                sender_id=user_id,
                sender_name="",
                sender_role="",
                message_id=message_id,
                metadata={"delivered_to": user_id}
            )
        )
    
    async def mark_message_read(self, message_id: str, user_id: int, room_id: str):
        """Mark a message as read by a user"""
        if message_id not in self.message_status:
            self.message_status[message_id] = {"delivered_to": [], "read_by": []}
        
        if user_id not in self.message_status[message_id]["read_by"]:
            self.message_status[message_id]["read_by"].append(user_id)
        
        # Notify the sender
        await self.broadcast_to_room(
            room_id=room_id,
            message=WebSocketMessage(
                type=MessageType.READ,
                room_id=room_id,
                sender_id=user_id,
                sender_name="",
                sender_role="",
                message_id=message_id,
                metadata={"read_by": user_id}
            )
        )
    
    def is_user_online(self, user_id: int) -> bool:
        """Check if a user is currently online"""
        return user_id in self.active_connections
    
    def get_online_users_in_room(self, room_id: str) -> List[int]:
        """Get list of online user IDs in a room"""
        if room_id not in self.rooms:
            return []
        return [uid for uid in self.rooms[room_id] if uid in self.active_connections]
    
    def get_room_count(self, room_id: str) -> int:
        """Get number of users in a room"""
        return len(self.rooms.get(room_id, set()))
    
    async def send_error(self, user_id: int, error_message: str, room_id: str = ""):
        """Send error message to a user"""
        await self.send_personal_message(
            user_id,
            WebSocketMessage(
                type=MessageType.ERROR,
                room_id=room_id,
                sender_id=0,
                sender_name="System",
                sender_role="system",
                content=error_message
            )
        )
    
    async def send_ack(self, user_id: int, message_id: str, room_id: str):
        """Send acknowledgment for a message"""
        await self.send_personal_message(
            user_id,
            WebSocketMessage(
                type=MessageType.ACK,
                room_id=room_id,
                sender_id=0,
                sender_name="System",
                sender_role="system",
                message_id=message_id
            )
        )


# Global WebSocket manager instance
ws_manager = WebSocketConnectionManager()
