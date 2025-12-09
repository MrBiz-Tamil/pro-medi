"""Payment processing and commission management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import os
import hmac
import hashlib
import logging

from database import get_session
from models import User, Payment, Appointment, CommissionTier, DoctorRating, DoctorProfile
from dependencies import get_current_user, require_doctor
from slowapi import Limiter
from slowapi.util import get_remote_address
import razorpay

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Rate limiter for payment endpoints
limiter = Limiter(key_func=get_remote_address)

# Initialize Razorpay client
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

# SECURITY: Validate payment credentials in production
is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
if is_production and (not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET):
    logger.warning("RAZORPAY credentials not configured in production!")

if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
else:
    razorpay_client = None

if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
else:
    razorpay_client = None

# Request/Response Models
class PaymentInitiate(BaseModel):
    consultation_fee: int  # in INR

class PaymentInitiateResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    consultation_fee: int
    platform_commission: int
    doctor_earnings: int
    commission_tier: str
    razorpay_key: str

class PaymentVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class PaymentResponse(BaseModel):
    id: int
    appointment_id: int
    consultation_fee: int
    platform_commission: int
    doctor_earnings: int
    status: str
    payment_method: str
    paid_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

class DoctorEarnings(BaseModel):
    doctor_id: int
    total_earnings: int
    pending_payout: int
    monthly_earnings: int
    total_consultations: int
    average_rating: float
    total_reviews: int
    current_tier: dict
    next_tier: Optional[dict]
    recent_transactions: List[dict]

@router.post("/appointments/{appointment_id}/initiate", response_model=PaymentInitiateResponse)
@limiter.limit("10/minute")
async def initiate_payment(
    request: Request,
    appointment_id: int,
    payment_data: PaymentInitiate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Initiate payment for an appointment (rate limited to prevent abuse)"""
    
    if not razorpay_client:
        raise HTTPException(
            status_code=503,
            detail="Payment service not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET"
        )
    
    # Verify appointment exists and belongs to current user
    appointment = session.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if appointment.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot pay for cancelled appointment")
    
    # Check if payment already exists
    existing_payment = session.exec(
        select(Payment).where(Payment.appointment_id == appointment_id)
    ).first()
    
    if existing_payment and existing_payment.status == "completed":
        raise HTTPException(status_code=400, detail="Payment already completed")
    
    # Calculate commission based on doctor's rating
    commission_info = await calculate_commission(appointment.doctor_id, payment_data.consultation_fee, session)
    
    # Create Razorpay order
    razorpay_order = razorpay_client.order.create({
        "amount": payment_data.consultation_fee * 100,  # Convert to paise
        "currency": "INR",
        "receipt": f"appointment_{appointment_id}",
        "notes": {
            "appointment_id": appointment_id,
            "doctor_id": appointment.doctor_id,
            "patient_id": current_user.id
        }
    })
    
    # Create or update payment record
    if existing_payment:
        payment = existing_payment
        payment.consultation_fee = payment_data.consultation_fee
        payment.platform_commission = commission_info["commission"]
        payment.doctor_earnings = commission_info["doctor_earnings"]
        payment.razorpay_order_id = razorpay_order["id"]
    else:
        payment = Payment(
            appointment_id=appointment_id,
            patient_id=current_user.id,
            doctor_id=appointment.doctor_id,
            consultation_fee=payment_data.consultation_fee,
            platform_commission=commission_info["commission"],
            doctor_earnings=commission_info["doctor_earnings"],
            payment_method="razorpay",
            razorpay_order_id=razorpay_order["id"],
            status="pending"
        )
        session.add(payment)
    
    session.commit()
    session.refresh(payment)
    
    return PaymentInitiateResponse(
        order_id=razorpay_order["id"],
        amount=payment_data.consultation_fee,
        currency="INR",
        consultation_fee=payment_data.consultation_fee,
        platform_commission=commission_info["commission"],
        doctor_earnings=commission_info["doctor_earnings"],
        commission_tier=commission_info["tier_name"],
        razorpay_key=RAZORPAY_KEY_ID
    )

@router.post("/verify")
async def verify_payment(
    payment_data: PaymentVerify,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Verify Razorpay payment signature"""
    
    # Verify signature
    generated_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{payment_data.razorpay_order_id}|{payment_data.razorpay_payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    if generated_signature != payment_data.razorpay_signature:
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    
    # Update payment status
    payment = session.exec(
        select(Payment).where(Payment.razorpay_order_id == payment_data.razorpay_order_id)
    ).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment.status = "completed"
    payment.razorpay_payment_id = payment_data.razorpay_payment_id
    payment.razorpay_signature = payment_data.razorpay_signature
    payment.paid_at = datetime.utcnow()
    
    session.add(payment)
    
    # Update appointment status to confirmed
    appointment = session.get(Appointment, payment.appointment_id)
    if appointment and appointment.status == "scheduled":
        appointment.status = "confirmed"
        session.add(appointment)
    
    session.commit()
    
    return {"message": "Payment verified successfully", "payment_id": payment.id}

@router.get("/appointments/{appointment_id}", response_model=PaymentResponse)
async def get_payment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get payment details for an appointment"""
    
    payment = session.exec(
        select(Payment).where(Payment.appointment_id == appointment_id)
    ).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Verify user has access
    if payment.patient_id != current_user.id and payment.doctor_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return payment

@router.get("/doctors/my-earnings", response_model=DoctorEarnings)
async def get_doctor_earnings(
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get doctor's earnings and statistics"""
    
    # Get all completed payments
    payments = session.exec(
        select(Payment)
        .where(Payment.doctor_id == current_user.id)
        .where(Payment.status == "completed")
    ).all()
    
    total_earnings = sum(p.doctor_earnings for p in payments)
    total_consultations = len(payments)
    
    # Calculate monthly earnings (current month)
    current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_payments = [p for p in payments if p.paid_at and p.paid_at >= current_month_start]
    monthly_earnings = sum(p.doctor_earnings for p in monthly_payments)
    
    # Pending payout (payments from last 7 days - simulating payout cycle)
    payout_cutoff = datetime.utcnow() - timedelta(days=7)
    pending_payments = [p for p in payments if p.paid_at and p.paid_at >= payout_cutoff]
    pending_payout = sum(p.doctor_earnings for p in pending_payments)
    
    # Get doctor's ratings
    ratings = session.exec(
        select(DoctorRating).where(DoctorRating.doctor_id == current_user.id)
    ).all()
    
    average_rating = sum(r.rating for r in ratings) / len(ratings) if ratings else 0.0
    total_reviews = len(ratings)
    
    # Get current commission tier
    current_tier_info = await get_commission_tier_for_rating(average_rating, session)
    
    # Get next tier
    next_tier = session.exec(
        select(CommissionTier)
        .where(CommissionTier.min_rating > average_rating)
        .order_by(CommissionTier.min_rating)
    ).first()
    
    next_tier_info = None
    if next_tier:
        next_tier_info = {
            "tier_name": next_tier.tier_name,
            "min_rating": next_tier.min_rating,
            "commission_amount": next_tier.commission_amount,
            "rating_gap": round(next_tier.min_rating - average_rating, 2)
        }
    
    # Get recent transactions (last 10)
    recent_payments = sorted(payments, key=lambda p: p.paid_at or p.created_at, reverse=True)[:10]
    recent_transactions = []
    
    for payment in recent_payments:
        appointment = session.get(Appointment, payment.appointment_id)
        patient = session.get(User, payment.patient_id)
        recent_transactions.append({
            "id": payment.id,
            "date": payment.paid_at or payment.created_at,
            "patient_name": patient.full_name if patient else "Unknown",
            "consultation_fee": payment.consultation_fee,
            "platform_commission": payment.platform_commission,
            "doctor_earnings": payment.doctor_earnings,
            "status": payment.status
        })
    
    return DoctorEarnings(
        doctor_id=current_user.id,
        total_earnings=total_earnings,
        pending_payout=pending_payout,
        monthly_earnings=monthly_earnings,
        total_consultations=total_consultations,
        average_rating=round(average_rating, 2),
        total_reviews=total_reviews,
        current_tier={
            "tier_name": current_tier_info["tier_name"],
            "commission_amount": current_tier_info["commission"],
            "min_rating": current_tier_info.get("min_rating", 0),
            "max_rating": current_tier_info.get("max_rating", 5)
        },
        next_tier=next_tier_info,
        recent_transactions=recent_transactions
    )

# Helper functions
async def calculate_commission(doctor_id: int, consultation_fee: int, session: Session) -> dict:
    """Calculate commission based on doctor's rating"""
    
    # Get doctor's average rating
    ratings = session.exec(
        select(DoctorRating).where(DoctorRating.doctor_id == doctor_id)
    ).all()
    
    if ratings:
        average_rating = sum(r.rating for r in ratings) / len(ratings)
    else:
        average_rating = 0.0  # New doctor
    
    # Get commission tier
    tier_info = await get_commission_tier_for_rating(average_rating, session)
    commission = tier_info["commission"]
    
    # Ensure commission doesn't exceed consultation fee
    if commission > consultation_fee * 0.2:  # Max 20% commission
        commission = int(consultation_fee * 0.2)
    
    doctor_earnings = consultation_fee - commission
    
    return {
        "commission": commission,
        "doctor_earnings": doctor_earnings,
        "tier_name": tier_info["tier_name"],
        "average_rating": round(average_rating, 2)
    }

async def get_commission_tier_for_rating(rating: float, session: Session) -> dict:
    """Get commission tier based on rating"""
    
    # Check if tiers exist in database
    tier = session.exec(
        select(CommissionTier)
        .where(CommissionTier.min_rating <= rating)
        .where(CommissionTier.max_rating >= rating)
    ).first()
    
    if tier:
        return {
            "tier_name": tier.tier_name,
            "commission": tier.commission_amount,
            "min_rating": tier.min_rating,
            "max_rating": tier.max_rating
        }
    
    # Default tiers if not in database
    if rating >= 4.5:
        return {"tier_name": "Top Rated", "commission": 1000}
    elif rating >= 4.0:
        return {"tier_name": "Highly Rated", "commission": 600}
    elif rating >= 3.0:
        return {"tier_name": "Good", "commission": 400}
    else:
        return {"tier_name": "New Doctor", "commission": 200}


# ==================== Additional Payment Endpoints for Mobile Apps ====================

class PaymentCreateRequest(BaseModel):
    appointment_id: int
    amount: int
    currency: Optional[str] = "INR"
    payment_method: Optional[str] = None
    notes: Optional[str] = None


class PaymentCreateResponse(BaseModel):
    payment_id: str
    order_id: str
    amount: int
    currency: str
    status: str
    razorpay_order_id: Optional[str] = None
    razorpay_key: Optional[str] = None


class PaymentHistoryItem(BaseModel):
    id: int
    payment_id: str
    appointment_id: int
    amount: int
    currency: str
    status: str
    payment_method: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    doctor_name: Optional[str]


class ReceiptResponse(BaseModel):
    receipt_number: str
    payment_id: int
    patient_name: str
    doctor_name: str
    appointment_date: str
    consultation_type: str
    amount: int
    tax: Optional[int] = None
    total: int
    payment_method: str
    payment_date: str
    pdf_url: Optional[str] = None


class PaymentMethodItem(BaseModel):
    id: str
    type: str  # card, upi, wallet, netbanking
    name: str
    last4: Optional[str] = None
    brand: Optional[str] = None
    upi_id: Optional[str] = None
    is_default: bool = False


@router.post("/create", response_model=PaymentCreateResponse)
async def create_payment(
    payment_data: PaymentCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create a payment order (alias for initiate_payment)"""
    
    if not razorpay_client:
        raise HTTPException(
            status_code=503,
            detail="Payment service not configured"
        )
    
    # Verify appointment
    appointment = session.get(Appointment, payment_data.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Check existing payment
    existing_payment = session.exec(
        select(Payment).where(Payment.appointment_id == payment_data.appointment_id)
    ).first()
    
    if existing_payment and existing_payment.status == "completed":
        raise HTTPException(status_code=400, detail="Payment already completed")
    
    # Calculate commission
    commission_info = await calculate_commission(appointment.doctor_id, payment_data.amount, session)
    
    # Create Razorpay order
    razorpay_order = razorpay_client.order.create({
        "amount": payment_data.amount * 100,
        "currency": payment_data.currency,
        "receipt": f"appointment_{payment_data.appointment_id}",
    })
    
    # Create/update payment record
    if existing_payment:
        payment = existing_payment
        payment.consultation_fee = payment_data.amount
        payment.platform_commission = commission_info["commission"]
        payment.doctor_earnings = commission_info["doctor_earnings"]
        payment.razorpay_order_id = razorpay_order["id"]
    else:
        payment = Payment(
            appointment_id=payment_data.appointment_id,
            patient_id=current_user.id,
            doctor_id=appointment.doctor_id,
            consultation_fee=payment_data.amount,
            platform_commission=commission_info["commission"],
            doctor_earnings=commission_info["doctor_earnings"],
            payment_method=payment_data.payment_method or "razorpay",
            razorpay_order_id=razorpay_order["id"],
            status="pending"
        )
        session.add(payment)
    
    session.commit()
    session.refresh(payment)
    
    return PaymentCreateResponse(
        payment_id=str(payment.id),
        order_id=razorpay_order["id"],
        amount=payment_data.amount,
        currency=payment_data.currency,
        status="pending",
        razorpay_order_id=razorpay_order["id"],
        razorpay_key=RAZORPAY_KEY_ID
    )


@router.get("/history")
async def get_payment_history(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get payment history for current user"""
    
    query = select(Payment).where(Payment.patient_id == current_user.id)
    
    if status:
        query = query.where(Payment.status == status)
    
    query = query.order_by(Payment.created_at.desc()).offset(offset).limit(limit)
    
    payments = session.exec(query).all()
    
    # Get total count
    count_query = select(func.count(Payment.id)).where(Payment.patient_id == current_user.id)
    if status:
        count_query = count_query.where(Payment.status == status)
    total = session.exec(count_query).first() or 0
    
    payments_list = []
    for payment in payments:
        doctor = session.get(User, payment.doctor_id)
        payments_list.append({
            "id": payment.id,
            "payment_id": str(payment.id),
            "appointment_id": payment.appointment_id,
            "amount": payment.consultation_fee,
            "currency": "INR",
            "status": payment.status,
            "payment_method": payment.payment_method,
            "created_at": payment.created_at.isoformat(),
            "completed_at": payment.paid_at.isoformat() if payment.paid_at else None,
            "doctor_name": doctor.full_name if doctor else "Unknown"
        })
    
    return {
        "payments": payments_list,
        "total": total
    }


@router.get("/{payment_id}")
async def get_payment_by_id(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get payment by ID"""
    
    payment = session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Verify access
    if payment.patient_id != current_user.id and payment.doctor_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    doctor = session.get(User, payment.doctor_id)
    patient = session.get(User, payment.patient_id)
    
    return {
        "id": payment.id,
        "appointment_id": payment.appointment_id,
        "patient_name": patient.full_name if patient else "Unknown",
        "doctor_name": doctor.full_name if doctor else "Unknown",
        "consultation_fee": payment.consultation_fee,
        "platform_commission": payment.platform_commission,
        "doctor_earnings": payment.doctor_earnings,
        "status": payment.status,
        "payment_method": payment.payment_method,
        "razorpay_order_id": payment.razorpay_order_id,
        "razorpay_payment_id": payment.razorpay_payment_id,
        "created_at": payment.created_at.isoformat(),
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None
    }


@router.get("/{payment_id}/receipt", response_model=ReceiptResponse)
async def get_receipt(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get receipt for a payment"""
    
    payment = session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.patient_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if payment.status != "completed":
        raise HTTPException(status_code=400, detail="Receipt only available for completed payments")
    
    appointment = session.get(Appointment, payment.appointment_id)
    doctor = session.get(User, payment.doctor_id)
    patient = session.get(User, payment.patient_id)
    
    return ReceiptResponse(
        receipt_number=f"RCP-{payment.id:06d}",
        payment_id=payment.id,
        patient_name=patient.full_name if patient else "Unknown",
        doctor_name=doctor.full_name if doctor else "Unknown",
        appointment_date=appointment.appointment_date.isoformat() if appointment else "",
        consultation_type=appointment.consultation_type if appointment else "Video",
        amount=payment.consultation_fee,
        tax=0,
        total=payment.consultation_fee,
        payment_method=payment.payment_method or "Razorpay",
        payment_date=payment.paid_at.isoformat() if payment.paid_at else payment.created_at.isoformat(),
        pdf_url=f"/api/payments/{payment_id}/receipt/download"
    )


@router.post("/{payment_id}/refund")
async def request_refund(
    payment_id: int,
    reason: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Request refund for a payment"""
    
    payment = session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.patient_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if payment.status != "completed":
        raise HTTPException(status_code=400, detail="Can only refund completed payments")
    
    # In production, initiate refund with Razorpay
    # For now, update status
    payment.status = "refund_requested"
    session.add(payment)
    session.commit()
    
    return {
        "refund_id": f"RFD-{payment.id:06d}",
        "status": "pending",
        "message": f"Refund request submitted. Reason: {reason}"
    }


@router.get("/methods", response_model=List[PaymentMethodItem])
async def get_payment_methods(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get saved payment methods"""
    
    # In production, fetch from payment_methods table
    # For now, return empty list
    return []


@router.post("/methods")
async def add_payment_method(
    type: str,  # card, upi
    token: Optional[str] = None,
    upi_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Add a payment method"""
    
    # In production, save to database
    return {
        "id": "pm_1",
        "type": type,
        "message": "Payment method added successfully"
    }


@router.delete("/methods/{method_id}")
async def remove_payment_method(
    method_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Remove a payment method"""
    
    # In production, delete from database
    return {"message": "Payment method removed successfully"}


@router.patch("/methods/{method_id}/default")
async def set_default_payment_method(
    method_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Set a payment method as default"""
    
    # In production, update in database
    return {"message": "Payment method set as default"}


@router.post("/webhook/razorpay")
async def razorpay_webhook(request: Request, session: Session = Depends(get_session)):
    """Handle Razorpay webhooks"""
    
    # Verify webhook signature
    webhook_signature = request.headers.get("X-Razorpay-Signature")
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    
    body = await request.body()
    
    if webhook_secret:
        expected_signature = hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if webhook_signature != expected_signature:
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    
    # Process webhook event
    # This is for automated payment confirmation
    # You can add more logic here based on Razorpay events
    
    return {"status": "ok"}
