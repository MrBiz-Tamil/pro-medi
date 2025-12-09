"""Pharmacy inventory management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from database import get_session
from models import User, PharmacyInventory
from schemas import PharmacyInventoryCreate, PharmacyInventoryUpdate, PharmacyInventoryResponse
from dependencies import get_current_user, require_admin
from typing import List
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/pharmacy", tags=["Pharmacy"])


@router.post("/inventory", response_model=PharmacyInventoryResponse, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    item_data: PharmacyInventoryCreate,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Add medicine to inventory (admin/pharmacist only)"""
    # Check for duplicate batch number
    existing = session.exec(
        select(PharmacyInventory).where(
            PharmacyInventory.batch_number == item_data.batch_number
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Medicine with this batch number already exists"
        )
    
    new_item = PharmacyInventory(
        **item_data.model_dump()
    )
    
    session.add(new_item)
    session.commit()
    session.refresh(new_item)
    
    return new_item


@router.get("/inventory", response_model=List[PharmacyInventoryResponse])
def list_inventory(
    search: str = None,
    low_stock_only: bool = False,
    expiring_soon: bool = False,
    session: Session = Depends(get_session)
):
    """List pharmacy inventory with filters (public endpoint for search)"""
    query = select(PharmacyInventory)
    
    # Apply filters
    if search:
        query = query.where(
            PharmacyInventory.medicine_name.ilike(f"%{search}%")
        )
    
    if low_stock_only:
        query = query.where(PharmacyInventory.stock_quantity < 10)
    
    if expiring_soon:
        thirty_days_from_now = datetime.utcnow() + timedelta(days=30)
        query = query.where(PharmacyInventory.expiry_date <= thirty_days_from_now)
    
    items = session.exec(query.order_by(PharmacyInventory.medicine_name)).all()
    
    return items


@router.get("/inventory/low-stock", response_model=List[PharmacyInventoryResponse])
def get_low_stock_items(
    threshold: int = 10,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get medicines with low stock (admin/pharmacist only)"""
    items = session.exec(
        select(PharmacyInventory)
        .where(PharmacyInventory.stock_quantity < threshold)
        .order_by(PharmacyInventory.stock_quantity)
    ).all()
    
    return items


@router.get("/inventory/expiring", response_model=List[PharmacyInventoryResponse])
def get_expiring_medicines(
    days: int = 30,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get medicines expiring within specified days (admin/pharmacist only)"""
    expiry_date = datetime.utcnow() + timedelta(days=days)
    
    items = session.exec(
        select(PharmacyInventory)
        .where(PharmacyInventory.expiry_date <= expiry_date)
        .order_by(PharmacyInventory.expiry_date)
    ).all()
    
    return items


@router.get("/inventory/{item_id}", response_model=PharmacyInventoryResponse)
def get_inventory_item(
    item_id: int,
    session: Session = Depends(get_session)
):
    """Get specific inventory item (public)"""
    item = session.get(PharmacyInventory, item_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicine not found"
        )
    
    return item


@router.put("/inventory/{item_id}", response_model=PharmacyInventoryResponse)
def update_inventory_item(
    item_id: int,
    item_data: PharmacyInventoryUpdate,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Update inventory item (admin/pharmacist only)"""
    item = session.get(PharmacyInventory, item_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicine not found"
        )
    
    # Update fields
    for key, value in item_data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    
    session.add(item)
    session.commit()
    session.refresh(item)
    
    return item


@router.patch("/inventory/{item_id}/stock")
def update_stock(
    item_id: int,
    quantity_change: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Update stock quantity (add or subtract)"""
    item = session.get(PharmacyInventory, item_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicine not found"
        )
    
    new_quantity = item.stock_quantity + quantity_change
    
    if new_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock quantity cannot be negative"
        )
    
    item.stock_quantity = new_quantity
    session.add(item)
    session.commit()
    session.refresh(item)
    
    return {
        "message": "Stock updated successfully",
        "medicine_name": item.medicine_name,
        "new_quantity": new_quantity
    }


@router.delete("/inventory/{item_id}")
def delete_inventory_item(
    item_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Delete inventory item (admin only)"""
    item = session.get(PharmacyInventory, item_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicine not found"
        )
    
    session.delete(item)
    session.commit()
    
    return {"message": "Medicine deleted from inventory"}


@router.get("/stats/summary")
def get_pharmacy_stats(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get pharmacy statistics (admin only)"""
    from sqlmodel import func
    
    total_items = session.exec(select(func.count(PharmacyInventory.id))).first()
    low_stock_count = session.exec(
        select(func.count(PharmacyInventory.id))
        .where(PharmacyInventory.stock_quantity < 10)
    ).first()
    
    thirty_days_from_now = datetime.utcnow() + timedelta(days=30)
    expiring_soon_count = session.exec(
        select(func.count(PharmacyInventory.id))
        .where(PharmacyInventory.expiry_date <= thirty_days_from_now)
    ).first()
    
    total_value = session.exec(
        select(func.sum(PharmacyInventory.stock_quantity * PharmacyInventory.price))
    ).first() or 0
    
    return {
        "total_items": total_items,
        "low_stock_items": low_stock_count,
        "expiring_soon": expiring_soon_count,
        "total_inventory_value": round(total_value, 2)
    }
