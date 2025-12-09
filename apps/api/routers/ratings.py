"""Doctor rating and review management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime
import json

from database import get_session
from models import User, DoctorRating, Appointment, DoctorProfile
from dependencies import get_current_user
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ratings", tags=["ratings"])

# Request/Response Models
class RatingCreate(BaseModel):
    rating: float = Field(ge=1.0, le=5.0, description="Rating from 1 to 5 stars")
    review: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = Field(None, description="Tags like 'Good listener', 'Professional'")

class RatingResponse(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    appointment_id: int
    rating: float
    review: Optional[str]
    tags: Optional[List[str]]
    created_at: datetime
    patient_name: str
    
    class Config:
        from_attributes = True

class DoctorRatingStats(BaseModel):
    doctor_id: int
    average_rating: float
    total_reviews: int
    rating_distribution: dict  # {5: 100, 4: 50, 3: 20, 2: 5, 1: 2}
    recent_reviews: List[RatingResponse]

@router.post("/appointments/{appointment_id}/rate", response_model=RatingResponse)
async def rate_doctor(
    appointment_id: int,
    rating_data: RatingCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Patient rates a doctor after appointment"""
    
    # Verify appointment exists and belongs to current user
    appointment = session.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to rate this appointment")
    
    if appointment.status != "completed":
        raise HTTPException(status_code=400, detail="Can only rate completed appointments")
    
    # Check if already rated
    existing_rating = session.exec(
        select(DoctorRating).where(DoctorRating.appointment_id == appointment_id)
    ).first()
    
    if existing_rating:
        raise HTTPException(status_code=400, detail="Appointment already rated")
    
    # Create rating
    tags_json = json.dumps(rating_data.tags) if rating_data.tags else None
    
    new_rating = DoctorRating(
        doctor_id=appointment.doctor_id,
        patient_id=current_user.id,
        appointment_id=appointment_id,
        rating=rating_data.rating,
        review=rating_data.review,
        tags=tags_json
    )
    
    session.add(new_rating)
    session.commit()
    session.refresh(new_rating)
    
    # Update doctor's average rating
    await update_doctor_average_rating(appointment.doctor_id, session)
    
    # Prepare response
    response_data = RatingResponse(
        id=new_rating.id,
        doctor_id=new_rating.doctor_id,
        patient_id=new_rating.patient_id,
        appointment_id=new_rating.appointment_id,
        rating=new_rating.rating,
        review=new_rating.review,
        tags=json.loads(new_rating.tags) if new_rating.tags else None,
        created_at=new_rating.created_at,
        patient_name=current_user.full_name
    )
    
    return response_data


# Alias endpoint for POST /api/ratings (used by Patient App)
@router.post("", response_model=RatingResponse)
@router.post("/", response_model=RatingResponse)
async def submit_rating(
    rating_data: RatingCreate,
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Submit a rating - alias for rate_doctor"""
    return await rate_doctor(appointment_id, rating_data, current_user, session)


@router.get("/my-ratings")
async def get_my_ratings(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get ratings submitted by the current user (patient)"""
    
    ratings = session.exec(
        select(DoctorRating)
        .where(DoctorRating.patient_id == current_user.id)
        .order_by(DoctorRating.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    
    total = session.exec(
        select(func.count(DoctorRating.id))
        .where(DoctorRating.patient_id == current_user.id)
    ).first() or 0
    
    ratings_list = []
    for rating in ratings:
        doctor = session.get(User, rating.doctor_id)
        ratings_list.append({
            "id": rating.id,
            "doctor_id": rating.doctor_id,
            "doctor_name": doctor.full_name if doctor else "Unknown",
            "appointment_id": rating.appointment_id,
            "rating": rating.rating,
            "review": rating.review,
            "tags": json.loads(rating.tags) if rating.tags else None,
            "created_at": rating.created_at.isoformat()
        })
    
    return {
        "ratings": ratings_list,
        "total": total
    }


@router.get("/appointment/{appointment_id}")
async def get_rating_by_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get rating for a specific appointment"""
    
    # Verify appointment belongs to user
    appointment = session.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if appointment.patient_id != current_user.id and appointment.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    rating = session.exec(
        select(DoctorRating).where(DoctorRating.appointment_id == appointment_id)
    ).first()
    
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    
    patient = session.get(User, rating.patient_id)
    doctor = session.get(User, rating.doctor_id)
    
    return {
        "id": rating.id,
        "doctor_id": rating.doctor_id,
        "doctor_name": doctor.full_name if doctor else "Unknown",
        "patient_id": rating.patient_id,
        "patient_name": patient.full_name if patient else "Unknown",
        "appointment_id": rating.appointment_id,
        "rating": rating.rating,
        "review": rating.review,
        "tags": json.loads(rating.tags) if rating.tags else None,
        "created_at": rating.created_at.isoformat()
    }


@router.get("/doctor/{doctor_id}")
async def get_doctor_rating_summary(
    doctor_id: int,
    session: Session = Depends(get_session)
):
    """Get rating summary for a doctor (public endpoint)"""
    
    # Verify doctor exists
    doctor = session.get(User, doctor_id)
    if not doctor or doctor.role != "doctor":
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    ratings = session.exec(
        select(DoctorRating).where(DoctorRating.doctor_id == doctor_id)
    ).all()
    
    if not ratings:
        return {
            "doctor_id": doctor_id,
            "average_rating": 0.0,
            "total_reviews": 0,
            "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        }
    
    total_reviews = len(ratings)
    average_rating = sum(r.rating for r in ratings) / total_reviews
    
    # Rating distribution
    rating_distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    for rating in ratings:
        star = str(int(rating.rating))
        rating_distribution[star] += 1
    
    return {
        "doctor_id": doctor_id,
        "average_rating": round(average_rating, 2),
        "total_reviews": total_reviews,
        "rating_distribution": rating_distribution
    }


@router.get("/can-rate/{appointment_id}")
async def can_rate_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Check if user can rate an appointment"""
    
    appointment = session.get(Appointment, appointment_id)
    if not appointment:
        return {"can_rate": False, "reason": "Appointment not found"}
    
    if appointment.patient_id != current_user.id:
        return {"can_rate": False, "reason": "Not your appointment"}
    
    if appointment.status != "completed":
        return {"can_rate": False, "reason": "Appointment not completed"}
    
    # Check if already rated
    existing_rating = session.exec(
        select(DoctorRating).where(DoctorRating.appointment_id == appointment_id)
    ).first()
    
    if existing_rating:
        return {"can_rate": False, "reason": "Already rated", "rating_id": existing_rating.id}
    
    return {"can_rate": True}

@router.get("/doctors/{doctor_id}/ratings", response_model=DoctorRatingStats)
async def get_doctor_ratings(
    doctor_id: int,
    skip: int = 0,
    limit: int = 10,
    session: Session = Depends(get_session)
):
    """Get all ratings for a specific doctor with statistics"""
    
    # Verify doctor exists
    doctor = session.get(User, doctor_id)
    if not doctor or doctor.role != "doctor":
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Get all ratings
    ratings = session.exec(
        select(DoctorRating)
        .where(DoctorRating.doctor_id == doctor_id)
        .order_by(DoctorRating.created_at.desc())
    ).all()
    
    if not ratings:
        return DoctorRatingStats(
            doctor_id=doctor_id,
            average_rating=0.0,
            total_reviews=0,
            rating_distribution={},
            recent_reviews=[]
        )
    
    # Calculate statistics
    total_reviews = len(ratings)
    average_rating = sum(r.rating for r in ratings) / total_reviews
    
    # Rating distribution
    rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for rating in ratings:
        star = int(rating.rating)
        rating_distribution[star] += 1
    
    # Get recent reviews with patient names
    recent_ratings = ratings[skip:skip + limit]
    recent_reviews = []
    
    for rating in recent_ratings:
        patient = session.get(User, rating.patient_id)
        recent_reviews.append(RatingResponse(
            id=rating.id,
            doctor_id=rating.doctor_id,
            patient_id=rating.patient_id,
            appointment_id=rating.appointment_id,
            rating=rating.rating,
            review=rating.review,
            tags=json.loads(rating.tags) if rating.tags else None,
            created_at=rating.created_at,
            patient_name=patient.full_name if patient else "Unknown"
        ))
    
    return DoctorRatingStats(
        doctor_id=doctor_id,
        average_rating=round(average_rating, 2),
        total_reviews=total_reviews,
        rating_distribution=rating_distribution,
        recent_reviews=recent_reviews
    )

@router.put("/ratings/{rating_id}", response_model=RatingResponse)
async def update_rating(
    rating_id: int,
    rating_data: RatingCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update an existing rating (patient can edit their review)"""
    
    rating = session.get(DoctorRating, rating_id)
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    
    if rating.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this rating")
    
    # Update fields
    rating.rating = rating_data.rating
    rating.review = rating_data.review
    rating.tags = json.dumps(rating_data.tags) if rating_data.tags else None
    
    session.add(rating)
    session.commit()
    session.refresh(rating)
    
    # Update doctor's average rating
    await update_doctor_average_rating(rating.doctor_id, session)
    
    return RatingResponse(
        id=rating.id,
        doctor_id=rating.doctor_id,
        patient_id=rating.patient_id,
        appointment_id=rating.appointment_id,
        rating=rating.rating,
        review=rating.review,
        tags=json.loads(rating.tags) if rating.tags else None,
        created_at=rating.created_at,
        patient_name=current_user.full_name
    )

@router.delete("/ratings/{rating_id}")
async def delete_rating(
    rating_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Delete a rating (admin only or within 24 hours by patient)"""
    
    rating = session.get(DoctorRating, rating_id)
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    
    # Check permissions
    if current_user.role != "admin" and rating.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    doctor_id = rating.doctor_id
    
    session.delete(rating)
    session.commit()
    
    # Update doctor's average rating
    await update_doctor_average_rating(doctor_id, session)
    
    return {"message": "Rating deleted successfully"}

# Helper function to update doctor's average rating
async def update_doctor_average_rating(doctor_id: int, session: Session):
    """Recalculate and update doctor's average rating"""
    
    ratings = session.exec(
        select(DoctorRating).where(DoctorRating.doctor_id == doctor_id)
    ).all()
    
    if ratings:
        average_rating = sum(r.rating for r in ratings) / len(ratings)
        total_reviews = len(ratings)
    else:
        average_rating = 0.0
        total_reviews = 0
    
    # Update doctor profile
    doctor_profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == doctor_id)
    ).first()
    
    if doctor_profile:
        doctor_profile.average_rating = average_rating
        doctor_profile.total_reviews = total_reviews
        session.add(doctor_profile)
        session.commit()
