"""Enhanced Billing, Invoicing and Payment Management"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from database import get_session
from models import (
    User, UserRole, Invoice, InvoiceItem, Payment, InsuranceClaim,
    TaxConfiguration, DiscountCode, InvoiceStatus, ServiceType,
    PaymentMethod, PaymentStatus, ClaimStatus, Appointment
)
from dependencies import get_current_user

router = APIRouter(prefix="/api/billing-enhanced", tags=["Billing & Invoicing"])


def generate_invoice_number() -> str:
    """Generate unique invoice number"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:6].upper()
    return f"INV-{timestamp}-{unique_id}"


def generate_payment_reference() -> str:
    """Generate unique payment reference"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8].upper()
    return f"PAY-{timestamp}-{unique_id}"


def generate_claim_number() -> str:
    """Generate unique claim number"""
    timestamp = datetime.now().strftime("%Y%m%d")
    unique_id = uuid.uuid4().hex[:6].upper()
    return f"CLM-{timestamp}-{unique_id}"


# ==================== INVOICE ENDPOINTS ====================

@router.get("/invoices", response_model=List[dict])
def get_invoices(
    patient_id: Optional[int] = None,
    status: Optional[InvoiceStatus] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get list of invoices with filters"""
    query = select(Invoice)
    
    # Role-based filtering
    if current_user.role == UserRole.PATIENT:
        query = query.where(Invoice.patient_id == current_user.id)
    elif patient_id:
        query = query.where(Invoice.patient_id == patient_id)
    
    if status:
        query = query.where(Invoice.status == status)
    if from_date:
        query = query.where(Invoice.generated_at >= from_date)
    if to_date:
        query = query.where(Invoice.generated_at <= to_date)
    
    query = query.order_by(Invoice.generated_at.desc()).offset(skip).limit(limit)
    invoices = session.exec(query).all()
    
    result = []
    for inv in invoices:
        patient = session.get(User, inv.patient_id)
        items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == inv.id)).all()
        result.append({
            **inv.model_dump(),
            "patient_name": patient.full_name if patient else None,
            "items_count": len(items),
        })
    
    return result


@router.get("/invoices/{invoice_id}")
def get_invoice(
    invoice_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get invoice details with items"""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check access
    if current_user.role == UserRole.PATIENT and invoice.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    patient = session.get(User, invoice.patient_id)
    items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)).all()
    payments = session.exec(select(Payment).where(Payment.invoice_id == invoice_id)).all()
    
    return {
        **invoice.model_dump(),
        "patient_name": patient.full_name if patient else None,
        "patient_phone": patient.phone_number if patient else None,
        "items": [item.model_dump() for item in items],
        "payments": [p.model_dump() for p in payments],
    }


@router.post("/invoices")
def create_invoice(
    patient_id: int,
    due_days: int = 30,
    appointment_id: Optional[int] = None,
    admission_id: Optional[int] = None,
    notes: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new invoice"""
    if current_user.role not in [UserRole.ADMIN, UserRole.DOCTOR, UserRole.PHARMACIST]:
        raise HTTPException(status_code=403, detail="Not authorized to create invoices")
    
    patient = session.get(User, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    invoice = Invoice(
        invoice_number=generate_invoice_number(),
        patient_id=patient_id,
        appointment_id=appointment_id,
        admission_id=admission_id,
        due_date=datetime.utcnow() + timedelta(days=due_days),
        notes=notes,
        generated_by=current_user.id,
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    
    return {"message": "Invoice created", "invoice": invoice.model_dump()}


@router.post("/invoices/{invoice_id}/items")
def add_invoice_item(
    invoice_id: int,
    service_type: ServiceType,
    description: str,
    quantity: int = 1,
    unit_price: float = 0.0,
    discount_percent: float = 0.0,
    tax_percent: float = 0.0,
    prescription_id: Optional[int] = None,
    pharmacy_item_id: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Add item to invoice"""
    if current_user.role not in [UserRole.ADMIN, UserRole.DOCTOR, UserRole.PHARMACIST]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if invoice.status not in [InvoiceStatus.DRAFT, InvoiceStatus.PENDING]:
        raise HTTPException(status_code=400, detail="Cannot modify this invoice")
    
    # Calculate totals
    subtotal = quantity * unit_price
    discount = subtotal * (discount_percent / 100)
    taxable = subtotal - discount
    tax = taxable * (tax_percent / 100)
    total = taxable + tax
    
    item = InvoiceItem(
        invoice_id=invoice_id,
        service_type=service_type,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        discount_percent=discount_percent,
        tax_percent=tax_percent,
        total_price=total,
        prescription_id=prescription_id,
        pharmacy_item_id=pharmacy_item_id,
    )
    session.add(item)
    
    # Update invoice totals
    items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)).all()
    items_list = list(items) + [item]
    
    invoice.subtotal = sum(i.quantity * i.unit_price for i in items_list)
    invoice.discount_amount = sum(i.quantity * i.unit_price * (i.discount_percent / 100) for i in items_list)
    invoice.tax_amount = sum((i.quantity * i.unit_price - i.quantity * i.unit_price * (i.discount_percent / 100)) * (i.tax_percent / 100) for i in items_list)
    invoice.total_amount = sum(i.total_price for i in items_list)
    invoice.balance_due = invoice.total_amount - invoice.paid_amount
    invoice.updated_at = datetime.utcnow()
    
    session.add(invoice)
    session.commit()
    session.refresh(item)
    
    return {"message": "Item added", "item": item.model_dump()}


@router.put("/invoices/{invoice_id}/status")
def update_invoice_status(
    invoice_id: int,
    status: InvoiceStatus,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update invoice status"""
    if current_user.role not in [UserRole.ADMIN, UserRole.DOCTOR, UserRole.PHARMACIST]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice.status = status
    invoice.updated_at = datetime.utcnow()
    
    if status == InvoiceStatus.PAID:
        invoice.paid_at = datetime.utcnow()
    
    session.add(invoice)
    session.commit()
    
    return {"message": "Invoice status updated"}


@router.delete("/invoices/{invoice_id}")
def cancel_invoice(
    invoice_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Cancel an invoice"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can cancel invoices")
    
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Cannot cancel paid invoice")
    
    invoice.status = InvoiceStatus.CANCELLED
    invoice.updated_at = datetime.utcnow()
    session.add(invoice)
    session.commit()
    
    return {"message": "Invoice cancelled"}


# ==================== PAYMENT ENDPOINTS ====================

@router.get("/payments", response_model=List[dict])
def get_payments(
    invoice_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    status: Optional[PaymentStatus] = None,
    payment_method: Optional[PaymentMethod] = None,
    skip: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get list of payments"""
    query = select(Payment)
    
    if current_user.role == UserRole.PATIENT:
        query = query.where(Payment.patient_id == current_user.id)
    elif patient_id:
        query = query.where(Payment.patient_id == patient_id)
    
    if invoice_id:
        query = query.where(Payment.invoice_id == invoice_id)
    if status:
        query = query.where(Payment.status == status)
    if payment_method:
        query = query.where(Payment.payment_method == payment_method)
    
    query = query.order_by(Payment.initiated_at.desc()).offset(skip).limit(limit)
    payments = session.exec(query).all()
    
    result = []
    for pay in payments:
        patient = session.get(User, pay.patient_id)
        invoice = session.get(Invoice, pay.invoice_id)
        result.append({
            **pay.model_dump(),
            "patient_name": patient.full_name if patient else None,
            "invoice_number": invoice.invoice_number if invoice else None,
        })
    
    return result


@router.post("/payments/initiate")
def initiate_payment(
    invoice_id: int,
    amount: float,
    payment_method: PaymentMethod,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Initiate a payment for an invoice"""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check access
    if current_user.role == UserRole.PATIENT and invoice.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Invoice already paid")
    
    if amount > invoice.balance_due:
        raise HTTPException(status_code=400, detail="Amount exceeds balance due")
    
    payment = Payment(
        payment_reference=generate_payment_reference(),
        invoice_id=invoice_id,
        patient_id=invoice.patient_id,
        amount=amount,
        payment_method=payment_method,
        status=PaymentStatus.PENDING,
    )
    session.add(payment)
    session.commit()
    session.refresh(payment)
    
    # Return payment details (in real app, this would include gateway checkout URL)
    return {
        "message": "Payment initiated",
        "payment": payment.model_dump(),
        "checkout_url": f"/checkout/{payment.payment_reference}",  # Placeholder
    }


@router.post("/payments/complete/{payment_id}")
def complete_payment(
    payment_id: int,
    gateway_transaction_id: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Complete a payment (called after gateway confirmation)"""
    payment = session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="Payment not in pending state")
    
    # Update payment
    payment.status = PaymentStatus.COMPLETED
    payment.completed_at = datetime.utcnow()
    payment.gateway_transaction_id = gateway_transaction_id
    payment.updated_at = datetime.utcnow()
    session.add(payment)
    
    # Update invoice
    invoice = session.get(Invoice, payment.invoice_id)
    if invoice:
        invoice.paid_amount += payment.amount
        invoice.balance_due = invoice.total_amount - invoice.paid_amount
        
        if invoice.balance_due <= 0:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.utcnow()
        elif invoice.paid_amount > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        
        invoice.updated_at = datetime.utcnow()
        session.add(invoice)
    
    session.commit()
    
    return {"message": "Payment completed successfully"}


@router.post("/payments/webhook")
def payment_webhook(
    gateway_order_id: str,
    gateway_payment_id: str,
    gateway_signature: str,
    status: str,
    session: Session = Depends(get_session)
):
    """Handle payment gateway webhook"""
    # Find payment by gateway order ID
    payment = session.exec(
        select(Payment).where(Payment.gateway_order_id == gateway_order_id)
    ).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # In real app, verify signature here
    
    if status == "success":
        payment.status = PaymentStatus.COMPLETED
        payment.completed_at = datetime.utcnow()
        payment.gateway_transaction_id = gateway_payment_id
        
        # Update invoice
        invoice = session.get(Invoice, payment.invoice_id)
        if invoice:
            invoice.paid_amount += payment.amount
            invoice.balance_due = invoice.total_amount - invoice.paid_amount
            if invoice.balance_due <= 0:
                invoice.status = InvoiceStatus.PAID
                invoice.paid_at = datetime.utcnow()
            elif invoice.paid_amount > 0:
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            session.add(invoice)
    else:
        payment.status = PaymentStatus.FAILED
    
    payment.updated_at = datetime.utcnow()
    session.add(payment)
    session.commit()
    
    return {"message": "Webhook processed"}


@router.post("/payments/{payment_id}/refund")
def refund_payment(
    payment_id: int,
    refund_amount: float,
    reason: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Process payment refund"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can process refunds")
    
    payment = session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.status != PaymentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Can only refund completed payments")
    
    if refund_amount > payment.amount:
        raise HTTPException(status_code=400, detail="Refund amount exceeds payment amount")
    
    payment.status = PaymentStatus.REFUNDED
    payment.refund_amount = refund_amount
    payment.refund_reason = reason
    payment.refunded_at = datetime.utcnow()
    payment.updated_at = datetime.utcnow()
    session.add(payment)
    
    # Update invoice
    invoice = session.get(Invoice, payment.invoice_id)
    if invoice:
        invoice.paid_amount -= refund_amount
        invoice.balance_due = invoice.total_amount - invoice.paid_amount
        invoice.status = InvoiceStatus.REFUNDED if invoice.paid_amount <= 0 else InvoiceStatus.PARTIALLY_PAID
        invoice.updated_at = datetime.utcnow()
        session.add(invoice)
    
    session.commit()
    
    return {"message": "Refund processed successfully"}


# ==================== INSURANCE CLAIM ENDPOINTS ====================

@router.get("/insurance/claims", response_model=List[dict])
def get_claims(
    patient_id: Optional[int] = None,
    status: Optional[ClaimStatus] = None,
    skip: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get list of insurance claims"""
    query = select(InsuranceClaim)
    
    if current_user.role == UserRole.PATIENT:
        query = query.where(InsuranceClaim.patient_id == current_user.id)
    elif patient_id:
        query = query.where(InsuranceClaim.patient_id == patient_id)
    
    if status:
        query = query.where(InsuranceClaim.status == status)
    
    query = query.order_by(InsuranceClaim.created_at.desc()).offset(skip).limit(limit)
    claims = session.exec(query).all()
    
    result = []
    for claim in claims:
        patient = session.get(User, claim.patient_id)
        invoice = session.get(Invoice, claim.invoice_id)
        result.append({
            **claim.model_dump(),
            "patient_name": patient.full_name if patient else None,
            "invoice_number": invoice.invoice_number if invoice else None,
        })
    
    return result


@router.get("/insurance/claims/{claim_id}")
def get_claim(
    claim_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get claim details"""
    claim = session.get(InsuranceClaim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    if current_user.role == UserRole.PATIENT and claim.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    patient = session.get(User, claim.patient_id)
    invoice = session.get(Invoice, claim.invoice_id)
    
    return {
        **claim.model_dump(),
        "patient_name": patient.full_name if patient else None,
        "invoice_number": invoice.invoice_number if invoice else None,
        "invoice_amount": invoice.total_amount if invoice else None,
    }


@router.post("/insurance/claims")
def submit_claim(
    invoice_id: int,
    insurance_provider: str,
    policy_number: str,
    policy_holder_name: str,
    policy_holder_relation: str = "self",
    claim_amount: Optional[float] = None,
    diagnosis_codes: Optional[str] = None,
    procedure_codes: Optional[str] = None,
    notes: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Submit insurance claim"""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if current_user.role == UserRole.PATIENT and invoice.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Use invoice total if claim amount not specified
    if claim_amount is None:
        claim_amount = invoice.total_amount
    
    claim = InsuranceClaim(
        claim_number=generate_claim_number(),
        patient_id=invoice.patient_id,
        invoice_id=invoice_id,
        insurance_provider=insurance_provider,
        policy_number=policy_number,
        policy_holder_name=policy_holder_name,
        policy_holder_relation=policy_holder_relation,
        claim_amount=claim_amount,
        diagnosis_codes=diagnosis_codes,
        procedure_codes=procedure_codes,
        notes=notes,
        status=ClaimStatus.SUBMITTED,
        submitted_at=datetime.utcnow(),
    )
    session.add(claim)
    session.commit()
    session.refresh(claim)
    
    return {"message": "Claim submitted", "claim": claim.model_dump()}


@router.put("/insurance/claims/{claim_id}/status")
def update_claim_status(
    claim_id: int,
    status: ClaimStatus,
    approved_amount: Optional[float] = None,
    copay_amount: Optional[float] = None,
    deductible_amount: Optional[float] = None,
    rejection_reason: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update claim status (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can update claim status")
    
    claim = session.get(InsuranceClaim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    claim.status = status
    claim.processed_at = datetime.utcnow()
    claim.updated_at = datetime.utcnow()
    
    if status in [ClaimStatus.APPROVED, ClaimStatus.PARTIALLY_APPROVED]:
        claim.approved_amount = approved_amount
        claim.copay_amount = copay_amount
        claim.deductible_amount = deductible_amount
    elif status == ClaimStatus.REJECTED:
        claim.rejection_reason = rejection_reason
    
    session.add(claim)
    session.commit()
    
    return {"message": "Claim status updated"}


# ==================== TAX & DISCOUNT ENDPOINTS ====================

@router.get("/tax-configs")
def get_tax_configurations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get active tax configurations"""
    configs = session.exec(
        select(TaxConfiguration).where(TaxConfiguration.is_active == True)
    ).all()
    return [c.model_dump() for c in configs]


@router.post("/tax-configs")
def create_tax_config(
    name: str,
    service_type: ServiceType,
    tax_percent: float,
    effective_from: datetime,
    effective_to: Optional[datetime] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create tax configuration (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can manage tax configs")
    
    config = TaxConfiguration(
        name=name,
        service_type=service_type,
        tax_percent=tax_percent,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    session.add(config)
    session.commit()
    session.refresh(config)
    
    return {"message": "Tax configuration created", "config": config.model_dump()}


@router.get("/discount-codes")
def get_discount_codes(
    active_only: bool = True,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get discount codes"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can view all discount codes")
    
    query = select(DiscountCode)
    if active_only:
        query = query.where(DiscountCode.is_active == True)
    
    codes = session.exec(query).all()
    return [c.model_dump() for c in codes]


@router.post("/discount-codes")
def create_discount_code(
    code: str,
    discount_type: str,
    discount_value: float,
    valid_from: datetime,
    valid_until: datetime,
    description: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_discount: Optional[float] = None,
    usage_limit: Optional[int] = None,
    applicable_services: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create discount code (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can create discount codes")
    
    # Check if code exists
    existing = session.exec(select(DiscountCode).where(DiscountCode.code == code)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Discount code already exists")
    
    discount = DiscountCode(
        code=code.upper(),
        description=description,
        discount_type=discount_type,
        discount_value=discount_value,
        min_amount=min_amount,
        max_discount=max_discount,
        usage_limit=usage_limit,
        valid_from=valid_from,
        valid_until=valid_until,
        applicable_services=applicable_services,
        created_by=current_user.id,
    )
    session.add(discount)
    session.commit()
    session.refresh(discount)
    
    return {"message": "Discount code created", "discount": discount.model_dump()}


@router.post("/discount-codes/validate")
def validate_discount_code(
    code: str,
    amount: float,
    service_type: Optional[ServiceType] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Validate and calculate discount"""
    discount = session.exec(
        select(DiscountCode).where(DiscountCode.code == code.upper())
    ).first()
    
    if not discount:
        raise HTTPException(status_code=404, detail="Invalid discount code")
    
    now = datetime.utcnow()
    if not discount.is_active:
        raise HTTPException(status_code=400, detail="Discount code is inactive")
    if now < discount.valid_from or now > discount.valid_until:
        raise HTTPException(status_code=400, detail="Discount code expired")
    if discount.usage_limit and discount.used_count >= discount.usage_limit:
        raise HTTPException(status_code=400, detail="Discount code usage limit reached")
    if discount.min_amount and amount < discount.min_amount:
        raise HTTPException(status_code=400, detail=f"Minimum amount of ₹{discount.min_amount} required")
    
    # Calculate discount
    if discount.discount_type == "percent":
        calculated_discount = amount * (discount.discount_value / 100)
    else:
        calculated_discount = discount.discount_value
    
    if discount.max_discount and calculated_discount > discount.max_discount:
        calculated_discount = discount.max_discount
    
    return {
        "valid": True,
        "code": discount.code,
        "discount_type": discount.discount_type,
        "discount_value": discount.discount_value,
        "calculated_discount": calculated_discount,
        "final_amount": amount - calculated_discount,
    }


# ==================== DASHBOARD ENDPOINT ====================

@router.get("/dashboard")
def get_billing_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get billing dashboard stats"""
    if current_user.role not in [UserRole.ADMIN, UserRole.DOCTOR, UserRole.PHARMACIST]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Total invoices
    total_invoices = len(session.exec(select(Invoice)).all())
    
    # Pending payments
    pending_invoices = session.exec(
        select(Invoice).where(Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID]))
    ).all()
    pending_amount = sum(i.balance_due for i in pending_invoices)
    
    # Today's collections
    today = datetime.utcnow().date()
    today_payments = session.exec(
        select(Payment).where(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.completed_at >= datetime(today.year, today.month, today.day)
        )
    ).all()
    today_collection = sum(p.amount for p in today_payments)
    
    # This month's collections
    month_start = datetime(today.year, today.month, 1)
    month_payments = session.exec(
        select(Payment).where(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.completed_at >= month_start
        )
    ).all()
    month_collection = sum(p.amount for p in month_payments)
    
    # Overdue invoices
    overdue_invoices = session.exec(
        select(Invoice).where(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID]),
            Invoice.due_date < datetime.utcnow()
        )
    ).all()
    overdue_amount = sum(i.balance_due for i in overdue_invoices)
    
    # Pending claims
    pending_claims = len(session.exec(
        select(InsuranceClaim).where(
            InsuranceClaim.status.in_([ClaimStatus.SUBMITTED, ClaimStatus.PROCESSING])
        )
    ).all())
    
    return {
        "total_invoices": total_invoices,
        "pending_invoices": len(pending_invoices),
        "pending_amount": pending_amount,
        "today_collection": today_collection,
        "month_collection": month_collection,
        "overdue_invoices": len(overdue_invoices),
        "overdue_amount": overdue_amount,
        "pending_claims": pending_claims,
    }
