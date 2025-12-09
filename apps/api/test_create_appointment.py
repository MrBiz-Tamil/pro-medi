#!/usr/bin/env python3
"""Test appointment creation directly"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from sqlmodel import Session
from database import engine
from models import Appointment, AppointmentStatus, AppointmentType

# Test data
patient_id = 2
doctor_id = 4
start_time = datetime(2025, 12, 9, 10, 0, 0)
end_time = datetime(2025, 12, 9, 10, 30, 0)

with Session(engine) as session:
    print("Creating appointment...")
    
    new_appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        start_time=start_time,
        end_time=end_time,
        appointment_type=AppointmentType.CONSULTATION,
        queue_number=1,
        notes="Test video call",
        status=AppointmentStatus.SCHEDULED
    )
    
    session.add(new_appointment)
    session.commit()
    session.refresh(new_appointment)
    
    print(f"✅ Appointment created! ID: {new_appointment.id}")
    print(f"  Patient: {new_appointment.patient_id}")
    print(f"  Doctor: {new_appointment.doctor_id}")
    print(f"  Start: {new_appointment.start_time}")
    print(f"  End: {new_appointment.end_time}")
    print(f"  Status: {new_appointment.status}")
    print(f"  Queue: {new_appointment.queue_number}")
