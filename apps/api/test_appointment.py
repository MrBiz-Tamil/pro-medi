#!/usr/bin/env python3
"""Test appointment creation"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from sqlmodel import Session
from database import engine
from models import User, Appointment, AppointmentStatus, AppointmentType, DoctorProfile, DoctorAvailability

# Test data
doctor_id = 4
start_time = datetime(2025, 12, 9, 10, 0, 0)  # Tuesday Dec 9 10:00 UTC
end_time = datetime(2025, 12, 9, 10, 30, 0)   # Tuesday Dec 9 10:30 UTC

with Session(engine) as session:
    # Check doctor exists
    doctor = session.get(User, doctor_id)
    print(f"Doctor: {doctor}")
    
    # Check doctor profile
    from sqlmodel import select
    profile = session.exec(select(DoctorProfile).where(DoctorProfile.user_id == doctor_id)).first()
    print(f"Doctor Profile: {profile}")
    print(f"  is_verified: {profile.is_verified if profile else 'N/A'}")
    
    # Check availability
    day_of_week = start_time.weekday()
    print(f"\nDay of week: {day_of_week}")
    
    availability = session.exec(
        select(DoctorAvailability).where(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.day_of_week == day_of_week,
            DoctorAvailability.is_available == True
        )
    ).first()
    print(f"Availability: {availability}")
    
    if availability:
        print(f"  Start: {availability.start_time}, End: {availability.end_time}")
        
        start_time_str = start_time.strftime("%H:%M")
        end_time_str = end_time.strftime("%H:%M")
        print(f"  Requested: {start_time_str} - {end_time_str}")
        
        if start_time_str < availability.start_time:
            print("  ERROR: Start time is before availability window")
        if end_time_str > availability.end_time:
            print("  ERROR: End time is after availability window")
    
    # Try to create appointment
    print("\nAttempting to create appointment...")
    try:
        # Import validators
        from validators.appointment_validator import (
            validate_appointment_time_not_past,
            validate_appointment_duration,
            validate_advance_booking_limit,
            validate_minimum_booking_notice,
            validate_patient_daily_limit,
            validate_doctor_daily_limit,
            validate_doctor_availability,
            validate_no_time_conflict,
            get_queue_number_for_appointment
        )
        
        print("Validating time not past...")
        validate_appointment_time_not_past(start_time)
        print("  OK")
        
        print("Validating duration...")
        validate_appointment_duration(start_time, end_time)
        print("  OK")
        
        print("Validating advance booking...")
        validate_advance_booking_limit(start_time, AppointmentType.CONSULTATION)
        print("  OK")
        
        print("Validating minimum booking notice...")
        validate_minimum_booking_notice(start_time, AppointmentType.CONSULTATION)
        print("  OK")
        
        print("Validating patient daily limit...")
        validate_patient_daily_limit(session, 2, start_time.date())  # Patient ID 2
        print("  OK")
        
        print("Validating doctor daily limit...")
        validate_doctor_daily_limit(session, doctor_id, start_time.date())
        print("  OK")
        
        print("Validating doctor availability...")
        validate_doctor_availability(session, doctor_id, start_time, end_time)
        print("  OK")
        
        print("Validating no time conflict...")
        validate_no_time_conflict(session, doctor_id, start_time, end_time)
        print("  OK")
        
        print("Getting queue number...")
        queue_number = get_queue_number_for_appointment(session, doctor_id, start_time.date(), AppointmentType.CONSULTATION)
        print(f"  Queue number: {queue_number}")
        
        print("\n✅ All validations passed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
