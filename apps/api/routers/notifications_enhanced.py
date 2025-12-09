"""WhatsApp Notification Module with Templates and Preferences"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, timedelta
import json

from database import get_session
from models import (
    User, UserRole, NotificationTemplate, NotificationLog, NotificationPreference,
    ScheduledNotification, NotificationType, NotificationChannel, NotificationStatus,
    ReminderTiming, Appointment
)
from dependencies import get_current_user

router = APIRouter(prefix="/api/notifications-enhanced", tags=["Notifications & WhatsApp"])


# ==================== HELPER FUNCTIONS ====================

def render_template(template: str, variables: dict) -> str:
    """Render template with variables"""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


async def send_whatsapp_message(phone: str, message: str, template_id: Optional[str] = None) -> dict:
    """
    Send WhatsApp message via provider (Twilio, Meta, etc.)
    This is a placeholder - implement actual provider integration
    """
    # In production, integrate with Twilio/Meta WhatsApp Business API
    # from twilio.rest import Client
    # client = Client(account_sid, auth_token)
    # message = client.messages.create(
    #     from_='whatsapp:+14155238886',
    #     body=message,
    #     to=f'whatsapp:{phone}'
    # )
    return {
        "success": True,
        "message_id": f"mock_{datetime.now().timestamp()}",
        "status": "sent"
    }


async def send_sms_message(phone: str, message: str) -> dict:
    """Send SMS message"""
    # Implement actual SMS provider integration
    return {
        "success": True,
        "message_id": f"sms_{datetime.now().timestamp()}",
        "status": "sent"
    }


async def send_email_notification(email: str, subject: str, message: str) -> dict:
    """Send email notification"""
    # Implement actual email provider integration
    return {
        "success": True,
        "message_id": f"email_{datetime.now().timestamp()}",
        "status": "sent"
    }


async def process_notification(
    notification_log: NotificationLog,
    session: Session
):
    """Process and send a notification"""
    try:
        result = {"success": False}
        
        if notification_log.channel == NotificationChannel.WHATSAPP:
            result = await send_whatsapp_message(
                notification_log.recipient_phone,
                notification_log.message_content
            )
        elif notification_log.channel == NotificationChannel.SMS:
            result = await send_sms_message(
                notification_log.recipient_phone,
                notification_log.message_content
            )
        elif notification_log.channel == NotificationChannel.EMAIL:
            result = await send_email_notification(
                notification_log.recipient_email,
                notification_log.subject or "MedHub Notification",
                notification_log.message_content
            )
        
        if result.get("success"):
            notification_log.status = NotificationStatus.SENT
            notification_log.sent_at = datetime.utcnow()
            notification_log.external_message_id = result.get("message_id")
        else:
            notification_log.status = NotificationStatus.FAILED
            notification_log.error_message = result.get("error", "Unknown error")
            notification_log.retry_count += 1
        
        session.add(notification_log)
        session.commit()
        
    except Exception as e:
        notification_log.status = NotificationStatus.FAILED
        notification_log.error_message = str(e)
        notification_log.retry_count += 1
        session.add(notification_log)
        session.commit()


# ==================== TEMPLATE ENDPOINTS ====================

@router.get("/templates", response_model=List[dict])
def get_templates(
    template_type: Optional[NotificationType] = None,
    channel: Optional[NotificationChannel] = None,
    is_active: bool = True,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get notification templates"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = select(NotificationTemplate)
    
    if template_type:
        query = query.where(NotificationTemplate.template_type == template_type)
    if channel:
        query = query.where(NotificationTemplate.channel == channel)
    if is_active is not None:
        query = query.where(NotificationTemplate.is_active == is_active)
    
    templates = session.exec(query.order_by(NotificationTemplate.template_type)).all()
    return [t.model_dump() for t in templates]


@router.get("/templates/{template_id}")
def get_template(
    template_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get template details"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    template = session.get(NotificationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template.model_dump()


@router.post("/templates")
def create_template(
    template_type: NotificationType,
    template_name: str,
    message_content: str,
    channel: NotificationChannel = NotificationChannel.WHATSAPP,
    subject: Optional[str] = None,
    variables: Optional[str] = None,
    language: str = "en",
    whatsapp_template_id: Optional[str] = None,
    whatsapp_template_name: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create notification template"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    template = NotificationTemplate(
        template_type=template_type,
        template_name=template_name,
        channel=channel,
        subject=subject,
        message_content=message_content,
        variables=variables,
        language=language,
        whatsapp_template_id=whatsapp_template_id,
        whatsapp_template_name=whatsapp_template_name,
        created_by=current_user.id,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    
    return {"message": "Template created", "template": template.model_dump()}


@router.put("/templates/{template_id}")
def update_template(
    template_id: int,
    template_name: Optional[str] = None,
    message_content: Optional[str] = None,
    subject: Optional[str] = None,
    variables: Optional[str] = None,
    is_active: Optional[bool] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update notification template"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    template = session.get(NotificationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if template_name is not None:
        template.template_name = template_name
    if message_content is not None:
        template.message_content = message_content
    if subject is not None:
        template.subject = subject
    if variables is not None:
        template.variables = variables
    if is_active is not None:
        template.is_active = is_active
    
    template.updated_at = datetime.utcnow()
    session.add(template)
    session.commit()
    
    return {"message": "Template updated"}


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Delete notification template (soft delete)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    template = session.get(NotificationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template.is_active = False
    template.updated_at = datetime.utcnow()
    session.add(template)
    session.commit()
    
    return {"message": "Template disabled"}


# ==================== SEND NOTIFICATION ENDPOINTS ====================

@router.post("/send")
async def send_notification(
    user_id: int,
    notification_type: NotificationType,
    channel: NotificationChannel = NotificationChannel.WHATSAPP,
    template_id: Optional[int] = None,
    message: Optional[str] = None,
    variables: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    background_tasks: BackgroundTasks = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Send notification to user"""
    if current_user.role not in [UserRole.ADMIN, UserRole.DOCTOR]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check user preferences
    preferences = session.exec(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    ).first()
    
    if preferences:
        if channel == NotificationChannel.WHATSAPP and not preferences.whatsapp_enabled:
            raise HTTPException(status_code=400, detail="User has disabled WhatsApp notifications")
        if channel == NotificationChannel.SMS and not preferences.sms_enabled:
            raise HTTPException(status_code=400, detail="User has disabled SMS notifications")
        if channel == NotificationChannel.EMAIL and not preferences.email_enabled:
            raise HTTPException(status_code=400, detail="User has disabled email notifications")
    
    # Get template if specified
    final_message = message
    subject = None
    
    if template_id:
        template = session.get(NotificationTemplate, template_id)
        if template:
            vars_dict = json.loads(variables) if variables else {}
            final_message = render_template(template.message_content, vars_dict)
            subject = template.subject
    
    if not final_message:
        raise HTTPException(status_code=400, detail="Message content required")
    
    # Create notification log
    notification_log = NotificationLog(
        user_id=user_id,
        template_id=template_id,
        notification_type=notification_type,
        channel=channel,
        recipient_phone=user.phone_number,
        recipient_email=user.email,
        subject=subject,
        message_content=final_message,
        status=NotificationStatus.PENDING,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    session.add(notification_log)
    session.commit()
    session.refresh(notification_log)
    
    # Send in background
    if background_tasks:
        background_tasks.add_task(process_notification, notification_log, session)
    else:
        await process_notification(notification_log, session)
    
    return {"message": "Notification queued", "log_id": notification_log.id}


@router.post("/send-bulk")
async def send_bulk_notification(
    user_ids: str,  # Comma-separated user IDs
    notification_type: NotificationType,
    channel: NotificationChannel = NotificationChannel.WHATSAPP,
    template_id: Optional[int] = None,
    message: Optional[str] = None,
    variables: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Send bulk notifications"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    ids = [int(x.strip()) for x in user_ids.split(",")]
    
    # Get template if specified
    template = None
    if template_id:
        template = session.get(NotificationTemplate, template_id)
    
    vars_dict = json.loads(variables) if variables else {}
    sent_count = 0
    
    for uid in ids:
        user = session.get(User, uid)
        if not user:
            continue
        
        final_message = message
        if template:
            user_vars = {**vars_dict, "patient_name": user.full_name}
            final_message = render_template(template.message_content, user_vars)
        
        if not final_message:
            continue
        
        notification_log = NotificationLog(
            user_id=uid,
            template_id=template_id,
            notification_type=notification_type,
            channel=channel,
            recipient_phone=user.phone_number,
            recipient_email=user.email,
            subject=template.subject if template else None,
            message_content=final_message,
            status=NotificationStatus.PENDING,
        )
        session.add(notification_log)
        sent_count += 1
    
    session.commit()
    
    return {"message": f"Queued {sent_count} notifications"}


# ==================== NOTIFICATION LOG ENDPOINTS ====================

@router.get("/logs", response_model=List[dict])
def get_notification_logs(
    user_id: Optional[int] = None,
    notification_type: Optional[NotificationType] = None,
    channel: Optional[NotificationChannel] = None,
    status: Optional[NotificationStatus] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get notification logs"""
    query = select(NotificationLog)
    
    # Role-based filtering
    if current_user.role == UserRole.PATIENT:
        query = query.where(NotificationLog.user_id == current_user.id)
    elif user_id:
        query = query.where(NotificationLog.user_id == user_id)
    
    if notification_type:
        query = query.where(NotificationLog.notification_type == notification_type)
    if channel:
        query = query.where(NotificationLog.channel == channel)
    if status:
        query = query.where(NotificationLog.status == status)
    if from_date:
        query = query.where(NotificationLog.created_at >= from_date)
    if to_date:
        query = query.where(NotificationLog.created_at <= to_date)
    
    query = query.order_by(NotificationLog.created_at.desc()).offset(skip).limit(limit)
    logs = session.exec(query).all()
    
    result = []
    for log in logs:
        user = session.get(User, log.user_id)
        result.append({
            **log.model_dump(),
            "user_name": user.full_name if user else None,
        })
    
    return result


@router.get("/logs/stats")
def get_notification_stats(
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get notification statistics"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = select(NotificationLog)
    if from_date:
        query = query.where(NotificationLog.created_at >= from_date)
    if to_date:
        query = query.where(NotificationLog.created_at <= to_date)
    
    logs = session.exec(query).all()
    
    # Calculate stats
    total = len(logs)
    by_status = {}
    by_channel = {}
    by_type = {}
    
    for log in logs:
        by_status[log.status.value] = by_status.get(log.status.value, 0) + 1
        by_channel[log.channel.value] = by_channel.get(log.channel.value, 0) + 1
        by_type[log.notification_type.value] = by_type.get(log.notification_type.value, 0) + 1
    
    return {
        "total": total,
        "by_status": by_status,
        "by_channel": by_channel,
        "by_type": by_type,
        "delivery_rate": (by_status.get("delivered", 0) / total * 100) if total > 0 else 0,
        "failure_rate": (by_status.get("failed", 0) / total * 100) if total > 0 else 0,
    }


# ==================== PREFERENCE ENDPOINTS ====================

@router.get("/preferences")
def get_my_preferences(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get current user's notification preferences"""
    preferences = session.exec(
        select(NotificationPreference).where(NotificationPreference.user_id == current_user.id)
    ).first()
    
    if not preferences:
        # Return defaults
        return {
            "user_id": current_user.id,
            "whatsapp_enabled": True,
            "sms_enabled": False,
            "email_enabled": True,
            "push_enabled": True,
            "appointment_reminders": True,
            "appointment_updates": True,
            "payment_alerts": True,
            "prescription_alerts": True,
            "shipment_updates": True,
            "lab_results": True,
            "promotional": False,
            "reminder_timing": "1hr",
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "preferred_language": "en",
        }
    
    return preferences.model_dump()


@router.put("/preferences")
def update_preferences(
    whatsapp_enabled: Optional[bool] = None,
    sms_enabled: Optional[bool] = None,
    email_enabled: Optional[bool] = None,
    push_enabled: Optional[bool] = None,
    appointment_reminders: Optional[bool] = None,
    appointment_updates: Optional[bool] = None,
    payment_alerts: Optional[bool] = None,
    prescription_alerts: Optional[bool] = None,
    shipment_updates: Optional[bool] = None,
    lab_results: Optional[bool] = None,
    promotional: Optional[bool] = None,
    reminder_timing: Optional[ReminderTiming] = None,
    quiet_hours_start: Optional[str] = None,
    quiet_hours_end: Optional[str] = None,
    preferred_language: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update notification preferences"""
    preferences = session.exec(
        select(NotificationPreference).where(NotificationPreference.user_id == current_user.id)
    ).first()
    
    if not preferences:
        preferences = NotificationPreference(user_id=current_user.id)
    
    if whatsapp_enabled is not None:
        preferences.whatsapp_enabled = whatsapp_enabled
    if sms_enabled is not None:
        preferences.sms_enabled = sms_enabled
    if email_enabled is not None:
        preferences.email_enabled = email_enabled
    if push_enabled is not None:
        preferences.push_enabled = push_enabled
    if appointment_reminders is not None:
        preferences.appointment_reminders = appointment_reminders
    if appointment_updates is not None:
        preferences.appointment_updates = appointment_updates
    if payment_alerts is not None:
        preferences.payment_alerts = payment_alerts
    if prescription_alerts is not None:
        preferences.prescription_alerts = prescription_alerts
    if shipment_updates is not None:
        preferences.shipment_updates = shipment_updates
    if lab_results is not None:
        preferences.lab_results = lab_results
    if promotional is not None:
        preferences.promotional = promotional
    if reminder_timing is not None:
        preferences.reminder_timing = reminder_timing
    if quiet_hours_start is not None:
        preferences.quiet_hours_start = quiet_hours_start
    if quiet_hours_end is not None:
        preferences.quiet_hours_end = quiet_hours_end
    if preferred_language is not None:
        preferences.preferred_language = preferred_language
    
    preferences.updated_at = datetime.utcnow()
    session.add(preferences)
    session.commit()
    
    return {"message": "Preferences updated"}


# ==================== WEBHOOK ENDPOINTS ====================

@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    message_id: Optional[str] = None,
    status: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Handle WhatsApp delivery status webhook"""
    if not message_id:
        return {"message": "No message ID"}
    
    # Find notification by external message ID
    notification = session.exec(
        select(NotificationLog).where(NotificationLog.external_message_id == message_id)
    ).first()
    
    if not notification:
        return {"message": "Notification not found"}
    
    if status == "delivered":
        notification.status = NotificationStatus.DELIVERED
        notification.delivered_at = datetime.utcnow()
    elif status == "read":
        notification.status = NotificationStatus.READ
        notification.read_at = datetime.utcnow()
    elif status == "failed":
        notification.status = NotificationStatus.FAILED
        notification.error_message = f"{error_code}: {error_message}"
    
    session.add(notification)
    session.commit()
    
    return {"message": "Webhook processed"}


@router.post("/webhook/sms")
async def sms_webhook(
    message_id: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Handle SMS delivery status webhook"""
    if not message_id:
        return {"message": "No message ID"}
    
    notification = session.exec(
        select(NotificationLog).where(NotificationLog.external_message_id == message_id)
    ).first()
    
    if not notification:
        return {"message": "Notification not found"}
    
    if status == "delivered":
        notification.status = NotificationStatus.DELIVERED
        notification.delivered_at = datetime.utcnow()
    elif status == "failed":
        notification.status = NotificationStatus.FAILED
    
    session.add(notification)
    session.commit()
    
    return {"message": "Webhook processed"}


# ==================== SCHEDULED NOTIFICATIONS ====================

@router.post("/schedule")
def schedule_notification(
    user_id: int,
    notification_type: NotificationType,
    scheduled_at: datetime,
    template_id: int,
    channel: NotificationChannel = NotificationChannel.WHATSAPP,
    variables_data: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Schedule a notification for later delivery"""
    if current_user.role not in [UserRole.ADMIN, UserRole.DOCTOR]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    template = session.get(NotificationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    vars_dict = json.loads(variables_data) if variables_data else {}
    message = render_template(template.message_content, vars_dict)
    
    scheduled = ScheduledNotification(
        user_id=user_id,
        template_id=template_id,
        notification_type=notification_type,
        channel=channel,
        message_content=message,
        variables_data=variables_data,
        scheduled_at=scheduled_at,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    session.add(scheduled)
    session.commit()
    session.refresh(scheduled)
    
    return {"message": "Notification scheduled", "scheduled_id": scheduled.id}


@router.get("/scheduled")
def get_scheduled_notifications(
    is_processed: bool = False,
    skip: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get scheduled notifications"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = select(ScheduledNotification).where(
        ScheduledNotification.is_processed == is_processed
    ).order_by(ScheduledNotification.scheduled_at).offset(skip).limit(limit)
    
    scheduled = session.exec(query).all()
    
    result = []
    for s in scheduled:
        user = session.get(User, s.user_id)
        result.append({
            **s.model_dump(),
            "user_name": user.full_name if user else None,
        })
    
    return result


@router.delete("/scheduled/{scheduled_id}")
def cancel_scheduled_notification(
    scheduled_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Cancel a scheduled notification"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    scheduled = session.get(ScheduledNotification, scheduled_id)
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled notification not found")
    
    if scheduled.is_processed:
        raise HTTPException(status_code=400, detail="Already processed")
    
    session.delete(scheduled)
    session.commit()
    
    return {"message": "Scheduled notification cancelled"}


# ==================== DASHBOARD ====================

@router.get("/dashboard")
def get_notification_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get notification dashboard stats"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Today's stats
    today = datetime.utcnow().date()
    today_start = datetime(today.year, today.month, today.day)
    
    today_logs = session.exec(
        select(NotificationLog).where(NotificationLog.created_at >= today_start)
    ).all()
    
    today_sent = sum(1 for l in today_logs if l.status in [NotificationStatus.SENT, NotificationStatus.DELIVERED, NotificationStatus.READ])
    today_delivered = sum(1 for l in today_logs if l.status in [NotificationStatus.DELIVERED, NotificationStatus.READ])
    today_failed = sum(1 for l in today_logs if l.status == NotificationStatus.FAILED)
    
    # Total templates
    total_templates = len(session.exec(select(NotificationTemplate).where(NotificationTemplate.is_active == True)).all())
    
    # Pending scheduled
    pending_scheduled = len(session.exec(
        select(ScheduledNotification).where(ScheduledNotification.is_processed == False)
    ).all())
    
    # Channel breakdown
    whatsapp_count = sum(1 for l in today_logs if l.channel == NotificationChannel.WHATSAPP)
    sms_count = sum(1 for l in today_logs if l.channel == NotificationChannel.SMS)
    email_count = sum(1 for l in today_logs if l.channel == NotificationChannel.EMAIL)
    
    return {
        "today_total": len(today_logs),
        "today_sent": today_sent,
        "today_delivered": today_delivered,
        "today_failed": today_failed,
        "delivery_rate": (today_delivered / today_sent * 100) if today_sent > 0 else 0,
        "total_templates": total_templates,
        "pending_scheduled": pending_scheduled,
        "by_channel": {
            "whatsapp": whatsapp_count,
            "sms": sms_count,
            "email": email_count,
        }
    }
