from typing import Optional, List
from pydantic import BaseModel, EmailStr
from models import UserRole, AppointmentStatus, AppointmentType
from datetime import datetime

# Request schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone_number: Optional[str] = None
    role: UserRole

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenRefresh(BaseModel):
    refresh_token: str

# Profile schemas
class DoctorProfileCreate(BaseModel):
    specialization: str
    license_number: str
    years_of_experience: int
    qualification: str
    consultation_fee: float
    bio: Optional[str] = None

class DoctorProfileUpdate(BaseModel):
    specialization: Optional[str] = None
    years_of_experience: Optional[int] = None
    qualification: Optional[str] = None
    consultation_fee: Optional[float] = None
    bio: Optional[str] = None

class DoctorProfileResponse(BaseModel):
    id: int
    user_id: int
    specialization: str
    license_number: str
    years_of_experience: int
    qualification: str
    consultation_fee: float
    is_verified: bool
    is_online: bool
    bio: Optional[str] = None
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True

class PatientProfileCreate(BaseModel):
    date_of_birth: Optional[datetime] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_number: Optional[str] = None

class PatientProfileUpdate(BaseModel):
    date_of_birth: Optional[datetime] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_number: Optional[str] = None

class PatientProfileResponse(BaseModel):
    id: int
    user_id: int
    date_of_birth: Optional[datetime] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_number: Optional[str] = None

    class Config:
        from_attributes = True

# Response schemas
class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    phone_number: Optional[str] = None
    is_active: bool
    doctor_profile: Optional[DoctorProfileResponse] = None
    patient_profile: Optional[PatientProfileResponse] = None

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

# Availability schemas
class DoctorAvailabilityCreate(BaseModel):
    day_of_week: int  # 0=Monday, 6=Sunday
    start_time: str   # Format: "HH:MM"
    end_time: str     # Format: "HH:MM"
    slot_duration: int = 30

class DoctorAvailabilityUpdate(BaseModel):
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    slot_duration: Optional[int] = None
    is_available: Optional[bool] = None

class DoctorAvailabilityResponse(BaseModel):
    id: int
    doctor_id: int
    day_of_week: int
    start_time: str
    end_time: str
    slot_duration: int
    is_available: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Appointment schemas
class AppointmentCreate(BaseModel):
    doctor_id: int
    start_time: datetime
    end_time: datetime
    appointment_type: AppointmentType = AppointmentType.CONSULTATION
    notes: Optional[str] = None

class AppointmentUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = None
    rating: Optional[int] = None
    feedback: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    status: str
    appointment_type: str
    queue_number: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    reschedule_count: int
    rating: Optional[int] = None
    feedback: Optional[str] = None

    class Config:
        from_attributes = True

# Prescription schemas
class PrescriptionCreate(BaseModel):
    appointment_id: int
    medicines: str  # JSON string or structured text
    instructions: Optional[str] = None

class PrescriptionUpdate(BaseModel):
    medicines: Optional[str] = None
    instructions: Optional[str] = None

class PrescriptionResponse(BaseModel):
    id: int
    appointment_id: int
    medicines: str
    instructions: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Medical Record schemas
class MedicalRecordCreate(BaseModel):
    patient_id: int
    diagnosis: str
    notes: Optional[str] = None
    file_url: Optional[str] = None

class MedicalRecordUpdate(BaseModel):
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    file_url: Optional[str] = None

class MedicalRecordResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    diagnosis: str
    notes: Optional[str] = None
    file_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Pharmacy Inventory schemas
class PharmacyInventoryCreate(BaseModel):
    medicine_name: str
    batch_number: str
    stock_quantity: int
    expiry_date: datetime
    price: float

class PharmacyInventoryUpdate(BaseModel):
    medicine_name: Optional[str] = None
    batch_number: Optional[str] = None
    stock_quantity: Optional[int] = None
    expiry_date: Optional[datetime] = None
    price: Optional[float] = None

class PharmacyInventoryResponse(BaseModel):
    id: int
    medicine_name: str
    batch_number: str
    stock_quantity: int
    expiry_date: datetime
    price: float

    class Config:
        from_attributes = True

# Billing schemas
class BillingCreate(BaseModel):
    appointment_id: Optional[int] = None
    amount: float
    payment_method: Optional[str] = None

class BillingUpdate(BaseModel):
    amount: Optional[float] = None
    payment_status: Optional[str] = None
    payment_method: Optional[str] = None

class BillingResponse(BaseModel):
    id: int
    appointment_id: Optional[int] = None
    amount: float
    payment_status: str
    payment_method: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Notification schemas
class NotificationTemplateCreate(BaseModel):
    template_type: str  # appointment_booked, appointment_cancelled, reminder, etc.
    message_content: str
    variables: Optional[str] = None  # JSON string of variable placeholders
    is_active: bool = True

class NotificationTemplateUpdate(BaseModel):
    message_content: Optional[str] = None
    variables: Optional[str] = None
    is_active: Optional[bool] = None

class NotificationTemplateResponse(BaseModel):
    id: int
    template_type: str
    message_content: str
    variables: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationLogResponse(BaseModel):
    id: int
    user_id: int
    appointment_id: Optional[int] = None
    notification_type: str
    status: str
    sent_at: datetime
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

# Activity Log schemas
class ActivityLogResponse(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_role: str
    activity_type: str
    activity_description: str
    ip_address: Optional[str] = None
    device_type: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

# Shipment Tracking Schemas
class CourierProviderCreate(BaseModel):
    name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    webhook_url: Optional[str] = None

class CourierProviderUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    webhook_url: Optional[str] = None
    is_active: Optional[bool] = None

class CourierProviderResponse(BaseModel):
    id: int
    name: str
    webhook_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ShipmentItemCreate(BaseModel):
    item_type: str
    item_id: int
    quantity: int = 1
    description: str

class ShipmentCreate(BaseModel):
    courier_id: int
    sender_name: str
    sender_phone: Optional[str] = None
    sender_address: str
    recipient_name: str
    recipient_phone: Optional[str] = None
    recipient_address: str
    package_weight: Optional[float] = None
    package_dimensions: Optional[str] = None
    estimated_delivery: Optional[datetime] = None
    items: List[ShipmentItemCreate] = []

class ShipmentUpdate(BaseModel):
    status: Optional[str] = None
    estimated_delivery: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None

class ShipmentItemResponse(BaseModel):
    id: int
    shipment_id: int
    item_type: str
    item_id: int
    quantity: int
    description: str
    created_at: datetime

    class Config:
        from_attributes = True

class ShipmentTrackingResponse(BaseModel):
    id: int
    shipment_id: int
    status: str
    location: Optional[str] = None
    description: str
    timestamp: datetime

    class Config:
        from_attributes = True

class ShipmentResponse(BaseModel):
    id: int
    tracking_number: str
    courier: CourierProviderResponse
    status: str
    sender_name: str
    sender_phone: Optional[str] = None
    sender_address: str
    recipient_name: str
    recipient_phone: Optional[str] = None
    recipient_address: str
    package_weight: Optional[float] = None
    package_dimensions: Optional[str] = None
    estimated_delivery: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    items: List[ShipmentItemResponse] = []
    tracking_history: List[ShipmentTrackingResponse] = []

    class Config:
        from_attributes = True

class ShipmentStatusUpdate(BaseModel):
    status: str
    location: Optional[str] = None
    description: str

class PublicTrackingResponse(BaseModel):
    tracking_number: str
    status: str
    estimated_delivery: Optional[datetime] = None
    last_update: datetime
    tracking_history: List[ShipmentTrackingResponse] = []

    class Config:
        from_attributes = True

