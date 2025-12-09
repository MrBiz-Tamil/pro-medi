"""Family Health Management API - Phase 12
Manage family members, shared health records, and family health tracking
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel, EmailStr
from enum import Enum
import uuid

from database import get_session
from models import User
from dependencies import get_current_user

router = APIRouter(prefix="/api/family", tags=["family"])


# ==================== Enums ====================

class RelationshipType(str, Enum):
    SPOUSE = "spouse"
    CHILD = "child"
    PARENT = "parent"
    SIBLING = "sibling"
    GRANDPARENT = "grandparent"
    GRANDCHILD = "grandchild"
    OTHER = "other"


class AccessLevel(str, Enum):
    FULL = "full"  # Can view all records and book appointments
    VIEW_ONLY = "view_only"  # Can only view records
    EMERGENCY = "emergency"  # Only emergency access
    NONE = "none"


class MemberStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"  # Invitation sent
    INACTIVE = "inactive"


# ==================== Schemas ====================

class FamilyMemberCreate(BaseModel):
    full_name: str
    relationship: RelationshipType
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    profile_photo: Optional[str] = None
    medical_conditions: Optional[List[str]] = []
    allergies: Optional[List[str]] = []
    emergency_contact: Optional[str] = None
    insurance_id: Optional[str] = None
    access_level: AccessLevel = AccessLevel.FULL


class FamilyMemberUpdate(BaseModel):
    full_name: Optional[str] = None
    relationship: Optional[RelationshipType] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    profile_photo: Optional[str] = None
    medical_conditions: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    emergency_contact: Optional[str] = None
    insurance_id: Optional[str] = None
    access_level: Optional[AccessLevel] = None


class FamilyMember(BaseModel):
    id: str
    user_id: int
    full_name: str
    relationship: RelationshipType
    date_of_birth: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    profile_photo: Optional[str] = None
    medical_conditions: List[str] = []
    allergies: List[str] = []
    emergency_contact: Optional[str] = None
    insurance_id: Optional[str] = None
    access_level: AccessLevel
    status: MemberStatus
    linked_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class FamilyMemberInvite(BaseModel):
    email: str
    relationship: RelationshipType
    access_level: AccessLevel = AccessLevel.VIEW_ONLY
    message: Optional[str] = None


class HealthRecordShare(BaseModel):
    member_id: str
    record_type: str  # prescription, lab_report, medical_history
    record_id: int
    can_edit: bool = False
    expires_at: Optional[datetime] = None


class FamilyHealthSummary(BaseModel):
    total_members: int
    members: List[dict]
    upcoming_appointments: List[dict]
    recent_prescriptions: List[dict]
    health_alerts: List[dict]


class EmergencyContact(BaseModel):
    id: str
    member_id: Optional[str] = None
    name: str
    relationship: str
    phone_number: str
    is_primary: bool = False


# ==================== In-Memory Storage (Replace with DB in production) ====================

# Simulated database storage
family_members_db: dict = {}
shared_records_db: dict = {}
emergency_contacts_db: dict = {}


def calculate_age(birth_date_str: str) -> Optional[int]:
    """Calculate age from birth date string"""
    try:
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except:
        return None


# ==================== Family Members Endpoints ====================

@router.get("/members", response_model=List[FamilyMember])
async def get_family_members(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get all family members for current user"""
    user_members = family_members_db.get(current_user.id, [])
    
    # Calculate ages
    for member in user_members:
        if member.get("date_of_birth"):
            member["age"] = calculate_age(member["date_of_birth"])
    
    return user_members


@router.post("/members", response_model=FamilyMember)
async def add_family_member(
    member_data: FamilyMemberCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Add a new family member"""
    now = datetime.utcnow()
    
    member = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "full_name": member_data.full_name,
        "relationship": member_data.relationship,
        "date_of_birth": member_data.date_of_birth,
        "age": calculate_age(member_data.date_of_birth) if member_data.date_of_birth else None,
        "gender": member_data.gender,
        "blood_group": member_data.blood_group,
        "phone_number": member_data.phone_number,
        "email": member_data.email,
        "profile_photo": member_data.profile_photo,
        "medical_conditions": member_data.medical_conditions or [],
        "allergies": member_data.allergies or [],
        "emergency_contact": member_data.emergency_contact,
        "insurance_id": member_data.insurance_id,
        "access_level": member_data.access_level,
        "status": MemberStatus.ACTIVE,
        "linked_user_id": None,
        "created_at": now,
        "updated_at": now
    }
    
    if current_user.id not in family_members_db:
        family_members_db[current_user.id] = []
    
    family_members_db[current_user.id].append(member)
    
    return member


@router.get("/members/{member_id}", response_model=FamilyMember)
async def get_family_member(
    member_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get a specific family member"""
    user_members = family_members_db.get(current_user.id, [])
    
    for member in user_members:
        if member["id"] == member_id:
            if member.get("date_of_birth"):
                member["age"] = calculate_age(member["date_of_birth"])
            return member
    
    raise HTTPException(status_code=404, detail="Family member not found")


@router.put("/members/{member_id}", response_model=FamilyMember)
async def update_family_member(
    member_id: str,
    member_data: FamilyMemberUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update a family member"""
    user_members = family_members_db.get(current_user.id, [])
    
    for i, member in enumerate(user_members):
        if member["id"] == member_id:
            update_data = member_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                member[key] = value
            member["updated_at"] = datetime.utcnow()
            
            if member.get("date_of_birth"):
                member["age"] = calculate_age(member["date_of_birth"])
            
            family_members_db[current_user.id][i] = member
            return member
    
    raise HTTPException(status_code=404, detail="Family member not found")


@router.delete("/members/{member_id}")
async def delete_family_member(
    member_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Delete a family member"""
    user_members = family_members_db.get(current_user.id, [])
    
    for i, member in enumerate(user_members):
        if member["id"] == member_id:
            family_members_db[current_user.id].pop(i)
            return {"message": "Family member removed successfully"}
    
    raise HTTPException(status_code=404, detail="Family member not found")


@router.post("/members/{member_id}/photo")
async def upload_member_photo(
    member_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Upload profile photo for a family member"""
    # In production, save to cloud storage
    photo_url = f"/uploads/family/{member_id}_{file.filename}"
    
    # Update member's photo
    user_members = family_members_db.get(current_user.id, [])
    for member in user_members:
        if member["id"] == member_id:
            member["profile_photo"] = photo_url
            member["updated_at"] = datetime.utcnow()
            return {"photo_url": photo_url}
    
    raise HTTPException(status_code=404, detail="Family member not found")


# ==================== Family Invitations ====================

@router.post("/invite")
async def invite_family_member(
    invite_data: FamilyMemberInvite,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Invite an existing user to join as family member"""
    # In production:
    # 1. Check if email exists in users table
    # 2. Send invitation email/notification
    # 3. Create pending family member record
    
    return {
        "message": f"Invitation sent to {invite_data.email}",
        "status": "pending",
        "expires_in_days": 7
    }


@router.get("/invitations")
async def get_pending_invitations(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get pending family invitations received by current user"""
    # In production, fetch from invitations table
    return {"invitations": []}


@router.post("/invitations/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Accept a family invitation"""
    return {"message": "Invitation accepted", "status": "active"}


@router.post("/invitations/{invitation_id}/decline")
async def decline_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Decline a family invitation"""
    return {"message": "Invitation declined"}


# ==================== Health Record Sharing ====================

@router.post("/share-record")
async def share_health_record(
    share_data: HealthRecordShare,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Share a health record with a family member"""
    share_id = str(uuid.uuid4())
    
    shared_record = {
        "id": share_id,
        "user_id": current_user.id,
        "member_id": share_data.member_id,
        "record_type": share_data.record_type,
        "record_id": share_data.record_id,
        "can_edit": share_data.can_edit,
        "expires_at": share_data.expires_at,
        "shared_at": datetime.utcnow()
    }
    
    if current_user.id not in shared_records_db:
        shared_records_db[current_user.id] = []
    
    shared_records_db[current_user.id].append(shared_record)
    
    return {
        "message": "Record shared successfully",
        "share_id": share_id
    }


@router.get("/shared-records")
async def get_shared_records(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get all shared health records"""
    return {
        "shared_by_me": shared_records_db.get(current_user.id, []),
        "shared_with_me": []  # In production, query records shared with this user
    }


@router.delete("/shared-records/{share_id}")
async def revoke_shared_record(
    share_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Revoke access to a shared record"""
    user_shares = shared_records_db.get(current_user.id, [])
    
    for i, share in enumerate(user_shares):
        if share["id"] == share_id:
            shared_records_db[current_user.id].pop(i)
            return {"message": "Access revoked successfully"}
    
    raise HTTPException(status_code=404, detail="Shared record not found")


# ==================== Emergency Contacts ====================

@router.get("/emergency-contacts", response_model=List[EmergencyContact])
async def get_emergency_contacts(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get all emergency contacts"""
    return emergency_contacts_db.get(current_user.id, [])


@router.post("/emergency-contacts", response_model=EmergencyContact)
async def add_emergency_contact(
    contact: EmergencyContact,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Add an emergency contact"""
    contact_data = contact.model_dump()
    contact_data["id"] = str(uuid.uuid4())
    
    if current_user.id not in emergency_contacts_db:
        emergency_contacts_db[current_user.id] = []
    
    # If this is primary, unset others
    if contact_data.get("is_primary"):
        for c in emergency_contacts_db[current_user.id]:
            c["is_primary"] = False
    
    emergency_contacts_db[current_user.id].append(contact_data)
    
    return contact_data


@router.delete("/emergency-contacts/{contact_id}")
async def delete_emergency_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Delete an emergency contact"""
    user_contacts = emergency_contacts_db.get(current_user.id, [])
    
    for i, contact in enumerate(user_contacts):
        if contact["id"] == contact_id:
            emergency_contacts_db[current_user.id].pop(i)
            return {"message": "Emergency contact removed"}
    
    raise HTTPException(status_code=404, detail="Contact not found")


# ==================== Family Health Summary ====================

@router.get("/health-summary", response_model=FamilyHealthSummary)
async def get_family_health_summary(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get comprehensive family health summary"""
    members = family_members_db.get(current_user.id, [])
    
    # Build health alerts based on member conditions
    health_alerts = []
    for member in members:
        # Check for chronic conditions
        if member.get("medical_conditions"):
            for condition in member["medical_conditions"]:
                health_alerts.append({
                    "member_id": member["id"],
                    "member_name": member["full_name"],
                    "type": "chronic_condition",
                    "message": f"{member['full_name']} has {condition}",
                    "severity": "info"
                })
        
        # Check for allergies
        if member.get("allergies"):
            health_alerts.append({
                "member_id": member["id"],
                "member_name": member["full_name"],
                "type": "allergy_alert",
                "message": f"{member['full_name']} has allergies: {', '.join(member['allergies'])}",
                "severity": "warning"
            })
    
    return FamilyHealthSummary(
        total_members=len(members),
        members=[{
            "id": m["id"],
            "name": m["full_name"],
            "relationship": m["relationship"],
            "age": calculate_age(m["date_of_birth"]) if m.get("date_of_birth") else None,
            "profile_photo": m.get("profile_photo")
        } for m in members],
        upcoming_appointments=[],  # In production, fetch from appointments
        recent_prescriptions=[],  # In production, fetch from prescriptions
        health_alerts=health_alerts
    )


# ==================== Book Appointment for Family Member ====================

@router.post("/members/{member_id}/book-appointment")
async def book_appointment_for_member(
    member_id: str,
    doctor_id: int,
    appointment_date: str,
    appointment_time: str,
    consultation_type: str = "video",
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Book an appointment for a family member"""
    # Verify member exists and user has access
    user_members = family_members_db.get(current_user.id, [])
    
    member = None
    for m in user_members:
        if m["id"] == member_id:
            member = m
            break
    
    if not member:
        raise HTTPException(status_code=404, detail="Family member not found")
    
    if member["access_level"] not in [AccessLevel.FULL]:
        raise HTTPException(status_code=403, detail="Insufficient access level to book appointments")
    
    # In production, create actual appointment
    return {
        "message": f"Appointment booked for {member['full_name']}",
        "appointment": {
            "member_id": member_id,
            "member_name": member["full_name"],
            "doctor_id": doctor_id,
            "date": appointment_date,
            "time": appointment_time,
            "type": consultation_type,
            "reason": reason,
            "status": "scheduled"
        }
    }
