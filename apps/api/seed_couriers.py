#!/usr/bin/env python3
"""
Seed script for Courier Providers
Run this to populate initial courier provider data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_session
from models import CourierProvider
from datetime import datetime

def seed_couriers():
    couriers = [
        {
            "name": "FedEx",
            "api_key": None,  # Will be set in production
            "api_secret": None,
            "webhook_url": "https://api.medhub.com/webhooks/fedex",
            "is_active": True
        },
        {
            "name": "DHL",
            "api_key": None,
            "api_secret": None,
            "webhook_url": "https://api.medhub.com/webhooks/dhl",
            "is_active": True
        },
        {
            "name": "India Post",
            "api_key": None,
            "api_secret": None,
            "webhook_url": "https://api.medhub.com/webhooks/indiapost",
            "is_active": True
        },
        {
            "name": "BlueDart",
            "api_key": None,
            "api_secret": None,
            "webhook_url": "https://api.medhub.com/webhooks/bluedart",
            "is_active": True
        },
        {
            "name": "Delhivery",
            "api_key": None,
            "api_secret": None,
            "webhook_url": "https://api.medhub.com/webhooks/delhivery",
            "is_active": True
        }
    ]

    session = next(get_session())

    try:
        for courier_data in couriers:
            # Check if courier already exists
            existing = session.query(CourierProvider).filter(
                CourierProvider.name == courier_data["name"]
            ).first()

            if not existing:
                courier = CourierProvider(**courier_data)
                session.add(courier)
                print(f"Added courier provider: {courier_data['name']}")
            else:
                print(f"Courier provider already exists: {courier_data['name']}")

        session.commit()
        print("Courier providers seeded successfully!")

    except Exception as e:
        session.rollback()
        print(f"Error seeding couriers: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    seed_couriers()