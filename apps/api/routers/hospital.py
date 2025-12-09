"""Hospital Management Router - OPD, IPD, Bed Management, Staff Scheduling"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, date, timedelta
from pydantic import BaseModel

from database import get_session
from models import (
    User, UserRole, Ward, WardType, Bed, BedStatus, 
    OPDQueue, OPDStatus, IPDAdmission, IPDStatus,
    StaffShift, NurseTask, TaskPriority, TaskStatus
)
from dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/hospital", tags=["Hospital Management"])


# ==================== SCHEMAS ====================

class WardCreate(BaseModel):
    name: str
    ward_type: WardType
    floor: int
    capacity: int
    description: Optional[str] = None

class WardUpdate(BaseModel):
    name: Optional[str] = None
    ward_type: Optional[WardType] = None
    floor: Optional[int] = None
    capacity: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class WardResponse(BaseModel):
    id: int
    name: str
    ward_type: WardType
    floor: int
    capacity: int
    current_occupancy: int
    description: Optional[str]
    is_active: bool
    available_beds: int = 0

class BedCreate(BaseModel):
    ward_id: int
    bed_number: str
    bed_type: str = "standard"
    daily_rate: float = 0
    features: Optional[str] = None

class BedUpdate(BaseModel):
    bed_type: Optional[str] = None
    status: Optional[BedStatus] = None
    daily_rate: Optional[float] = None
    features: Optional[str] = None

class BedResponse(BaseModel):
    id: int
    ward_id: int
    bed_number: str
    bed_type: str
    status: BedStatus
    daily_rate: float
    ward_name: Optional[str] = None
    patient_name: Optional[str] = None

class OPDQueueCreate(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_id: Optional[int] = None
    queue_date: datetime
    priority: int = 0
    notes: Optional[str] = None

class OPDQueueUpdate(BaseModel):
    status: Optional[OPDStatus] = None
    priority: Optional[int] = None
    notes: Optional[str] = None

class OPDQueueResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    token_number: int
    queue_date: datetime
    status: OPDStatus
    estimated_wait_time: Optional[int]
    patient_name: str
    doctor_name: str

class IPDAdmissionCreate(BaseModel):
    patient_id: int
    doctor_id: int
    bed_id: int
    diagnosis: str
    treatment_plan: Optional[str] = None
    admission_type: str = "regular"
    admission_notes: Optional[str] = None
    expected_discharge_date: Optional[datetime] = None

class IPDAdmissionUpdate(BaseModel):
    status: Optional[IPDStatus] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    discharge_notes: Optional[str] = None
    discharge_summary: Optional[str] = None
    expected_discharge_date: Optional[datetime] = None

class IPDAdmissionResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    bed_id: int
    admission_date: datetime
    status: IPDStatus
    diagnosis: str
    patient_name: str
    doctor_name: str
    bed_number: str
    ward_name: str

class StaffShiftCreate(BaseModel):
    staff_id: int
    ward_id: Optional[int] = None
    shift_date: datetime
    start_time: str
    end_time: str
    shift_type: str = "regular"
    notes: Optional[str] = None

class StaffShiftResponse(BaseModel):
    id: int
    staff_id: int
    ward_id: Optional[int]
    shift_date: datetime
    start_time: str
    end_time: str
    shift_type: str
    status: str
    staff_name: str
    ward_name: Optional[str] = None

class NurseTaskCreate(BaseModel):
    nurse_id: int
    patient_id: int
    admission_id: Optional[int] = None
    task_type: str
    description: str
    priority: TaskPriority = TaskPriority.MEDIUM
    due_at: datetime

class NurseTaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    completion_notes: Optional[str] = None

class NurseTaskResponse(BaseModel):
    id: int
    nurse_id: int
    patient_id: int
    task_type: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    due_at: datetime
    nurse_name: str
    patient_name: str

class HospitalDashboard(BaseModel):
    total_wards: int
    total_beds: int
    available_beds: int
    occupied_beds: int
    opd_today: int
    opd_waiting: int
    ipd_current: int
    pending_tasks: int


# ==================== WARD ENDPOINTS ====================

@router.post("/wards", response_model=WardResponse)
def create_ward(
    ward_data: WardCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """Create a new ward"""
    ward = Ward(**ward_data.dict())
    session.add(ward)
    session.commit()
    session.refresh(ward)
    
    return WardResponse(
        **ward.dict(),
        available_beds=ward.capacity - ward.current_occupancy
    )

@router.get("/wards", response_model=List[WardResponse])
def get_wards(
    ward_type: Optional[WardType] = None,
    is_active: bool = True,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get all wards with optional filtering"""
    query = select(Ward).where(Ward.is_active == is_active)
    if ward_type:
        query = query.where(Ward.ward_type == ward_type)
    
    wards = session.exec(query).all()
    
    return [
        WardResponse(
            **ward.dict(),
            available_beds=ward.capacity - ward.current_occupancy
        )
        for ward in wards
    ]

@router.get("/wards/{ward_id}", response_model=WardResponse)
def get_ward(
    ward_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get ward details"""
    ward = session.get(Ward, ward_id)
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")
    
    return WardResponse(
        **ward.dict(),
        available_beds=ward.capacity - ward.current_occupancy
    )

@router.put("/wards/{ward_id}", response_model=WardResponse)
def update_ward(
    ward_id: int,
    ward_data: WardUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """Update ward details"""
    ward = session.get(Ward, ward_id)
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")
    
    for key, value in ward_data.dict(exclude_unset=True).items():
        setattr(ward, key, value)
    
    session.commit()
    session.refresh(ward)
    
    return WardResponse(
        **ward.dict(),
        available_beds=ward.capacity - ward.current_occupancy
    )


# ==================== BED ENDPOINTS ====================

@router.post("/beds", response_model=BedResponse)
def create_bed(
    bed_data: BedCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """Create a new bed"""
    # Verify ward exists
    ward = session.get(Ward, bed_data.ward_id)
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")
    
    # Check for duplicate bed number in ward
    existing = session.exec(
        select(Bed)
        .where(Bed.ward_id == bed_data.ward_id)
        .where(Bed.bed_number == bed_data.bed_number)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bed number already exists in this ward")
    
    bed = Bed(**bed_data.dict())
    session.add(bed)
    session.commit()
    session.refresh(bed)
    
    return BedResponse(**bed.dict(), ward_name=ward.name)

@router.get("/beds", response_model=List[BedResponse])
def get_beds(
    ward_id: Optional[int] = None,
    status: Optional[BedStatus] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get all beds with optional filtering"""
    query = select(Bed)
    if ward_id:
        query = query.where(Bed.ward_id == ward_id)
    if status:
        query = query.where(Bed.status == status)
    
    beds = session.exec(query).all()
    result = []
    
    for bed in beds:
        ward = session.get(Ward, bed.ward_id)
        
        # Get patient name if occupied
        patient_name = None
        if bed.status == BedStatus.OCCUPIED:
            admission = session.exec(
                select(IPDAdmission)
                .where(IPDAdmission.bed_id == bed.id)
                .where(IPDAdmission.status == IPDStatus.ADMITTED)
            ).first()
            if admission:
                patient = session.get(User, admission.patient_id)
                patient_name = patient.full_name if patient else None
        
        result.append(BedResponse(
            **bed.dict(),
            ward_name=ward.name if ward else None,
            patient_name=patient_name
        ))
    
    return result

@router.put("/beds/{bed_id}", response_model=BedResponse)
def update_bed(
    bed_id: int,
    bed_data: BedUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.NURSE]))
):
    """Update bed details"""
    bed = session.get(Bed, bed_id)
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    
    old_status = bed.status
    
    for key, value in bed_data.dict(exclude_unset=True).items():
        setattr(bed, key, value)
    
    # Update ward occupancy if status changed
    if bed_data.status and old_status != bed_data.status:
        ward = session.get(Ward, bed.ward_id)
        if ward:
            if old_status == BedStatus.OCCUPIED and bed_data.status != BedStatus.OCCUPIED:
                ward.current_occupancy = max(0, ward.current_occupancy - 1)
            elif old_status != BedStatus.OCCUPIED and bed_data.status == BedStatus.OCCUPIED:
                ward.current_occupancy += 1
    
    session.commit()
    session.refresh(bed)
    
    ward = session.get(Ward, bed.ward_id)
    return BedResponse(**bed.dict(), ward_name=ward.name if ward else None)

@router.get("/beds/availability", response_model=dict)
def get_bed_availability(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get bed availability summary by ward type"""
    wards = session.exec(select(Ward).where(Ward.is_active == True)).all()
    
    availability = {}
    for ward in wards:
        beds = session.exec(select(Bed).where(Bed.ward_id == ward.id)).all()
        available = sum(1 for bed in beds if bed.status == BedStatus.AVAILABLE)
        occupied = sum(1 for bed in beds if bed.status == BedStatus.OCCUPIED)
        
        if ward.ward_type.value not in availability:
            availability[ward.ward_type.value] = {"total": 0, "available": 0, "occupied": 0}
        
        availability[ward.ward_type.value]["total"] += len(beds)
        availability[ward.ward_type.value]["available"] += available
        availability[ward.ward_type.value]["occupied"] += occupied
    
    return availability


# ==================== OPD QUEUE ENDPOINTS ====================

@router.post("/opd/queue", response_model=OPDQueueResponse)
def add_to_opd_queue(
    queue_data: OPDQueueCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.NURSE, UserRole.DOCTOR]))
):
    """Add patient to OPD queue"""
    # Get next token number for the day
    today_start = datetime.combine(queue_data.queue_date.date(), datetime.min.time())
    today_end = datetime.combine(queue_data.queue_date.date(), datetime.max.time())
    
    last_token = session.exec(
        select(OPDQueue)
        .where(OPDQueue.doctor_id == queue_data.doctor_id)
        .where(OPDQueue.queue_date >= today_start)
        .where(OPDQueue.queue_date <= today_end)
        .order_by(OPDQueue.token_number.desc())
    ).first()
    
    token_number = (last_token.token_number + 1) if last_token else 1
    
    # Calculate estimated wait time (15 min per patient ahead)
    waiting_count = session.exec(
        select(OPDQueue)
        .where(OPDQueue.doctor_id == queue_data.doctor_id)
        .where(OPDQueue.queue_date >= today_start)
        .where(OPDQueue.queue_date <= today_end)
        .where(OPDQueue.status == OPDStatus.WAITING)
    ).all()
    
    estimated_wait = len(waiting_count) * 15
    
    queue_entry = OPDQueue(
        **queue_data.dict(),
        token_number=token_number,
        check_in_time=datetime.utcnow(),
        estimated_wait_time=estimated_wait
    )
    
    session.add(queue_entry)
    session.commit()
    session.refresh(queue_entry)
    
    patient = session.get(User, queue_data.patient_id)
    doctor = session.get(User, queue_data.doctor_id)
    
    return OPDQueueResponse(
        **queue_entry.dict(),
        patient_name=patient.full_name if patient else "Unknown",
        doctor_name=doctor.full_name if doctor else "Unknown"
    )

@router.get("/opd/queue", response_model=List[OPDQueueResponse])
def get_opd_queue(
    doctor_id: Optional[int] = None,
    queue_date: Optional[date] = None,
    status: Optional[OPDStatus] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get OPD queue"""
    query = select(OPDQueue)
    
    if doctor_id:
        query = query.where(OPDQueue.doctor_id == doctor_id)
    
    if queue_date:
        day_start = datetime.combine(queue_date, datetime.min.time())
        day_end = datetime.combine(queue_date, datetime.max.time())
        query = query.where(OPDQueue.queue_date >= day_start).where(OPDQueue.queue_date <= day_end)
    
    if status:
        query = query.where(OPDQueue.status == status)
    
    query = query.order_by(OPDQueue.priority.desc(), OPDQueue.token_number)
    
    entries = session.exec(query).all()
    result = []
    
    for entry in entries:
        patient = session.get(User, entry.patient_id)
        doctor = session.get(User, entry.doctor_id)
        result.append(OPDQueueResponse(
            **entry.dict(),
            patient_name=patient.full_name if patient else "Unknown",
            doctor_name=doctor.full_name if doctor else "Unknown"
        ))
    
    return result

@router.put("/opd/queue/{queue_id}/call-next")
def call_next_patient(
    queue_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.DOCTOR, UserRole.NURSE]))
):
    """Call next patient in queue"""
    queue_entry = session.get(OPDQueue, queue_id)
    if not queue_entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    
    queue_entry.status = OPDStatus.IN_CONSULTATION
    queue_entry.consultation_start_time = datetime.utcnow()
    
    session.commit()
    
    return {"message": "Patient called", "token_number": queue_entry.token_number}

@router.put("/opd/queue/{queue_id}/complete")
def complete_opd_consultation(
    queue_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.DOCTOR]))
):
    """Mark OPD consultation as complete"""
    queue_entry = session.get(OPDQueue, queue_id)
    if not queue_entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    
    queue_entry.status = OPDStatus.COMPLETED
    queue_entry.consultation_end_time = datetime.utcnow()
    
    session.commit()
    
    return {"message": "Consultation completed"}


# ==================== IPD ADMISSION ENDPOINTS ====================

@router.post("/ipd/admissions", response_model=IPDAdmissionResponse)
def create_admission(
    admission_data: IPDAdmissionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.DOCTOR, UserRole.NURSE]))
):
    """Create new IPD admission"""
    # Verify bed is available
    bed = session.get(Bed, admission_data.bed_id)
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    if bed.status != BedStatus.AVAILABLE:
        raise HTTPException(status_code=400, detail="Bed is not available")
    
    # Create admission
    admission = IPDAdmission(
        **admission_data.dict(),
        admission_date=datetime.utcnow()
    )
    
    session.add(admission)
    
    # Update bed status
    bed.status = BedStatus.OCCUPIED
    
    # Update ward occupancy
    ward = session.get(Ward, bed.ward_id)
    if ward:
        ward.current_occupancy += 1
    
    session.commit()
    session.refresh(admission)
    
    patient = session.get(User, admission.patient_id)
    doctor = session.get(User, admission.doctor_id)
    
    return IPDAdmissionResponse(
        **admission.dict(),
        patient_name=patient.full_name if patient else "Unknown",
        doctor_name=doctor.full_name if doctor else "Unknown",
        bed_number=bed.bed_number,
        ward_name=ward.name if ward else "Unknown"
    )

@router.get("/ipd/admissions", response_model=List[IPDAdmissionResponse])
def get_admissions(
    status: Optional[IPDStatus] = None,
    ward_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get IPD admissions"""
    query = select(IPDAdmission)
    
    if status:
        query = query.where(IPDAdmission.status == status)
    if doctor_id:
        query = query.where(IPDAdmission.doctor_id == doctor_id)
    
    admissions = session.exec(query).all()
    result = []
    
    for admission in admissions:
        bed = session.get(Bed, admission.bed_id)
        if ward_id and bed and bed.ward_id != ward_id:
            continue
            
        patient = session.get(User, admission.patient_id)
        doctor = session.get(User, admission.doctor_id)
        ward = session.get(Ward, bed.ward_id) if bed else None
        
        result.append(IPDAdmissionResponse(
            **admission.dict(),
            patient_name=patient.full_name if patient else "Unknown",
            doctor_name=doctor.full_name if doctor else "Unknown",
            bed_number=bed.bed_number if bed else "Unknown",
            ward_name=ward.name if ward else "Unknown"
        ))
    
    return result

@router.put("/ipd/admissions/{admission_id}/discharge")
def discharge_patient(
    admission_id: int,
    discharge_notes: str = "",
    discharge_summary: str = "",
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.DOCTOR, UserRole.ADMIN]))
):
    """Discharge IPD patient"""
    admission = session.get(IPDAdmission, admission_id)
    if not admission:
        raise HTTPException(status_code=404, detail="Admission not found")
    
    if admission.status != IPDStatus.ADMITTED:
        raise HTTPException(status_code=400, detail="Patient is not currently admitted")
    
    admission.status = IPDStatus.DISCHARGED
    admission.actual_discharge_date = datetime.utcnow()
    admission.discharge_notes = discharge_notes
    admission.discharge_summary = discharge_summary
    
    # Free up the bed
    bed = session.get(Bed, admission.bed_id)
    if bed:
        bed.status = BedStatus.AVAILABLE
        ward = session.get(Ward, bed.ward_id)
        if ward:
            ward.current_occupancy = max(0, ward.current_occupancy - 1)
    
    session.commit()
    
    return {"message": "Patient discharged successfully"}


# ==================== STAFF SHIFT ENDPOINTS ====================

@router.post("/shifts", response_model=StaffShiftResponse)
def create_shift(
    shift_data: StaffShiftCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """Create staff shift"""
    staff = session.get(User, shift_data.staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    shift = StaffShift(**shift_data.dict())
    session.add(shift)
    session.commit()
    session.refresh(shift)
    
    ward = session.get(Ward, shift.ward_id) if shift.ward_id else None
    
    return StaffShiftResponse(
        **shift.dict(),
        staff_name=staff.full_name,
        ward_name=ward.name if ward else None
    )

@router.get("/shifts", response_model=List[StaffShiftResponse])
def get_shifts(
    staff_id: Optional[int] = None,
    ward_id: Optional[int] = None,
    shift_date: Optional[date] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get staff shifts"""
    query = select(StaffShift)
    
    if staff_id:
        query = query.where(StaffShift.staff_id == staff_id)
    if ward_id:
        query = query.where(StaffShift.ward_id == ward_id)
    if shift_date:
        day_start = datetime.combine(shift_date, datetime.min.time())
        day_end = datetime.combine(shift_date, datetime.max.time())
        query = query.where(StaffShift.shift_date >= day_start).where(StaffShift.shift_date <= day_end)
    
    shifts = session.exec(query).all()
    result = []
    
    for shift in shifts:
        staff = session.get(User, shift.staff_id)
        ward = session.get(Ward, shift.ward_id) if shift.ward_id else None
        result.append(StaffShiftResponse(
            **shift.dict(),
            staff_name=staff.full_name if staff else "Unknown",
            ward_name=ward.name if ward else None
        ))
    
    return result


# ==================== NURSE TASK ENDPOINTS ====================

@router.post("/tasks", response_model=NurseTaskResponse)
def create_task(
    task_data: NurseTaskCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.DOCTOR, UserRole.NURSE]))
):
    """Create nurse task"""
    task = NurseTask(**task_data.dict(), created_by=current_user.id)
    session.add(task)
    session.commit()
    session.refresh(task)
    
    nurse = session.get(User, task.nurse_id)
    patient = session.get(User, task.patient_id)
    
    return NurseTaskResponse(
        **task.dict(),
        nurse_name=nurse.full_name if nurse else "Unknown",
        patient_name=patient.full_name if patient else "Unknown"
    )

@router.get("/tasks", response_model=List[NurseTaskResponse])
def get_tasks(
    nurse_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get nurse tasks"""
    query = select(NurseTask)
    
    if nurse_id:
        query = query.where(NurseTask.nurse_id == nurse_id)
    if patient_id:
        query = query.where(NurseTask.patient_id == patient_id)
    if status:
        query = query.where(NurseTask.status == status)
    if priority:
        query = query.where(NurseTask.priority == priority)
    
    query = query.order_by(NurseTask.priority.desc(), NurseTask.due_at)
    
    tasks = session.exec(query).all()
    result = []
    
    for task in tasks:
        nurse = session.get(User, task.nurse_id)
        patient = session.get(User, task.patient_id)
        result.append(NurseTaskResponse(
            **task.dict(),
            nurse_name=nurse.full_name if nurse else "Unknown",
            patient_name=patient.full_name if patient else "Unknown"
        ))
    
    return result

@router.put("/tasks/{task_id}/complete")
def complete_task(
    task_id: int,
    completion_notes: str = "",
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.NURSE, UserRole.DOCTOR]))
):
    """Mark task as complete"""
    task = session.get(NurseTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.utcnow()
    task.completion_notes = completion_notes
    
    session.commit()
    
    return {"message": "Task completed"}


# ==================== DASHBOARD ENDPOINT ====================

@router.get("/dashboard", response_model=HospitalDashboard)
def get_hospital_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get hospital dashboard statistics"""
    # Ward and bed counts
    wards = session.exec(select(Ward).where(Ward.is_active == True)).all()
    beds = session.exec(select(Bed)).all()
    
    available_beds = sum(1 for bed in beds if bed.status == BedStatus.AVAILABLE)
    occupied_beds = sum(1 for bed in beds if bed.status == BedStatus.OCCUPIED)
    
    # OPD counts for today
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    
    opd_today = session.exec(
        select(OPDQueue)
        .where(OPDQueue.queue_date >= today_start)
        .where(OPDQueue.queue_date <= today_end)
    ).all()
    
    opd_waiting = sum(1 for entry in opd_today if entry.status == OPDStatus.WAITING)
    
    # IPD current admissions
    ipd_current = session.exec(
        select(IPDAdmission)
        .where(IPDAdmission.status == IPDStatus.ADMITTED)
    ).all()
    
    # Pending tasks
    pending_tasks = session.exec(
        select(NurseTask)
        .where(NurseTask.status == TaskStatus.PENDING)
    ).all()
    
    return HospitalDashboard(
        total_wards=len(wards),
        total_beds=len(beds),
        available_beds=available_beds,
        occupied_beds=occupied_beds,
        opd_today=len(opd_today),
        opd_waiting=opd_waiting,
        ipd_current=len(ipd_current),
        pending_tasks=len(pending_tasks)
    )
