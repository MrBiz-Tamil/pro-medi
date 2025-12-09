"""Business rule configuration and validation"""
from typing import Optional
from pydantic import BaseModel


class BusinessRules(BaseModel):
    """Business rules configuration"""
    # Appointment rules
    MAX_APPOINTMENTS_PER_PATIENT_PER_DAY: int = 3
    MAX_APPOINTMENTS_PER_DOCTOR_PER_DAY: int = 20
    MAX_ADVANCE_BOOKING_DAYS: int = 90
    MIN_BOOKING_NOTICE_HOURS: int = 2
    MIN_APPOINTMENT_DURATION_MINUTES: int = 15
    MAX_APPOINTMENT_DURATION_MINUTES: int = 120
    
    # Cancellation rules
    CANCELLATION_HOURS_BEFORE: int = 24
    MAX_RESCHEDULES_PER_APPOINTMENT: int = 2
    
    # Doctor availability rules
    MAX_WORKING_HOURS_PER_DAY: int = 12
    DEFAULT_SLOT_DURATION_MINUTES: int = 30
    
    # Emergency rules
    EMERGENCY_QUEUE_PRIORITY: int = 0
    ALLOW_EMERGENCY_SAME_DAY: bool = True
    
    # License validation
    REQUIRE_LICENSE_EXPIRY: bool = True
    LICENSE_EXPIRY_WARNING_DAYS: int = 30


# Global instance - can be loaded from database
business_rules = BusinessRules()


def get_business_rules() -> BusinessRules:
    """Get current business rules"""
    return business_rules


def update_business_rule(key: str, value: any) -> None:
    """Update a business rule"""
    if hasattr(business_rules, key):
        setattr(business_rules, key, value)
    else:
        raise ValueError(f"Unknown business rule: {key}")
