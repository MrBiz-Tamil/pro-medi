"""Activity logging middleware and utilities"""
from typing import Optional
from datetime import datetime
from sqlmodel import Session, select
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json


def log_admin_activity(
    admin_id: int,
    action_type: str,
    description: str,
    target_user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra_data: Optional[str] = None
):
    """Create an admin activity log entry"""
    from models import AdminActivityLog
    
    return AdminActivityLog(
        admin_id=admin_id,
        action_type=action_type,
        description=description,
        target_user_id=target_user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data=extra_data
    )


class ActivityLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically log user activities"""
    
    def __init__(self, app, db_session_factory):
        super().__init__(app)
        self.db_session_factory = db_session_factory
    
    async def dispatch(self, request: Request, call_next):
        # Skip logging for health check, docs, and static files
        skip_paths = ["/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"]
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        
        # Get user info from request state (set by auth dependency)
        user = getattr(request.state, "user", None)
        
        # Process request
        response = await call_next(request)
        
        # Log activity if user is authenticated and request was successful
        if user and response.status_code < 400:
            try:
                activity_type = self._determine_activity_type(request.method, request.url.path)
                if activity_type:
                    from models import ActivityLog
                    
                    # Get client IP
                    client_host = request.client.host if request.client else "unknown"
                    forwarded_for = request.headers.get("X-Forwarded-For")
                    ip_address = forwarded_for.split(",")[0] if forwarded_for else client_host
                    
                    # Get user agent
                    user_agent = request.headers.get("User-Agent", "unknown")
                    
                    # Determine device type from user agent
                    device_type = self._determine_device_type(user_agent)
                    
                    # Create activity description
                    description = self._create_description(request.method, request.url.path, activity_type)
                    
                    # Create log entry
                    db = self.db_session_factory()
                    try:
                        log_entry = ActivityLog(
                            user_id=user.id,
                            user_name=user.full_name,
                            user_role=user.role.value,
                            activity_type=activity_type,
                            activity_description=description,
                            ip_address=ip_address,
                            device_type=device_type,
                            user_agent=user_agent
                        )
                        db.add(log_entry)
                        db.commit()
                    finally:
                        db.close()
            except Exception as e:
                # Don't fail the request if logging fails
                print(f"Activity logging error: {str(e)}")
        
        return response
    
    def _determine_activity_type(self, method: str, path: str) -> Optional[str]:
        """Determine activity type from request method and path"""
        # Login/Logout
        if "/auth/login" in path:
            return "login"
        elif "/auth/logout" in path:
            return "logout"
        
        # Appointment activities
        elif "/appointments" in path:
            if method == "POST":
                return "appointment_book"
            elif method == "PUT" or method == "PATCH":
                if "/cancel" in path:
                    return "appointment_cancel"
                elif "/reschedule" in path:
                    return "appointment_reschedule"
                return "appointment_update"
            elif method == "DELETE":
                return "appointment_cancel"
        
        # Chat/Video activities
        elif "/chat" in path and method == "POST":
            return "chat_message"
        elif "/video" in path:
            if "/start" in path:
                return "video_call_start"
            elif "/end" in path:
                return "video_call_end"
            elif method == "POST":
                return "video_call_create"
        
        # Prescription activities
        elif "/prescriptions" in path and method == "POST":
            return "prescription_create"
        
        # Medical records
        elif "/medical-records" in path and method in ["GET", "POST"]:
            return "medical_record_access"
        
        # Profile updates
        elif "/doctors/profile" in path or "/patients/profile" in path:
            if method in ["PUT", "PATCH"]:
                return "profile_update"
        
        # Medicine orders
        elif "/pharmacy/order" in path and method == "POST":
            return "medicine_order"
        
        return None
    
    def _determine_device_type(self, user_agent: str) -> str:
        """Determine device type from user agent string"""
        user_agent_lower = user_agent.lower()
        
        if "mobile" in user_agent_lower or "android" in user_agent_lower or "iphone" in user_agent_lower:
            return "mobile"
        elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
            return "tablet"
        else:
            return "desktop"
    
    def _create_description(self, method: str, path: str, activity_type: str) -> str:
        """Create human-readable activity description"""
        descriptions = {
            "login": "User logged in",
            "logout": "User logged out",
            "appointment_book": "Booked a new appointment",
            "appointment_cancel": "Cancelled an appointment",
            "appointment_reschedule": "Rescheduled an appointment",
            "appointment_update": "Updated appointment details",
            "chat_message": "Sent a chat message",
            "video_call_start": "Started a video consultation",
            "video_call_end": "Ended a video consultation",
            "video_call_create": "Created a video consultation session",
            "prescription_create": "Created a prescription",
            "medical_record_access": "Accessed medical records",
            "profile_update": "Updated profile information",
            "medicine_order": "Placed a medicine order"
        }
        
        return descriptions.get(activity_type, f"{method} request to {path}")
