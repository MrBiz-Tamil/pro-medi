"""Medical records management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from database import get_session
from models import User, MedicalRecord, Appointment
from schemas import MedicalRecordCreate, MedicalRecordUpdate, MedicalRecordResponse
from dependencies import get_current_user, require_doctor
from typing import List

router = APIRouter(prefix="/api/medical-records", tags=["Medical Records"])


def check_doctor_patient_relationship(session: Session, doctor_id: int, patient_id: int) -> bool:
    """
    Check if a doctor has a valid relationship with a patient.
    A doctor can only access records of patients they have treated (had an appointment with).
    """
    # Check if there's any completed appointment between this doctor and patient
    appointment = session.exec(
        select(Appointment)
        .where(Appointment.doctor_id == doctor_id)
        .where(Appointment.patient_id == patient_id)
    ).first()
    
    return appointment is not None


@router.post("", response_model=MedicalRecordResponse, status_code=status.HTTP_201_CREATED)
def create_medical_record(
    record_data: MedicalRecordCreate,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Create medical record (doctors only)"""
    # Verify patient exists
    patient = session.get(User, record_data.patient_id)
    if not patient or patient.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    # Create record with doctor_id from current user
    new_record = MedicalRecord(
        patient_id=record_data.patient_id,
        doctor_id=current_user.id,
        diagnosis=record_data.diagnosis,
        notes=record_data.notes,
        file_url=record_data.file_url
    )
    
    session.add(new_record)
    session.commit()
    session.refresh(new_record)
    
    return new_record


@router.get("/patient/{patient_id}", response_model=List[MedicalRecordResponse])
def get_patient_records(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get medical records for a patient.
    
    Access rules:
    - Patients can only view their own records
    - Doctors can only view records of patients they have treated (had appointments with)
    - Admins can view all records
    """
    # Patients can only see their own records
    if current_user.role == "patient":
        if current_user.id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own medical records"
            )
    
    # Doctors can only see records of patients they have a relationship with
    elif current_user.role == "doctor":
        if not check_doctor_patient_relationship(session, current_user.id, patient_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view records of patients you have treated"
            )
    
    # Admin can see all
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    records = session.exec(
        select(MedicalRecord)
        .where(MedicalRecord.patient_id == patient_id)
        .order_by(MedicalRecord.created_at.desc())
    ).all()
    
    return records


@router.get("/my-records", response_model=List[MedicalRecordResponse])
def get_my_records(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current user's medical records (patients) or created records (doctors)"""
    if current_user.role == "patient":
        records = session.exec(
            select(MedicalRecord)
            .where(MedicalRecord.patient_id == current_user.id)
            .order_by(MedicalRecord.created_at.desc())
        ).all()
    elif current_user.role == "doctor":
        records = session.exec(
            select(MedicalRecord)
            .where(MedicalRecord.doctor_id == current_user.id)
            .order_by(MedicalRecord.created_at.desc())
        ).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients and doctors can view medical records"
        )
    
    return records


@router.get("/{record_id}", response_model=MedicalRecordResponse)
def get_medical_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get specific medical record"""
    record = session.get(MedicalRecord, record_id)
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical record not found"
        )
    
    # Check access
    if current_user.role == "patient" and record.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own medical records"
        )
    
    if current_user.role not in ["patient", "doctor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return record


@router.put("/{record_id}", response_model=MedicalRecordResponse)
def update_medical_record(
    record_id: int,
    record_data: MedicalRecordUpdate,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Update medical record (doctors only)"""
    record = session.get(MedicalRecord, record_id)
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical record not found"
        )
    
    # Verify doctor is the creator
    if record.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own medical records"
        )
    
    # Update fields
    for key, value in record_data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    
    session.add(record)
    session.commit()
    session.refresh(record)
    
    return record


@router.delete("/{record_id}")
def delete_medical_record(
    record_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Delete medical record (doctors only)"""
    record = session.get(MedicalRecord, record_id)
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical record not found"
        )
    
    # Verify doctor is the creator
    if record.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own medical records"
        )
    
    session.delete(record)
    session.commit()
    
    return {"message": "Medical record deleted successfully"}
