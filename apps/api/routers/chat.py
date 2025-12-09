"""WebSocket chat router for real-time doctor-patient communication"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from typing import Dict, List, Optional
from datetime import datetime
import json
from database import get_session
from models import User, ChatRoom, ChatMessage
from dependencies import get_current_user
from auth import decode_token

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Connection manager to handle WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
    
    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
    
    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
    
    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
            except Exception:
                self.disconnect(user_id)
    
    async def broadcast_to_room(self, message: str, room_id: int, sender_id: int, db: Session):
        # Get room participants
        room = db.get(ChatRoom, room_id)
        if not room:
            return
        
        participants = [room.doctor_id, room.patient_id]
        for user_id in participants:
            if user_id != sender_id:  # Don't send back to sender
                await self.send_personal_message(message, user_id)

manager = ConnectionManager()

# HTTP endpoints for chat history and room management

@router.post("/rooms", response_model=dict)
async def create_or_get_chat_room(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Create or get existing chat room for an appointment"""
    from models import Appointment
    
    # Get appointment
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Check if user is part of this appointment
    if current_user.id not in [appointment.doctor_id, appointment.patient_id]:
        raise HTTPException(status_code=403, detail="Not authorized to access this chat")
    
    # Check if room already exists
    statement = select(ChatRoom).where(ChatRoom.appointment_id == appointment_id)
    existing_room = db.exec(statement).first()
    
    if existing_room:
        return {
            "room_id": existing_room.id,
            "appointment_id": existing_room.appointment_id,
            "doctor_id": existing_room.doctor_id,
            "patient_id": existing_room.patient_id,
            "created_at": existing_room.created_at.isoformat(),
            "is_active": existing_room.is_active
        }
    
    # Create new room
    new_room = ChatRoom(
        appointment_id=appointment_id,
        doctor_id=appointment.doctor_id,
        patient_id=appointment.patient_id,
        is_active=True
    )
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    
    return {
        "room_id": new_room.id,
        "appointment_id": new_room.appointment_id,
        "doctor_id": new_room.doctor_id,
        "patient_id": new_room.patient_id,
        "created_at": new_room.created_at.isoformat(),
        "is_active": new_room.is_active
    }


@router.get("/rooms/{room_id}/messages")
async def get_chat_messages(
    room_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get chat message history for a room"""
    # Check if room exists and user has access
    room = db.get(ChatRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    if current_user.id not in [room.doctor_id, room.patient_id]:
        raise HTTPException(status_code=403, detail="Not authorized to access this chat")
    
    # Get messages
    statement = (
        select(ChatMessage)
        .where(ChatMessage.room_id == room_id)
        .order_by(ChatMessage.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    messages = db.exec(statement).all()
    
    # Mark messages as read
    for message in messages:
        if message.receiver_id == current_user.id and not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
    db.commit()
    
    return {
        "room_id": room_id,
        "messages": [
            {
                "id": msg.id,
                "sender_id": msg.sender_id,
                "receiver_id": msg.receiver_id,
                "message": msg.message,
                "created_at": msg.created_at.isoformat(),
                "is_read": msg.is_read,
                "read_at": msg.read_at.isoformat() if msg.read_at else None
            }
            for msg in reversed(messages)  # Return in chronological order
        ]
    }


@router.get("/rooms")
async def get_user_chat_rooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get all chat rooms for current user"""
    if current_user.role.value == "doctor":
        statement = select(ChatRoom).where(ChatRoom.doctor_id == current_user.id)
    else:
        statement = select(ChatRoom).where(ChatRoom.patient_id == current_user.id)
    
    rooms = db.exec(statement).all()
    
    result = []
    for room in rooms:
        # Get last message
        last_msg_statement = (
            select(ChatMessage)
            .where(ChatMessage.room_id == room.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        last_message = db.exec(last_msg_statement).first()
        
        # Get unread count
        unread_statement = (
            select(ChatMessage)
            .where(
                ChatMessage.room_id == room.id,
                ChatMessage.receiver_id == current_user.id,
                ChatMessage.is_read == False
            )
        )
        unread_count = len(db.exec(unread_statement).all())
        
        # Get other user info
        other_user_id = room.doctor_id if current_user.id == room.patient_id else room.patient_id
        other_user = db.get(User, other_user_id)
        
        result.append({
            "room_id": room.id,
            "appointment_id": room.appointment_id,
            "other_user": {
                "id": other_user.id,
                "name": other_user.full_name,
                "role": other_user.role.value
            },
            "last_message": {
                "message": last_message.message if last_message else None,
                "created_at": last_message.created_at.isoformat() if last_message else None
            },
            "unread_count": unread_count,
            "is_active": room.is_active
        })
    
    return result


@router.post("/rooms/{room_id}/close")
async def close_chat_room(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Close a chat room (only doctors can close)"""
    room = db.get(ChatRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    # Only doctor can close the room
    if current_user.id != room.doctor_id:
        raise HTTPException(status_code=403, detail="Only doctor can close the chat room")
    
    room.is_active = False
    room.closed_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Chat room closed successfully"}


# WebSocket endpoint for real-time chat

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: int,
    token: str,
    db: Session = Depends(get_session)
):
    """WebSocket endpoint for real-time chat"""
    try:
        # Authenticate user from token
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        user = db.get(User, int(user_id))
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Verify room access
        room = db.get(ChatRoom, room_id)
        if not room or user.id not in [room.doctor_id, room.patient_id]:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Connect to WebSocket
        await manager.connect(user.id, websocket)
        
        # Send connection success message
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "user_id": user.id,
            "room_id": room_id
        })
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Handle typing indicator
                if message_data.get("type") == "typing":
                    await manager.broadcast_to_room(
                        json.dumps({
                            "type": "typing",
                            "user_id": user.id,
                            "is_typing": message_data.get("is_typing", False)
                        }),
                        room_id,
                        user.id,
                        db
                    )
                    continue
                
                # Handle regular message
                message_text = message_data.get("message", "").strip()
                if not message_text:
                    continue
                
                # Determine receiver
                receiver_id = room.doctor_id if user.id == room.patient_id else room.patient_id
                
                # Save message to database
                new_message = ChatMessage(
                    room_id=room_id,
                    sender_id=user.id,
                    receiver_id=receiver_id,
                    message=message_text,
                    is_read=False
                )
                db.add(new_message)
                db.commit()
                db.refresh(new_message)
                
                # Broadcast to room
                broadcast_data = {
                    "type": "message",
                    "id": new_message.id,
                    "room_id": room_id,
                    "sender_id": user.id,
                    "sender_name": user.full_name,
                    "receiver_id": receiver_id,
                    "message": message_text,
                    "created_at": new_message.created_at.isoformat(),
                    "is_read": False
                }
                
                # Send to sender (confirmation)
                await websocket.send_json(broadcast_data)
                
                # Send to receiver
                await manager.broadcast_to_room(
                    json.dumps(broadcast_data),
                    room_id,
                    user.id,
                    db
                )
                
        except WebSocketDisconnect:
            manager.disconnect(user.id)
            
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
