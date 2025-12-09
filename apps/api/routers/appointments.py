from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select, func
from database import get_session
from models import User, Appointment, AppointmentStatus, AppointmentType, DoctorProfile
from schemas import AppointmentCreate, AppointmentUpdate, AppointmentResponse
from dependencies import get_current_user, require_doctor
from datetime import datetime, date
from typing import List
from validators.appointment_validator import (
    validate_appointment_time_not_past,
    validate_appointment_duration,
    validate_advance_booking_limit,
    validate_minimum_booking_notice,
    validate_patient_daily_limit,
    validate_doctor_daily_limit,
    validate_doctor_availability,
    validate_no_time_conflict,
    validate_cancellation_policy,
    validate_reschedule_limit,
    get_queue_number_for_appointment
)

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])

def generate_queue_number(session: Session, doctor_id: int, appointment_date: date) -> int:
    """Generate the next queue number for a doctor on a specific date"""
    # Get the max queue number for this doctor on this date
    result = session.exec(
        select(func.max(Appointment.queue_number))
        .where(
            Appointment.doctor_id == doctor_id,
            func.date(Appointment.start_time) == appointment_date
        )
    ).first()
    
    return (result or 0) + 1

@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment_data: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create a new appointment (patients only)"""
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can book appointments"
        )
    
    # Verify doctor exists and is verified
    doctor = session.get(User, appointment_data.doctor_id)
    if not doctor or doctor.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    doctor_profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == appointment_data.doctor_id)
    ).first()
    
    if not doctor_profile or not doctor_profile.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor is not verified"
        )
    
    # Run all validation checks
    validate_appointment_time_not_past(appointment_data.start_time)
    validate_appointment_duration(appointment_data.start_time, appointment_data.end_time)
    validate_advance_booking_limit(appointment_data.start_time, appointment_data.appointment_type)
    validate_minimum_booking_notice(appointment_data.start_time, appointment_data.appointment_type)
    
    appointment_date = appointment_data.start_time.date()
    validate_patient_daily_limit(session, current_user.id, appointment_date)
    validate_doctor_daily_limit(session, appointment_data.doctor_id, appointment_date)
    
    # Check doctor availability
    validate_doctor_availability(
        session,
        appointment_data.doctor_id,
        appointment_data.start_time,
        appointment_data.end_time
    )
    
    # Check for time slot conflicts
    validate_no_time_conflict(
        session,
        appointment_data.doctor_id,
        appointment_data.start_time,
        appointment_data.end_time
    )
    
    # Generate queue number with priority for emergencies
    queue_number = get_queue_number_for_appointment(
        session,
        appointment_data.doctor_id,
        appointment_date,
        appointment_data.appointment_type
    )
    
    # Create appointment
    new_appointment = Appointment(
        patient_id=current_user.id,
        doctor_id=appointment_data.doctor_id,
        start_time=appointment_data.start_time,
        end_time=appointment_data.end_time,
        appointment_type=appointment_data.appointment_type,
        queue_number=queue_number,
        notes=appointment_data.notes,
        status=AppointmentStatus.SCHEDULED
    )
    
    session.add(new_appointment)
    session.commit()
    session.refresh(new_appointment)
    
    return new_appointment

@router.get("/my-appointments", response_model=List[AppointmentResponse])
def get_my_appointments(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current user's appointments (patients see their bookings, doctors see their schedule)"""
    if current_user.role == "patient":
        appointments = session.exec(
            select(Appointment)
            .where(Appointment.patient_id == current_user.id)
            .order_by(Appointment.start_time.desc())
        ).all()
    elif current_user.role == "doctor":
        appointments = session.exec(
            select(Appointment)
            .where(Appointment.doctor_id == current_user.id)
            .order_by(Appointment.start_time.desc())
        ).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients and doctors can view appointments"
        )
    
    return appointments

@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get appointment details"""
    appointment = session.get(Appointment, appointment_id)
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Check if user has access to this appointment
    if appointment.patient_id != current_user.id and appointment.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this appointment"
        )
    
    return appointment

@router.put("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: int,
    appointment_data: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update appointment (reschedule or update status)"""
    appointment = session.get(Appointment, appointment_id)
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Check permissions
    if appointment.patient_id != current_user.id and appointment.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this appointment"
        )
    
    # If rescheduling, validate reschedule limit and check for conflicts
    is_rescheduling = appointment_data.start_time or appointment_data.end_time
    
    if is_rescheduling:
        # Check reschedule limit
        validate_reschedule_limit(appointment)
        
        new_start = appointment_data.start_time or appointment.start_time
        new_end = appointment_data.end_time or appointment.end_time
        
        # Run time validations
        validate_appointment_time_not_past(new_start)
        validate_appointment_duration(new_start, new_end)
        validate_advance_booking_limit(new_start, appointment.appointment_type)
        validate_minimum_booking_notice(new_start, appointment.appointment_type)
        
        # Check doctor availability
        validate_doctor_availability(
            session,
            appointment.doctor_id,
            new_start,
            new_end
        )
        
        # Check for conflicts
        validate_no_time_conflict(
            session,
            appointment.doctor_id,
            new_start,
            new_end,
            exclude_appointment_id=appointment_id
        )
        
        # Increment reschedule count
        appointment.reschedule_count += 1
    
    # Update fields
    for key, value in appointment_data.model_dump(exclude_unset=True).items():
        setattr(appointment, key, value)
    
    session.add(appointment)
    session.commit()
    session.refresh(appointment)
    
    return appointment

@router.delete("/{appointment_id}")
def cancel_appointment(
    appointment_id: int,
    cancellation_reason: str = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Cancel an appointment"""
    appointment = session.get(Appointment, appointment_id)
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Check permissions (patients and doctors can cancel)
    if appointment.patient_id != current_user.id and appointment.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to cancel this appointment"
        )
    
    # Validate cancellation policy
    validate_cancellation_policy(appointment)
    
    # Update status and metadata
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = datetime.utcnow()
    appointment.cancelled_by = current_user.id
    appointment.cancellation_reason = cancellation_reason
    
    session.add(appointment)
    session.commit()
    
    return {"message": "Appointment cancelled successfully"}

@router.get("/doctor/{doctor_id}/upcoming", response_model=List[AppointmentResponse])
def get_doctor_upcoming_appointments(
    doctor_id: int,
    session: Session = Depends(get_session)
):
    """Get upcoming appointments for a specific doctor (public endpoint for booking UI)"""
    appointments = session.exec(
        select(Appointment)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.start_time >= datetime.utcnow()
        )
        .order_by(Appointment.start_time)
    ).all()
    
    return appointments
