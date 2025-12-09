"""Earnings management endpoints for doctors"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from enum import Enum

from database import get_session
from models import User, Payment, Appointment, DoctorRating, DoctorProfile
from dependencies import get_current_user, require_doctor

router = APIRouter(prefix="/api/earnings", tags=["earnings"])


# ==================== Schemas ====================

class EarningsSummary(BaseModel):
    total_earnings: float
    this_month: float
    last_month: float
    pending_withdrawal: float
    available_balance: float
    total_consultations: int
    commission_rate: float
    current_tier: str


class DailyEarning(BaseModel):
    date: str
    amount: float
    consultations: int


class MonthlyEarning(BaseModel):
    month: str
    amount: float
    consultations: int


class TopPerformingDay(BaseModel):
    day: str
    amount: float


class EarningsAnalytics(BaseModel):
    daily_earnings: List[DailyEarning]
    monthly_earnings: List[MonthlyEarning]
    top_performing_days: List[TopPerformingDay]


class Transaction(BaseModel):
    id: int
    date: datetime
    type: str
    amount: float
    patient_name: Optional[str] = None
    appointment_id: Optional[int] = None
    status: str
    description: Optional[str] = None


class TransactionList(BaseModel):
    transactions: List[Transaction]
    total: int
    page: int
    pages: int


class CommissionTierInfo(BaseModel):
    tier: int
    name: str
    rating_min: float
    rating_max: float
    commission_per_consultation: float
    benefits: List[str]
    badge_icon: str
    badge_color: str


class WithdrawalRequest(BaseModel):
    amount: float
    bank_account_id: int
    notes: Optional[str] = None


class WithdrawalResponse(BaseModel):
    withdrawal_id: int
    status: str
    message: str


class WithdrawalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    completed = "completed"
    rejected = "rejected"


class WithdrawalItem(BaseModel):
    id: int
    amount: float
    status: WithdrawalStatus
    requested_at: datetime
    processed_at: Optional[datetime] = None
    bank_account: dict


class BankAccount(BaseModel):
    id: int
    account_holder: str
    account_number: str
    ifsc_code: str
    bank_name: str
    is_primary: bool


class BankAccountCreate(BaseModel):
    account_holder: str
    account_number: str
    ifsc_code: str
    bank_name: str
    is_primary: Optional[bool] = False


class ExportResponse(BaseModel):
    download_url: str
    expires_at: str


# ==================== Commission Tiers ====================

COMMISSION_TIERS = [
    {
        "tier": 1,
        "name": "Bronze",
        "rating_min": 0,
        "rating_max": 3.5,
        "commission_per_consultation": 200,
        "benefits": ["Basic visibility", "Standard support", "Basic analytics"],
        "badge_icon": "🥉",
        "badge_color": "#CD7F32",
    },
    {
        "tier": 2,
        "name": "Silver",
        "rating_min": 3.5,
        "rating_max": 4.0,
        "commission_per_consultation": 400,
        "benefits": ["Priority listing", "Email support", "Enhanced analytics"],
        "badge_icon": "🥈",
        "badge_color": "#C0C0C0",
    },
    {
        "tier": 3,
        "name": "Gold",
        "rating_min": 4.0,
        "rating_max": 4.5,
        "commission_per_consultation": 600,
        "benefits": ["Featured badge", "Phone support", "Advanced analytics", "Promotional features"],
        "badge_icon": "🥇",
        "badge_color": "#FFD700",
    },
    {
        "tier": 4,
        "name": "Platinum",
        "rating_min": 4.5,
        "rating_max": 5.0,
        "commission_per_consultation": 1000,
        "benefits": ["Top placement", "Dedicated manager", "Premium analytics", "Priority support", "Marketing boost"],
        "badge_icon": "💎",
        "badge_color": "#E5E4E2",
    },
]


def get_tier_for_rating(rating: float) -> dict:
    """Get commission tier based on rating"""
    for tier in reversed(COMMISSION_TIERS):
        if rating >= tier["rating_min"]:
            return tier
    return COMMISSION_TIERS[0]


# ==================== Endpoints ====================

@router.get("/summary", response_model=EarningsSummary)
async def get_earnings_summary(
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get earnings summary for the doctor"""
    
    # Get all completed payments for this doctor
    payments = session.exec(
        select(Payment)
        .where(Payment.doctor_id == current_user.id)
        .where(Payment.status == "completed")
    ).all()
    
    total_earnings = sum(p.doctor_earnings for p in payments)
    total_consultations = len(payments)
    
    # Current month earnings
    now = datetime.utcnow()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_payments = [p for p in payments if p.paid_at and p.paid_at >= current_month_start]
    this_month = sum(p.doctor_earnings for p in this_month_payments)
    
    # Last month earnings
    last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    last_month_payments = [p for p in payments if p.paid_at and last_month_start <= p.paid_at < current_month_start]
    last_month = sum(p.doctor_earnings for p in last_month_payments)
    
    # Pending withdrawal (earnings from last 7 days - simulating payout cycle)
    payout_cutoff = now - timedelta(days=7)
    pending_payments = [p for p in payments if p.paid_at and p.paid_at >= payout_cutoff]
    pending_withdrawal = sum(p.doctor_earnings for p in pending_payments)
    
    # Available balance (older earnings ready for withdrawal)
    available_balance = total_earnings - pending_withdrawal
    
    # Get average rating and commission tier
    ratings = session.exec(
        select(DoctorRating).where(DoctorRating.doctor_id == current_user.id)
    ).all()
    
    average_rating = sum(r.rating for r in ratings) / len(ratings) if ratings else 0.0
    tier = get_tier_for_rating(average_rating)
    
    return EarningsSummary(
        total_earnings=total_earnings,
        this_month=this_month,
        last_month=last_month,
        pending_withdrawal=pending_withdrawal,
        available_balance=max(0, available_balance),
        total_consultations=total_consultations,
        commission_rate=tier["commission_per_consultation"],
        current_tier=tier["name"]
    )


@router.get("/analytics", response_model=EarningsAnalytics)
async def get_earnings_analytics(
    period: str = "month",  # week, month, year
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get earnings analytics for the doctor"""
    
    now = datetime.utcnow()
    
    # Determine date range based on period
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "year":
        start_date = now - timedelta(days=365)
    else:  # month
        start_date = now - timedelta(days=30)
    
    # Get payments within range
    payments = session.exec(
        select(Payment)
        .where(Payment.doctor_id == current_user.id)
        .where(Payment.status == "completed")
        .where(Payment.paid_at >= start_date)
    ).all()
    
    # Daily earnings
    daily_data = {}
    for payment in payments:
        if payment.paid_at:
            day_key = payment.paid_at.strftime("%Y-%m-%d")
            if day_key not in daily_data:
                daily_data[day_key] = {"amount": 0, "consultations": 0}
            daily_data[day_key]["amount"] += payment.doctor_earnings
            daily_data[day_key]["consultations"] += 1
    
    daily_earnings = [
        DailyEarning(date=date, amount=data["amount"], consultations=data["consultations"])
        for date, data in sorted(daily_data.items())
    ]
    
    # Monthly earnings (last 12 months)
    monthly_data = {}
    all_payments = session.exec(
        select(Payment)
        .where(Payment.doctor_id == current_user.id)
        .where(Payment.status == "completed")
        .where(Payment.paid_at >= now - timedelta(days=365))
    ).all()
    
    for payment in all_payments:
        if payment.paid_at:
            month_key = payment.paid_at.strftime("%Y-%m")
            if month_key not in monthly_data:
                monthly_data[month_key] = {"amount": 0, "consultations": 0}
            monthly_data[month_key]["amount"] += payment.doctor_earnings
            monthly_data[month_key]["consultations"] += 1
    
    monthly_earnings = [
        MonthlyEarning(month=month, amount=data["amount"], consultations=data["consultations"])
        for month, data in sorted(monthly_data.items())
    ]
    
    # Top performing days
    day_of_week_data = {}
    for payment in all_payments:
        if payment.paid_at:
            day_name = payment.paid_at.strftime("%A")
            if day_name not in day_of_week_data:
                day_of_week_data[day_name] = 0
            day_of_week_data[day_name] += payment.doctor_earnings
    
    top_performing_days = sorted(
        [TopPerformingDay(day=day, amount=amount) for day, amount in day_of_week_data.items()],
        key=lambda x: x.amount,
        reverse=True
    )[:5]
    
    return EarningsAnalytics(
        daily_earnings=daily_earnings,
        monthly_earnings=monthly_earnings,
        top_performing_days=top_performing_days
    )


@router.get("/transactions", response_model=TransactionList)
async def get_transactions(
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get transaction history for the doctor"""
    
    # Get total count
    total_query = select(func.count(Payment.id)).where(
        Payment.doctor_id == current_user.id,
        Payment.status == "completed"
    )
    total = session.exec(total_query).first() or 0
    
    # Get paginated payments
    offset = (page - 1) * limit
    payments = session.exec(
        select(Payment)
        .where(Payment.doctor_id == current_user.id)
        .where(Payment.status == "completed")
        .order_by(Payment.paid_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    
    transactions = []
    for payment in payments:
        # Get patient name
        patient = session.get(User, payment.patient_id)
        patient_name = patient.full_name if patient else "Unknown"
        
        transactions.append(Transaction(
            id=payment.id,
            date=payment.paid_at or payment.created_at,
            type="consultation",
            amount=payment.doctor_earnings,
            patient_name=patient_name,
            appointment_id=payment.appointment_id,
            status=payment.status,
            description=f"Consultation fee: ₹{payment.consultation_fee}"
        ))
    
    pages = (total + limit - 1) // limit  # Ceiling division
    
    return TransactionList(
        transactions=transactions,
        total=total,
        page=page,
        pages=pages
    )


@router.get("/commission-tiers", response_model=List[CommissionTierInfo])
async def get_commission_tiers():
    """Get all commission tiers"""
    return [CommissionTierInfo(**tier) for tier in COMMISSION_TIERS]


@router.post("/withdraw", response_model=WithdrawalResponse)
async def request_withdrawal(
    request: WithdrawalRequest,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Request a withdrawal"""
    
    # Calculate available balance
    payments = session.exec(
        select(Payment)
        .where(Payment.doctor_id == current_user.id)
        .where(Payment.status == "completed")
    ).all()
    
    total_earnings = sum(p.doctor_earnings for p in payments)
    
    # Pending (last 7 days not withdrawable)
    now = datetime.utcnow()
    payout_cutoff = now - timedelta(days=7)
    pending_payments = [p for p in payments if p.paid_at and p.paid_at >= payout_cutoff]
    pending_amount = sum(p.doctor_earnings for p in pending_payments)
    
    available_balance = total_earnings - pending_amount
    
    if request.amount > available_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance. Available: ₹{available_balance}"
        )
    
    if request.amount < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Minimum withdrawal amount is ₹100"
        )
    
    # In production, create a withdrawal record in database
    # For now, return success response
    return WithdrawalResponse(
        withdrawal_id=1,  # Would be actual ID from database
        status="pending",
        message=f"Withdrawal request of ₹{request.amount} submitted successfully. Processing time: 2-3 business days."
    )


@router.get("/withdrawals", response_model=List[WithdrawalItem])
async def get_withdrawals(
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get withdrawal history"""
    
    # In production, fetch from withdrawals table
    # For now, return empty list or mock data
    return []


@router.get("/bank-accounts", response_model=List[BankAccount])
async def get_bank_accounts(
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get linked bank accounts"""
    
    # In production, fetch from bank_accounts table
    # For now, return empty list
    return []


@router.post("/bank-accounts", response_model=dict)
async def add_bank_account(
    account: BankAccountCreate,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Add a bank account"""
    
    # In production, save to database
    # For now, return success response
    return {
        "id": 1,
        "message": "Bank account added successfully"
    }


@router.delete("/bank-accounts/{account_id}")
async def remove_bank_account(
    account_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Remove a bank account"""
    
    # In production, delete from database
    return {"message": "Bank account removed successfully"}


@router.post("/export", response_model=ExportResponse)
async def export_earnings_report(
    format: str = "pdf",  # pdf or excel
    date_from: str = None,
    date_to: str = None,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Export earnings report"""
    
    # In production, generate and upload report
    # For now, return mock URL
    expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    
    return ExportResponse(
        download_url=f"/api/earnings/download/report_{current_user.id}.{format}",
        expires_at=expires_at
    )
