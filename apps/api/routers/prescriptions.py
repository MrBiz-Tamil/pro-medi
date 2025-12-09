"""Prescription management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from database import get_session
from models import User, Prescription, Appointment, AppointmentStatus
from schemas import PrescriptionCreate, PrescriptionUpdate, PrescriptionResponse
from dependencies import get_current_user, require_doctor
from typing import List

router = APIRouter(prefix="/api/prescriptions", tags=["Prescriptions"])


@router.post("", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED)
def create_prescription(
    prescription_data: PrescriptionCreate,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Create prescription for an appointment (doctors only)"""
    # Verify appointment exists
    appointment = session.get(Appointment, prescription_data.appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Verify doctor is the assigned doctor for this appointment
    if appointment.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create prescriptions for your own appointments"
        )
    
    # Check if prescription already exists
    existing = session.exec(
        select(Prescription).where(Prescription.appointment_id == prescription_data.appointment_id)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prescription already exists for this appointment. Use update endpoint."
        )
    
    # Create prescription
    new_prescription = Prescription(
        **prescription_data.model_dump()
    )
    
    session.add(new_prescription)
    
    # Mark appointment as completed if not already
    if appointment.status != AppointmentStatus.COMPLETED:
        appointment.status = AppointmentStatus.COMPLETED
        session.add(appointment)
    
    session.commit()
    session.refresh(new_prescription)
    
    return new_prescription


@router.get("", response_model=List[PrescriptionResponse])
def get_my_prescriptions(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get prescriptions based on user role"""
    if current_user.role == "patient":
        # Get prescriptions for patient's appointments
        prescriptions = session.exec(
            select(Prescription)
            .join(Appointment, Prescription.appointment_id == Appointment.id)
            .where(Appointment.patient_id == current_user.id)
            .order_by(Prescription.created_at.desc())
        ).all()
    elif current_user.role == "doctor":
        # Get prescriptions created by this doctor
        prescriptions = session.exec(
            select(Prescription)
            .join(Appointment, Prescription.appointment_id == Appointment.id)
            .where(Appointment.doctor_id == current_user.id)
            .order_by(Prescription.created_at.desc())
        ).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients and doctors can view prescriptions"
        )
    
    return prescriptions


@router.get("/{prescription_id}", response_model=PrescriptionResponse)
def get_prescription(
    prescription_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get prescription details"""
    prescription = session.get(Prescription, prescription_id)
    
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found"
        )
    
    # Get appointment to verify access
    appointment = session.get(Appointment, prescription.appointment_id)
    
    if appointment.patient_id != current_user.id and appointment.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this prescription"
        )
    
    return prescription


@router.get("/appointment/{appointment_id}", response_model=PrescriptionResponse)
def get_prescription_by_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get prescription for a specific appointment"""
    appointment = session.get(Appointment, appointment_id)
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Verify access
    if appointment.patient_id != current_user.id and appointment.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this appointment"
        )
    
    prescription = session.exec(
        select(Prescription).where(Prescription.appointment_id == appointment_id)
    ).first()
    
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No prescription found for this appointment"
        )
    
    return prescription


@router.put("/{prescription_id}", response_model=PrescriptionResponse)
def update_prescription(
    prescription_id: int,
    prescription_data: PrescriptionUpdate,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Update prescription (doctors only)"""
    prescription = session.get(Prescription, prescription_id)
    
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found"
        )
    
    # Verify doctor is the assigned doctor
    appointment = session.get(Appointment, prescription.appointment_id)
    if appointment.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own prescriptions"
        )
    
    # Update fields
    for key, value in prescription_data.model_dump(exclude_unset=True).items():
        setattr(prescription, key, value)
    
    session.add(prescription)
    session.commit()
    session.refresh(prescription)
    
    return prescription


@router.delete("/{prescription_id}")
def delete_prescription(
    prescription_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Delete prescription (doctors only)"""
    prescription = session.get(Prescription, prescription_id)
    
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found"
        )
    
    # Verify doctor is the assigned doctor
    appointment = session.get(Appointment, prescription.appointment_id)
    if appointment.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own prescriptions"
        )
    
    session.delete(prescription)
    session.commit()
    
    return {"message": "Prescription deleted successfully"}
