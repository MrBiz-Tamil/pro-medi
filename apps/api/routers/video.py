"""Video consultation router for WebRTC-based video calls"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional
from datetime import datetime, timedelta
import uuid
from database import get_session
from models import User, VideoConsultation, Appointment, AppointmentStatus
from dependencies import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/api/video", tags=["Video Consultation"])

class VideoSessionRequest(BaseModel):
    appointment_id: int

class VideoSessionResponse(BaseModel):
    session_id: str
    appointment_id: int
    doctor_id: int
    patient_id: int
    status: str
    created_at: str

class UpdateSessionRequest(BaseModel):
    status: Optional[str] = None
    call_quality: Optional[str] = None

@router.post("/sessions", response_model=VideoSessionResponse)
async def create_video_session(
    request: VideoSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Create a new video consultation session"""
    # Get appointment
    appointment = db.get(Appointment, request.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Check if user is part of this appointment
    if current_user.id not in [appointment.doctor_id, appointment.patient_id]:
        raise HTTPException(status_code=403, detail="Not authorized for this appointment")
    
    # Check if appointment is scheduled
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise HTTPException(status_code=400, detail="Appointment is not scheduled")
    
    # Check if session already exists
    statement = select(VideoConsultation).where(
        VideoConsultation.appointment_id == request.appointment_id
    )
    existing_session = db.exec(statement).first()
    
    if existing_session:
        return VideoSessionResponse(
            session_id=existing_session.session_id,
            appointment_id=existing_session.appointment_id,
            doctor_id=existing_session.doctor_id,
            patient_id=existing_session.patient_id,
            status=existing_session.status,
            created_at=existing_session.created_at.isoformat()
        )
    
    # Create new session
    session_id = str(uuid.uuid4())
    new_session = VideoConsultation(
        appointment_id=request.appointment_id,
        doctor_id=appointment.doctor_id,
        patient_id=appointment.patient_id,
        session_id=session_id,
        status="scheduled"
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return VideoSessionResponse(
        session_id=new_session.session_id,
        appointment_id=new_session.appointment_id,
        doctor_id=new_session.doctor_id,
        patient_id=new_session.patient_id,
        status=new_session.status,
        created_at=new_session.created_at.isoformat()
    )


@router.get("/sessions/{session_id}")
async def get_video_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get video session details"""
    statement = select(VideoConsultation).where(
        VideoConsultation.session_id == session_id
    )
    session = db.exec(statement).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Video session not found")
    
    # Check if user is part of this session
    if current_user.id not in [session.doctor_id, session.patient_id]:
        raise HTTPException(status_code=403, detail="Not authorized for this session")
    
    # Get other user info
    other_user_id = session.doctor_id if current_user.id == session.patient_id else session.patient_id
    other_user = db.get(User, other_user_id)
    
    return {
        "session_id": session.session_id,
        "appointment_id": session.appointment_id,
        "status": session.status,
        "start_time": session.start_time.isoformat() if session.start_time else None,
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "duration_minutes": session.duration_minutes,
        "call_quality": session.call_quality,
        "other_user": {
            "id": other_user.id,
            "name": other_user.full_name,
            "role": other_user.role.value
        },
        "created_at": session.created_at.isoformat()
    }


@router.post("/sessions/{session_id}/start")
async def start_video_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Start a video consultation session"""
    statement = select(VideoConsultation).where(
        VideoConsultation.session_id == session_id
    )
    session = db.exec(statement).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Video session not found")
    
    # Check if user is part of this session
    if current_user.id not in [session.doctor_id, session.patient_id]:
        raise HTTPException(status_code=403, detail="Not authorized for this session")
    
    # Only doctor can start the session
    if current_user.id != session.doctor_id:
        raise HTTPException(status_code=403, detail="Only doctor can start the session")
    
    # Check if already started
    if session.status == "in_progress":
        raise HTTPException(status_code=400, detail="Session already in progress")
    
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Session already completed")
    
    # Start session
    session.status = "in_progress"
    session.start_time = datetime.utcnow()
    db.commit()
    
    return {
        "message": "Video session started successfully",
        "session_id": session.session_id,
        "start_time": session.start_time.isoformat()
    }


@router.post("/sessions/{session_id}/end")
async def end_video_session(
    session_id: str,
    call_quality: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """End a video consultation session"""
    statement = select(VideoConsultation).where(
        VideoConsultation.session_id == session_id
    )
    session = db.exec(statement).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Video session not found")
    
    # Check if user is part of this session
    if current_user.id not in [session.doctor_id, session.patient_id]:
        raise HTTPException(status_code=403, detail="Not authorized for this session")
    
    # Check if session is in progress
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session is not in progress")
    
    # End session
    session.status = "completed"
    session.end_time = datetime.utcnow()
    
    # Calculate duration
    if session.start_time:
        duration = session.end_time - session.start_time
        session.duration_minutes = int(duration.total_seconds() / 60)
    
    # Set call quality if provided
    if call_quality:
        session.call_quality = call_quality
    
    db.commit()
    
    # Update appointment status to completed
    appointment = db.get(Appointment, session.appointment_id)
    if appointment and current_user.id == session.doctor_id:
        appointment.status = AppointmentStatus.COMPLETED
        db.commit()
    
    return {
        "message": "Video session ended successfully",
        "session_id": session.session_id,
        "duration_minutes": session.duration_minutes,
        "end_time": session.end_time.isoformat()
    }


@router.get("/sessions/appointment/{appointment_id}")
async def get_session_by_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get video session by appointment ID"""
    # Get appointment
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Check if user is part of this appointment
    if current_user.id not in [appointment.doctor_id, appointment.patient_id]:
        raise HTTPException(status_code=403, detail="Not authorized for this appointment")
    
    # Get session
    statement = select(VideoConsultation).where(
        VideoConsultation.appointment_id == appointment_id
    )
    session = db.exec(statement).first()
    
    if not session:
        return {"session": None}
    
    return {
        "session_id": session.session_id,
        "appointment_id": session.appointment_id,
        "status": session.status,
        "start_time": session.start_time.isoformat() if session.start_time else None,
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "duration_minutes": session.duration_minutes,
        "call_quality": session.call_quality,
        "created_at": session.created_at.isoformat()
    }


@router.get("/history")
async def get_video_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get video consultation history for current user"""
    if current_user.role.value == "doctor":
        statement = select(VideoConsultation).where(
            VideoConsultation.doctor_id == current_user.id
        ).order_by(VideoConsultation.created_at.desc())
    else:
        statement = select(VideoConsultation).where(
            VideoConsultation.patient_id == current_user.id
        ).order_by(VideoConsultation.created_at.desc())
    
    sessions = db.exec(statement).all()
    
    result = []
    for session in sessions:
        # Get other user info
        other_user_id = session.doctor_id if current_user.id == session.patient_id else session.patient_id
        other_user = db.get(User, other_user_id)
        
        # Get appointment info
        appointment = db.get(Appointment, session.appointment_id)
        
        result.append({
            "session_id": session.session_id,
            "appointment_id": session.appointment_id,
            "appointment_date": appointment.appointment_date.isoformat() if appointment else None,
            "appointment_time": appointment.appointment_time.isoformat() if appointment else None,
            "other_user": {
                "id": other_user.id,
                "name": other_user.full_name,
                "role": other_user.role.value
            },
            "status": session.status,
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "duration_minutes": session.duration_minutes,
            "call_quality": session.call_quality,
            "created_at": session.created_at.isoformat()
        })
    
    return result


@router.post("/sessions/{session_id}/cancel")
async def cancel_video_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Cancel a video consultation session"""
    statement = select(VideoConsultation).where(
        VideoConsultation.session_id == session_id
    )
    session = db.exec(statement).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Video session not found")
    
    # Check if user is part of this session
    if current_user.id not in [session.doctor_id, session.patient_id]:
        raise HTTPException(status_code=403, detail="Not authorized for this session")
    
    # Check if session can be cancelled
    if session.status in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Session cannot be cancelled")
    
    # Cancel session
    session.status = "cancelled"
    db.commit()
    
    return {
        "message": "Video session cancelled successfully",
        "session_id": session.session_id
    }
