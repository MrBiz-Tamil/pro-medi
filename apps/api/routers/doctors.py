from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from database import get_session
from models import User, DoctorProfile, UserRole, DoctorAvailability
from schemas import DoctorProfileCreate, DoctorProfileUpdate, DoctorProfileResponse, DoctorAvailabilityCreate, DoctorAvailabilityUpdate, DoctorAvailabilityResponse
from dependencies import get_current_user, require_doctor
from datetime import datetime
from typing import List, Optional
from validators.time_validator import validate_time_range, get_duration_hours
from validators.business_rules import get_business_rules
from utils.cache import DoctorCache, cache
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/doctors", tags=["Doctors"])

@router.post("/profile", response_model=DoctorProfileResponse, status_code=status.HTTP_201_CREATED)
def create_doctor_profile(
    profile_data: DoctorProfileCreate,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Create doctor profile (only for users with doctor role)"""
    # Check if profile already exists
    existing_profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == current_user.id)
    ).first()
    
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor profile already exists"
        )
    
    # Create new profile
    new_profile = DoctorProfile(
        user_id=current_user.id,
        **profile_data.model_dump()
    )
    
    session.add(new_profile)
    session.commit()
    session.refresh(new_profile)
    
    # Invalidate related caches
    DoctorCache.invalidate_verified_list()
    logger.info(f"Created doctor profile for user {current_user.id}, cache invalidated")
    
    return new_profile

@router.get("/profile", response_model=DoctorProfileResponse)
def get_my_doctor_profile(
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get current doctor's profile"""
    profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == current_user.id)
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found"
        )
    
    return profile

@router.put("/profile", response_model=DoctorProfileResponse)
def update_doctor_profile(
    profile_data: DoctorProfileUpdate,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Update doctor profile"""
    profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == current_user.id)
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found"
        )
    
    # Update fields
    for key, value in profile_data.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    
    session.add(profile)
    session.commit()
    session.refresh(profile)
    
    # Invalidate caches for this doctor
    DoctorCache.invalidate_all_for_doctor(current_user.id)
    logger.info(f"Updated doctor profile for user {current_user.id}, caches invalidated")
    
    return profile


@router.get("/search", response_model=List[DoctorProfileResponse])
def search_doctors(
    q: str,
    session: Session = Depends(get_session)
):
    """Search doctors by name or specialization (public endpoint)"""
    search_term = f"%{q.lower()}%"
    
    # Search in doctor profiles - join with users for name search
    profiles = session.exec(
        select(DoctorProfile)
        .join(User, DoctorProfile.user_id == User.id)
        .where(DoctorProfile.is_verified == True)
        .where(
            (func.lower(User.full_name).like(search_term)) |
            (func.lower(DoctorProfile.specialization).like(search_term)) |
            (func.lower(DoctorProfile.qualification).like(search_term))
        )
    ).all()
    
    return profiles


@router.get("/top-rated", response_model=List[DoctorProfileResponse])
def get_top_rated_doctors(
    limit: int = 10,
    session: Session = Depends(get_session)
):
    """Get top rated doctors (public endpoint)"""
    from models import DoctorRating
    
    # Get doctors with ratings, ordered by average rating
    # Subquery to get average ratings
    rating_subquery = (
        select(
            DoctorRating.doctor_id,
            func.avg(DoctorRating.rating).label("avg_rating"),
            func.count(DoctorRating.id).label("total_reviews")
        )
        .group_by(DoctorRating.doctor_id)
        .subquery()
    )
    
    # Join with doctor profiles and order by rating
    profiles = session.exec(
        select(DoctorProfile)
        .join(rating_subquery, DoctorProfile.user_id == rating_subquery.c.doctor_id, isouter=True)
        .where(DoctorProfile.is_verified == True)
        .order_by(rating_subquery.c.avg_rating.desc().nullslast())
        .limit(limit)
    ).all()
    
    return profiles


@router.get("/nearby", response_model=List[DoctorProfileResponse])
def get_nearby_doctors(
    lat: float,
    lng: float,
    radius: float = 10,  # km
    session: Session = Depends(get_session)
):
    """Get nearby doctors based on location (public endpoint)
    
    Note: This is a simplified implementation. For production,
    use PostGIS or a proper geospatial solution.
    """
    # For now, return all verified doctors
    # In production, filter by distance using Haversine formula or PostGIS
    
    profiles = session.exec(
        select(DoctorProfile)
        .where(DoctorProfile.is_verified == True)
        .where(DoctorProfile.is_online == True)  # Prefer online doctors for availability
        .limit(20)
    ).all()
    
    # If doctors have latitude/longitude stored, we could filter like:
    # WHERE (
    #   6371 * acos(
    #     cos(radians(:lat)) * cos(radians(latitude)) *
    #     cos(radians(longitude) - radians(:lng)) +
    #     sin(radians(:lat)) * sin(radians(latitude))
    #   )
    # ) <= :radius
    
    return profiles


@router.get("/specialization/{specialization}", response_model=List[DoctorProfileResponse])
def get_doctors_by_specialization(
    specialization: str,
    session: Session = Depends(get_session)
):
    """Get doctors by specialization (public endpoint)"""
    
    profiles = session.exec(
        select(DoctorProfile)
        .where(DoctorProfile.is_verified == True)
        .where(func.lower(DoctorProfile.specialization) == specialization.lower())
    ).all()
    
    return profiles


@router.get("/patients")
def get_doctor_patients(
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get list of patients the doctor has treated"""
    from models import Appointment
    
    # Get unique patient IDs from appointments
    patient_ids_query = (
        select(Appointment.patient_id)
        .where(Appointment.doctor_id == current_user.id)
        .distinct()
    )
    
    patient_ids = session.exec(patient_ids_query).all()
    
    if not patient_ids:
        return {"patients": [], "total": 0}
    
    # Get patient details
    patients_query = select(User).where(User.id.in_(patient_ids))
    
    if search:
        search_term = f"%{search.lower()}%"
        patients_query = patients_query.where(
            func.lower(User.full_name).like(search_term) |
            func.lower(User.email).like(search_term)
        )
    
    total = len(session.exec(patients_query).all())
    
    patients = session.exec(
        patients_query.offset(offset).limit(limit)
    ).all()
    
    patients_list = []
    for patient in patients:
        # Get last visit
        last_appointment = session.exec(
            select(Appointment)
            .where(Appointment.patient_id == patient.id)
            .where(Appointment.doctor_id == current_user.id)
            .where(Appointment.status == "completed")
            .order_by(Appointment.appointment_date.desc())
        ).first()
        
        # Count total visits
        visit_count = session.exec(
            select(func.count(Appointment.id))
            .where(Appointment.patient_id == patient.id)
            .where(Appointment.doctor_id == current_user.id)
            .where(Appointment.status == "completed")
        ).first() or 0
        
        patients_list.append({
            "id": patient.id,
            "full_name": patient.full_name,
            "email": patient.email,
            "phone_number": patient.phone_number,
            "profile_photo": getattr(patient, 'profile_photo', None),
            "last_visit": last_appointment.appointment_date.isoformat() if last_appointment else None,
            "total_visits": visit_count
        })
    
    return {
        "patients": patients_list,
        "total": total
    }


@router.get("/list", response_model=List[DoctorProfileResponse])
def list_verified_doctors(session: Session = Depends(get_session)):
    """List all verified doctors (public endpoint) - cached for performance"""
    # Try to get from cache first
    cached_data = DoctorCache.get_verified_list()
    if cached_data is not None:
        logger.debug("Returning verified doctors from cache")
        return cached_data
    
    # Fetch from database
    profiles = session.exec(
        select(DoctorProfile).where(DoctorProfile.is_verified == True)
    ).all()
    
    # Convert to dict for caching
    profiles_data = [profile.model_dump() for profile in profiles]
    
    # Cache the result
    DoctorCache.set_verified_list(profiles_data)
    logger.debug(f"Cached {len(profiles_data)} verified doctors")
    
    return profiles

@router.get("/{doctor_id}/profile", response_model=DoctorProfileResponse)
def get_doctor_profile_by_id(
    doctor_id: int,
    session: Session = Depends(get_session)
):
    """Get specific doctor's profile by user ID (public endpoint) - cached"""
    # Try cache first
    cached_profile = DoctorCache.get_profile(doctor_id)
    if cached_profile is not None:
        logger.debug(f"Returning doctor {doctor_id} profile from cache")
        return cached_profile
    
    # Fetch from database
    profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == doctor_id)
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found"
        )
    
    # Cache the result
    profile_data = profile.model_dump()
    DoctorCache.set_profile(doctor_id, profile_data)
    logger.debug(f"Cached doctor {doctor_id} profile")
    
    return profile

@router.post("/online")
def set_doctor_online(
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Set doctor status to online"""
    profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == current_user.id)
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found"
        )
    
    profile.is_online = True
    profile.last_seen = datetime.utcnow()
    session.add(profile)
    session.commit()
    
    # Invalidate online doctors cache and profile cache
    DoctorCache.invalidate_online_doctors()
    DoctorCache.invalidate_profile(current_user.id)
    logger.info(f"Doctor {current_user.id} set to online, cache invalidated")
    
    return {"message": "Status set to online", "is_online": True}

@router.post("/offline")
def set_doctor_offline(
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Set doctor status to offline"""
    profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == current_user.id)
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found"
        )
    
    profile.is_online = False
    profile.last_seen = datetime.utcnow()
    session.add(profile)
    session.commit()
    
    # Invalidate online doctors cache and profile cache
    DoctorCache.invalidate_online_doctors()
    DoctorCache.invalidate_profile(current_user.id)
    logger.info(f"Doctor {current_user.id} set to offline, cache invalidated")
    
    return {"message": "Status set to offline", "is_online": False}

@router.get("/online-doctors", response_model=List[DoctorProfileResponse])
def get_online_doctors(session: Session = Depends(get_session)):
    """Get list of all online doctors (public endpoint) - cached"""
    # Try cache first
    cached_data = DoctorCache.get_online_doctors()
    if cached_data is not None:
        logger.debug("Returning online doctors from cache")
        return cached_data
    
    # Fetch from database
    online_doctors = session.exec(
        select(DoctorProfile).where(
            DoctorProfile.is_online == True,
            DoctorProfile.is_verified == True
        )
    ).all()
    
    # Cache the result
    doctors_data = [doctor.model_dump() for doctor in online_doctors]
    DoctorCache.set_online_doctors(doctors_data)
    logger.debug(f"Cached {len(doctors_data)} online doctors")
    
    return online_doctors

# Availability Management Endpoints

@router.post("/availability", response_model=DoctorAvailabilityResponse, status_code=status.HTTP_201_CREATED)
def create_availability(
    availability_data: DoctorAvailabilityCreate,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Create availability slot for doctor"""
    # Validate time format and range
    validate_time_range(availability_data.start_time, availability_data.end_time)
    
    # Validate working hours limit
    rules = get_business_rules()
    duration_hours = get_duration_hours(availability_data.start_time, availability_data.end_time)
    
    if duration_hours > rules.MAX_WORKING_HOURS_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot set more than {rules.MAX_WORKING_HOURS_PER_DAY} hours per day"
        )
    
    # Check for existing availability on the same day
    existing = session.exec(
        select(DoctorAvailability).where(
            DoctorAvailability.doctor_id == current_user.id,
            DoctorAvailability.day_of_week == availability_data.day_of_week
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Availability already exists for this day. Use update endpoint instead."
        )
    
    new_availability = DoctorAvailability(
        doctor_id=current_user.id,
        **availability_data.model_dump()
    )
    
    session.add(new_availability)
    session.commit()
    session.refresh(new_availability)
    
    # Invalidate availability cache
    DoctorCache.invalidate_availability(current_user.id)
    logger.info(f"Created availability for doctor {current_user.id}, cache invalidated")
    
    return new_availability

@router.get("/availability", response_model=List[DoctorAvailabilityResponse])
def get_my_availability(
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Get current doctor's availability schedule"""
    availability = session.exec(
        select(DoctorAvailability)
        .where(DoctorAvailability.doctor_id == current_user.id)
        .order_by(DoctorAvailability.day_of_week)
    ).all()
    
    return availability

@router.get("/{doctor_id}/availability", response_model=List[DoctorAvailabilityResponse])
def get_doctor_availability(
    doctor_id: int,
    session: Session = Depends(get_session)
):
    """Get specific doctor's availability (public endpoint) - cached"""
    # Try cache first
    cached_data = DoctorCache.get_availability(doctor_id)
    if cached_data is not None:
        logger.debug(f"Returning doctor {doctor_id} availability from cache")
        return cached_data
    
    # Fetch from database
    availability = session.exec(
        select(DoctorAvailability)
        .where(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.is_available == True
        )
        .order_by(DoctorAvailability.day_of_week)
    ).all()
    
    # Cache the result
    availability_data = [slot.model_dump() for slot in availability]
    DoctorCache.set_availability(doctor_id, availability_data)
    logger.debug(f"Cached doctor {doctor_id} availability")
    
    return availability

@router.put("/availability/{availability_id}", response_model=DoctorAvailabilityResponse)
def update_availability(
    availability_id: int,
    availability_data: DoctorAvailabilityUpdate,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Update availability slot"""
    availability = session.get(DoctorAvailability, availability_id)
    
    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability not found"
        )
    
    if availability.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own availability"
        )
    
    # Validate time changes if provided
    new_start = availability_data.start_time or availability.start_time
    new_end = availability_data.end_time or availability.end_time
    
    if availability_data.start_time or availability_data.end_time:
        validate_time_range(new_start, new_end)
        
        # Validate working hours limit
        rules = get_business_rules()
        duration_hours = get_duration_hours(new_start, new_end)
        
        if duration_hours > rules.MAX_WORKING_HOURS_PER_DAY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot set more than {rules.MAX_WORKING_HOURS_PER_DAY} hours per day"
            )
    
    for key, value in availability_data.model_dump(exclude_unset=True).items():
        setattr(availability, key, value)
    
    session.add(availability)
    session.commit()
    session.refresh(availability)
    
    # Invalidate availability cache
    DoctorCache.invalidate_availability(current_user.id)
    logger.info(f"Updated availability for doctor {current_user.id}, cache invalidated")
    
    return availability

@router.delete("/availability/{availability_id}")
def delete_availability(
    availability_id: int,
    current_user: User = Depends(require_doctor),
    session: Session = Depends(get_session)
):
    """Delete availability slot"""
    availability = session.get(DoctorAvailability, availability_id)
    
    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability not found"
        )
    
    if availability.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own availability"
        )
    
    session.delete(availability)
    session.commit()
    
    # Invalidate availability cache
    DoctorCache.invalidate_availability(current_user.id)
    logger.info(f"Deleted availability for doctor {current_user.id}, cache invalidated")
    
    return {"message": "Availability deleted successfully"}

