"""
LiveKit Service for Audio/Video Calls
Handles LiveKit token generation, room management, and call tracking.
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

# LiveKit Server SDK
try:
    from livekit import api
    from livekit.api import AccessToken, VideoGrants
    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    VideoGrants = None  # Placeholder for type hints when not available
    AccessToken = None
    logging.warning("LiveKit SDK not installed. Install with: pip install livekit-api")

logger = logging.getLogger(__name__)


class CallType(str, Enum):
    """Types of calls supported"""
    AUDIO = "audio"
    VIDEO = "video"
    SCREEN_SHARE = "screen_share"


class ParticipantRole(str, Enum):
    """Participant roles in a call"""
    DOCTOR = "doctor"
    PATIENT = "patient"
    ADMIN = "admin"  # For call monitoring


@dataclass
class LiveKitConfig:
    """LiveKit server configuration"""
    api_key: str
    api_secret: str
    ws_url: str
    http_url: str
    
    @classmethod
    def from_env(cls) -> 'LiveKitConfig':
        """Load configuration from environment variables"""
        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")
        
        # SECURITY: In production, require proper credentials
        is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        if is_production and (not api_key or not api_secret or api_key == "devkey"):
            raise ValueError(
                "LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in production. "
                "Generate secure keys from your LiveKit server."
            )
        
        return cls(
            api_key=api_key or "devkey",  # Only allow devkey in development
            api_secret=api_secret or "secret",
            ws_url=os.getenv("LIVEKIT_WS_URL", "ws://localhost:7880"),
            http_url=os.getenv("LIVEKIT_HTTP_URL", "http://localhost:7880")
        )


@dataclass
class CallSession:
    """Represents an active or completed call session"""
    session_id: str
    room_name: str
    appointment_id: int
    doctor_id: int
    patient_id: int
    call_type: CallType
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: int = 0
    recording_url: Optional[str] = None
    status: str = "pending"  # pending, active, completed, failed
    metadata: Optional[Dict[str, Any]] = None


class LiveKitService:
    """
    Service for managing LiveKit audio/video calls.
    
    Features:
    - Token generation with role-based permissions
    - Room creation and management
    - Call session tracking
    - Recording management
    - Participant management
    """
    
    def __init__(self, config: Optional[LiveKitConfig] = None):
        self.config = config or LiveKitConfig.from_env()
        self._active_sessions: Dict[str, CallSession] = {}
        
        if not LIVEKIT_AVAILABLE:
            logger.warning("LiveKit SDK not available. Call features will be limited.")
    
    def generate_token(
        self,
        room_name: str,
        participant_identity: str,
        participant_name: str,
        role: ParticipantRole,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 3600  # 1 hour default
    ) -> str:
        """
        Generate a LiveKit access token for a participant.
        
        Args:
            room_name: Name of the room to join
            participant_identity: Unique identifier for the participant
            participant_name: Display name for the participant
            role: Role of the participant (doctor/patient/admin)
            metadata: Optional metadata to include in token
            ttl_seconds: Token validity duration
            
        Returns:
            JWT access token string
        """
        if not LIVEKIT_AVAILABLE:
            # Return a mock token for development
            return self._generate_mock_token(room_name, participant_identity, role)
        
        # Create video grants based on role
        grants = self._create_grants_for_role(room_name, role)
        
        # Create access token
        token = AccessToken(
            api_key=self.config.api_key,
            api_secret=self.config.api_secret
        )
        
        # Set token claims
        token.identity = participant_identity
        token.name = participant_name
        token.ttl = timedelta(seconds=ttl_seconds)
        token.video_grants = grants
        
        # Add metadata if provided
        if metadata:
            token.metadata = str(metadata)
        
        return token.to_jwt()
    
    def _create_grants_for_role(self, room_name: str, role: ParticipantRole) -> Any:
        """Create appropriate video grants based on participant role"""
        if not LIVEKIT_AVAILABLE:
            return None
            
        grants = VideoGrants(
            room=room_name,
            room_join=True,
            can_publish=True,
            can_subscribe=True,
        )
        
        if role == ParticipantRole.DOCTOR:
            # Doctors get full permissions
            grants.can_publish_data = True
            grants.can_update_own_metadata = True
            grants.room_record = True
            
        elif role == ParticipantRole.PATIENT:
            # Patients get standard permissions
            grants.can_publish_data = True
            grants.can_update_own_metadata = True
            grants.room_record = False
            
        elif role == ParticipantRole.ADMIN:
            # Admins can monitor but not publish
            grants.can_publish = False
            grants.can_subscribe = True
            grants.room_admin = True
            grants.room_record = True
        
        return grants
    
    def _generate_mock_token(
        self, 
        room_name: str, 
        participant_identity: str, 
        role: ParticipantRole
    ) -> str:
        """Generate a mock token for development when LiveKit SDK is not available"""
        import base64
        import json
        
        payload = {
            "room": room_name,
            "identity": participant_identity,
            "role": role.value,
            "exp": int(time.time()) + 3600,
            "iss": "mock-livekit",
            "sub": participant_identity
        }
        
        # Simple base64 encoding for mock purposes (NOT SECURE - dev only)
        return "mock_" + base64.b64encode(json.dumps(payload).encode()).decode()
    
    def create_room_name(self, appointment_id: int) -> str:
        """Generate a unique room name for an appointment"""
        timestamp = int(time.time())
        return f"consultation_{appointment_id}_{timestamp}"
    
    def create_call_session(
        self,
        appointment_id: int,
        doctor_id: int,
        patient_id: int,
        call_type: CallType = CallType.VIDEO
    ) -> CallSession:
        """Create a new call session for an appointment"""
        room_name = self.create_room_name(appointment_id)
        session_id = f"session_{appointment_id}_{int(time.time())}"
        
        session = CallSession(
            session_id=session_id,
            room_name=room_name,
            appointment_id=appointment_id,
            doctor_id=doctor_id,
            patient_id=patient_id,
            call_type=call_type,
            status="pending"
        )
        
        self._active_sessions[session_id] = session
        logger.info(f"Created call session {session_id} for appointment {appointment_id}")
        
        return session
    
    def start_call(self, session_id: str) -> Optional[CallSession]:
        """Mark a call session as started"""
        if session_id not in self._active_sessions:
            return None
        
        session = self._active_sessions[session_id]
        session.started_at = datetime.utcnow()
        session.status = "active"
        
        logger.info(f"Call session {session_id} started")
        return session
    
    def end_call(self, session_id: str) -> Optional[CallSession]:
        """Mark a call session as ended and calculate duration"""
        if session_id not in self._active_sessions:
            return None
        
        session = self._active_sessions[session_id]
        session.ended_at = datetime.utcnow()
        session.status = "completed"
        
        if session.started_at:
            duration = session.ended_at - session.started_at
            session.duration_seconds = int(duration.total_seconds())
        
        logger.info(f"Call session {session_id} ended. Duration: {session.duration_seconds}s")
        return session
    
    def get_session(self, session_id: str) -> Optional[CallSession]:
        """Get a call session by ID"""
        return self._active_sessions.get(session_id)
    
    def get_active_sessions(self) -> List[CallSession]:
        """Get all active call sessions"""
        return [s for s in self._active_sessions.values() if s.status == "active"]
    
    def get_session_by_appointment(self, appointment_id: int) -> Optional[CallSession]:
        """Get active session for an appointment"""
        for session in self._active_sessions.values():
            if session.appointment_id == appointment_id and session.status in ["pending", "active"]:
                return session
        return None
    
    async def get_room_participants(self, room_name: str) -> List[Dict[str, Any]]:
        """Get list of participants in a room"""
        if not LIVEKIT_AVAILABLE:
            return []
        
        try:
            room_service = api.RoomServiceClient(
                self.config.http_url,
                self.config.api_key,
                self.config.api_secret
            )
            
            participants = await room_service.list_participants(
                api.ListParticipantsRequest(room=room_name)
            )
            
            return [
                {
                    "identity": p.identity,
                    "name": p.name,
                    "state": p.state,
                    "joined_at": p.joined_at,
                    "metadata": p.metadata
                }
                for p in participants.participants
            ]
        except Exception as e:
            logger.error(f"Error getting room participants: {e}")
            return []
    
    async def remove_participant(self, room_name: str, identity: str) -> bool:
        """Remove a participant from a room"""
        if not LIVEKIT_AVAILABLE:
            return False
        
        try:
            room_service = api.RoomServiceClient(
                self.config.http_url,
                self.config.api_key,
                self.config.api_secret
            )
            
            await room_service.remove_participant(
                api.RoomParticipantIdentity(room=room_name, identity=identity)
            )
            
            logger.info(f"Removed participant {identity} from room {room_name}")
            return True
        except Exception as e:
            logger.error(f"Error removing participant: {e}")
            return False
    
    async def start_recording(self, room_name: str, output_file: str) -> Optional[str]:
        """Start recording a room"""
        if not LIVEKIT_AVAILABLE:
            return None
        
        try:
            egress_service = api.EgressServiceClient(
                self.config.http_url,
                self.config.api_key,
                self.config.api_secret
            )
            
            # Start room composite egress (recording)
            egress = await egress_service.start_room_composite_egress(
                api.RoomCompositeEgressRequest(
                    room_name=room_name,
                    file_outputs=[api.EncodedFileOutput(
                        file_type=api.EncodedFileType.MP4,
                        filepath=output_file
                    )]
                )
            )
            
            logger.info(f"Started recording for room {room_name}: {egress.egress_id}")
            return egress.egress_id
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            return None
    
    async def stop_recording(self, egress_id: str) -> bool:
        """Stop a recording"""
        if not LIVEKIT_AVAILABLE:
            return False
        
        try:
            egress_service = api.EgressServiceClient(
                self.config.http_url,
                self.config.api_key,
                self.config.api_secret
            )
            
            await egress_service.stop_egress(api.StopEgressRequest(egress_id=egress_id))
            
            logger.info(f"Stopped recording: {egress_id}")
            return True
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            return False


# Global LiveKit service instance
livekit_service = LiveKitService()
