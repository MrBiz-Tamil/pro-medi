#!/usr/bin/env python3
"""
Quick seed script for admin user to test shipment API
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_session
from models import User, UserRole
from passlib.hash import bcrypt

def seed_admin():
    session = next(get_session())

    try:
        # Check if admin already exists
        existing = session.query(User).filter(User.email == "admin@test.com").first()
        if existing:
            print("Admin user already exists")
            return

        # Create admin user
        admin = User(
            email="admin@test.com",
            password_hash=bcrypt.hash("Test@123"),
            full_name="Admin User",
            phone_number="9876543213",
            role=UserRole.ADMIN,
            is_active=True
        )

        session.add(admin)
        session.commit()
        print("✅ Admin user created successfully!")
        print("   Email: admin@test.com")
        print("   Password: Test@123")

    except Exception as e:
        session.rollback()
        print(f"❌ Error creating admin user: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    seed_admin()