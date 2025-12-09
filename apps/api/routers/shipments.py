from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import uuid
import httpx
import hashlib
import hmac
import json

from database import get_session
from models import Shipment, ShipmentItem, CourierProvider, ShipmentTracking, ShipmentStatus, User
from schemas import (
    ShipmentCreate, ShipmentResponse, ShipmentUpdate, ShipmentStatusUpdate,
    CourierProviderCreate, CourierProviderResponse, CourierProviderUpdate,
    PublicTrackingResponse, ShipmentTrackingResponse
)
from dependencies import get_current_user

router = APIRouter(prefix="/shipments", tags=["shipments"])

# ==================== CARRIER INTEGRATION CLASSES ====================

class CarrierAPIBase:
    """Base class for carrier API integrations"""
    
    def __init__(self, api_key: str, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    async def create_shipment(self, shipment_data: dict) -> dict:
        raise NotImplementedError
    
    async def get_tracking(self, tracking_number: str) -> dict:
        raise NotImplementedError
    
    async def calculate_rate(self, origin: str, destination: str, weight: float) -> dict:
        raise NotImplementedError


class IndiaPostAPI(CarrierAPIBase):
    """India Post API integration (simulated)"""
    BASE_URL = "https://api.indiapost.gov.in/v1"  # Simulated endpoint
    
    async def create_shipment(self, shipment_data: dict) -> dict:
        # In production, this would call actual India Post API
        tracking_number = f"IP{uuid.uuid4().hex[:12].upper()}"
        return {
            "success": True,
            "tracking_number": tracking_number,
            "carrier": "India Post",
            "estimated_days": 5,
            "cost": shipment_data.get("weight", 1) * 50  # ₹50 per kg base rate
        }
    
    async def get_tracking(self, tracking_number: str) -> dict:
        # Simulated tracking response
        return {
            "success": True,
            "tracking_number": tracking_number,
            "status": "in_transit",
            "current_location": "Mumbai Sorting Center",
            "events": [
                {"status": "picked_up", "location": "Origin Office", "timestamp": datetime.utcnow().isoformat()},
                {"status": "in_transit", "location": "Mumbai Sorting Center", "timestamp": datetime.utcnow().isoformat()}
            ]
        }
    
    async def calculate_rate(self, origin: str, destination: str, weight: float) -> dict:
        # Simulated rate calculation
        base_rate = 50
        per_kg_rate = 30
        distance_factor = 1.2  # Would be calculated based on pincodes
        
        total = (base_rate + (weight * per_kg_rate)) * distance_factor
        return {
            "carrier": "India Post",
            "service": "Speed Post",
            "rate": round(total, 2),
            "currency": "INR",
            "estimated_days": 5,
            "origin": origin,
            "destination": destination,
            "weight": weight
        }


class ShiprocketAPI(CarrierAPIBase):
    """Shiprocket API integration (simulated)"""
    BASE_URL = "https://apiv2.shiprocket.in/v1/external"
    
    async def authenticate(self) -> str:
        # In production, this would call Shiprocket auth endpoint
        return "simulated_token"
    
    async def create_shipment(self, shipment_data: dict) -> dict:
        tracking_number = f"SR{uuid.uuid4().hex[:12].upper()}"
        return {
            "success": True,
            "order_id": f"ORD-{uuid.uuid4().hex[:8].upper()}",
            "tracking_number": tracking_number,
            "carrier": "Shiprocket",
            "courier_name": "Bluedart",
            "estimated_days": 3,
            "cost": shipment_data.get("weight", 1) * 80
        }
    
    async def get_tracking(self, tracking_number: str) -> dict:
        return {
            "success": True,
            "tracking_number": tracking_number,
            "status": "in_transit",
            "current_location": "Delhi Hub",
            "courier_name": "Bluedart",
            "events": [
                {"status": "picked_up", "location": "Pickup Point", "timestamp": datetime.utcnow().isoformat()},
                {"status": "in_transit", "location": "Delhi Hub", "timestamp": datetime.utcnow().isoformat()}
            ]
        }
    
    async def calculate_rate(self, origin: str, destination: str, weight: float) -> dict:
        # Simulated multi-courier rate response
        return {
            "rates": [
                {
                    "carrier": "Shiprocket",
                    "courier": "Bluedart",
                    "rate": round(weight * 80 + 40, 2),
                    "currency": "INR",
                    "estimated_days": 3
                },
                {
                    "carrier": "Shiprocket",
                    "courier": "Delhivery",
                    "rate": round(weight * 70 + 35, 2),
                    "currency": "INR",
                    "estimated_days": 4
                },
                {
                    "carrier": "Shiprocket",
                    "courier": "DTDC",
                    "rate": round(weight * 60 + 30, 2),
                    "currency": "INR",
                    "estimated_days": 5
                }
            ],
            "origin": origin,
            "destination": destination,
            "weight": weight
        }


# Carrier factory
def get_carrier_api(courier: CourierProvider) -> CarrierAPIBase:
    carrier_name = courier.name.lower()
    if "india post" in carrier_name:
        return IndiaPostAPI(courier.api_key, courier.api_secret)
    elif "shiprocket" in carrier_name:
        return ShiprocketAPI(courier.api_key, courier.api_secret)
    else:
        # Default carrier handler
        return CarrierAPIBase(courier.api_key, courier.api_secret)


# ==================== PYDANTIC SCHEMAS ====================

class RateCalculationRequest(BaseModel):
    origin_pincode: str
    destination_pincode: str
    weight: float  # in kg
    courier_id: Optional[int] = None

class RateCalculationResponse(BaseModel):
    rates: List[Dict[str, Any]]
    cheapest: Optional[Dict[str, Any]] = None
    fastest: Optional[Dict[str, Any]] = None

class WebhookPayload(BaseModel):
    carrier: str
    tracking_number: str
    status: str
    location: Optional[str] = None
    timestamp: Optional[str] = None
    signature: Optional[str] = None

class ShipmentAnalytics(BaseModel):
    total_shipments: int
    pending: int
    in_transit: int
    delivered: int
    failed: int
    avg_delivery_days: Optional[float] = None
    on_time_delivery_rate: Optional[float] = None
    by_courier: List[Dict[str, Any]]
    by_status: List[Dict[str, Any]]
    recent_shipments: List[Dict[str, Any]]

class BulkStatusUpdateRequest(BaseModel):
    shipment_ids: List[int]
    status: str
    location: Optional[str] = None
    description: Optional[str] = None

class CarrierSyncResult(BaseModel):
    synced: int
    failed: int
    details: List[Dict[str, Any]]

# Helper function to generate tracking number
def generate_tracking_number() -> str:
    return f"MED-{uuid.uuid4().hex[:12].upper()}"

# Courier Provider Management (Admin only)
@router.post("/couriers", response_model=CourierProviderResponse)
async def create_courier_provider(
    courier: CourierProviderCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can manage courier providers")

    # Check if courier already exists
    existing = session.query(CourierProvider).filter(CourierProvider.name == courier.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Courier provider already exists")

    db_courier = CourierProvider(**courier.dict())
    session.add(db_courier)
    session.commit()
    session.refresh(db_courier)
    return db_courier

@router.get("/couriers", response_model=List[CourierProviderResponse])
async def get_courier_providers(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view courier providers")

    couriers = session.query(CourierProvider).filter(CourierProvider.is_active == True).all()
    return couriers

@router.put("/couriers/{courier_id}", response_model=CourierProviderResponse)
async def update_courier_provider(
    courier_id: int,
    courier_update: CourierProviderUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update courier providers")

    courier = session.query(CourierProvider).filter(CourierProvider.id == courier_id).first()
    if not courier:
        raise HTTPException(status_code=404, detail="Courier provider not found")

    for field, value in courier_update.dict(exclude_unset=True).items():
        setattr(courier, field, value)

    courier.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(courier)
    return courier

# Shipment Management
@router.post("/", response_model=ShipmentResponse)
async def create_shipment(
    shipment: ShipmentCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # Only pharmacists and admins can create shipments
    if current_user.role not in ["admin", "pharmacist"]:
        raise HTTPException(status_code=403, detail="Only pharmacists and admins can create shipments")

    # Verify courier exists
    courier = session.query(CourierProvider).filter(
        CourierProvider.id == shipment.courier_id,
        CourierProvider.is_active == True
    ).first()
    if not courier:
        raise HTTPException(status_code=404, detail="Courier provider not found or inactive")

    # Generate tracking number
    tracking_number = generate_tracking_number()

    # Create shipment
    db_shipment = Shipment(
        tracking_number=tracking_number,
        courier_id=shipment.courier_id,
        sender_name=shipment.sender_name,
        sender_phone=shipment.sender_phone,
        sender_address=shipment.sender_address,
        recipient_name=shipment.recipient_name,
        recipient_phone=shipment.recipient_phone,
        recipient_address=shipment.recipient_address,
        package_weight=shipment.package_weight,
        package_dimensions=shipment.package_dimensions,
        estimated_delivery=shipment.estimated_delivery,
        created_by=current_user.id
    )

    session.add(db_shipment)
    session.commit()
    session.refresh(db_shipment)

    # Create shipment items
    for item in shipment.items:
        db_item = ShipmentItem(
            shipment_id=db_shipment.id,
            item_type=item.item_type,
            item_id=item.item_id,
            quantity=item.quantity,
            description=item.description
        )
        session.add(db_item)

    # Create initial tracking entry
    initial_tracking = ShipmentTracking(
        shipment_id=db_shipment.id,
        status=ShipmentStatus.PENDING,
        description="Shipment created and ready for pickup"
    )
    session.add(initial_tracking)

    session.commit()

    # Return shipment with relationships loaded
    shipment_with_relations = session.query(Shipment).filter(Shipment.id == db_shipment.id).first()
    return shipment_with_relations

@router.get("/", response_model=List[ShipmentResponse])
async def get_shipments(
    status: Optional[str] = None,
    courier_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    query = session.query(Shipment)

    # Role-based filtering
    if current_user.role == "patient":
        # Patients can only see shipments where they are recipients
        # This would need additional logic to match patient info
        pass  # For now, show all (will be filtered by business logic)
    elif current_user.role == "pharmacist":
        # Pharmacists can see shipments they created
        query = query.filter(Shipment.created_by == current_user.id)
    # Admins can see all shipments

    if status:
        query = query.filter(Shipment.status == status)
    if courier_id:
        query = query.filter(Shipment.courier_id == courier_id)

    shipments = query.offset(offset).limit(limit).all()
    return shipments

@router.get("/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(
    shipment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    shipment = session.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Role-based access control
    if current_user.role == "patient":
        # Check if user is the recipient (simplified check)
        pass  # Would need more sophisticated matching
    elif current_user.role == "pharmacist" and shipment.created_by != current_user.id:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

    return shipment

@router.put("/{shipment_id}", response_model=ShipmentResponse)
async def update_shipment(
    shipment_id: int,
    shipment_update: ShipmentUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    shipment = session.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Only creator, pharmacists, or admins can update
    if current_user.role not in ["admin", "pharmacist"] and shipment.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    for field, value in shipment_update.dict(exclude_unset=True).items():
        setattr(shipment, field, value)

    shipment.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(shipment)
    return shipment

@router.post("/{shipment_id}/tracking", response_model=ShipmentTrackingResponse)
async def add_tracking_update(
    shipment_id: int,
    tracking_update: ShipmentStatusUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    shipment = session.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Only admins and pharmacists can add tracking updates
    if current_user.role not in ["admin", "pharmacist"]:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate status
    try:
        status_enum = ShipmentStatus(tracking_update.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Update shipment status
    shipment.status = status_enum
    if status_enum == ShipmentStatus.DELIVERED:
        shipment.actual_delivery = datetime.utcnow()
    shipment.updated_at = datetime.utcnow()

    # Create tracking entry
    tracking_entry = ShipmentTracking(
        shipment_id=shipment_id,
        status=status_enum,
        location=tracking_update.location,
        description=tracking_update.description
    )

    session.add(tracking_entry)
    session.commit()
    session.refresh(tracking_entry)
    return tracking_entry

# Public tracking endpoint (no authentication required)
@router.get("/track/{tracking_number}", response_model=PublicTrackingResponse)
async def track_shipment_public(
    tracking_number: str,
    session: Session = Depends(get_session)
):
    shipment = session.query(Shipment).filter(Shipment.tracking_number == tracking_number).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Get latest tracking update
    latest_tracking = session.query(ShipmentTracking).filter(
        ShipmentTracking.shipment_id == shipment.id
    ).order_by(ShipmentTracking.timestamp.desc()).first()

    response = PublicTrackingResponse(
        tracking_number=shipment.tracking_number,
        status=shipment.status,
        estimated_delivery=shipment.estimated_delivery,
        last_update=latest_tracking.timestamp if latest_tracking else shipment.created_at,
        tracking_history=shipment.tracking_history
    )

    return response


# ==================== RATE CALCULATION ====================

@router.post("/rates/calculate", response_model=RateCalculationResponse)
async def calculate_shipping_rates(
    request: RateCalculationRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Calculate shipping rates from multiple carriers"""
    all_rates = []
    
    if request.courier_id:
        couriers = session.query(CourierProvider).filter(
            CourierProvider.id == request.courier_id,
            CourierProvider.is_active == True
        ).all()
    else:
        couriers = session.query(CourierProvider).filter(
            CourierProvider.is_active == True
        ).all()
    
    for courier in couriers:
        try:
            carrier_api = get_carrier_api(courier)
            rate_response = await carrier_api.calculate_rate(
                request.origin_pincode,
                request.destination_pincode,
                request.weight
            )
            
            if "rates" in rate_response:
                all_rates.extend(rate_response["rates"])
            else:
                all_rates.append({
                    **rate_response,
                    "courier_id": courier.id,
                    "courier_name": courier.name
                })
        except Exception as e:
            # Log error but continue with other carriers
            print(f"Rate calculation failed for {courier.name}: {str(e)}")
    
    # Find cheapest and fastest options
    cheapest = min(all_rates, key=lambda x: x.get("rate", float("inf"))) if all_rates else None
    fastest = min(all_rates, key=lambda x: x.get("estimated_days", float("inf"))) if all_rates else None
    
    return RateCalculationResponse(rates=all_rates, cheapest=cheapest, fastest=fastest)


# ==================== CARRIER SYNC ====================

@router.post("/sync/{shipment_id}")
async def sync_shipment_with_carrier(
    shipment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Sync shipment status with carrier API"""
    if current_user.role not in ["admin", "pharmacist"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    shipment = session.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    courier = session.query(CourierProvider).filter(
        CourierProvider.id == shipment.courier_id
    ).first()
    
    if not courier:
        raise HTTPException(status_code=404, detail="Courier not found")
    
    try:
        carrier_api = get_carrier_api(courier)
        tracking_data = await carrier_api.get_tracking(shipment.tracking_number)
        
        if tracking_data.get("success"):
            # Map carrier status to our status
            status_mapping = {
                "picked_up": ShipmentStatus.PICKED_UP,
                "in_transit": ShipmentStatus.IN_TRANSIT,
                "out_for_delivery": ShipmentStatus.OUT_FOR_DELIVERY,
                "delivered": ShipmentStatus.DELIVERED,
                "failed": ShipmentStatus.FAILED_DELIVERY,
                "returned": ShipmentStatus.RETURNED
            }
            
            carrier_status = tracking_data.get("status", "").lower().replace(" ", "_")
            new_status = status_mapping.get(carrier_status)
            
            if new_status and new_status != shipment.status:
                # Update shipment status
                old_status = shipment.status
                shipment.status = new_status
                shipment.updated_at = datetime.utcnow()
                
                if new_status == ShipmentStatus.DELIVERED:
                    shipment.actual_delivery = datetime.utcnow()
                
                # Add tracking entry
                tracking_entry = ShipmentTracking(
                    shipment_id=shipment.id,
                    status=new_status,
                    location=tracking_data.get("current_location"),
                    description=f"Status synced from {courier.name}: {carrier_status}"
                )
                session.add(tracking_entry)
                session.commit()
                
                return {
                    "success": True,
                    "shipment_id": shipment.id,
                    "old_status": old_status,
                    "new_status": new_status,
                    "carrier_data": tracking_data
                }
        
        return {
            "success": True,
            "shipment_id": shipment.id,
            "status": shipment.status,
            "message": "No status change detected"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Carrier sync failed: {str(e)}")


@router.post("/sync/bulk", response_model=CarrierSyncResult)
async def bulk_sync_shipments(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Sync all active shipments with their carriers"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can perform bulk sync")
    
    # Get all non-delivered, non-cancelled shipments
    active_shipments = session.query(Shipment).filter(
        Shipment.status.notin_([ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED, ShipmentStatus.RETURNED])
    ).all()
    
    synced = 0
    failed = 0
    details = []
    
    for shipment in active_shipments:
        try:
            courier = session.query(CourierProvider).filter(
                CourierProvider.id == shipment.courier_id
            ).first()
            
            if courier:
                carrier_api = get_carrier_api(courier)
                tracking_data = await carrier_api.get_tracking(shipment.tracking_number)
                
                if tracking_data.get("success"):
                    synced += 1
                    details.append({
                        "shipment_id": shipment.id,
                        "tracking_number": shipment.tracking_number,
                        "status": "synced"
                    })
                else:
                    failed += 1
                    details.append({
                        "shipment_id": shipment.id,
                        "tracking_number": shipment.tracking_number,
                        "status": "failed",
                        "error": "No response from carrier"
                    })
        except Exception as e:
            failed += 1
            details.append({
                "shipment_id": shipment.id,
                "tracking_number": shipment.tracking_number,
                "status": "failed",
                "error": str(e)
            })
    
    return CarrierSyncResult(synced=synced, failed=failed, details=details)


# ==================== WEBHOOKS ====================

@router.post("/webhook/indiapost")
async def india_post_webhook(
    request: Request,
    session: Session = Depends(get_session)
):
    """Webhook endpoint for India Post status updates"""
    try:
        payload = await request.json()
        
        # Verify webhook signature (in production)
        # signature = request.headers.get("X-Webhook-Signature")
        # if not verify_webhook_signature(payload, signature, "indiapost"):
        #     raise HTTPException(status_code=401, detail="Invalid signature")
        
        tracking_number = payload.get("tracking_number")
        if not tracking_number:
            raise HTTPException(status_code=400, detail="Missing tracking number")
        
        shipment = session.query(Shipment).filter(
            Shipment.tracking_number == tracking_number
        ).first()
        
        if not shipment:
            # Log but don't fail - might be for a different system
            return {"success": True, "message": "Shipment not found, ignored"}
        
        status_mapping = {
            "booked": ShipmentStatus.PENDING,
            "picked_up": ShipmentStatus.PICKED_UP,
            "in_transit": ShipmentStatus.IN_TRANSIT,
            "out_for_delivery": ShipmentStatus.OUT_FOR_DELIVERY,
            "delivered": ShipmentStatus.DELIVERED,
            "undelivered": ShipmentStatus.FAILED_DELIVERY,
            "rto": ShipmentStatus.RETURNED
        }
        
        carrier_status = payload.get("status", "").lower()
        new_status = status_mapping.get(carrier_status)
        
        if new_status:
            shipment.status = new_status
            shipment.updated_at = datetime.utcnow()
            
            if new_status == ShipmentStatus.DELIVERED:
                shipment.actual_delivery = datetime.utcnow()
            
            tracking_entry = ShipmentTracking(
                shipment_id=shipment.id,
                status=new_status,
                location=payload.get("location"),
                description=payload.get("description", f"Status update from India Post: {carrier_status}")
            )
            session.add(tracking_entry)
            session.commit()
        
        return {"success": True, "message": "Webhook processed"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


@router.post("/webhook/shiprocket")
async def shiprocket_webhook(
    request: Request,
    session: Session = Depends(get_session)
):
    """Webhook endpoint for Shiprocket status updates"""
    try:
        payload = await request.json()
        
        # Shiprocket sends AWB number
        awb = payload.get("awb")
        tracking_number = payload.get("tracking_number") or awb
        
        if not tracking_number:
            raise HTTPException(status_code=400, detail="Missing tracking number")
        
        shipment = session.query(Shipment).filter(
            Shipment.tracking_number == tracking_number
        ).first()
        
        if not shipment:
            return {"success": True, "message": "Shipment not found, ignored"}
        
        status_mapping = {
            "pickup scheduled": ShipmentStatus.PENDING,
            "picked up": ShipmentStatus.PICKED_UP,
            "in transit": ShipmentStatus.IN_TRANSIT,
            "out for delivery": ShipmentStatus.OUT_FOR_DELIVERY,
            "delivered": ShipmentStatus.DELIVERED,
            "delivery failed": ShipmentStatus.FAILED_DELIVERY,
            "rto initiated": ShipmentStatus.RETURNED,
            "rto delivered": ShipmentStatus.RETURNED
        }
        
        carrier_status = payload.get("current_status", "").lower()
        new_status = status_mapping.get(carrier_status)
        
        if new_status:
            shipment.status = new_status
            shipment.updated_at = datetime.utcnow()
            
            if new_status == ShipmentStatus.DELIVERED:
                shipment.actual_delivery = datetime.utcnow()
            
            tracking_entry = ShipmentTracking(
                shipment_id=shipment.id,
                status=new_status,
                location=payload.get("current_location"),
                description=payload.get("status_description", f"Status update from Shiprocket: {carrier_status}")
            )
            session.add(tracking_entry)
            session.commit()
        
        return {"success": True, "message": "Webhook processed"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


# ==================== ADMIN ANALYTICS ====================

@router.get("/admin/analytics", response_model=ShipmentAnalytics)
async def get_shipment_analytics(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get shipment analytics and statistics"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view analytics")
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Total shipments in period
    total_query = session.query(Shipment).filter(Shipment.created_at >= start_date)
    total_shipments = total_query.count()
    
    # Count by status
    pending = total_query.filter(Shipment.status == ShipmentStatus.PENDING).count()
    in_transit = total_query.filter(Shipment.status.in_([
        ShipmentStatus.PICKED_UP, ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY
    ])).count()
    delivered = total_query.filter(Shipment.status == ShipmentStatus.DELIVERED).count()
    failed = total_query.filter(Shipment.status.in_([
        ShipmentStatus.FAILED_DELIVERY, ShipmentStatus.RETURNED, ShipmentStatus.CANCELLED
    ])).count()
    
    # Average delivery days for delivered shipments
    delivered_shipments = session.query(Shipment).filter(
        Shipment.created_at >= start_date,
        Shipment.status == ShipmentStatus.DELIVERED,
        Shipment.actual_delivery.isnot(None)
    ).all()
    
    avg_delivery_days = None
    if delivered_shipments:
        total_days = sum(
            (s.actual_delivery - s.created_at).days 
            for s in delivered_shipments
        )
        avg_delivery_days = round(total_days / len(delivered_shipments), 1)
    
    # On-time delivery rate
    on_time_count = 0
    for s in delivered_shipments:
        if s.estimated_delivery and s.actual_delivery <= s.estimated_delivery:
            on_time_count += 1
    
    on_time_rate = round((on_time_count / len(delivered_shipments)) * 100, 1) if delivered_shipments else None
    
    # By courier breakdown
    by_courier = []
    couriers = session.query(CourierProvider).all()
    for courier in couriers:
        count = total_query.filter(Shipment.courier_id == courier.id).count()
        if count > 0:
            by_courier.append({
                "courier_id": courier.id,
                "courier_name": courier.name,
                "shipment_count": count
            })
    
    # By status breakdown
    by_status = [
        {"status": "pending", "count": pending},
        {"status": "in_transit", "count": in_transit},
        {"status": "delivered", "count": delivered},
        {"status": "failed", "count": failed}
    ]
    
    # Recent shipments
    recent = session.query(Shipment).order_by(Shipment.created_at.desc()).limit(10).all()
    recent_shipments = [{
        "id": s.id,
        "tracking_number": s.tracking_number,
        "status": s.status,
        "recipient_name": s.recipient_name,
        "created_at": s.created_at.isoformat()
    } for s in recent]
    
    return ShipmentAnalytics(
        total_shipments=total_shipments,
        pending=pending,
        in_transit=in_transit,
        delivered=delivered,
        failed=failed,
        avg_delivery_days=avg_delivery_days,
        on_time_delivery_rate=on_time_rate,
        by_courier=by_courier,
        by_status=by_status,
        recent_shipments=recent_shipments
    )


@router.post("/admin/bulk-update")
async def bulk_update_shipment_status(
    request: BulkStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Bulk update shipment statuses"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can perform bulk updates")
    
    try:
        status_enum = ShipmentStatus(request.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    updated = 0
    failed = 0
    
    for shipment_id in request.shipment_ids:
        try:
            shipment = session.query(Shipment).filter(Shipment.id == shipment_id).first()
            if shipment:
                shipment.status = status_enum
                shipment.updated_at = datetime.utcnow()
                
                if status_enum == ShipmentStatus.DELIVERED:
                    shipment.actual_delivery = datetime.utcnow()
                
                tracking_entry = ShipmentTracking(
                    shipment_id=shipment.id,
                    status=status_enum,
                    location=request.location,
                    description=request.description or f"Bulk status update to {request.status}"
                )
                session.add(tracking_entry)
                updated += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    
    session.commit()
    
    return {
        "success": True,
        "updated": updated,
        "failed": failed,
        "total": len(request.shipment_ids)
    }


@router.get("/admin/shipments")
async def admin_list_all_shipments(
    status: Optional[str] = None,
    courier_id: Optional[int] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Admin endpoint to list all shipments with filters"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can access this endpoint")
    
    query = session.query(Shipment)
    
    if status:
        try:
            status_enum = ShipmentStatus(status)
            query = query.filter(Shipment.status == status_enum)
        except ValueError:
            pass
    
    if courier_id:
        query = query.filter(Shipment.courier_id == courier_id)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Shipment.tracking_number.ilike(search_filter)) |
            (Shipment.recipient_name.ilike(search_filter)) |
            (Shipment.recipient_phone.ilike(search_filter))
        )
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.filter(Shipment.created_at >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.filter(Shipment.created_at <= end)
        except ValueError:
            pass
    
    total = query.count()
    shipments = query.order_by(Shipment.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "shipments": [{
            "id": s.id,
            "tracking_number": s.tracking_number,
            "status": s.status,
            "courier_id": s.courier_id,
            "sender_name": s.sender_name,
            "recipient_name": s.recipient_name,
            "recipient_phone": s.recipient_phone,
            "recipient_address": s.recipient_address,
            "package_weight": s.package_weight,
            "estimated_delivery": s.estimated_delivery.isoformat() if s.estimated_delivery else None,
            "actual_delivery": s.actual_delivery.isoformat() if s.actual_delivery else None,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "items": [{
                "id": item.id,
                "item_type": item.item_type,
                "description": item.description,
                "quantity": item.quantity
            } for item in s.items],
            "tracking_history": [{
                "id": t.id,
                "status": t.status,
                "location": t.location,
                "description": t.description,
                "timestamp": t.timestamp.isoformat()
            } for t in s.tracking_history]
        } for s in shipments],
        "limit": limit,
        "offset": offset
    }


# ==================== LABEL GENERATION ====================

@router.get("/{shipment_id}/label")
async def generate_shipping_label(
    shipment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Generate shipping label data for a shipment"""
    if current_user.role not in ["admin", "pharmacist"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    shipment = session.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    courier = session.query(CourierProvider).filter(
        CourierProvider.id == shipment.courier_id
    ).first()
    
    # Return label data (in production, this could generate actual PDF/image)
    return {
        "tracking_number": shipment.tracking_number,
        "barcode_data": shipment.tracking_number,  # Can be used to generate barcode
        "courier_name": courier.name if courier else "Unknown",
        "sender": {
            "name": shipment.sender_name,
            "phone": shipment.sender_phone,
            "address": shipment.sender_address
        },
        "recipient": {
            "name": shipment.recipient_name,
            "phone": shipment.recipient_phone,
            "address": shipment.recipient_address
        },
        "package": {
            "weight": shipment.package_weight,
            "dimensions": shipment.package_dimensions
        },
        "items": [{
            "description": item.description,
            "quantity": item.quantity
        } for item in shipment.items],
        "created_at": shipment.created_at.isoformat(),
        "estimated_delivery": shipment.estimated_delivery.isoformat() if shipment.estimated_delivery else None
    }