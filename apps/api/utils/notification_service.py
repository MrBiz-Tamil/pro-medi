"""WhatsApp/SMS notification service using Twilio"""
import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from datetime import datetime
from typing import Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

class NotificationService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")  # e.g., whatsapp:+14155238886
        self.sms_from = os.getenv("TWILIO_SMS_FROM")  # e.g., +1234567890
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            print("Warning: Twilio credentials not configured. Notifications will be simulated.")
    
    def _is_configured(self) -> bool:
        """Check if Twilio is properly configured"""
        return self.client is not None and self.whatsapp_from and self.sms_from
    
    def send_whatsapp(self, to_phone: str, message: str) -> Tuple[bool, Optional[str]]:
        """
        Send WhatsApp message via Twilio
        
        Args:
            to_phone: Phone number in E.164 format (e.g., +919876543210)
            message: Message content
            
        Returns:
            (success: bool, message_sid or error: str)
        """
        if not self._is_configured():
            print(f"[SIMULATED WhatsApp] To: {to_phone}, Message: {message}")
            return True, "simulated_message_sid"
        
        try:
            # Format phone number for WhatsApp
            if not to_phone.startswith("whatsapp:"):
                to_phone = f"whatsapp:{to_phone}"
            
            message_obj = self.client.messages.create(
                from_=self.whatsapp_from,
                body=message,
                to=to_phone
            )
            
            return True, message_obj.sid
            
        except TwilioRestException as e:
            error_msg = f"Twilio error: {str(e)}"
            print(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(error_msg)
            return False, error_msg
    
    def send_sms(self, to_phone: str, message: str) -> Tuple[bool, Optional[str]]:
        """
        Send SMS via Twilio
        
        Args:
            to_phone: Phone number in E.164 format (e.g., +919876543210)
            message: Message content
            
        Returns:
            (success: bool, message_sid or error: str)
        """
        if not self._is_configured():
            print(f"[SIMULATED SMS] To: {to_phone}, Message: {message}")
            return True, "simulated_message_sid"
        
        try:
            message_obj = self.client.messages.create(
                from_=self.sms_from,
                body=message,
                to=to_phone
            )
            
            return True, message_obj.sid
            
        except TwilioRestException as e:
            error_msg = f"Twilio error: {str(e)}"
            print(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(error_msg)
            return False, error_msg
    
    def send_notification(
        self, 
        to_phone: str, 
        message: str, 
        notification_type: str = "whatsapp"
    ) -> Tuple[bool, Optional[str]]:
        """
        Send notification via specified channel
        
        Args:
            to_phone: Phone number
            message: Message content
            notification_type: "whatsapp" or "sms"
            
        Returns:
            (success: bool, message_sid or error: str)
        """
        if notification_type == "whatsapp":
            return self.send_whatsapp(to_phone, message)
        elif notification_type == "sms":
            return self.send_sms(to_phone, message)
        else:
            return False, f"Invalid notification type: {notification_type}"


# Template rendering functions
def render_appointment_booked(patient_name: str, doctor_name: str, date: str, time: str, queue_number: int) -> str:
    """Render appointment booked notification template"""
    return f"""Hello {patient_name},

Your appointment has been booked successfully! 🎉

👨‍⚕️ Doctor: Dr. {doctor_name}
📅 Date: {date}
🕒 Time: {time}
🎫 Token Number: {queue_number}

Please arrive 10 minutes before your scheduled time.

Thank you for choosing MedHub!"""


def render_appointment_cancelled(patient_name: str, doctor_name: str, date: str, time: str) -> str:
    """Render appointment cancelled notification template"""
    return f"""Hello {patient_name},

Your appointment has been cancelled.

👨‍⚕️ Doctor: Dr. {doctor_name}
📅 Date: {date}
🕒 Time: {time}

If you wish to reschedule, please book a new appointment through the app.

MedHub Team"""


def render_appointment_rescheduled(patient_name: str, doctor_name: str, old_date: str, old_time: str, new_date: str, new_time: str) -> str:
    """Render appointment rescheduled notification template"""
    return f"""Hello {patient_name},

Your appointment has been rescheduled.

👨‍⚕️ Doctor: Dr. {doctor_name}

Previous Schedule:
📅 {old_date} at {old_time}

New Schedule:
📅 {new_date} at {new_time}

MedHub Team"""


def render_appointment_reminder(patient_name: str, doctor_name: str, date: str, time: str, hours_until: int) -> str:
    """Render appointment reminder notification template"""
    if hours_until < 1:
        time_text = "in 30 minutes"
    elif hours_until < 24:
        time_text = f"in {hours_until} hour(s)"
    else:
        time_text = "tomorrow"
    
    return f"""Reminder: You have an appointment {time_text}! ⏰

👨‍⚕️ Doctor: Dr. {doctor_name}
📅 Date: {date}
🕒 Time: {time}

Please arrive on time.

MedHub Team"""


def render_appointment_confirmed(patient_name: str, doctor_name: str, date: str, time: str) -> str:
    """Render appointment confirmed notification template"""
    return f"""Hello {patient_name},

Your appointment has been confirmed by Dr. {doctor_name}! ✅

📅 Date: {date}
🕒 Time: {time}

See you soon!

MedHub Team"""


def render_consultation_complete(patient_name: str, doctor_name: str) -> str:
    """Render post-consultation follow-up message"""
    return f"""Hello {patient_name},

Thank you for your consultation with Dr. {doctor_name}! 🏥

Your prescription and medical records are now available in the app.

Please rate your experience to help us improve.

Take care!
MedHub Team"""


# Singleton instance
notification_service = NotificationService()
