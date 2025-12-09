from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from database import get_session
from models import User, PatientProfile, Appointment, DoctorProfile
from schemas import PatientProfileCreate, PatientProfileUpdate, PatientProfileResponse
from dependencies import get_current_user, require_patient, require_doctor
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(prefix="/api/patients", tags=["Patients"])


# ==================== Additional Schemas for Doctor App ====================

class PatientBasicInfo(BaseModel):
    id: int
    full_name: str
    email: str
    phone_number: Optional[str] = None
    profile_photo: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    last_visit: Optional[datetime] = None
    total_visits: int = 0


class PatientEMR(BaseModel):
    patient_id: int
    patient_name: str
    medical_history: List[dict] = []
    allergies: List[str] = []
    current_medications: List[dict] = []
    vitals_history: List[dict] = []
    recent_consultations: List[dict] = []


class VitalRecord(BaseModel):
    recorded_at: datetime
    blood_pressure: Optional[str] = None
    heart_rate: Optional[int] = None
    temperature: Optional[float] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    oxygen_saturation: Optional[int] = None
    blood_sugar: Optional[float] = None
    notes: Optional[str] = None

@router.post("/profile", response_model=PatientProfileResponse, status_code=status.HTTP_201_CREATED)
def create_patient_profile(
    profile_data: PatientProfileCreate,
    current_user: User = Depends(require_patient),
    session: Session = Depends(get_session)
):
    """Create patient profile (only for users with patient role)"""
    # Check if profile already exists
    existing_profile = session.exec(
        select(PatientProfile).where(PatientProfile.user_id == current_user.id)
    ).first()
    
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient profile already exists"
        )
    
    # Create new profile
    new_profile = PatientProfile(
        user_id=current_user.id,
        **profile_data.model_dump()
    )
    
    session.add(new_profile)
    session.commit()
    session.refresh(new_profile)
    
    return new_profile

@router.get("/profile", response_model=PatientProfileResponse)
def get_my_patient_profile(
    current_user: User = Depends(require_patient),
    session: Session = Depends(get_session)
):
    """Get current patient's profile"""
    profile = session.exec(
        select(PatientProfile).where(PatientProfile.user_id == current_user.id)
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )
    
    return profile

@router.put("/profile", response_model=PatientProfileResponse)
def update_patient_profile(
    profile_data: PatientProfileUpdate,
    current_user: User = Depends(require_patient),
    session: Session = Depends(get_session)
):
    """Update patient profile"""
    profile = session.exec(
        select(PatientProfile).where(PatientProfile.user_id == current_user.id)
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )
    
    # Update fields
    for key, value in profile_data.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    
    session.add(profile)
    session.commit()
    session.refresh(profile)
    
    return profile


# ==================== Endpoints for Doctor App ====================

@router.get("/{patient_id}/profile")
def get_patient_profile_by_id(
    patient_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get patient profile by ID (for doctors)"""
    
    # Verify doctor has treated this patient (has appointment history)
    appointment = session.exec(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .where(Appointment.doctor_id == current_user.id)
    ).first()
    
    if not appointment and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view patients you have treated"
        )
    
    patient = session.get(User, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    profile = session.exec(
        select(PatientProfile).where(PatientProfile.user_id == patient_id)
    ).first()
    
    # Count visits
    total_visits = session.exec(
        select(func.count(Appointment.id))
        .where(Appointment.patient_id == patient_id)
        .where(Appointment.doctor_id == current_user.id)
        .where(Appointment.status == "completed")
    ).first() or 0
    
    # Last visit
    last_appointment = session.exec(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .where(Appointment.doctor_id == current_user.id)
        .where(Appointment.status == "completed")
        .order_by(Appointment.appointment_date.desc())
    ).first()
    
    return {
        "id": patient.id,
        "full_name": patient.full_name,
        "email": patient.email,
        "phone_number": patient.phone_number,
        "profile_photo": getattr(patient, 'profile_photo', None),
        "age": getattr(profile, 'age', None) if profile else None,
        "gender": getattr(profile, 'gender', None) if profile else None,
        "blood_group": getattr(profile, 'blood_group', None) if profile else None,
        "date_of_birth": getattr(profile, 'date_of_birth', None) if profile else None,
        "emergency_contact": getattr(profile, 'emergency_contact', None) if profile else None,
        "address": getattr(profile, 'address', None) if profile else None,
        "last_visit": last_appointment.appointment_date if last_appointment else None,
        "total_visits": total_visits
    }


@router.get("/{patient_id}/emr")
def get_patient_emr(
    patient_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get patient's Electronic Medical Record (for doctors)"""
    
    # Verify doctor has treated this patient
    appointment = session.exec(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .where(Appointment.doctor_id == current_user.id)
    ).first()
    
    if not appointment and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view patients you have treated"
        )
    
    patient = session.get(User, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get patient's appointments with this doctor
    appointments = session.exec(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .where(Appointment.doctor_id == current_user.id)
        .order_by(Appointment.appointment_date.desc())
        .limit(20)
    ).all()
    
    recent_consultations = []
    for apt in appointments:
        recent_consultations.append({
            "appointment_id": apt.id,
            "date": apt.appointment_date.isoformat(),
            "type": apt.consultation_type,
            "status": apt.status,
            "chief_complaint": getattr(apt, 'reason', None),
            "diagnosis": getattr(apt, 'diagnosis', None),
            "notes": getattr(apt, 'notes', None)
        })
    
    return {
        "patient_id": patient_id,
        "patient_name": patient.full_name,
        "medical_history": [],  # Would come from medical_history table
        "allergies": [],  # Would come from patient_allergies table
        "current_medications": [],  # Would come from patient_medications table
        "vitals_history": [],  # Would come from patient_vitals table
        "recent_consultations": recent_consultations
    }


@router.get("/{patient_id}/medical-history")
def get_patient_medical_history(
    patient_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get patient's medical history"""
    
    # In production, fetch from medical_history table
    return {
        "patient_id": patient_id,
        "conditions": [],
        "surgeries": [],
        "family_history": [],
        "immunizations": []
    }


@router.get("/{patient_id}/allergies")
def get_patient_allergies(
    patient_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get patient's allergies"""
    
    # In production, fetch from patient_allergies table
    return {
        "patient_id": patient_id,
        "allergies": []
    }


@router.get("/{patient_id}/medications")
def get_patient_medications(
    patient_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get patient's current medications"""
    
    # In production, fetch from patient_medications table
    return {
        "patient_id": patient_id,
        "current_medications": [],
        "past_medications": []
    }


@router.get("/{patient_id}/vitals")
def get_patient_vitals(
    patient_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get patient's vitals history"""
    
    # In production, fetch from patient_vitals table
    return {
        "patient_id": patient_id,
        "vitals": [],
        "latest": None
    }


@router.post("/{patient_id}/vitals")
def record_patient_vitals(
    patient_id: int,
    vitals: VitalRecord,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Record patient vitals"""
    
    # In production, save to patient_vitals table
    return {
        "message": "Vitals recorded successfully",
        "recorded_at": datetime.utcnow().isoformat()
    }


@router.get("/{patient_id}/documents")
def get_patient_documents(
    patient_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get patient's uploaded documents"""
    
    # In production, fetch from patient_documents table
    return {
        "patient_id": patient_id,
        "documents": []
    }
