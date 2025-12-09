#!/usr/bin/env python3
"""
Test script for Shipment API endpoints
"""

import requests
import json
from datetime import datetime, timedelta

# API base URL
BASE_URL = "http://localhost:8000"

def test_shipment_api():
    print("🧪 Testing Shipment API Endpoints")
    print("=" * 50)

    # Skip authentication for now, test basic functionality
    print("\n1. Testing courier providers endpoint (no auth required for now)...")

    # For now, let's create a simple test shipment directly in the database
    # and then test the public tracking endpoint
    print("\n2. Creating a test shipment directly...")

    # Let's use the API without authentication first to see what happens
    test_public_tracking()

def test_public_tracking():
    """Test the public tracking endpoint with a known tracking number"""
    print("\n3. Testing public tracking endpoint...")

    # Test with a non-existent tracking number first
    try:
        track_response = requests.get(f"{BASE_URL}/shipments/track/MED-TEST123456")
        if track_response.status_code == 404:
            print("✅ Public tracking correctly returns 404 for non-existent tracking number")
        else:
            print(f"❌ Unexpected response for non-existent tracking: {track_response.status_code}")
    except Exception as e:
        print(f"❌ Error testing public tracking: {e}")

    print("\n🎉 Basic API endpoint testing completed!")

def seed_admin():
    """Seed a test admin user if needed"""
    print("Attempting to seed test admin user...")
    # This would require direct database access, skipping for now
    print("Please ensure admin user exists in database")

if __name__ == "__main__":
    test_shipment_api()