"""Billing and payment management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from database import get_session
from models import User, Billing, Appointment
from schemas import BillingCreate, BillingUpdate, BillingResponse
from dependencies import get_current_user, require_admin
from typing import List
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/billing", tags=["Billing"])


@router.post("", response_model=BillingResponse, status_code=status.HTTP_201_CREATED)
def create_billing(
    billing_data: BillingCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create billing record"""
    # If appointment_id provided, verify it exists and user has access
    if billing_data.appointment_id:
        appointment = session.get(Appointment, billing_data.appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        # Check if billing already exists for this appointment
        existing = session.exec(
            select(Billing).where(Billing.appointment_id == billing_data.appointment_id)
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Billing record already exists for this appointment"
            )
        
        # Verify user is patient or doctor of the appointment
        if appointment.patient_id != current_user.id and appointment.doctor_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to create billing for this appointment"
            )
    
    new_billing = Billing(
        **billing_data.model_dump()
    )
    
    session.add(new_billing)
    session.commit()
    session.refresh(new_billing)
    
    return new_billing


@router.get("", response_model=List[BillingResponse])
def list_billings(
    payment_status: str = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """List billing records based on user role"""
    query = select(Billing)
    
    # Filter by payment status if provided
    if payment_status:
        query = query.where(Billing.payment_status == payment_status)
    
    # Role-based filtering
    if current_user.role == "patient":
        # Get billings for patient's appointments
        query = query.join(Appointment, Billing.appointment_id == Appointment.id)
        query = query.where(Appointment.patient_id == current_user.id)
    elif current_user.role == "doctor":
        # Get billings for doctor's appointments
        query = query.join(Appointment, Billing.appointment_id == Appointment.id)
        query = query.where(Appointment.doctor_id == current_user.id)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    billings = session.exec(query.order_by(Billing.created_at.desc())).all()
    
    return billings


@router.get("/pending", response_model=List[BillingResponse])
def get_pending_billings(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get pending billings"""
    query = select(Billing).where(Billing.payment_status == "pending")
    
    # Role-based filtering
    if current_user.role == "patient":
        query = query.join(Appointment, Billing.appointment_id == Appointment.id)
        query = query.where(Appointment.patient_id == current_user.id)
    elif current_user.role == "doctor":
        query = query.join(Appointment, Billing.appointment_id == Appointment.id)
        query = query.where(Appointment.doctor_id == current_user.id)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    billings = session.exec(query.order_by(Billing.created_at.desc())).all()
    
    return billings


@router.get("/{billing_id}", response_model=BillingResponse)
def get_billing(
    billing_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get specific billing record"""
    billing = session.get(Billing, billing_id)
    
    if not billing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing record not found"
        )
    
    # Check access
    if billing.appointment_id:
        appointment = session.get(Appointment, billing.appointment_id)
        if appointment.patient_id != current_user.id and appointment.doctor_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this billing record"
            )
    
    return billing


@router.get("/appointment/{appointment_id}", response_model=BillingResponse)
def get_billing_by_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get billing for a specific appointment"""
    appointment = session.get(Appointment, appointment_id)
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Verify access
    if appointment.patient_id != current_user.id and appointment.doctor_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this appointment"
        )
    
    billing = session.exec(
        select(Billing).where(Billing.appointment_id == appointment_id)
    ).first()
    
    if not billing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No billing found for this appointment"
        )
    
    return billing


@router.put("/{billing_id}", response_model=BillingResponse)
def update_billing(
    billing_id: int,
    billing_data: BillingUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update billing record"""
    billing = session.get(Billing, billing_id)
    
    if not billing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing record not found"
        )
    
    # Check access (admin or patient can update)
    if billing.appointment_id:
        appointment = session.get(Appointment, billing.appointment_id)
        if appointment.patient_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this billing"
            )
    
    # Update fields
    for key, value in billing_data.model_dump(exclude_unset=True).items():
        setattr(billing, key, value)
    
    session.add(billing)
    session.commit()
    session.refresh(billing)
    
    return billing


@router.patch("/{billing_id}/mark-paid")
def mark_as_paid(
    billing_id: int,
    payment_method: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Mark billing as paid"""
    billing = session.get(Billing, billing_id)
    
    if not billing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing record not found"
        )
    
    billing.payment_status = "paid"
    billing.payment_method = payment_method
    
    session.add(billing)
    session.commit()
    
    return {"message": "Billing marked as paid", "billing_id": billing_id}


@router.delete("/{billing_id}")
def delete_billing(
    billing_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Delete billing record (admin only)"""
    billing = session.get(Billing, billing_id)
    
    if not billing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing record not found"
        )
    
    session.delete(billing)
    session.commit()
    
    return {"message": "Billing record deleted"}


@router.get("/stats/revenue")
def get_revenue_stats(
    days: int = 30,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get revenue statistics (admin only)"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    total_revenue = session.exec(
        select(func.sum(Billing.amount))
        .where(
            Billing.payment_status == "paid",
            Billing.created_at >= start_date
        )
    ).first() or 0
    
    pending_revenue = session.exec(
        select(func.sum(Billing.amount))
        .where(
            Billing.payment_status == "pending",
            Billing.created_at >= start_date
        )
    ).first() or 0
    
    total_transactions = session.exec(
        select(func.count(Billing.id))
        .where(Billing.created_at >= start_date)
    ).first()
    
    paid_count = session.exec(
        select(func.count(Billing.id))
        .where(
            Billing.payment_status == "paid",
            Billing.created_at >= start_date
        )
    ).first()
    
    return {
        "period_days": days,
        "total_revenue": round(total_revenue, 2),
        "pending_revenue": round(pending_revenue, 2),
        "total_transactions": total_transactions,
        "paid_transactions": paid_count,
        "pending_transactions": total_transactions - paid_count
    }
