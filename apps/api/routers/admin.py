from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select
from typing import List
from database import get_session
from models import User, DoctorProfile, UserRole, AdminActivityLog, Appointment
from schemas import UserResponse, AppointmentResponse
from dependencies import require_admin

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def log_activity(
    session: Session,
    admin_id: int,
    action_type: str,
    description: str,
    target_user_id: int = None,
    request: Request = None
):
    """Log admin activity"""
    ip_address = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    
    log = AdminActivityLog(
        admin_id=admin_id,
        action_type=action_type,
        target_user_id=target_user_id,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    session.add(log)
    session.commit()

@router.get("/users", response_model=List[UserResponse])
def list_all_users(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """List all users (admin only)"""
    users = session.exec(select(User)).all()
    return users

@router.put("/users/{user_id}/activate")
def activate_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Activate a user account (admin only)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = True
    session.add(user)
    
    # Log activity
    log_activity(
        session=session,
        admin_id=current_user.id,
        action_type="activate_user",
        description=f"Activated user {user.email}",
        target_user_id=user_id,
        request=request
    )
    
    session.commit()
    
    return {"message": f"User {user.email} activated successfully"}

@router.put("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Deactivate a user account (admin only)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = False
    session.add(user)
    
    # Log activity
    log_activity(
        session=session,
        admin_id=current_user.id,
        action_type="deactivate_user",
        description=f"Deactivated user {user.email}",
        target_user_id=user_id,
        request=request
    )
    
    session.commit()
    
    return {"message": f"User {user.email} deactivated successfully"}

@router.put("/doctors/{doctor_id}/verify")
def verify_doctor(
    doctor_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Verify a doctor profile (admin only)"""
    doctor_profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == doctor_id)
    ).first()
    
    if not doctor_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found"
        )
    
    doctor_profile.is_verified = True
    session.add(doctor_profile)
    
    # Log activity
    log_activity(
        session=session,
        admin_id=current_user.id,
        action_type="verify_doctor",
        description=f"Verified doctor profile for user ID {doctor_id}",
        target_user_id=doctor_id,
        request=request
    )
    
    session.commit()
    
    return {"message": "Doctor verified successfully"}

@router.put("/doctors/{doctor_id}/unverify")
def unverify_doctor(
    doctor_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Remove verification from doctor profile (admin only)"""
    doctor_profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == doctor_id)
    ).first()
    
    if not doctor_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found"
        )
    
    doctor_profile.is_verified = False
    session.add(doctor_profile)
    
    # Log activity
    log_activity(
        session=session,
        admin_id=current_user.id,
        action_type="unverify_doctor",
        description=f"Removed verification from doctor profile for user ID {doctor_id}",
        target_user_id=doctor_id,
        request=request
    )
    
    session.commit()
    
    return {"message": "Doctor verification removed"}

@router.get("/doctors/pending-verification")
def get_pending_doctors(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get list of doctors pending verification (admin only)"""
    pending_doctors = session.exec(
        select(DoctorProfile).where(DoctorProfile.is_verified == False)
    ).all()
    
    return pending_doctors

@router.get("/doctors/online-status")
def get_all_doctors_status(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get online/offline status of all doctors (admin only)"""
    doctors = session.exec(select(DoctorProfile)).all()
    
    return [
        {
            "doctor_id": doc.user_id,
            "is_online": doc.is_online,
            "is_verified": doc.is_verified,
            "last_seen": doc.last_seen,
            "specialization": doc.specialization
        }
        for doc in doctors
    ]

@router.get("/appointments", response_model=List[AppointmentResponse])
def get_all_appointments(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get all appointments in the system (admin only)"""
    appointments = session.exec(
        select(Appointment).order_by(Appointment.start_time.desc())
    ).all()
    
    return appointments
