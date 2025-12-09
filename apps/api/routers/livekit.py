"""
LiveKit Router - Token generation and call management for audio/video calls
Uses LiveKit SFU for scalable, low-latency video/audio streaming
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select, and_, or_, func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging
import uuid

from database import get_session
from models import User, VideoConsultation, Appointment, AppointmentStatus, DoctorProfile
from dependencies import get_current_user
from services.livekit_service import livekit_service, CallType, ParticipantRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/livekit", tags=["LiveKit Video/Audio"])


# ==================== Request/Response Models ====================

class TokenRequest(BaseModel):
    """Request for LiveKit access token"""
    room_name: str = Field(..., description="Room name for the call")
    appointment_id: Optional[int] = Field(None, description="Associated appointment ID")
    call_type: str = Field(default="video", description="Type of call: audio, video, screen_share")

class TokenResponse(BaseModel):
    """Response with LiveKit token and room info"""
    token: str
    room_name: str
    room_url: str
    participant_name: str
    participant_role: str
    call_type: str
    expires_in: int

class StartCallRequest(BaseModel):
    """Request to start a call"""
    appointment_id: int
    call_type: str = Field(default="video")

class CallSessionResponse(BaseModel):
    """Response for call session info"""
    session_id: str
    appointment_id: int
    room_name: str
    doctor_id: int
    patient_id: int
    call_type: str
    status: str
    token: str
    room_url: str
    start_time: Optional[str]
    created_at: str

class EndCallRequest(BaseModel):
    """Request to end a call"""
    session_id: str
    call_quality: Optional[str] = Field(None, description="Call quality rating: excellent, good, fair, poor")

class CallLogResponse(BaseModel):
    """Response for call log entry"""
    id: int
    session_id: str
    appointment_id: int
    doctor_name: str
    patient_name: str
    call_type: str
    status: str
    start_time: Optional[str]
    end_time: Optional[str]
    duration_minutes: Optional[int]
    call_quality: Optional[str]
    created_at: str

class RecordingRequest(BaseModel):
    """Request to start/stop recording"""
    session_id: str

class ActiveCallsResponse(BaseModel):
    """Response for admin active calls monitoring"""
    total_active_calls: int
    calls: List[dict]


# ==================== Token Generation Endpoints ====================

@router.post("/token", response_model=TokenResponse)
async def get_livekit_token(
    request: TokenRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Generate a LiveKit access token for joining a room.
    
    The token contains:
    - User identity
    - Room access permissions
    - Role-based capabilities (publish, subscribe, recording)
    """
    # Determine participant role
    if current_user.role.value == "doctor":
        role = ParticipantRole.DOCTOR
    elif current_user.role.value == "admin":
        role = ParticipantRole.ADMIN
    else:
        role = ParticipantRole.PATIENT
    
    # Parse call type
    try:
        call_type = CallType(request.call_type)
    except ValueError:
        call_type = CallType.VIDEO
    
    # If appointment_id provided, verify access
    if request.appointment_id:
        appointment = session.get(Appointment, request.appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        if current_user.id not in [appointment.doctor_id, appointment.patient_id]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to join this call"
            )
    
    # Generate token
    token = livekit_service.generate_token(
        room_name=request.room_name,
        participant_id=str(current_user.id),
        participant_name=current_user.full_name,
        role=role,
        call_type=call_type
    )
    
    logger.info(f"Generated LiveKit token for user {current_user.id} in room {request.room_name}")
    
    return TokenResponse(
        token=token,
        room_name=request.room_name,
        room_url=livekit_service.config.livekit_url,
        participant_name=current_user.full_name,
        participant_role=role.value,
        call_type=call_type.value,
        expires_in=3600  # Token valid for 1 hour
    )


@router.get("/token/{appointment_id}", response_model=TokenResponse)
async def get_token_for_appointment(
    appointment_id: int,
    call_type: str = Query(default="video"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get a LiveKit token for a specific appointment.
    Room name is auto-generated from appointment ID.
    """
    appointment = session.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    if current_user.id not in [appointment.doctor_id, appointment.patient_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to join this call"
        )
    
    # Generate room name from appointment
    room_name = f"appointment_{appointment_id}"
    
    # Determine role
    if current_user.id == appointment.doctor_id:
        role = ParticipantRole.DOCTOR
    else:
        role = ParticipantRole.PATIENT
    
    try:
        ct = CallType(call_type)
    except ValueError:
        ct = CallType.VIDEO
    
    token = livekit_service.generate_token(
        room_name=room_name,
        participant_id=str(current_user.id),
        participant_name=current_user.full_name,
        role=role,
        call_type=ct
    )
    
    return TokenResponse(
        token=token,
        room_name=room_name,
        room_url=livekit_service.config.livekit_url,
        participant_name=current_user.full_name,
        participant_role=role.value,
        call_type=ct.value,
        expires_in=3600
    )


# ==================== Call Session Management ====================

@router.post("/call/start", response_model=CallSessionResponse)
async def start_call(
    request: StartCallRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Start a new call session for an appointment.
    Only doctors can initiate calls.
    """
    appointment = session.get(Appointment, request.appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Only doctor can start the call
    if current_user.id != appointment.doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can initiate calls"
        )
    
    # Check appointment status
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment is not in scheduled status"
        )
    
    # Check for existing active session
    existing = session.exec(
        select(VideoConsultation).where(
            and_(
                VideoConsultation.appointment_id == request.appointment_id,
                VideoConsultation.status.in_(["scheduled", "in_progress"])
            )
        )
    ).first()
    
    if existing and existing.status == "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A call is already in progress for this appointment"
        )
    
    # Parse call type
    try:
        call_type = CallType(request.call_type)
    except ValueError:
        call_type = CallType.VIDEO
    
    # Create or update video consultation record
    room_name = f"appointment_{request.appointment_id}"
    session_id = str(uuid.uuid4())
    
    if existing:
        existing.session_id = session_id
        existing.status = "in_progress"
        existing.start_time = datetime.utcnow()
        video_session = existing
    else:
        video_session = VideoConsultation(
            appointment_id=request.appointment_id,
            doctor_id=appointment.doctor_id,
            patient_id=appointment.patient_id,
            session_id=session_id,
            status="in_progress",
            start_time=datetime.utcnow()
        )
        session.add(video_session)
    
    # Update appointment status
    appointment.actual_start_time = datetime.utcnow()
    
    session.commit()
    session.refresh(video_session)
    
    # Create call session in service
    await livekit_service.create_call_session(
        session_id=session_id,
        room_name=room_name,
        doctor_id=appointment.doctor_id,
        patient_id=appointment.patient_id,
        call_type=call_type
    )
    
    # Generate token for doctor
    token = livekit_service.generate_token(
        room_name=room_name,
        participant_id=str(current_user.id),
        participant_name=current_user.full_name,
        role=ParticipantRole.DOCTOR,
        call_type=call_type
    )
    
    logger.info(f"Doctor {current_user.id} started call {session_id} for appointment {request.appointment_id}")
    
    return CallSessionResponse(
        session_id=session_id,
        appointment_id=request.appointment_id,
        room_name=room_name,
        doctor_id=appointment.doctor_id,
        patient_id=appointment.patient_id,
        call_type=call_type.value,
        status="in_progress",
        token=token,
        room_url=livekit_service.config.livekit_url,
        start_time=video_session.start_time.isoformat() if video_session.start_time else None,
        created_at=video_session.created_at.isoformat()
    )


@router.post("/call/join/{session_id}", response_model=CallSessionResponse)
async def join_call(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Join an existing call session.
    """
    video_session = session.exec(
        select(VideoConsultation).where(VideoConsultation.session_id == session_id)
    ).first()
    
    if not video_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call session not found"
        )
    
    if current_user.id not in [video_session.doctor_id, video_session.patient_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to join this call"
        )
    
    if video_session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Call is not active (status: {video_session.status})"
        )
    
    room_name = f"appointment_{video_session.appointment_id}"
    
    # Determine role
    if current_user.id == video_session.doctor_id:
        role = ParticipantRole.DOCTOR
    else:
        role = ParticipantRole.PATIENT
    
    # Get call type from active session
    active_session = livekit_service.get_active_session(session_id)
    call_type = active_session.call_type if active_session else CallType.VIDEO
    
    token = livekit_service.generate_token(
        room_name=room_name,
        participant_id=str(current_user.id),
        participant_name=current_user.full_name,
        role=role,
        call_type=call_type
    )
    
    logger.info(f"User {current_user.id} joined call {session_id}")
    
    return CallSessionResponse(
        session_id=session_id,
        appointment_id=video_session.appointment_id,
        room_name=room_name,
        doctor_id=video_session.doctor_id,
        patient_id=video_session.patient_id,
        call_type=call_type.value,
        status=video_session.status,
        token=token,
        room_url=livekit_service.config.livekit_url,
        start_time=video_session.start_time.isoformat() if video_session.start_time else None,
        created_at=video_session.created_at.isoformat()
    )


@router.post("/call/end")
async def end_call(
    request: EndCallRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    End an active call session.
    Both doctor and patient can end the call.
    """
    video_session = session.exec(
        select(VideoConsultation).where(VideoConsultation.session_id == request.session_id)
    ).first()
    
    if not video_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call session not found"
        )
    
    if current_user.id not in [video_session.doctor_id, video_session.patient_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to end this call"
        )
    
    if video_session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Call is not in progress"
        )
    
    # End session
    video_session.status = "completed"
    video_session.end_time = datetime.utcnow()
    video_session.call_quality = request.call_quality
    
    # Calculate duration
    if video_session.start_time:
        duration = video_session.end_time - video_session.start_time
        video_session.duration_minutes = int(duration.total_seconds() / 60)
    
    # Update appointment
    appointment = session.get(Appointment, video_session.appointment_id)
    if appointment:
        appointment.actual_end_time = datetime.utcnow()
        appointment.status = AppointmentStatus.COMPLETED
    
    session.commit()
    
    # End session in service
    await livekit_service.end_call(request.session_id)
    
    logger.info(f"Call {request.session_id} ended by user {current_user.id}, duration: {video_session.duration_minutes} minutes")
    
    return {
        "message": "Call ended successfully",
        "session_id": request.session_id,
        "duration_minutes": video_session.duration_minutes,
        "call_quality": video_session.call_quality
    }


# ==================== Recording Endpoints ====================

@router.post("/recording/start")
async def start_recording(
    request: RecordingRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Start recording a call session.
    Only doctors can start recording.
    """
    video_session = session.exec(
        select(VideoConsultation).where(VideoConsultation.session_id == request.session_id)
    ).first()
    
    if not video_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call session not found"
        )
    
    # Only doctor can record
    if current_user.id != video_session.doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can start recording"
        )
    
    if video_session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Call is not in progress"
        )
    
    room_name = f"appointment_{video_session.appointment_id}"
    
    try:
        recording_id = await livekit_service.start_recording(request.session_id, room_name)
        logger.info(f"Started recording {recording_id} for session {request.session_id}")
        
        return {
            "message": "Recording started",
            "session_id": request.session_id,
            "recording_id": recording_id
        }
    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start recording"
        )


@router.post("/recording/stop")
async def stop_recording(
    request: RecordingRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Stop recording a call session.
    """
    video_session = session.exec(
        select(VideoConsultation).where(VideoConsultation.session_id == request.session_id)
    ).first()
    
    if not video_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call session not found"
        )
    
    if current_user.id != video_session.doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can stop recording"
        )
    
    try:
        recording_url = await livekit_service.stop_recording(request.session_id)
        
        # Save recording URL
        video_session.recording_url = recording_url
        session.commit()
        
        logger.info(f"Stopped recording for session {request.session_id}")
        
        return {
            "message": "Recording stopped",
            "session_id": request.session_id,
            "recording_url": recording_url
        }
    except Exception as e:
        logger.error(f"Failed to stop recording: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop recording"
        )


# ==================== Call History & Logs ====================

@router.get("/calls/history", response_model=List[CallLogResponse])
async def get_call_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get call history for the current user.
    """
    query = select(VideoConsultation).where(
        or_(
            VideoConsultation.doctor_id == current_user.id,
            VideoConsultation.patient_id == current_user.id
        )
    ).order_by(VideoConsultation.created_at.desc()).offset(offset).limit(limit)
    
    calls = session.exec(query).all()
    
    result = []
    for call in calls:
        doctor = session.get(User, call.doctor_id)
        patient = session.get(User, call.patient_id)
        
        result.append(CallLogResponse(
            id=call.id,
            session_id=call.session_id,
            appointment_id=call.appointment_id,
            doctor_name=doctor.full_name if doctor else "Unknown",
            patient_name=patient.full_name if patient else "Unknown",
            call_type="video",  # Default, could be enhanced
            status=call.status,
            start_time=call.start_time.isoformat() if call.start_time else None,
            end_time=call.end_time.isoformat() if call.end_time else None,
            duration_minutes=call.duration_minutes,
            call_quality=call.call_quality,
            created_at=call.created_at.isoformat()
        ))
    
    return result


@router.get("/calls/active")
async def get_my_active_calls(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get active calls for the current user.
    """
    calls = session.exec(
        select(VideoConsultation).where(
            and_(
                or_(
                    VideoConsultation.doctor_id == current_user.id,
                    VideoConsultation.patient_id == current_user.id
                ),
                VideoConsultation.status == "in_progress"
            )
        )
    ).all()
    
    result = []
    for call in calls:
        room_name = f"appointment_{call.appointment_id}"
        
        # Determine role
        if current_user.id == call.doctor_id:
            role = ParticipantRole.DOCTOR
        else:
            role = ParticipantRole.PATIENT
        
        # Get other participant
        other_id = call.patient_id if current_user.id == call.doctor_id else call.doctor_id
        other_user = session.get(User, other_id)
        
        result.append({
            "session_id": call.session_id,
            "appointment_id": call.appointment_id,
            "room_name": room_name,
            "status": call.status,
            "start_time": call.start_time.isoformat() if call.start_time else None,
            "other_participant": {
                "id": other_user.id,
                "name": other_user.full_name,
                "role": other_user.role.value
            } if other_user else None
        })
    
    return result


# ==================== Admin Endpoints ====================

@router.get("/admin/active-calls", response_model=ActiveCallsResponse)
async def admin_get_active_calls(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get all active calls (admin only).
    For live monitoring dashboard.
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    active_calls = session.exec(
        select(VideoConsultation).where(VideoConsultation.status == "in_progress")
    ).all()
    
    calls_data = []
    for call in active_calls:
        doctor = session.get(User, call.doctor_id)
        patient = session.get(User, call.patient_id)
        
        duration = None
        if call.start_time:
            duration = int((datetime.utcnow() - call.start_time).total_seconds() / 60)
        
        calls_data.append({
            "session_id": call.session_id,
            "appointment_id": call.appointment_id,
            "doctor": {
                "id": doctor.id,
                "name": doctor.full_name
            } if doctor else None,
            "patient": {
                "id": patient.id,
                "name": patient.full_name
            } if patient else None,
            "start_time": call.start_time.isoformat() if call.start_time else None,
            "duration_minutes": duration,
            "status": call.status
        })
    
    return ActiveCallsResponse(
        total_active_calls=len(calls_data),
        calls=calls_data
    )


@router.get("/admin/call-stats")
async def admin_get_call_stats(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get call statistics (admin only).
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    since = datetime.utcnow() - timedelta(days=days)
    
    # Total calls
    total_calls = session.exec(
        select(func.count(VideoConsultation.id)).where(
            VideoConsultation.created_at >= since
        )
    ).one()
    
    # Completed calls
    completed_calls = session.exec(
        select(func.count(VideoConsultation.id)).where(
            and_(
                VideoConsultation.created_at >= since,
                VideoConsultation.status == "completed"
            )
        )
    ).one()
    
    # Average duration
    avg_duration = session.exec(
        select(func.avg(VideoConsultation.duration_minutes)).where(
            and_(
                VideoConsultation.created_at >= since,
                VideoConsultation.status == "completed",
                VideoConsultation.duration_minutes.isnot(None)
            )
        )
    ).one()
    
    # Calls by quality
    quality_stats = {}
    for quality in ["excellent", "good", "fair", "poor"]:
        count = session.exec(
            select(func.count(VideoConsultation.id)).where(
                and_(
                    VideoConsultation.created_at >= since,
                    VideoConsultation.call_quality == quality
                )
            )
        ).one()
        quality_stats[quality] = count
    
    return {
        "period_days": days,
        "total_calls": total_calls,
        "completed_calls": completed_calls,
        "completion_rate": round((completed_calls / total_calls * 100) if total_calls > 0 else 0, 2),
        "average_duration_minutes": round(avg_duration or 0, 1),
        "quality_breakdown": quality_stats,
        "active_calls": len(livekit_service.active_sessions)
    }


@router.get("/admin/doctor-call-stats/{doctor_id}")
async def admin_get_doctor_call_stats(
    doctor_id: int,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get call statistics for a specific doctor (admin only).
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    doctor = session.get(User, doctor_id)
    if not doctor or doctor.role.value != "doctor":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    since = datetime.utcnow() - timedelta(days=days)
    
    # Doctor's calls
    total_calls = session.exec(
        select(func.count(VideoConsultation.id)).where(
            and_(
                VideoConsultation.doctor_id == doctor_id,
                VideoConsultation.created_at >= since
            )
        )
    ).one()
    
    completed_calls = session.exec(
        select(func.count(VideoConsultation.id)).where(
            and_(
                VideoConsultation.doctor_id == doctor_id,
                VideoConsultation.created_at >= since,
                VideoConsultation.status == "completed"
            )
        )
    ).one()
    
    avg_duration = session.exec(
        select(func.avg(VideoConsultation.duration_minutes)).where(
            and_(
                VideoConsultation.doctor_id == doctor_id,
                VideoConsultation.created_at >= since,
                VideoConsultation.status == "completed",
                VideoConsultation.duration_minutes.isnot(None)
            )
        )
    ).one()
    
    total_duration = session.exec(
        select(func.sum(VideoConsultation.duration_minutes)).where(
            and_(
                VideoConsultation.doctor_id == doctor_id,
                VideoConsultation.created_at >= since,
                VideoConsultation.status == "completed",
                VideoConsultation.duration_minutes.isnot(None)
            )
        )
    ).one()
    
    return {
        "doctor_id": doctor_id,
        "doctor_name": doctor.full_name,
        "period_days": days,
        "total_calls": total_calls,
        "completed_calls": completed_calls,
        "completion_rate": round((completed_calls / total_calls * 100) if total_calls > 0 else 0, 2),
        "average_duration_minutes": round(avg_duration or 0, 1),
        "total_call_minutes": total_duration or 0
    }
