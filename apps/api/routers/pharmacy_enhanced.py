"""Enhanced Pharmacy Management - Orders, Suppliers, Medicines"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import uuid
import logging

from database import get_session
from models import (
    User, UserRole, PharmacyInventory, Supplier, Medicine, MedicineCategory,
    PharmacyOrder, PharmacyOrderItem, OrderStatus, PaymentStatus
)
from dependencies import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pharmacy-enhanced", tags=["Pharmacy Enhanced"])


# ==================== SCHEMAS ====================

class SupplierCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    gst_number: Optional[str] = None
    payment_terms: Optional[str] = None

class SupplierResponse(BaseModel):
    id: int
    name: str
    contact_person: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    gst_number: Optional[str]
    payment_terms: Optional[str]
    is_active: bool

class MedicineCreate(BaseModel):
    name: str
    generic_name: Optional[str] = None
    category: MedicineCategory = MedicineCategory.TABLETS
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    composition: Optional[str] = None
    side_effects: Optional[str] = None
    dosage_instructions: Optional[str] = None
    requires_prescription: bool = False
    unit: str = "piece"

class MedicineResponse(BaseModel):
    id: int
    name: str
    generic_name: Optional[str]
    category: MedicineCategory
    manufacturer: Optional[str]
    description: Optional[str]
    requires_prescription: bool
    unit: str
    is_active: bool

class OrderItemCreate(BaseModel):
    inventory_id: int
    quantity: int

class OrderCreate(BaseModel):
    prescription_id: Optional[int] = None
    items: List[OrderItemCreate]
    delivery_address: str
    delivery_phone: str
    payment_method: str = "cash"
    notes: Optional[str] = None

class OrderResponse(BaseModel):
    id: int
    order_number: str
    patient_id: int
    status: OrderStatus
    payment_status: PaymentStatus
    subtotal: float
    tax: float
    discount: float
    delivery_charge: float
    total_amount: float
    delivery_address: str
    ordered_at: datetime
    patient_name: Optional[str] = None
    items: List[dict] = []

class PharmacyDashboard(BaseModel):
    total_medicines: int
    total_inventory_items: int
    low_stock_items: int
    expiring_soon: int
    total_orders: int
    pending_orders: int
    total_suppliers: int
    inventory_value: float


# ==================== SUPPLIER ENDPOINTS ====================

@router.post("/suppliers", response_model=SupplierResponse)
def create_supplier(
    supplier_data: SupplierCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Create a new supplier"""
    supplier = Supplier(**supplier_data.dict())
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return supplier

@router.get("/suppliers", response_model=List[SupplierResponse])
def get_suppliers(
    is_active: bool = True,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Get all suppliers"""
    suppliers = session.exec(
        select(Supplier)
        .where(Supplier.is_active == is_active)
        .order_by(Supplier.name)
    ).all()
    return suppliers

@router.put("/suppliers/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    supplier_data: SupplierCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Update supplier"""
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    for key, value in supplier_data.dict(exclude_unset=True).items():
        setattr(supplier, key, value)
    
    session.commit()
    session.refresh(supplier)
    return supplier


# ==================== MEDICINE CATALOG ENDPOINTS ====================

@router.post("/medicines", response_model=MedicineResponse)
def create_medicine(
    medicine_data: MedicineCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Add medicine to catalog"""
    medicine = Medicine(**medicine_data.dict())
    session.add(medicine)
    session.commit()
    session.refresh(medicine)
    return medicine

@router.get("/medicines", response_model=List[MedicineResponse])
def get_medicines(
    search: Optional[str] = None,
    category: Optional[MedicineCategory] = None,
    requires_prescription: Optional[bool] = None,
    session: Session = Depends(get_session)
):
    """Get medicine catalog (public)"""
    query = select(Medicine).where(Medicine.is_active == True)
    
    if search:
        query = query.where(
            (Medicine.name.ilike(f"%{search}%")) |
            (Medicine.generic_name.ilike(f"%{search}%"))
        )
    
    if category:
        query = query.where(Medicine.category == category)
    
    if requires_prescription is not None:
        query = query.where(Medicine.requires_prescription == requires_prescription)
    
    medicines = session.exec(query.order_by(Medicine.name)).all()
    return medicines

@router.get("/medicines/{medicine_id}", response_model=MedicineResponse)
def get_medicine(
    medicine_id: int,
    session: Session = Depends(get_session)
):
    """Get medicine details (public)"""
    medicine = session.get(Medicine, medicine_id)
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return medicine


# ==================== ORDER ENDPOINTS ====================

@router.post("/orders", response_model=OrderResponse)
def create_order(
    order_data: OrderCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new pharmacy order"""
    # Generate order number
    order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    # Calculate totals
    subtotal = 0
    order_items = []
    
    for item in order_data.items:
        inventory = session.get(PharmacyInventory, item.inventory_id)
        if not inventory:
            raise HTTPException(status_code=404, detail=f"Inventory item {item.inventory_id} not found")
        
        if inventory.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient stock for {inventory.medicine_name}. Available: {inventory.stock_quantity}"
            )
        
        item_total = inventory.selling_price * item.quantity
        subtotal += item_total
        
        order_items.append({
            "inventory_id": item.inventory_id,
            "medicine_name": inventory.medicine_name,
            "quantity": item.quantity,
            "unit_price": inventory.selling_price,
            "total_price": item_total,
            "batch_number": inventory.batch_number
        })
    
    # Calculate tax and total
    tax = round(subtotal * 0.05, 2)  # 5% GST
    delivery_charge = 0 if subtotal >= 500 else 50  # Free delivery above ₹500
    total_amount = subtotal + tax + delivery_charge
    
    # Create order
    order = PharmacyOrder(
        order_number=order_number,
        patient_id=current_user.id,
        prescription_id=order_data.prescription_id,
        subtotal=subtotal,
        tax=tax,
        delivery_charge=delivery_charge,
        total_amount=total_amount,
        delivery_address=order_data.delivery_address,
        delivery_phone=order_data.delivery_phone,
        payment_method=order_data.payment_method,
        notes=order_data.notes
    )
    
    session.add(order)
    session.commit()
    session.refresh(order)
    
    # Create order items and update stock
    for item_data in order_items:
        order_item = PharmacyOrderItem(
            order_id=order.id,
            **item_data
        )
        session.add(order_item)
        
        # Reduce stock
        inventory = session.get(PharmacyInventory, item_data["inventory_id"])
        inventory.stock_quantity -= item_data["quantity"]
    
    session.commit()
    
    return OrderResponse(
        **order.dict(),
        patient_name=current_user.full_name,
        items=order_items
    )

@router.get("/orders", response_model=List[OrderResponse])
def get_orders(
    status: Optional[OrderStatus] = None,
    patient_id: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get orders (patients see own, pharmacist/admin see all)"""
    query = select(PharmacyOrder)
    
    # Role-based filtering
    if current_user.role == UserRole.PATIENT:
        query = query.where(PharmacyOrder.patient_id == current_user.id)
    elif patient_id:
        query = query.where(PharmacyOrder.patient_id == patient_id)
    
    if status:
        query = query.where(PharmacyOrder.status == status)
    
    query = query.order_by(PharmacyOrder.ordered_at.desc())
    
    orders = session.exec(query).all()
    result = []
    
    for order in orders:
        patient = session.get(User, order.patient_id)
        items = session.exec(
            select(PharmacyOrderItem).where(PharmacyOrderItem.order_id == order.id)
        ).all()
        
        result.append(OrderResponse(
            **order.dict(),
            patient_name=patient.full_name if patient else None,
            items=[item.dict() for item in items]
        ))
    
    return result

@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get order details"""
    order = session.get(PharmacyOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check access
    if current_user.role == UserRole.PATIENT and order.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    patient = session.get(User, order.patient_id)
    items = session.exec(
        select(PharmacyOrderItem).where(PharmacyOrderItem.order_id == order.id)
    ).all()
    
    return OrderResponse(
        **order.dict(),
        patient_name=patient.full_name if patient else None,
        items=[item.dict() for item in items]
    )

@router.put("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    new_status: OrderStatus,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Update order status"""
    order = session.get(PharmacyOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.status = new_status
    
    # Set timestamps
    if new_status == OrderStatus.CONFIRMED:
        order.confirmed_at = datetime.utcnow()
    elif new_status == OrderStatus.SHIPPED:
        order.shipped_at = datetime.utcnow()
    elif new_status == OrderStatus.DELIVERED:
        order.delivered_at = datetime.utcnow()
        order.payment_status = PaymentStatus.PAID
    elif new_status == OrderStatus.CANCELLED:
        order.cancelled_at = datetime.utcnow()
        # Restore stock
        items = session.exec(
            select(PharmacyOrderItem).where(PharmacyOrderItem.order_id == order.id)
        ).all()
        for item in items:
            inventory = session.get(PharmacyInventory, item.inventory_id)
            if inventory:
                inventory.stock_quantity += item.quantity
    
    session.commit()
    
    return {"message": f"Order status updated to {new_status}"}

@router.post("/orders/{order_id}/cancel")
def cancel_order(
    order_id: int,
    reason: str = "Customer requested cancellation",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Cancel an order"""
    order = session.get(PharmacyOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check access
    if current_user.role == UserRole.PATIENT and order.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Can only cancel pending or confirmed orders
    if order.status not in [OrderStatus.PENDING, OrderStatus.CONFIRMED]:
        raise HTTPException(status_code=400, detail="Cannot cancel order in current status")
    
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.utcnow()
    order.cancellation_reason = reason
    
    # Restore stock
    items = session.exec(
        select(PharmacyOrderItem).where(PharmacyOrderItem.order_id == order.id)
    ).all()
    for item in items:
        inventory = session.get(PharmacyInventory, item.inventory_id)
        if inventory:
            inventory.stock_quantity += item.quantity
    
    session.commit()
    
    return {"message": "Order cancelled successfully"}


# ==================== DASHBOARD ENDPOINT ====================

@router.get("/dashboard", response_model=PharmacyDashboard)
def get_pharmacy_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Get pharmacy dashboard statistics"""
    # Counts
    total_medicines = session.exec(select(func.count(Medicine.id))).first() or 0
    total_inventory = session.exec(select(func.count(PharmacyInventory.id))).first() or 0
    total_suppliers = session.exec(select(func.count(Supplier.id)).where(Supplier.is_active == True)).first() or 0
    total_orders = session.exec(select(func.count(PharmacyOrder.id))).first() or 0
    pending_orders = session.exec(
        select(func.count(PharmacyOrder.id))
        .where(PharmacyOrder.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED]))
    ).first() or 0
    
    # Low stock (below reorder level)
    low_stock = session.exec(
        select(func.count(PharmacyInventory.id))
        .where(PharmacyInventory.stock_quantity < PharmacyInventory.reorder_level)
    ).first() or 0
    
    # Expiring soon (30 days)
    thirty_days = datetime.utcnow() + timedelta(days=30)
    expiring_soon = session.exec(
        select(func.count(PharmacyInventory.id))
        .where(PharmacyInventory.expiry_date <= thirty_days)
    ).first() or 0
    
    # Inventory value
    inventory_value = session.exec(
        select(func.sum(PharmacyInventory.stock_quantity * PharmacyInventory.selling_price))
    ).first() or 0
    
    return PharmacyDashboard(
        total_medicines=total_medicines,
        total_inventory_items=total_inventory,
        low_stock_items=low_stock,
        expiring_soon=expiring_soon,
        total_orders=total_orders,
        pending_orders=pending_orders,
        total_suppliers=total_suppliers,
        inventory_value=round(inventory_value, 2)
    )


# ==================== SUPPLIER GET BY ID ====================

@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Get a specific supplier by ID"""
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    return supplier


# ==================== INVENTORY MANAGEMENT ====================

class InventoryCreate(BaseModel):
    medicine_id: int
    supplier_id: Optional[int] = None
    batch_number: str
    quantity: int
    unit_price: float
    selling_price: float
    expiry_date: str
    reorder_level: int = 10


class InventoryUpdate(BaseModel):
    quantity: Optional[int] = None
    unit_price: Optional[float] = None
    selling_price: Optional[float] = None
    reorder_level: Optional[int] = None
    is_active: Optional[bool] = None


class InventoryResponse(BaseModel):
    id: int
    medicine_id: int
    medicine_name: Optional[str] = None
    supplier_id: Optional[int]
    supplier_name: Optional[str] = None
    batch_number: str
    stock_quantity: int
    unit_price: float
    selling_price: float
    expiry_date: datetime
    reorder_level: int
    is_active: bool
    created_at: datetime


class StoreInventoryItem(BaseModel):
    """Public store inventory item - limited info for customers"""
    id: int
    medicine_id: int
    medicine_name: str
    generic_name: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    requires_prescription: bool = False
    selling_price: float
    stock_quantity: int
    unit: str = "piece"


@router.get("/store/products", response_model=List[StoreInventoryItem])
def get_store_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    in_stock_only: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    session: Session = Depends(get_session)
):
    """Get products available in the store (public endpoint for customers)"""
    try:
        from sqlalchemy import text
        
        # First, check which columns exist in the pharmacyinventory table
        # Use a simple query to get column names
        schema_check = session.exec(text("PRAGMA table_info(pharmacyinventory)")).all()
        existing_columns = {row[1] for row in schema_check}  # row[1] is column name
        
        # Build query based on available columns
        price_col = "price"  # Default column that should always exist
        if "selling_price" in existing_columns:
            price_col = "COALESCE(selling_price, price, 0)"
        elif "price" in existing_columns:
            price_col = "COALESCE(price, 0)"
        else:
            price_col = "0"
        
        # Use basic columns that should exist in any version
        # SECURITY FIX: Use parameterized queries to prevent SQL injection
        sql = f"""
            SELECT id, medicine_name, batch_number, stock_quantity, 
                   {price_col} as price_value, 
                   expiry_date, is_active
            FROM pharmacyinventory
            WHERE is_active = 1
        """
        
        if in_stock_only:
            sql += " AND stock_quantity > 0"
        
        sql += " AND expiry_date > :now"
        sql += " LIMIT :limit OFFSET :skip"
        
        result_rows = session.exec(text(sql).bindparams(now=datetime.utcnow(), limit=limit, skip=skip)).all()
        
        result = []
        for row in result_rows:
            medicine_name = row[1] if row[1] else "Unknown Medicine"
            
            # Apply search filter
            if search and search.lower() not in medicine_name.lower():
                continue
            
            result.append(StoreInventoryItem(
                id=row[0],
                medicine_id=None,
                medicine_name=medicine_name,
                generic_name=None,
                category=None,
                manufacturer=None,
                description=None,
                requires_prescription=False,
                selling_price=float(row[4]) if row[4] else 0.0,
                stock_quantity=int(row[3]) if row[3] else 0,
                unit="piece"
            ))
        
        return result
    except Exception as e:
        # If there's a database schema issue, return empty list
        # This prevents 500 errors and allows the frontend to show mock data
        logger.error(f"Error fetching store products: {e}")
        return []


@router.get("/inventory", response_model=List[InventoryResponse])
def get_inventory(
    medicine_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    low_stock_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Get inventory items with optional filters"""
    query = select(PharmacyInventory).where(PharmacyInventory.is_active == True)
    
    if medicine_id:
        query = query.where(PharmacyInventory.medicine_id == medicine_id)
    if supplier_id:
        query = query.where(PharmacyInventory.supplier_id == supplier_id)
    if low_stock_only:
        query = query.where(PharmacyInventory.stock_quantity < PharmacyInventory.reorder_level)
    
    query = query.offset(skip).limit(limit)
    items = session.exec(query).all()
    
    result = []
    for item in items:
        medicine = session.get(Medicine, item.medicine_id)
        supplier = session.get(Supplier, item.supplier_id) if item.supplier_id else None
        result.append(InventoryResponse(
            id=item.id,
            medicine_id=item.medicine_id,
            medicine_name=medicine.name if medicine else None,
            supplier_id=item.supplier_id,
            supplier_name=supplier.name if supplier else None,
            batch_number=item.batch_number,
            stock_quantity=item.stock_quantity,
            unit_price=item.unit_price,
            selling_price=item.selling_price,
            expiry_date=item.expiry_date,
            reorder_level=item.reorder_level,
            is_active=item.is_active,
            created_at=item.created_at
        ))
    return result


@router.post("/inventory", response_model=InventoryResponse)
def create_inventory(
    data: InventoryCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Create a new inventory item"""
    # Verify medicine exists
    medicine = session.get(Medicine, data.medicine_id)
    if not medicine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicine not found"
        )
    
    # Verify supplier if provided
    supplier = None
    if data.supplier_id:
        supplier = session.get(Supplier, data.supplier_id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found"
            )
    
    try:
        expiry = datetime.strptime(data.expiry_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid expiry date format. Use YYYY-MM-DD"
        )
    
    inventory = PharmacyInventory(
        medicine_id=data.medicine_id,
        supplier_id=data.supplier_id,
        batch_number=data.batch_number,
        stock_quantity=data.quantity,
        unit_price=data.unit_price,
        selling_price=data.selling_price,
        expiry_date=expiry,
        reorder_level=data.reorder_level
    )
    
    session.add(inventory)
    session.commit()
    session.refresh(inventory)
    
    return InventoryResponse(
        id=inventory.id,
        medicine_id=inventory.medicine_id,
        medicine_name=medicine.name,
        supplier_id=inventory.supplier_id,
        supplier_name=supplier.name if supplier else None,
        batch_number=inventory.batch_number,
        stock_quantity=inventory.stock_quantity,
        unit_price=inventory.unit_price,
        selling_price=inventory.selling_price,
        expiry_date=inventory.expiry_date,
        reorder_level=inventory.reorder_level,
        is_active=inventory.is_active,
        created_at=inventory.created_at
    )


@router.put("/inventory/{inventory_id}", response_model=InventoryResponse)
def update_inventory(
    inventory_id: int,
    data: InventoryUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Update inventory item"""
    inventory = session.get(PharmacyInventory, inventory_id)
    if not inventory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found"
        )
    
    if data.quantity is not None:
        inventory.stock_quantity = data.quantity
    if data.unit_price is not None:
        inventory.unit_price = data.unit_price
    if data.selling_price is not None:
        inventory.selling_price = data.selling_price
    if data.reorder_level is not None:
        inventory.reorder_level = data.reorder_level
    if data.is_active is not None:
        inventory.is_active = data.is_active
    
    session.add(inventory)
    session.commit()
    session.refresh(inventory)
    
    medicine = session.get(Medicine, inventory.medicine_id)
    supplier = session.get(Supplier, inventory.supplier_id) if inventory.supplier_id else None
    
    return InventoryResponse(
        id=inventory.id,
        medicine_id=inventory.medicine_id,
        medicine_name=medicine.name if medicine else None,
        supplier_id=inventory.supplier_id,
        supplier_name=supplier.name if supplier else None,
        batch_number=inventory.batch_number,
        stock_quantity=inventory.stock_quantity,
        unit_price=inventory.unit_price,
        selling_price=inventory.selling_price,
        expiry_date=inventory.expiry_date,
        reorder_level=inventory.reorder_level,
        is_active=inventory.is_active,
        created_at=inventory.created_at
    )


# ==================== INVENTORY ENHANCEMENTS ====================

@router.get("/inventory/alerts")
def get_inventory_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.PHARMACIST]))
):
    """Get combined alerts for low stock and expiring items"""
    thirty_days = datetime.utcnow() + timedelta(days=30)
    
    # Low stock items
    low_stock = session.exec(
        select(PharmacyInventory)
        .where(PharmacyInventory.stock_quantity < PharmacyInventory.reorder_level)
        .where(PharmacyInventory.is_active == True)
    ).all()
    
    # Expiring soon
    expiring = session.exec(
        select(PharmacyInventory)
        .where(PharmacyInventory.expiry_date <= thirty_days)
        .where(PharmacyInventory.is_active == True)
        .order_by(PharmacyInventory.expiry_date)
    ).all()
    
    # Expired
    expired = session.exec(
        select(PharmacyInventory)
        .where(PharmacyInventory.expiry_date < datetime.utcnow())
        .where(PharmacyInventory.is_active == True)
    ).all()
    
    return {
        "low_stock": [item.dict() for item in low_stock],
        "expiring_soon": [item.dict() for item in expiring],
        "expired": [item.dict() for item in expired],
        "total_alerts": len(low_stock) + len(expiring) + len(expired)
    }
