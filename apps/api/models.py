from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, String
from enum import Enum

class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"
    NURSE = "nurse"
    PHARMACIST = "pharmacist"
    LAB_TECHNICIAN = "lab_technician"

class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class AppointmentType(str, Enum):
    CONSULTATION = "consultation"
    FOLLOW_UP = "follow_up"
    EMERGENCY = "emergency"

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    role: UserRole
    full_name: str
    phone_number: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    doctor_appointments: List["Appointment"] = Relationship(back_populates="doctor", sa_relationship_kwargs={"foreign_keys": "Appointment.doctor_id"})
    patient_appointments: List["Appointment"] = Relationship(back_populates="patient", sa_relationship_kwargs={"foreign_keys": "Appointment.patient_id"})
    medical_records: List["MedicalRecord"] = Relationship(back_populates="patient", sa_relationship_kwargs={"foreign_keys": "MedicalRecord.patient_id"})
    doctor_profile: Optional["DoctorProfile"] = Relationship(back_populates="user")
    patient_profile: Optional["PatientProfile"] = Relationship(back_populates="user")

class DoctorProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True)
    specialization: str
    license_number: str = Field(unique=True, index=True)
    years_of_experience: int
    qualification: str
    consultation_fee: float = Field(ge=0)
    is_verified: bool = Field(default=False)
    is_online: bool = Field(default=False)
    bio: Optional[str] = None
    last_seen: Optional[datetime] = None
    
    # Business rule fields
    license_expiry_date: Optional[datetime] = None
    max_appointments_per_day: int = Field(default=20)
    advance_booking_days: int = Field(default=90)
    min_booking_notice_hours: int = Field(default=2)
    cancellation_hours_before: int = Field(default=24)
    average_rating: Optional[float] = Field(default=None, ge=0, le=5)
    total_consultations: int = Field(default=0)
    profile_completion_percent: int = Field(default=0, ge=0, le=100)
    
    user: User = Relationship(back_populates="doctor_profile")

class PatientProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True)
    date_of_birth: Optional[datetime] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_number: Optional[str] = None
    
    user: User = Relationship(back_populates="patient_profile")

class DoctorAvailability(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="user.id")
    day_of_week: int = Field(ge=0, le=6)  # 0=Monday, 6=Sunday
    start_time: str  # Format: "HH:MM"
    end_time: str    # Format: "HH:MM"
    slot_duration: int = Field(default=30)  # Duration in minutes
    is_available: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Appointment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="user.id")
    doctor_id: int = Field(foreign_key="user.id")
    start_time: datetime
    end_time: datetime
    status: str = Field(default="scheduled", sa_column=Column(String(20)))
    appointment_type: str = Field(default="consultation", sa_column=Column(String(20)))
    queue_number: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Tracking fields
    reschedule_count: int = Field(default=0)
    cancellation_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[int] = None  # user_id who cancelled
    confirmation_sent: bool = Field(default=False)
    reminder_sent: bool = Field(default=False)
    actual_start_time: Optional[datetime] = None  # When doctor started
    actual_end_time: Optional[datetime] = None    # When completed
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    feedback: Optional[str] = None
    
    # Relationships
    patient: User = Relationship(back_populates="patient_appointments", sa_relationship_kwargs={"foreign_keys": "Appointment.patient_id"})
    doctor: User = Relationship(back_populates="doctor_appointments", sa_relationship_kwargs={"foreign_keys": "Appointment.doctor_id"})
    prescription: Optional["Prescription"] = Relationship(back_populates="appointment")
    billing: Optional["Billing"] = Relationship(back_populates="appointment")

class Prescription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointment.id")
    medicines: str  # JSON string or simple text for now
    instructions: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    appointment: Appointment = Relationship(back_populates="prescription")

class MedicalRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="user.id")
    doctor_id: int = Field(foreign_key="user.id") # The doctor who created the record
    diagnosis: str
    notes: Optional[str] = None
    file_url: Optional[str] = None # For lab reports etc
    created_at: datetime = Field(default_factory=datetime.utcnow)

    patient: User = Relationship(back_populates="medical_records", sa_relationship_kwargs={"foreign_keys": "[MedicalRecord.patient_id]"})


# ==================== PHARMACY MODELS ====================

class MedicineCategory(str, Enum):
    TABLETS = "tablets"
    CAPSULES = "capsules"
    SYRUP = "syrup"
    INJECTION = "injection"
    CREAM = "cream"
    DROPS = "drops"
    INHALER = "inhaler"
    POWDER = "powder"
    OTHER = "other"

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"

class Supplier(SQLModel, table=True):
    """Pharmacy suppliers"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    gst_number: Optional[str] = None
    payment_terms: Optional[str] = None  # e.g., "Net 30", "COD"
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Medicine(SQLModel, table=True):
    """Medicine catalog"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    generic_name: Optional[str] = None
    category: MedicineCategory = Field(default=MedicineCategory.TABLETS)
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    composition: Optional[str] = None
    side_effects: Optional[str] = None
    contraindications: Optional[str] = None
    dosage_instructions: Optional[str] = None
    requires_prescription: bool = Field(default=False)
    unit: str = Field(default="piece")  # piece, strip, bottle, etc.
    hsn_code: Optional[str] = None  # For GST
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PharmacyInventory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    medicine_id: Optional[int] = Field(default=None, foreign_key="medicine.id")
    medicine_name: str  # Kept for backward compatibility
    batch_number: str = Field(index=True)
    stock_quantity: int
    reorder_level: int = Field(default=10)
    unit_price: float = Field(default=0)  # Purchase price
    selling_price: float = Field(default=0)  # MRP
    price: float  # Kept for backward compatibility
    manufacturing_date: Optional[datetime] = None
    expiry_date: datetime
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")
    rack_location: Optional[str] = None  # Storage location
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PharmacyOrder(SQLModel, table=True):
    """Patient pharmacy orders"""
    id: Optional[int] = Field(default=None, primary_key=True)
    order_number: str = Field(unique=True, index=True)
    patient_id: int = Field(foreign_key="user.id")
    prescription_id: Optional[int] = Field(default=None, foreign_key="prescription.id")
    status: OrderStatus = Field(default=OrderStatus.PENDING)
    payment_status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    payment_method: Optional[str] = None  # cash, card, upi, wallet
    subtotal: float = Field(default=0)
    tax: float = Field(default=0)
    discount: float = Field(default=0)
    delivery_charge: float = Field(default=0)
    total_amount: float = Field(default=0)
    delivery_address: Optional[str] = None
    delivery_phone: Optional[str] = None
    notes: Optional[str] = None
    ordered_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None

class PharmacyOrderItem(SQLModel, table=True):
    """Items in pharmacy orders"""
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="pharmacyorder.id")
    inventory_id: int = Field(foreign_key="pharmacyinventory.id")
    medicine_name: str
    quantity: int
    unit_price: float
    total_price: float
    batch_number: Optional[str] = None


class Billing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: Optional[int] = Field(default=None, foreign_key="appointment.id")
    amount: float
    payment_status: str = Field(default="pending") # pending, paid, failed
    payment_method: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    appointment: Optional[Appointment] = Relationship(back_populates="billing")

class SystemConfiguration(SQLModel, table=True):
    """System-wide configuration settings"""
    id: Optional[int] = Field(default=None, primary_key=True)
    config_key: str = Field(unique=True, index=True)
    config_value: str
    description: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: int = Field(foreign_key="user.id")

class AdminActivityLog(SQLModel, table=True):
    """Log for admin actions"""
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_id: int = Field(foreign_key="user.id")
    action_type: str  # verify_doctor, deactivate_user, activate_user, etc.
    target_user_id: Optional[int] = None
    description: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    extra_data: Optional[str] = None  # JSON string for additional data

class NotificationTemplate(SQLModel, table=True):
    """WhatsApp/Email notification templates"""
    id: Optional[int] = Field(default=None, primary_key=True)
    template_type: str = Field(index=True)  # appointment_booked, cancelled, reminder, etc.
    message_content: str
    variables: Optional[str] = None  # JSON string of variable placeholders
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class NotificationLog(SQLModel, table=True):
    """Log of all sent notifications"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    appointment_id: Optional[int] = Field(default=None, foreign_key="appointment.id")
    notification_type: str  # whatsapp, email, sms
    template_type: str  # appointment_booked, reminder, etc.
    status: str = Field(default="pending")  # pending, sent, failed
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None

class ActivityLog(SQLModel, table=True):
    """User activity tracking for security and monitoring"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    user_name: str
    user_role: str = Field(index=True)
    activity_type: str = Field(index=True)  # login, logout, appointment_book, etc.
    activity_description: str
    ip_address: Optional[str] = None
    device_type: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    extra_info: Optional[str] = None  # JSON string for additional context

class ChatRoom(SQLModel, table=True):
    """Chat rooms for doctor-patient communication"""
    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointment.id", unique=True, index=True)
    doctor_id: int = Field(foreign_key="user.id", index=True)
    patient_id: int = Field(foreign_key="user.id", index=True)
    room_identifier: Optional[str] = Field(default=None, unique=True, index=True)  # Unique room ID for WebSocket
    is_active: bool = Field(default=True)
    last_message: Optional[str] = None  # Preview of last message
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    SYSTEM = "system"

class ChatMessage(SQLModel, table=True):
    """Individual chat messages with delivery tracking"""
    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="chatroom.id", index=True)
    sender_id: int = Field(foreign_key="user.id", index=True)
    receiver_id: int = Field(foreign_key="user.id", index=True)
    message_type: str = Field(default="text")  # text, image, file, audio, system
    message: str  # For text messages or caption
    file_url: Optional[str] = None  # URL for file/image/audio
    file_name: Optional[str] = None  # Original file name
    file_size: Optional[int] = None  # File size in bytes
    is_delivered: bool = Field(default=False)
    delivered_at: Optional[datetime] = None
    is_read: bool = Field(default=False)
    read_at: Optional[datetime] = None
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

class CallType(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"
    SCREEN_SHARE = "screen_share"

class VideoConsultation(SQLModel, table=True):
    """Video/Audio consultation sessions and call logs"""
    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointment.id", unique=True, index=True)
    doctor_id: int = Field(foreign_key="user.id", index=True)
    patient_id: int = Field(foreign_key="user.id", index=True)
    session_id: str = Field(unique=True)  # Unique session identifier for LiveKit
    room_name: Optional[str] = Field(default=None, index=True)  # LiveKit room name
    call_type: str = Field(default="video")  # audio, video, screen_share
    status: str = Field(default="scheduled")  # scheduled, in_progress, completed, cancelled, missed
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    recording_url: Optional[str] = None  # If call is recorded
    recording_id: Optional[str] = None  # LiveKit recording ID
    call_quality: Optional[str] = None  # excellent, good, fair, poor
    ended_by: Optional[int] = Field(default=None, foreign_key="user.id")  # Who ended the call
    end_reason: Optional[str] = None  # normal, timeout, error, network_issue
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DoctorRating(SQLModel, table=True):
    """Patient ratings and reviews for doctors"""
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="user.id", index=True)
    patient_id: int = Field(foreign_key="user.id", index=True)
    appointment_id: int = Field(foreign_key="appointment.id", unique=True, index=True)
    rating: float = Field(ge=1.0, le=5.0)  # 1-5 stars
    review: Optional[str] = None
    tags: Optional[str] = None  # JSON string: ["Good listener", "Thorough"]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CommissionTier(SQLModel, table=True):
    """Commission tiers based on doctor ratings"""
    id: Optional[int] = Field(default=None, primary_key=True)
    tier_name: str  # "New Doctor", "Good", "Highly Rated", "Top Rated"
    min_rating: float
    max_rating: float
    commission_amount: int  # INR (200, 400, 600, 1000)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Payment(SQLModel, table=True):
    """Payment transactions and commission tracking"""
    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointment.id", unique=True, index=True)
    patient_id: int = Field(foreign_key="user.id", index=True)
    doctor_id: int = Field(foreign_key="user.id", index=True)
    consultation_fee: int  # Total fee in INR
    platform_commission: int  # 200-1000 based on rating
    doctor_earnings: int  # consultation_fee - commission
    payment_method: str  # "razorpay", "upi", "card"
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    status: str = Field(default="pending")  # pending, completed, failed, refunded
    paid_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ConsentLog(SQLModel, table=True):
    """User consent tracking for legal compliance"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    consent_type: str  # "terms", "privacy", "medical_data_sharing"
    version: str  # "v1.0"
    accepted_at: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None

# Shipment Tracking Models
class ShipmentStatus(str, Enum):
    PENDING = "pending"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED_DELIVERY = "failed_delivery"
    RETURNED = "returned"
    CANCELLED = "cancelled"

class CourierProvider(SQLModel, table=True):
    """Courier service providers (FedEx, DHL, India Post, etc.)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)  # "FedEx", "DHL", "India Post"
    api_key: Optional[str] = None  # Encrypted in production
    api_secret: Optional[str] = None  # Encrypted in production
    webhook_url: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    shipments: List["Shipment"] = Relationship(back_populates="courier")

class Shipment(SQLModel, table=True):
    """Main shipment tracking table"""
    id: Optional[int] = Field(default=None, primary_key=True)
    tracking_number: str = Field(unique=True, index=True)
    courier_id: int = Field(foreign_key="courierprovider.id")
    status: ShipmentStatus = Field(default=ShipmentStatus.PENDING)

    # Sender Information
    sender_name: str
    sender_phone: Optional[str] = None
    sender_address: str

    # Recipient Information
    recipient_name: str
    recipient_phone: Optional[str] = None
    recipient_address: str

    # Package Details
    package_weight: Optional[float] = None  # in kg
    package_dimensions: Optional[str] = None  # "10x10x5 cm"
    estimated_delivery: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None

    # Metadata
    created_by: int = Field(foreign_key="user.id")  # User who created the shipment
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    courier: CourierProvider = Relationship(back_populates="shipments")
    items: List["ShipmentItem"] = Relationship(back_populates="shipment")
    tracking_history: List["ShipmentTracking"] = Relationship(back_populates="shipment")

class ShipmentItem(SQLModel, table=True):
    """Items within a shipment (prescriptions, lab reports, medicines)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id")
    item_type: str  # "prescription", "lab_report", "medicine", "medical_supply"
    item_id: int  # Reference to the actual item (prescription.id, etc.)
    quantity: int = Field(default=1)
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    shipment: Shipment = Relationship(back_populates="items")

class ShipmentTracking(SQLModel, table=True):
    """Tracking history for shipments"""
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id")
    status: ShipmentStatus
    location: Optional[str] = None  # Current location
    description: str  # Status description
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    shipment: Shipment = Relationship(back_populates="tracking_history")


# ==================== HOSPITAL MANAGEMENT MODELS ====================

class WardType(str, Enum):
    GENERAL = "general"
    ICU = "icu"
    NICU = "nicu"
    PRIVATE = "private"
    SEMI_PRIVATE = "semi_private"
    EMERGENCY = "emergency"
    MATERNITY = "maternity"
    PEDIATRIC = "pediatric"

class BedStatus(str, Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    RESERVED = "reserved"

class OPDStatus(str, Enum):
    WAITING = "waiting"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"

class IPDStatus(str, Enum):
    ADMITTED = "admitted"
    DISCHARGED = "discharged"
    TRANSFERRED = "transferred"
    DECEASED = "deceased"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Ward(SQLModel, table=True):
    """Hospital ward/department"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    ward_type: WardType
    floor: int
    capacity: int
    current_occupancy: int = Field(default=0)
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    beds: List["Bed"] = Relationship(back_populates="ward")

class Bed(SQLModel, table=True):
    """Hospital bed"""
    id: Optional[int] = Field(default=None, primary_key=True)
    ward_id: int = Field(foreign_key="ward.id")
    bed_number: str = Field(index=True)
    bed_type: str = Field(default="standard")  # standard, electric, icu_bed
    status: BedStatus = Field(default=BedStatus.AVAILABLE)
    daily_rate: float = Field(default=0)
    features: Optional[str] = None  # JSON string for bed features
    last_maintained: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    ward: Ward = Relationship(back_populates="beds")
    admissions: List["IPDAdmission"] = Relationship(back_populates="bed")

class OPDQueue(SQLModel, table=True):
    """OPD patient queue"""
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="user.id")
    doctor_id: int = Field(foreign_key="user.id")
    appointment_id: Optional[int] = Field(default=None, foreign_key="appointment.id")
    token_number: int
    queue_date: datetime
    status: OPDStatus = Field(default=OPDStatus.WAITING)
    check_in_time: Optional[datetime] = None
    consultation_start_time: Optional[datetime] = None
    consultation_end_time: Optional[datetime] = None
    estimated_wait_time: Optional[int] = None  # in minutes
    priority: int = Field(default=0)  # Higher = more urgent
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class IPDAdmission(SQLModel, table=True):
    """IPD patient admission"""
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="user.id")
    doctor_id: int = Field(foreign_key="user.id")
    bed_id: int = Field(foreign_key="bed.id")
    admission_date: datetime
    expected_discharge_date: Optional[datetime] = None
    actual_discharge_date: Optional[datetime] = None
    status: IPDStatus = Field(default=IPDStatus.ADMITTED)
    diagnosis: str
    treatment_plan: Optional[str] = None
    admission_type: str = Field(default="regular")  # regular, emergency, scheduled
    admission_notes: Optional[str] = None
    discharge_notes: Optional[str] = None
    discharge_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    bed: Bed = Relationship(back_populates="admissions")

class StaffShift(SQLModel, table=True):
    """Staff shift scheduling"""
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(foreign_key="user.id")
    ward_id: Optional[int] = Field(default=None, foreign_key="ward.id")
    shift_date: datetime
    start_time: str  # Format: "HH:MM"
    end_time: str    # Format: "HH:MM"
    shift_type: str = Field(default="regular")  # morning, afternoon, night, regular
    status: str = Field(default="scheduled")  # scheduled, completed, absent, leave
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class NurseTask(SQLModel, table=True):
    """Tasks assigned to nurses"""
    id: Optional[int] = Field(default=None, primary_key=True)
    nurse_id: int = Field(foreign_key="user.id")
    patient_id: int = Field(foreign_key="user.id")
    admission_id: Optional[int] = Field(default=None, foreign_key="ipdadmission.id")
    task_type: str  # vitals_check, medication, wound_dressing, etc.
    description: str
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    due_at: datetime
    completed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== BILLING & INVOICING MODELS ====================

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class ServiceType(str, Enum):
    CONSULTATION = "consultation"
    PHARMACY = "pharmacy"
    LAB_TEST = "lab_test"
    PROCEDURE = "procedure"
    ROOM_CHARGES = "room_charges"
    NURSING = "nursing"
    EQUIPMENT = "equipment"
    THERAPY = "therapy"
    AMBULANCE = "ambulance"
    OTHER = "other"

class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    NET_BANKING = "net_banking"
    INSURANCE = "insurance"
    WALLET = "wallet"
    CHEQUE = "cheque"

class InvoicePaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class ClaimStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    APPROVED = "approved"
    PARTIALLY_APPROVED = "partially_approved"
    REJECTED = "rejected"
    APPEALED = "appealed"

class Invoice(SQLModel, table=True):
    """Patient invoices for all services"""
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_number: str = Field(unique=True, index=True)
    patient_id: int = Field(foreign_key="user.id")
    appointment_id: Optional[int] = Field(default=None, foreign_key="appointment.id")
    admission_id: Optional[int] = Field(default=None, foreign_key="ipdadmission.id")
    
    # Amounts
    subtotal: float = Field(default=0.0)
    tax_amount: float = Field(default=0.0)
    discount_amount: float = Field(default=0.0)
    total_amount: float = Field(default=0.0)
    paid_amount: float = Field(default=0.0)
    balance_due: float = Field(default=0.0)
    
    # Status and dates
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT)
    due_date: datetime
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None
    
    # Additional info
    notes: Optional[str] = None
    terms_conditions: Optional[str] = None
    generated_by: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class InvoiceItem(SQLModel, table=True):
    """Individual line items in an invoice"""
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id")
    service_type: ServiceType
    description: str
    quantity: int = Field(default=1)
    unit_price: float
    discount_percent: float = Field(default=0.0)
    tax_percent: float = Field(default=0.0)
    total_price: float
    
    # Optional references
    prescription_id: Optional[int] = Field(default=None, foreign_key="prescription.id")
    pharmacy_item_id: Optional[int] = Field(default=None, foreign_key="pharmacyinventory.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class InvoicePayment(SQLModel, table=True):
    """Payment records for invoices"""
    __tablename__ = "invoicepayment"
    id: Optional[int] = Field(default=None, primary_key=True)
    payment_reference: str = Field(unique=True, index=True)
    invoice_id: int = Field(foreign_key="invoice.id")
    patient_id: int = Field(foreign_key="user.id")
    
    amount: float
    payment_method: PaymentMethod
    status: InvoicePaymentStatus = Field(default=InvoicePaymentStatus.PENDING)
    
    # Gateway details
    gateway_name: Optional[str] = None  # razorpay, stripe, etc.
    gateway_transaction_id: Optional[str] = None
    gateway_order_id: Optional[str] = None
    gateway_response: Optional[str] = None  # JSON string
    
    # Timestamps
    initiated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Refund info
    refund_amount: Optional[float] = None
    refund_reason: Optional[str] = None
    refunded_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class InsuranceClaim(SQLModel, table=True):
    """Insurance claim submissions"""
    id: Optional[int] = Field(default=None, primary_key=True)
    claim_number: str = Field(unique=True, index=True)
    patient_id: int = Field(foreign_key="user.id")
    invoice_id: int = Field(foreign_key="invoice.id")
    
    # Insurance details
    insurance_provider: str
    policy_number: str
    policy_holder_name: str
    policy_holder_relation: str = Field(default="self")  # self, spouse, child, parent
    
    # Amounts
    claim_amount: float
    approved_amount: Optional[float] = None
    copay_amount: Optional[float] = None
    deductible_amount: Optional[float] = None
    
    # Status
    status: ClaimStatus = Field(default=ClaimStatus.DRAFT)
    rejection_reason: Optional[str] = None
    
    # Documents (stored as JSON array of file paths)
    documents: Optional[str] = None
    
    # Timestamps
    submitted_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    
    # Notes
    diagnosis_codes: Optional[str] = None  # ICD codes
    procedure_codes: Optional[str] = None  # CPT codes
    notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TaxConfiguration(SQLModel, table=True):
    """Tax configuration for different service types"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    service_type: ServiceType
    tax_percent: float
    is_active: bool = Field(default=True)
    effective_from: datetime
    effective_to: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DiscountCode(SQLModel, table=True):
    """Discount codes and coupons"""
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    description: Optional[str] = None
    discount_type: str = Field(default="percent")  # percent, fixed
    discount_value: float
    min_amount: Optional[float] = None
    max_discount: Optional[float] = None
    usage_limit: Optional[int] = None
    used_count: int = Field(default=0)
    valid_from: datetime
    valid_until: datetime
    is_active: bool = Field(default=True)
    applicable_services: Optional[str] = None  # JSON array of service types
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== NOTIFICATION MODELS ====================

class NotificationType(str, Enum):
    APPOINTMENT_CONFIRMATION = "appointment_confirmation"
    APPOINTMENT_REMINDER = "appointment_reminder"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_DUE = "payment_due"
    PAYMENT_FAILED = "payment_failed"
    PRESCRIPTION_READY = "prescription_ready"
    SHIPMENT_CREATED = "shipment_created"
    SHIPMENT_DISPATCHED = "shipment_dispatched"
    SHIPMENT_DELIVERED = "shipment_delivered"
    LAB_RESULT_READY = "lab_result_ready"
    DOCTOR_AVAILABLE = "doctor_available"
    PROMOTIONAL = "promotional"
    SYSTEM_ALERT = "system_alert"

class NotificationChannel(str, Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"

class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ReminderTiming(str, Enum):
    MINUTES_15 = "15min"
    MINUTES_30 = "30min"
    HOUR_1 = "1hr"
    HOURS_2 = "2hr"
    HOURS_24 = "24hr"
    DAYS_2 = "2days"

class NotificationTemplateV2(SQLModel, table=True):
    """Templates for different notification types - Enhanced version"""
    __tablename__ = "notificationtemplate_v2"
    id: Optional[int] = Field(default=None, primary_key=True)
    template_type: NotificationType
    template_name: str
    channel: NotificationChannel = Field(default=NotificationChannel.WHATSAPP)
    
    # Content
    subject: Optional[str] = None  # For email
    message_content: str  # Template with variables like {{patient_name}}, {{doctor_name}}
    variables: Optional[str] = None  # JSON array of variable names
    
    # Metadata
    language: str = Field(default="en")
    is_active: bool = Field(default=True)
    
    # WhatsApp specific
    whatsapp_template_id: Optional[str] = None  # For pre-approved WhatsApp templates
    whatsapp_template_name: Optional[str] = None
    
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class NotificationLogV2(SQLModel, table=True):
    """Log of all sent notifications - Enhanced version"""
    __tablename__ = "notificationlog_v2"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    template_id: Optional[int] = Field(default=None, foreign_key="notificationtemplate_v2.id")
    
    notification_type: NotificationType
    channel: NotificationChannel
    
    # Recipient details
    recipient_phone: Optional[str] = None
    recipient_email: Optional[str] = None
    
    # Content
    subject: Optional[str] = None
    message_content: str
    
    # Status tracking
    status: NotificationStatus = Field(default=NotificationStatus.PENDING)
    error_message: Optional[str] = None
    retry_count: int = Field(default=0)
    
    # External IDs
    external_message_id: Optional[str] = None  # WhatsApp/SMS provider message ID
    
    # Timestamps
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    
    # Reference
    reference_type: Optional[str] = None  # appointment, payment, shipment
    reference_id: Optional[int] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class NotificationPreference(SQLModel, table=True):
    """User notification preferences"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True)
    
    # Channel preferences
    whatsapp_enabled: bool = Field(default=True)
    sms_enabled: bool = Field(default=False)
    email_enabled: bool = Field(default=True)
    push_enabled: bool = Field(default=True)
    
    # Type preferences
    appointment_reminders: bool = Field(default=True)
    appointment_updates: bool = Field(default=True)
    payment_alerts: bool = Field(default=True)
    prescription_alerts: bool = Field(default=True)
    shipment_updates: bool = Field(default=True)
    lab_results: bool = Field(default=True)
    promotional: bool = Field(default=False)
    
    # Timing preferences
    reminder_timing: ReminderTiming = Field(default=ReminderTiming.HOUR_1)
    quiet_hours_start: Optional[str] = None  # Format: "22:00"
    quiet_hours_end: Optional[str] = None    # Format: "07:00"
    
    # Language
    preferred_language: str = Field(default="en")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ScheduledNotification(SQLModel, table=True):
    """Scheduled notifications (e.g., appointment reminders)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    template_id: int = Field(foreign_key="notificationtemplate_v2.id")
    
    notification_type: NotificationType
    channel: NotificationChannel
    
    # Content
    message_content: str
    variables_data: Optional[str] = None  # JSON data for template variables
    
    # Scheduling
    scheduled_at: datetime
    is_processed: bool = Field(default=False)
    processed_at: Optional[datetime] = None
    
    # Reference
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== PHASE 11: Doctor Productivity & KPI Models ====================

class MetricPeriod(str, Enum):
    """Period for metrics aggregation"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

class DoctorMetrics(SQLModel, table=True):
    """Daily metrics tracking for doctors"""
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="user.id", index=True)
    date: datetime = Field(index=True)
    
    # Time tracking
    login_time: Optional[datetime] = None
    logout_time: Optional[datetime] = None
    active_duration_minutes: int = Field(default=0)  # Total active time
    online_duration_minutes: int = Field(default=0)  # Online consultation availability
    
    # Appointment metrics
    total_appointments: int = Field(default=0)
    completed_appointments: int = Field(default=0)
    cancelled_appointments: int = Field(default=0)
    no_show_appointments: int = Field(default=0)
    rescheduled_appointments: int = Field(default=0)
    
    # Consultation types
    online_consultations: int = Field(default=0)
    in_person_consultations: int = Field(default=0)
    follow_up_consultations: int = Field(default=0)
    emergency_consultations: int = Field(default=0)
    
    # Time efficiency
    avg_consultation_duration_minutes: float = Field(default=0)
    avg_wait_time_minutes: float = Field(default=0)
    avg_response_time_minutes: float = Field(default=0)
    
    # Revenue
    revenue_generated: float = Field(default=0)
    revenue_pending: float = Field(default=0)
    
    # Patient feedback
    total_ratings: int = Field(default=0)
    sum_ratings: float = Field(default=0)  # For calculating average
    avg_rating: Optional[float] = Field(default=None, ge=0, le=5)
    
    # Prescriptions & records
    prescriptions_written: int = Field(default=0)
    medical_records_updated: int = Field(default=0)
    lab_orders_placed: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class DoctorProductivityScore(SQLModel, table=True):
    """Aggregated productivity scores for ranking"""
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="user.id", index=True)
    period: MetricPeriod
    period_start: datetime
    period_end: datetime
    
    # Individual scores (0-100)
    availability_score: float = Field(default=0, ge=0, le=100)
    efficiency_score: float = Field(default=0, ge=0, le=100)
    quality_score: float = Field(default=0, ge=0, le=100)
    revenue_score: float = Field(default=0, ge=0, le=100)
    patient_satisfaction_score: float = Field(default=0, ge=0, le=100)
    
    # Weighted overall score
    overall_score: float = Field(default=0, ge=0, le=100)
    
    # Ranking
    rank_in_department: Optional[int] = None
    rank_overall: Optional[int] = None
    percentile: Optional[float] = None
    
    # Aggregated metrics for the period
    total_consultations: int = Field(default=0)
    total_revenue: float = Field(default=0)
    avg_rating: Optional[float] = None
    completion_rate: float = Field(default=0)  # Percentage
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DoctorSession(SQLModel, table=True):
    """Track doctor login/logout sessions for time calculation"""
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="user.id", index=True)
    
    session_start: datetime
    session_end: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    
    # Session type
    is_online_consultation: bool = Field(default=False)
    device_type: Optional[str] = None  # desktop, mobile, tablet
    ip_address: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DoctorTarget(SQLModel, table=True):
    """Monthly/weekly targets for doctors"""
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="user.id", index=True)
    period: MetricPeriod
    period_start: datetime
    period_end: datetime
    
    # Targets
    target_consultations: int = Field(default=0)
    target_revenue: float = Field(default=0)
    target_online_hours: float = Field(default=0)
    target_rating: float = Field(default=4.5, ge=0, le=5)
    
    # Achievement
    actual_consultations: int = Field(default=0)
    actual_revenue: float = Field(default=0)
    actual_online_hours: float = Field(default=0)
    actual_rating: Optional[float] = None
    
    
    # Completion percentages
    consultation_achievement: float = Field(default=0)
    revenue_achievement: float = Field(default=0)
    online_hours_achievement: float = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== AI HEALTH ASSISTANT MODELS ====================

class UrgencyLevel(str, Enum):
    LOW = "low"  # Can wait, self-care advised
    MODERATE = "moderate"  # Should see doctor within days
    HIGH = "high"  # See doctor today
    EMERGENCY = "emergency"  # Go to ER immediately

class RecommendationType(str, Enum):
    SELF_CARE = "self_care"
    GENERAL_PHYSICIAN = "general_physician"
    SPECIALIST = "specialist"
    EMERGENCY = "emergency"
    WELLNESS = "wellness"  # Traditional/alternative medicine

class SymptomSeverity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"

class AIMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class SymptomCheck(SQLModel, table=True):
    """Patient symptom check submissions"""
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="user.id", index=True)
    session_id: str = Field(index=True)  # UUID for tracking conversation session
    
    # Symptoms data
    primary_symptom: str
    symptoms: str  # JSON array of symptoms
    duration: str  # e.g., "2 days", "1 week"
    severity: SymptomSeverity = Field(default=SymptomSeverity.MODERATE)
    additional_notes: Optional[str] = None
    
    # AI Assessment
    ai_assessment: Optional[str] = None  # AI analysis text
    urgency_level: UrgencyLevel = Field(default=UrgencyLevel.LOW)
    recommended_specialization: Optional[str] = None  # Cardiology, Dermatology, etc.
    confidence_score: Optional[float] = None  # 0-1 confidence in assessment
    
    # Metadata
    is_reviewed_by_doctor: bool = Field(default=False)
    reviewed_by: Optional[int] = Field(default=None, foreign_key="user.id")
    review_notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class AIConversation(SQLModel, table=True):
    """AI chat conversation sessions"""
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="user.id", index=True)
    session_id: str = Field(unique=True, index=True)
    
    # Conversation summary
    title: Optional[str] = None  # Auto-generated title
    summary: Optional[str] = None  # AI-generated summary
    
    # Action tracking
    action_taken: Optional[str] = None  # booked_appointment, referred_to_doctor, self_care
    doctor_id: Optional[int] = Field(default=None, foreign_key="user.id")
    appointment_id: Optional[int] = Field(default=None, foreign_key="appointment.id")
    
    # Status
    is_active: bool = Field(default=True)
    is_escalated: bool = Field(default=False)  # Escalated to human support
    message_count: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_at: Optional[datetime] = None

class AIMessage(SQLModel, table=True):
    """Individual messages in AI conversations"""
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="aiconversation.id", index=True)
    
    role: AIMessageRole
    content: str
    
    # Metadata
    tokens_used: Optional[int] = None
    model_used: Optional[str] = None  # gpt-4, claude, etc.
    response_time_ms: Optional[int] = None
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthRecommendation(SQLModel, table=True):
    """AI-generated health recommendations"""
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="user.id", index=True)
    symptom_check_id: Optional[int] = Field(default=None, foreign_key="symptomcheck.id")
    conversation_id: Optional[int] = Field(default=None, foreign_key="aiconversation.id")
    
    recommendation_type: RecommendationType
    
    # Recommendation details
    title: str
    details: str  # Main recommendation text
    instructions: Optional[str] = None  # Step-by-step instructions
    warnings: Optional[str] = None  # Important warnings
    
    # Doctor routing
    doctor_id: Optional[int] = Field(default=None, foreign_key="user.id")
    specialization: Optional[str] = None
    
    # Follow-up
    follow_up_required: bool = Field(default=False)
    follow_up_days: Optional[int] = None
    follow_up_notes: Optional[str] = None
    
    # Status
    is_acknowledged: bool = Field(default=False)
    acknowledged_at: Optional[datetime] = None
    is_followed: bool = Field(default=False)  # Patient followed recommendation
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WellnessRecommendation(SQLModel, table=True):
    """Traditional/Alternative medicine recommendations (Siddha, Varma, Ayurveda)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="user.id", index=True)
    
    # Wellness type
    wellness_type: str  # siddha, varma, ayurveda, yoga, naturopathy
    category: str  # diet, lifestyle, herbal, therapy, exercise
    
    # Recommendation
    title: str
    description: str
    benefits: Optional[str] = None
    
    # Specifics
    dosage_or_duration: Optional[str] = None  # e.g., "Twice daily", "15 minutes"
    precautions: Optional[str] = None
    contraindications: Optional[str] = None  # When NOT to follow
    
    # Source/References
    traditional_reference: Optional[str] = None  # Classical text reference
    
    # Tracking
    is_active: bool = Field(default=True)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CommonSymptom(SQLModel, table=True):
    """Pre-defined common symptoms for quick selection"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    category: str  # head, chest, abdomen, skin, general, etc.
    description: Optional[str] = None
    
    # Related data
    common_causes: Optional[str] = None  # JSON array
    associated_symptoms: Optional[str] = None  # JSON array
    typical_specializations: Optional[str] = None  # JSON array of relevant specialists
    
    # Urgency indicators
    emergency_if: Optional[str] = None  # Conditions that make this symptom urgent
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== BLOG & EXPERIENCE SHARING MODULE ====================

class BlogPostStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"

class BlogCategory(str, Enum):
    SIDDHA = "siddha"
    VARMA = "varma"
    WELLNESS = "wellness"
    MEDICAL_SCIENCE = "medical_science"
    LIFESTYLE = "lifestyle"
    YOGA = "yoga"
    DIET = "diet"
    CASE_STUDIES = "case_studies"
    MENTAL_HEALTH = "mental_health"
    PREVENTIVE_CARE = "preventive_care"

class BlogPost(SQLModel, table=True):
    """Blog posts created by verified doctors"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Author
    doctor_id: int = Field(foreign_key="user.id", index=True)
    
    # Content
    title: str = Field(index=True)
    slug: str = Field(unique=True, index=True)  # URL-friendly version of title
    excerpt: Optional[str] = None  # Short summary for previews
    content: str  # Rich text/HTML content
    cover_image_url: Optional[str] = None
    
    # Categorization
    category: BlogCategory
    tags: Optional[str] = None  # JSON array of tags
    
    # SEO
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    
    # Publishing
    status: BlogPostStatus = Field(default=BlogPostStatus.DRAFT)
    is_featured: bool = Field(default=False)
    published_at: Optional[datetime] = None
    scheduled_publish_at: Optional[datetime] = None
    
    # Metrics
    reading_time_minutes: int = Field(default=5)  # Auto-calculated
    view_count: int = Field(default=0)
    like_count: int = Field(default=0)
    comment_count: int = Field(default=0)
    
    # Admin moderation
    rejection_reason: Optional[str] = None
    moderated_by: Optional[int] = Field(default=None, foreign_key="user.id")
    moderated_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class BlogComment(SQLModel, table=True):
    """Comments on blog posts"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # References
    post_id: int = Field(foreign_key="blogpost.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    parent_comment_id: Optional[int] = Field(default=None, foreign_key="blogcomment.id")  # For nested comments
    
    # Content
    content: str
    
    # Engagement
    like_count: int = Field(default=0)
    helpful_count: int = Field(default=0)
    
    # Moderation
    is_approved: bool = Field(default=True)  # Auto-approve or require moderation
    is_spam: bool = Field(default=False)
    is_reported: bool = Field(default=False)
    report_reason: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class BlogLike(SQLModel, table=True):
    """Likes on blog posts"""
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="blogpost.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CommentLike(SQLModel, table=True):
    """Likes/helpful votes on comments"""
    id: Optional[int] = Field(default=None, primary_key=True)
    comment_id: int = Field(foreign_key="blogcomment.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    is_helpful: bool = Field(default=False)  # Helpful vote vs regular like
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BlogFollower(SQLModel, table=True):
    """Users following doctors for blog updates"""
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="user.id", index=True)
    follower_id: int = Field(foreign_key="user.id", index=True)
    notify_email: bool = Field(default=True)
    notify_whatsapp: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BlogView(SQLModel, table=True):
    """Track blog post views"""
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="blogpost.id", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")  # Optional for anonymous views
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== ADDRESS MODELS ====================

class AddressType(str, Enum):
    HOME = "home"
    WORK = "work"
    SHIPPING = "shipping"
    BILLING = "billing"
    OTHER = "other"


class DeliveryStatus(str, Enum):
    DELIVERY = "delivery"
    NON_DELIVERY = "non_delivery"
    UNKNOWN = "unknown"


class Address(SQLModel, table=True):
    """User addresses with pincode verification"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    
    # Address type
    address_type: AddressType = Field(default=AddressType.HOME)
    label: Optional[str] = None  # Custom label like "Mom's House"
    
    # Address details
    address_line_1: str
    address_line_2: Optional[str] = None
    landmark: Optional[str] = None
    
    # Location details (auto-filled from pincode verification)
    pincode: str = Field(index=True)
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: str = Field(default="India")
    
    # Post office details
    post_office_name: Optional[str] = None
    branch_type: Optional[str] = None  # Head Post Office, Sub Post Office, etc.
    delivery_status: DeliveryStatus = Field(default=DeliveryStatus.UNKNOWN)
    
    # Verification status
    is_pincode_verified: bool = Field(default=False)
    pincode_verified_at: Optional[datetime] = None
    
    # Flags
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)
    
    # Contact for this address
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    
    # Geo coordinates (optional)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PincodeCache(SQLModel, table=True):
    """Cache for pincode lookups to reduce API calls"""
    id: Optional[int] = Field(default=None, primary_key=True)
    pincode: str = Field(unique=True, index=True)
    
    # Location details
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: str = Field(default="India")
    
    # Post offices (JSON string)
    post_offices_json: Optional[str] = None  # JSON array of post office details
    
    # Validation
    is_valid: bool = Field(default=True)
    is_delivery_available: bool = Field(default=False)
    
    # Cache management
    last_verified_at: datetime = Field(default_factory=datetime.utcnow)
    verification_count: int = Field(default=1)

