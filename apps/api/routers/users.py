"""User profile and account management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr
import os
import uuid

from database import get_session
from models import User
from dependencies import get_current_user
from auth import get_password_hash, verify_password

router = APIRouter(prefix="/api/users", tags=["users"])


# ==================== Schemas ====================

class UserProfile(BaseModel):
    id: int
    email: str
    full_name: str
    phone_number: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    profile_photo: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    emergency_contact: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    emergency_contact: Optional[str] = None


class AddressCreate(BaseModel):
    type: str = "home"  # home, work, other
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    country: str = "India"
    is_default: bool = False


class Address(BaseModel):
    id: int
    user_id: int
    type: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    country: str
    is_default: bool
    created_at: datetime


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class PhotoUploadResponse(BaseModel):
    photo_url: str
    message: str


# ==================== Endpoints ====================

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current user's profile"""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone_number=current_user.phone_number,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=getattr(current_user, 'is_verified', False),
        profile_photo=getattr(current_user, 'profile_photo', None),
        date_of_birth=getattr(current_user, 'date_of_birth', None),
        gender=getattr(current_user, 'gender', None),
        blood_group=getattr(current_user, 'blood_group', None),
        emergency_contact=getattr(current_user, 'emergency_contact', None),
        created_at=current_user.created_at
    )


@router.put("/me", response_model=UserProfile)
async def update_current_user_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update current user's profile"""
    
    # Update allowed fields
    update_data = profile_data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        if hasattr(current_user, key):
            setattr(current_user, key, value)
    
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone_number=current_user.phone_number,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=getattr(current_user, 'is_verified', False),
        profile_photo=getattr(current_user, 'profile_photo', None),
        date_of_birth=getattr(current_user, 'date_of_birth', None),
        gender=getattr(current_user, 'gender', None),
        blood_group=getattr(current_user, 'blood_group', None),
        emergency_contact=getattr(current_user, 'emergency_contact', None),
        created_at=current_user.created_at
    )


@router.post("/me/photo", response_model=PhotoUploadResponse)
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Upload profile photo"""
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and WebP images are allowed"
        )
    
    # Validate file size (max 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 5MB"
        )
    
    # Generate unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"profile_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    
    # Create uploads directory if not exists
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "profiles")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    
    # Update user profile
    photo_url = f"/uploads/profiles/{filename}"
    if hasattr(current_user, 'profile_photo'):
        current_user.profile_photo = photo_url
        session.add(current_user)
        session.commit()
    
    return PhotoUploadResponse(
        photo_url=photo_url,
        message="Profile photo uploaded successfully"
    )


@router.delete("/me/photo")
async def delete_profile_photo(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Delete profile photo"""
    
    if hasattr(current_user, 'profile_photo') and current_user.profile_photo:
        # Delete file if exists
        filepath = os.path.join(os.path.dirname(__file__), "..", current_user.profile_photo.lstrip("/"))
        if os.path.exists(filepath):
            os.remove(filepath)
        
        current_user.profile_photo = None
        session.add(current_user)
        session.commit()
    
    return {"message": "Profile photo deleted successfully"}


@router.put("/me/password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Change user password"""
    
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password length
    if len(password_data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    # Update password
    current_user.password_hash = get_password_hash(password_data.new_password)
    session.add(current_user)
    session.commit()
    
    return {"message": "Password changed successfully"}


# ==================== Address Management ====================

# In-memory storage for addresses (in production, use database model)
# This is a simplified implementation

@router.get("/me/addresses", response_model=List[Address])
async def get_user_addresses(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get user's saved addresses"""
    
    # In production, fetch from UserAddress table
    # For now, return empty list or mock data
    return []


@router.post("/me/addresses", response_model=Address)
async def add_address(
    address_data: AddressCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Add a new address"""
    
    # In production, save to UserAddress table
    # For now, return mock response
    now = datetime.utcnow()
    
    return Address(
        id=1,
        user_id=current_user.id,
        type=address_data.type,
        address_line1=address_data.address_line1,
        address_line2=address_data.address_line2,
        city=address_data.city,
        state=address_data.state,
        pincode=address_data.pincode,
        country=address_data.country,
        is_default=address_data.is_default,
        created_at=now
    )


@router.put("/me/addresses/{address_id}", response_model=Address)
async def update_address(
    address_id: int,
    address_data: AddressCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update an address"""
    
    # In production, update in UserAddress table
    now = datetime.utcnow()
    
    return Address(
        id=address_id,
        user_id=current_user.id,
        type=address_data.type,
        address_line1=address_data.address_line1,
        address_line2=address_data.address_line2,
        city=address_data.city,
        state=address_data.state,
        pincode=address_data.pincode,
        country=address_data.country,
        is_default=address_data.is_default,
        created_at=now
    )


@router.delete("/me/addresses/{address_id}")
async def delete_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Delete an address"""
    
    # In production, delete from UserAddress table
    return {"message": "Address deleted successfully"}


@router.patch("/me/addresses/{address_id}/default")
async def set_default_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Set an address as default"""
    
    # In production, update in UserAddress table
    return {"message": "Address set as default"}
