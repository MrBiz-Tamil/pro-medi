"""Notification management router"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from typing import Optional, List
from datetime import datetime
from database import get_session
from models import User, NotificationTemplate, NotificationLog, Appointment
from dependencies import get_current_user, require_admin
from pydantic import BaseModel
from utils.notification_service import (
    notification_service,
    render_appointment_booked,
    render_appointment_cancelled,
    render_appointment_rescheduled,
    render_appointment_reminder,
    render_appointment_confirmed,
    render_consultation_complete
)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

# Request/Response Models
class NotificationTemplateCreate(BaseModel):
    template_type: str
    message_content: str
    variables: Optional[str] = None
    is_active: bool = True

class NotificationTemplateUpdate(BaseModel):
    message_content: Optional[str] = None
    variables: Optional[str] = None
    is_active: Optional[bool] = None

class SendNotificationRequest(BaseModel):
    user_id: int
    appointment_id: Optional[int] = None
    template_type: str
    notification_type: str = "whatsapp"  # whatsapp or sms

# Template Management (Admin only)

@router.post("/templates", dependencies=[Depends(require_admin)])
async def create_template(
    template: NotificationTemplateCreate,
    db: Session = Depends(get_session)
):
    """Create a new notification template (Admin only)"""
    new_template = NotificationTemplate(
        template_type=template.template_type,
        message_content=template.message_content,
        variables=template.variables,
        is_active=template.is_active
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    
    return {
        "id": new_template.id,
        "template_type": new_template.template_type,
        "message_content": new_template.message_content,
        "is_active": new_template.is_active
    }


@router.get("/templates")
async def get_templates(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get all notification templates"""
    statement = select(NotificationTemplate)
    templates = db.exec(statement).all()
    
    return [
        {
            "id": t.id,
            "template_type": t.template_type,
            "message_content": t.message_content,
            "variables": t.variables,
            "is_active": t.is_active,
            "created_at": t.created_at.isoformat()
        }
        for t in templates
    ]


@router.put("/templates/{template_id}", dependencies=[Depends(require_admin)])
async def update_template(
    template_id: int,
    update: NotificationTemplateUpdate,
    db: Session = Depends(get_session)
):
    """Update a notification template (Admin only)"""
    template = db.get(NotificationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if update.message_content is not None:
        template.message_content = update.message_content
    if update.variables is not None:
        template.variables = update.variables
    if update.is_active is not None:
        template.is_active = update.is_active
    
    template.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Template updated successfully"}


@router.delete("/templates/{template_id}", dependencies=[Depends(require_admin)])
async def delete_template(
    template_id: int,
    db: Session = Depends(get_session)
):
    """Delete a notification template (Admin only)"""
    template = db.get(NotificationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(template)
    db.commit()
    
    return {"message": "Template deleted successfully"}


# Notification Sending

def send_notification_background(
    user_id: int,
    message: str,
    notification_type: str,
    template_type: str,
    appointment_id: Optional[int],
    db: Session
):
    """Background task to send notification and log it"""
    user = db.get(User, user_id)
    if not user or not user.phone_number:
        return
    
    # Send notification
    success, result = notification_service.send_notification(
        to_phone=user.phone_number,
        message=message,
        notification_type=notification_type
    )
    
    # Log notification
    log_entry = NotificationLog(
        user_id=user_id,
        appointment_id=appointment_id,
        notification_type=notification_type,
        template_type=template_type,
        status="sent" if success else "failed",
        error_message=None if success else result
    )
    db.add(log_entry)
    db.commit()


@router.post("/send")
async def send_notification(
    request: SendNotificationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Send a notification to a user"""
    # Get user
    user = db.get(User, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.phone_number:
        raise HTTPException(status_code=400, detail="User has no phone number")
    
    # Get appointment if provided
    appointment = None
    if request.appointment_id:
        appointment = db.get(Appointment, request.appointment_id)
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Render message based on template type
    message = ""
    if request.template_type == "appointment_booked" and appointment:
        doctor = db.get(User, appointment.doctor_id)
        message = render_appointment_booked(
            patient_name=user.full_name,
            doctor_name=doctor.full_name if doctor else "Doctor",
            date=appointment.appointment_date.strftime("%Y-%m-%d"),
            time=appointment.appointment_time.strftime("%H:%M"),
            queue_number=appointment.queue_number or 0
        )
    elif request.template_type == "appointment_cancelled" and appointment:
        doctor = db.get(User, appointment.doctor_id)
        message = render_appointment_cancelled(
            patient_name=user.full_name,
            doctor_name=doctor.full_name if doctor else "Doctor",
            date=appointment.appointment_date.strftime("%Y-%m-%d"),
            time=appointment.appointment_time.strftime("%H:%M")
        )
    elif request.template_type == "appointment_reminder" and appointment:
        doctor = db.get(User, appointment.doctor_id)
        message = render_appointment_reminder(
            patient_name=user.full_name,
            doctor_name=doctor.full_name if doctor else "Doctor",
            date=appointment.appointment_date.strftime("%Y-%m-%d"),
            time=appointment.appointment_time.strftime("%H:%M"),
            hours_until=24
        )
    elif request.template_type == "consultation_complete" and appointment:
        doctor = db.get(User, appointment.doctor_id)
        message = render_consultation_complete(
            patient_name=user.full_name,
            doctor_name=doctor.full_name if doctor else "Doctor"
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid template type or missing appointment")
    
    # Send notification in background
    background_tasks.add_task(
        send_notification_background,
        user_id=request.user_id,
        message=message,
        notification_type=request.notification_type,
        template_type=request.template_type,
        appointment_id=request.appointment_id,
        db=db
    )
    
    return {"message": "Notification queued for sending"}


@router.get("")
async def get_user_notifications(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get current user's notifications"""
    statement = (
        select(NotificationLog)
        .where(NotificationLog.user_id == current_user.id)
        .order_by(NotificationLog.sent_at.desc())
        .offset(skip)
        .limit(limit)
    )
    notifications = db.exec(statement).all()
    return notifications


@router.get("/logs")
async def get_notification_logs(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get notification logs for current user"""
    statement = (
        select(NotificationLog)
        .where(NotificationLog.user_id == current_user.id)
        .order_by(NotificationLog.sent_at.desc())
        .offset(skip)
        .limit(limit)
    )
    logs = db.exec(statement).all()
    
    return [
        {
            "id": log.id,
            "notification_type": log.notification_type,
            "template_type": log.template_type,
            "status": log.status,
            "sent_at": log.sent_at.isoformat(),
            "error_message": log.error_message
        }
        for log in logs
    ]


@router.get("/logs/all", dependencies=[Depends(require_admin)])
async def get_all_notification_logs(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_session)
):
    """Get all notification logs (Admin only)"""
    statement = select(NotificationLog).order_by(NotificationLog.sent_at.desc())
    
    if status:
        statement = statement.where(NotificationLog.status == status)
    
    statement = statement.offset(skip).limit(limit)
    logs = db.exec(statement).all()
    
    result = []
    for log in logs:
        user = db.get(User, log.user_id)
        result.append({
            "id": log.id,
            "user": {
                "id": user.id if user else None,
                "name": user.full_name if user else "Unknown",
                "phone": user.phone_number if user else None
            },
            "notification_type": log.notification_type,
            "template_type": log.template_type,
            "status": log.status,
            "sent_at": log.sent_at.isoformat(),
            "error_message": log.error_message
        })
    
    return result


@router.patch("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Mark a notification as read"""
    notification = db.get(NotificationLog, notification_id)
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Verify notification belongs to current user
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this notification")
    
    # Update status to read (if you have a read status in your system)
    # For now, we'll just return success since NotificationLog doesn't have a 'read' field
    # You may want to add a 'is_read' boolean field to NotificationLog model
    
    return {"message": "Notification marked as read"}
