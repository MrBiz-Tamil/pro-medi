#!/usr/bin/env python3
"""
Seed script to create all test users for local development
Run with: python seed_test_users.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from database import engine
from sqlmodel import Session, select
from models import User, UserRole, DoctorProfile, PatientProfile, DoctorAvailability
import bcrypt

# Password for all test users
TEST_PASSWORD = "Test@123"
# Generate bcrypt hash
PASSWORD_HASH = bcrypt.hashpw(TEST_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def seed_test_users():
    with Session(engine) as session:
        print("\n🌱 Seeding test users...\n")
        
        # 1. Admin User
        admin = session.exec(select(User).where(User.email == "admin@test.com")).first()
        if not admin:
            admin = User(
                email="admin@test.com",
                password_hash=PASSWORD_HASH,
                full_name="Admin User",
                phone_number="9876543230",
                role=UserRole.ADMIN,
                is_active=True
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
            print("✅ Created: Admin User (admin@test.com)")
        else:
            print("⏭️  Exists: Admin User (admin@test.com)")

        # 2. Patient User
        patient = session.exec(select(User).where(User.email == "patient@test.com")).first()
        if not patient:
            patient = User(
                email="patient@test.com",
                password_hash=PASSWORD_HASH,
                full_name="John Patient",
                phone_number="9876543210",
                role=UserRole.PATIENT,
                is_active=True
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)
            
            # Create patient profile
            patient_profile = PatientProfile(
                user_id=patient.id,
                date_of_birth=datetime(1990, 1, 15),
                blood_group="O+",
                allergies="None",
                medical_conditions="No significant medical history",
                emergency_contact_name="Jane Patient",
                emergency_contact_phone="9876543211"
            )
            session.add(patient_profile)
            session.commit()
            print("✅ Created: Patient User (patient@test.com)")
        else:
            print("⏭️  Exists: Patient User (patient@test.com)")

        # 3. Patient User #2
        patient2 = session.exec(select(User).where(User.email == "patient2@test.com")).first()
        if not patient2:
            patient2 = User(
                email="patient2@test.com",
                password_hash=PASSWORD_HASH,
                full_name="Mary Johnson",
                phone_number="9876543250",
                role=UserRole.PATIENT,
                is_active=True
            )
            session.add(patient2)
            session.commit()
            session.refresh(patient2)
            
            patient2_profile = PatientProfile(
                user_id=patient2.id,
                date_of_birth=datetime(1985, 6, 20),
                blood_group="A+",
                allergies="Penicillin",
                medical_conditions="Hypertension (controlled)",
                emergency_contact_name="Robert Johnson",
                emergency_contact_phone="9876543251"
            )
            session.add(patient2_profile)
            session.commit()
            print("✅ Created: Patient User #2 (patient2@test.com)")
        else:
            print("⏭️  Exists: Patient User #2 (patient2@test.com)")

        # 4. Doctor User (General Physician)
        doctor = session.exec(select(User).where(User.email == "doctor@test.com")).first()
        if not doctor:
            doctor = User(
                email="doctor@test.com",
                password_hash=PASSWORD_HASH,
                full_name="Dr. Sarah Smith",
                phone_number="9876543220",
                role=UserRole.DOCTOR,
                is_active=True
            )
            session.add(doctor)
            session.commit()
            session.refresh(doctor)
            
            doctor_profile = DoctorProfile(
                user_id=doctor.id,
                specialization="General Physician",
                license_number="MH-12345-2020",
                years_of_experience=8,
                qualification="MBBS, MD (General Medicine)",
                consultation_fee=500.0,
                is_verified=True,
                is_online=True,
                bio="Experienced general physician with expertise in preventive care and chronic disease management.",
                average_rating=4.5,
                total_consultations=25,
                profile_completion_percent=100
            )
            session.add(doctor_profile)
            session.commit()
            
            # Add availability for Monday-Friday 9:00-17:00
            for day in range(5):  # 0=Monday to 4=Friday
                avail = DoctorAvailability(
                    doctor_id=doctor.id,
                    day_of_week=day,
                    start_time="09:00",
                    end_time="17:00",
                    slot_duration=30,
                    is_available=True
                )
                session.add(avail)
            session.commit()
            print("✅ Created: Doctor User (doctor@test.com) with availability")
        else:
            # Ensure availability exists for existing doctor
            existing_avail = session.exec(select(DoctorAvailability).where(DoctorAvailability.doctor_id == doctor.id)).first()
            if not existing_avail:
                for day in range(5):  # 0=Monday to 4=Friday
                    avail = DoctorAvailability(
                        doctor_id=doctor.id,
                        day_of_week=day,
                        start_time="09:00",
                        end_time="17:00",
                        slot_duration=30,
                        is_available=True
                    )
                    session.add(avail)
                session.commit()
                print("⏭️  Exists: Doctor User (doctor@test.com) - Added availability")
            else:
                print("⏭️  Exists: Doctor User (doctor@test.com)")

        # 5. Doctor User (Cardiologist)
        cardiologist = session.exec(select(User).where(User.email == "cardiologist@test.com")).first()
        if not cardiologist:
            cardiologist = User(
                email="cardiologist@test.com",
                password_hash=PASSWORD_HASH,
                full_name="Dr. Rajesh Kumar",
                phone_number="9876543240",
                role=UserRole.DOCTOR,
                is_active=True
            )
            session.add(cardiologist)
            session.commit()
            session.refresh(cardiologist)
            
            cardio_profile = DoctorProfile(
                user_id=cardiologist.id,
                specialization="Cardiologist",
                license_number="MH-67890-2015",
                years_of_experience=12,
                qualification="MBBS, MD (Cardiology), DM (Interventional Cardiology)",
                consultation_fee=1000.0,
                is_verified=True,
                is_online=True,
                bio="Senior cardiologist specializing in interventional cardiology and heart failure management.",
                average_rating=4.8,
                total_consultations=50,
                profile_completion_percent=100
            )
            session.add(cardio_profile)
            session.commit()
            
            # Add availability for Monday-Friday 10:00-18:00
            for day in range(5):  # 0=Monday to 4=Friday
                avail = DoctorAvailability(
                    doctor_id=cardiologist.id,
                    day_of_week=day,
                    start_time="10:00",
                    end_time="18:00",
                    slot_duration=30,
                    is_available=True
                )
                session.add(avail)
            session.commit()
            print("✅ Created: Cardiologist User (cardiologist@test.com) with availability")
        else:
            # Ensure availability exists for existing cardiologist
            existing_avail = session.exec(select(DoctorAvailability).where(DoctorAvailability.doctor_id == cardiologist.id)).first()
            if not existing_avail:
                for day in range(5):  # 0=Monday to 4=Friday
                    avail = DoctorAvailability(
                        doctor_id=cardiologist.id,
                        day_of_week=day,
                        start_time="10:00",
                        end_time="18:00",
                        slot_duration=30,
                        is_available=True
                    )
                    session.add(avail)
                session.commit()
                print("⏭️  Exists: Cardiologist User (cardiologist@test.com) - Added availability")
            else:
                print("⏭️  Exists: Cardiologist User (cardiologist@test.com)")

        # 6. Pharmacist User
        pharmacist = session.exec(select(User).where(User.email == "pharmacist@test.com")).first()
        if not pharmacist:
            pharmacist = User(
                email="pharmacist@test.com",
                password_hash=PASSWORD_HASH,
                full_name="Mike Pharmacy",
                phone_number="9876543260",
                role=UserRole.PHARMACIST,
                is_active=True
            )
            session.add(pharmacist)
            session.commit()
            print("✅ Created: Pharmacist User (pharmacist@test.com)")
        else:
            print("⏭️  Exists: Pharmacist User (pharmacist@test.com)")

        print("\n" + "="*50)
        print("🎉 Test users seeding complete!")
        print("="*50)
        print("\n📋 Test Credentials:")
        print("-" * 50)
        print(f"{'Email':<30} {'Role':<15} Password")
        print("-" * 50)
        print(f"{'admin@test.com':<30} {'ADMIN':<15} Test@123")
        print(f"{'patient@test.com':<30} {'PATIENT':<15} Test@123")
        print(f"{'patient2@test.com':<30} {'PATIENT':<15} Test@123")
        print(f"{'doctor@test.com':<30} {'DOCTOR':<15} Test@123")
        print(f"{'cardiologist@test.com':<30} {'DOCTOR':<15} Test@123")
        print(f"{'pharmacist@test.com':<30} {'PHARMACIST':<15} Test@123")
        print("-" * 50)
        print()

if __name__ == "__main__":
    seed_test_users()
