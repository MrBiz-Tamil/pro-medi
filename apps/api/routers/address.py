"""
Address Router - Address Management with Pincode Verification
Uses India Post API: https://api.postalpincode.in/pincode/{PINCODE}
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from database import get_session
from dependencies import get_current_user
from models import User, Address, AddressType, DeliveryStatus, PincodeCache
from services.pincode_service import (
    verify_pincode, 
    get_post_offices, 
    check_delivery_availability,
    PincodeVerificationResult,
    PostOffice,
    get_cache_stats
)
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/address", tags=["Address Management"])


# ==================== SCHEMAS ====================

class AddressCreate(BaseModel):
    """Schema for creating a new address"""
    address_type: AddressType = AddressType.HOME
    label: Optional[str] = None
    address_line_1: str = Field(..., min_length=5, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    landmark: Optional[str] = Field(None, max_length=255)
    pincode: str = Field(..., pattern=r"^\d{6}$")
    post_office_name: Optional[str] = None
    is_default: bool = False
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=15)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AddressUpdate(BaseModel):
    """Schema for updating an address"""
    address_type: Optional[AddressType] = None
    label: Optional[str] = None
    address_line_1: Optional[str] = Field(None, min_length=5, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    landmark: Optional[str] = Field(None, max_length=255)
    pincode: Optional[str] = Field(None, pattern=r"^\d{6}$")
    post_office_name: Optional[str] = None
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=15)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AddressResponse(BaseModel):
    """Response schema for address"""
    id: int
    user_id: int
    address_type: AddressType
    label: Optional[str]
    address_line_1: str
    address_line_2: Optional[str]
    landmark: Optional[str]
    pincode: str
    city: Optional[str]
    district: Optional[str]
    state: Optional[str]
    country: str
    post_office_name: Optional[str]
    branch_type: Optional[str]
    delivery_status: DeliveryStatus
    is_pincode_verified: bool
    pincode_verified_at: Optional[datetime]
    is_default: bool
    is_active: bool
    contact_name: Optional[str]
    contact_phone: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PincodeVerifyResponse(BaseModel):
    """Response for pincode verification"""
    pincode: str
    is_valid: bool
    message: str
    city: Optional[str]
    district: Optional[str]
    state: Optional[str]
    is_delivery_available: bool
    post_offices: List[dict]


class DeliveryCheckResponse(BaseModel):
    """Response for delivery availability check"""
    pincode: str
    is_valid: bool
    is_delivery_available: bool
    delivery_post_offices: List[str]
    total_post_offices: int
    message: str


# ==================== PINCODE VERIFICATION ENDPOINTS ====================

@router.get("/verify-pincode/{pincode}", response_model=PincodeVerifyResponse)
async def verify_pincode_endpoint(pincode: str):
    """
    Verify a pincode and get location details using India Post API.
    
    - **pincode**: 6-digit Indian postal code
    
    Returns city, district, state, and list of post offices for the pincode.
    """
    if not pincode or not pincode.isdigit() or len(pincode) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pincode format. Pincode must be 6 digits."
        )
    
    result = await verify_pincode(pincode)
    
    return PincodeVerifyResponse(
        pincode=result.pincode,
        is_valid=result.is_valid,
        message=result.message,
        city=result.city,
        district=result.district,
        state=result.state,
        is_delivery_available=result.is_delivery_available,
        post_offices=[
            {
                "name": po.name,
                "branch_type": po.branch_type,
                "delivery_status": po.delivery_status,
                "district": po.district,
                "state": po.state
            }
            for po in result.post_offices
        ]
    )


@router.get("/post-offices/{pincode}")
async def get_post_offices_endpoint(pincode: str):
    """
    Get list of all post offices for a given pincode.
    
    - **pincode**: 6-digit Indian postal code
    """
    if not pincode or not pincode.isdigit() or len(pincode) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pincode format. Pincode must be 6 digits."
        )
    
    post_offices = await get_post_offices(pincode)
    
    if not post_offices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No post offices found for pincode {pincode}"
        )
    
    return {
        "pincode": pincode,
        "count": len(post_offices),
        "post_offices": [
            {
                "name": po.name,
                "branch_type": po.branch_type,
                "delivery_status": po.delivery_status,
                "circle": po.circle,
                "district": po.district,
                "division": po.division,
                "region": po.region,
                "block": po.block,
                "state": po.state
            }
            for po in post_offices
        ]
    }


@router.get("/check-delivery/{pincode}", response_model=DeliveryCheckResponse)
async def check_delivery_endpoint(pincode: str):
    """
    Check if delivery service is available for a given pincode.
    
    - **pincode**: 6-digit Indian postal code
    
    Useful for pharmacy orders and shipment verification.
    """
    if not pincode or not pincode.isdigit() or len(pincode) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pincode format. Pincode must be 6 digits."
        )
    
    result = await check_delivery_availability(pincode)
    return DeliveryCheckResponse(**result)


# ==================== ADDRESS CRUD ENDPOINTS ====================

@router.post("", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    address_data: AddressCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new address for the current user.
    
    The pincode will be automatically verified and location details 
    (city, district, state) will be auto-filled from India Post API.
    """
    # Verify the pincode first
    pincode_result = await verify_pincode(address_data.pincode)
    
    if not pincode_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pincode: {pincode_result.message}"
        )
    
    # If this is set as default, unset other default addresses
    if address_data.is_default:
        statement = select(Address).where(
            Address.user_id == current_user.id,
            Address.is_default == True,
            Address.is_active == True
        )
        existing_defaults = session.exec(statement).all()
        for addr in existing_defaults:
            addr.is_default = False
            session.add(addr)
    
    # Get post office details if specified
    selected_po = None
    if address_data.post_office_name:
        for po in pincode_result.post_offices:
            if po.name.lower() == address_data.post_office_name.lower():
                selected_po = po
                break
    
    # Use first post office if none specified
    if not selected_po and pincode_result.post_offices:
        selected_po = pincode_result.post_offices[0]
    
    # Determine delivery status
    delivery_status = DeliveryStatus.UNKNOWN
    if selected_po:
        if selected_po.delivery_status.lower() == "delivery":
            delivery_status = DeliveryStatus.DELIVERY
        else:
            delivery_status = DeliveryStatus.NON_DELIVERY
    
    # Create the address
    address = Address(
        user_id=current_user.id,
        address_type=address_data.address_type,
        label=address_data.label,
        address_line_1=address_data.address_line_1,
        address_line_2=address_data.address_line_2,
        landmark=address_data.landmark,
        pincode=address_data.pincode,
        city=pincode_result.city,
        district=pincode_result.district,
        state=pincode_result.state,
        country="India",
        post_office_name=selected_po.name if selected_po else None,
        branch_type=selected_po.branch_type if selected_po else None,
        delivery_status=delivery_status,
        is_pincode_verified=True,
        pincode_verified_at=datetime.utcnow(),
        is_default=address_data.is_default,
        contact_name=address_data.contact_name,
        contact_phone=address_data.contact_phone,
        latitude=address_data.latitude,
        longitude=address_data.longitude
    )
    
    session.add(address)
    session.commit()
    session.refresh(address)
    
    logger.info(f"Address created for user {current_user.id}: {address.id}")
    
    return address


@router.get("", response_model=List[AddressResponse])
async def get_my_addresses(
    address_type: Optional[AddressType] = None,
    include_inactive: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get all addresses for the current user.
    
    - **address_type**: Filter by address type (home, work, shipping, billing)
    - **include_inactive**: Include soft-deleted addresses
    """
    statement = select(Address).where(Address.user_id == current_user.id)
    
    if address_type:
        statement = statement.where(Address.address_type == address_type)
    
    if not include_inactive:
        statement = statement.where(Address.is_active == True)
    
    statement = statement.order_by(Address.is_default.desc(), Address.created_at.desc())
    
    addresses = session.exec(statement).all()
    return addresses


@router.get("/{address_id}", response_model=AddressResponse)
async def get_address(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific address by ID.
    """
    address = session.get(Address, address_id)
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    if address.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this address"
        )
    
    return address


@router.put("/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: int,
    address_data: AddressUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing address.
    
    If pincode is changed, it will be re-verified and location details updated.
    """
    address = session.get(Address, address_id)
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    if address.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this address"
        )
    
    # If pincode is being changed, re-verify it
    if address_data.pincode and address_data.pincode != address.pincode:
        pincode_result = await verify_pincode(address_data.pincode)
        
        if not pincode_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid pincode: {pincode_result.message}"
            )
        
        # Update location details from new pincode
        address.pincode = address_data.pincode
        address.city = pincode_result.city
        address.district = pincode_result.district
        address.state = pincode_result.state
        address.is_pincode_verified = True
        address.pincode_verified_at = datetime.utcnow()
        
        # Update post office if specified or use first one
        selected_po = None
        if address_data.post_office_name:
            for po in pincode_result.post_offices:
                if po.name.lower() == address_data.post_office_name.lower():
                    selected_po = po
                    break
        if not selected_po and pincode_result.post_offices:
            selected_po = pincode_result.post_offices[0]
        
        if selected_po:
            address.post_office_name = selected_po.name
            address.branch_type = selected_po.branch_type
            if selected_po.delivery_status.lower() == "delivery":
                address.delivery_status = DeliveryStatus.DELIVERY
            else:
                address.delivery_status = DeliveryStatus.NON_DELIVERY
    
    # Update other fields
    update_data = address_data.model_dump(exclude_unset=True, exclude={"pincode", "post_office_name"})
    for key, value in update_data.items():
        setattr(address, key, value)
    
    address.updated_at = datetime.utcnow()
    
    session.add(address)
    session.commit()
    session.refresh(address)
    
    logger.info(f"Address updated: {address_id}")
    
    return address


@router.delete("/{address_id}")
async def delete_address(
    address_id: int,
    hard_delete: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an address (soft delete by default).
    
    - **hard_delete**: If true, permanently delete the address
    """
    address = session.get(Address, address_id)
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    if address.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this address"
        )
    
    if hard_delete:
        session.delete(address)
        message = "Address permanently deleted"
    else:
        address.is_active = False
        address.updated_at = datetime.utcnow()
        session.add(address)
        message = "Address deleted"
    
    session.commit()
    
    logger.info(f"Address deleted: {address_id} (hard_delete={hard_delete})")
    
    return {"message": message, "address_id": address_id}


@router.put("/{address_id}/set-default", response_model=AddressResponse)
async def set_default_address(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Set an address as the default address.
    
    This will unset any existing default address.
    """
    address = session.get(Address, address_id)
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    if address.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this address"
        )
    
    if not address.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set inactive address as default"
        )
    
    # Unset existing default addresses
    statement = select(Address).where(
        Address.user_id == current_user.id,
        Address.is_default == True,
        Address.is_active == True
    )
    existing_defaults = session.exec(statement).all()
    for addr in existing_defaults:
        addr.is_default = False
        session.add(addr)
    
    # Set this address as default
    address.is_default = True
    address.updated_at = datetime.utcnow()
    session.add(address)
    
    session.commit()
    session.refresh(address)
    
    logger.info(f"Default address set: {address_id}")
    
    return address


# ==================== ADMIN/UTILITY ENDPOINTS ====================

@router.get("/user/{user_id}/addresses", response_model=List[AddressResponse])
async def get_user_addresses_admin(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get all addresses for a specific user (Admin only).
    
    Useful for pharmacy orders and shipment management.
    """
    # Check if current user is admin
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    statement = select(Address).where(
        Address.user_id == user_id,
        Address.is_active == True
    ).order_by(Address.is_default.desc())
    
    addresses = session.exec(statement).all()
    return addresses


@router.get("/cache/stats")
async def get_pincode_cache_stats(
    current_user: User = Depends(get_current_user)
):
    """
    Get pincode cache statistics (Admin only).
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return get_cache_stats()
