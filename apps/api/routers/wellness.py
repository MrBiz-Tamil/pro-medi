"""Wellness & Preventive Care API - Phase 13
Health goals, wellness tracking, preventive screenings, and lifestyle management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from pydantic import BaseModel, Field
from enum import Enum
import uuid
import random

from database import get_session
from models import User
from dependencies import get_current_user

router = APIRouter(prefix="/api/wellness", tags=["wellness"])


# ==================== Enums ====================

class GoalCategory(str, Enum):
    WEIGHT = "weight"
    EXERCISE = "exercise"
    NUTRITION = "nutrition"
    SLEEP = "sleep"
    HYDRATION = "hydration"
    MEDITATION = "meditation"
    STEPS = "steps"
    HEART_HEALTH = "heart_health"
    MENTAL_HEALTH = "mental_health"
    CUSTOM = "custom"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class GoalFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ScreeningStatus(str, Enum):
    DUE = "due"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== Schemas ====================

class HealthGoalCreate(BaseModel):
    category: GoalCategory
    title: str
    description: Optional[str] = None
    target_value: float
    current_value: float = 0
    unit: str  # kg, steps, minutes, liters, etc.
    frequency: GoalFrequency = GoalFrequency.DAILY
    start_date: str
    end_date: Optional[str] = None
    reminder_time: Optional[str] = None  # HH:MM format
    reminder_days: List[str] = []  # ["monday", "tuesday", etc.]


class HealthGoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    status: Optional[GoalStatus] = None
    reminder_time: Optional[str] = None
    reminder_days: Optional[List[str]] = None


class HealthGoal(BaseModel):
    id: str
    user_id: int
    category: GoalCategory
    title: str
    description: Optional[str] = None
    target_value: float
    current_value: float
    unit: str
    frequency: GoalFrequency
    start_date: str
    end_date: Optional[str] = None
    status: GoalStatus
    progress_percentage: float
    streak_days: int = 0
    reminder_time: Optional[str] = None
    reminder_days: List[str] = []
    created_at: datetime
    updated_at: datetime


class GoalProgressLog(BaseModel):
    goal_id: str
    value: float
    notes: Optional[str] = None
    logged_at: Optional[str] = None  # Defaults to now


class DailyWellnessLog(BaseModel):
    date: str
    mood: Optional[int] = Field(None, ge=1, le=5)  # 1-5 scale
    energy_level: Optional[int] = Field(None, ge=1, le=5)
    stress_level: Optional[int] = Field(None, ge=1, le=5)
    sleep_hours: Optional[float] = None
    sleep_quality: Optional[int] = Field(None, ge=1, le=5)
    water_intake_liters: Optional[float] = None
    steps: Optional[int] = None
    exercise_minutes: Optional[int] = None
    meditation_minutes: Optional[int] = None
    notes: Optional[str] = None


class PreventiveScreening(BaseModel):
    id: str
    name: str
    description: str
    category: str  # general, cardiac, cancer, diabetes, etc.
    recommended_frequency: str  # "yearly", "every 2 years", etc.
    recommended_age_start: Optional[int] = None
    recommended_age_end: Optional[int] = None
    gender_specific: Optional[str] = None  # "male", "female", or None for both
    last_done_date: Optional[str] = None
    next_due_date: Optional[str] = None
    status: ScreeningStatus
    risk_factors: List[str] = []
    notes: Optional[str] = None


class HealthRiskAssessment(BaseModel):
    overall_risk_score: float  # 0-100
    risk_level: RiskLevel
    risk_factors: List[dict]
    recommendations: List[str]
    screenings_due: List[str]
    lifestyle_score: float
    last_assessed: datetime


class WellnessTip(BaseModel):
    id: str
    category: str
    title: str
    content: str
    source: Optional[str] = None
    image_url: Optional[str] = None
    is_personalized: bool = False


class WellnessChallenge(BaseModel):
    id: str
    title: str
    description: str
    category: GoalCategory
    duration_days: int
    daily_target: float
    unit: str
    participants_count: int
    start_date: str
    end_date: str
    reward_points: int
    is_joined: bool = False
    user_progress: Optional[float] = None


# ==================== In-Memory Storage ====================

health_goals_db: Dict[int, List[dict]] = {}
goal_progress_db: Dict[str, List[dict]] = {}
wellness_logs_db: Dict[int, Dict[str, dict]] = {}
screenings_db: Dict[int, List[dict]] = {}
challenges_db: List[dict] = []


# ==================== Default Data ====================

DEFAULT_SCREENINGS = [
    {
        "name": "Complete Blood Count (CBC)",
        "description": "Basic blood test to check overall health",
        "category": "general",
        "recommended_frequency": "yearly",
        "recommended_age_start": 18
    },
    {
        "name": "Lipid Profile",
        "description": "Cholesterol and triglyceride levels",
        "category": "cardiac",
        "recommended_frequency": "yearly",
        "recommended_age_start": 20
    },
    {
        "name": "Blood Pressure Check",
        "description": "Monitor for hypertension",
        "category": "cardiac",
        "recommended_frequency": "every 6 months",
        "recommended_age_start": 18
    },
    {
        "name": "Blood Sugar (HbA1c)",
        "description": "Diabetes screening",
        "category": "diabetes",
        "recommended_frequency": "yearly",
        "recommended_age_start": 35
    },
    {
        "name": "Thyroid Function Test",
        "description": "Check thyroid hormone levels",
        "category": "general",
        "recommended_frequency": "every 2 years",
        "recommended_age_start": 35
    },
    {
        "name": "Eye Examination",
        "description": "Vision and eye health check",
        "category": "general",
        "recommended_frequency": "every 2 years",
        "recommended_age_start": 18
    },
    {
        "name": "Dental Checkup",
        "description": "Oral health examination",
        "category": "general",
        "recommended_frequency": "every 6 months",
        "recommended_age_start": 3
    },
    {
        "name": "Mammogram",
        "description": "Breast cancer screening",
        "category": "cancer",
        "recommended_frequency": "yearly",
        "recommended_age_start": 40,
        "gender_specific": "female"
    },
    {
        "name": "Pap Smear",
        "description": "Cervical cancer screening",
        "category": "cancer",
        "recommended_frequency": "every 3 years",
        "recommended_age_start": 21,
        "recommended_age_end": 65,
        "gender_specific": "female"
    },
    {
        "name": "Prostate Screening (PSA)",
        "description": "Prostate cancer screening",
        "category": "cancer",
        "recommended_frequency": "yearly",
        "recommended_age_start": 50,
        "gender_specific": "male"
    },
    {
        "name": "Colonoscopy",
        "description": "Colorectal cancer screening",
        "category": "cancer",
        "recommended_frequency": "every 10 years",
        "recommended_age_start": 45
    },
    {
        "name": "Bone Density Test",
        "description": "Osteoporosis screening",
        "category": "general",
        "recommended_frequency": "every 2 years",
        "recommended_age_start": 65
    },
    {
        "name": "ECG/EKG",
        "description": "Heart rhythm check",
        "category": "cardiac",
        "recommended_frequency": "yearly",
        "recommended_age_start": 40
    },
    {
        "name": "Vitamin D Test",
        "description": "Check vitamin D levels",
        "category": "general",
        "recommended_frequency": "yearly",
        "recommended_age_start": 18
    }
]

WELLNESS_TIPS = [
    {
        "category": "nutrition",
        "title": "Eat More Colorful Vegetables",
        "content": "Try to include vegetables of different colors in your meals. Each color provides different nutrients and antioxidants."
    },
    {
        "category": "exercise",
        "title": "Take Walking Breaks",
        "content": "If you sit for long hours, take a 5-minute walking break every hour to improve circulation and reduce back pain."
    },
    {
        "category": "sleep",
        "title": "Maintain Sleep Schedule",
        "content": "Go to bed and wake up at the same time every day, even on weekends, to regulate your body's internal clock."
    },
    {
        "category": "hydration",
        "title": "Start Your Day with Water",
        "content": "Drink a glass of water first thing in the morning to kickstart your metabolism and hydrate your body."
    },
    {
        "category": "mental_health",
        "title": "Practice Gratitude",
        "content": "Write down 3 things you're grateful for each day. This simple practice can significantly improve your mental well-being."
    },
    {
        "category": "stress",
        "title": "Deep Breathing Exercise",
        "content": "When stressed, try the 4-7-8 breathing technique: inhale for 4 seconds, hold for 7, exhale for 8 seconds."
    }
]


# ==================== Health Goals Endpoints ====================

@router.get("/goals", response_model=List[HealthGoal])
async def get_health_goals(
    status: Optional[GoalStatus] = None,
    category: Optional[GoalCategory] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get all health goals for current user"""
    user_goals = health_goals_db.get(current_user.id, [])
    
    if status:
        user_goals = [g for g in user_goals if g["status"] == status]
    
    if category:
        user_goals = [g for g in user_goals if g["category"] == category]
    
    # Calculate progress percentage
    for goal in user_goals:
        if goal["target_value"] > 0:
            goal["progress_percentage"] = min(100, (goal["current_value"] / goal["target_value"]) * 100)
        else:
            goal["progress_percentage"] = 0
    
    return user_goals


@router.post("/goals", response_model=HealthGoal)
async def create_health_goal(
    goal_data: HealthGoalCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create a new health goal"""
    now = datetime.utcnow()
    
    progress = 0
    if goal_data.target_value > 0:
        progress = min(100, (goal_data.current_value / goal_data.target_value) * 100)
    
    goal = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "category": goal_data.category,
        "title": goal_data.title,
        "description": goal_data.description,
        "target_value": goal_data.target_value,
        "current_value": goal_data.current_value,
        "unit": goal_data.unit,
        "frequency": goal_data.frequency,
        "start_date": goal_data.start_date,
        "end_date": goal_data.end_date,
        "status": GoalStatus.ACTIVE,
        "progress_percentage": progress,
        "streak_days": 0,
        "reminder_time": goal_data.reminder_time,
        "reminder_days": goal_data.reminder_days,
        "created_at": now,
        "updated_at": now
    }
    
    if current_user.id not in health_goals_db:
        health_goals_db[current_user.id] = []
    
    health_goals_db[current_user.id].append(goal)
    
    return goal


@router.get("/goals/{goal_id}", response_model=HealthGoal)
async def get_health_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get a specific health goal"""
    user_goals = health_goals_db.get(current_user.id, [])
    
    for goal in user_goals:
        if goal["id"] == goal_id:
            if goal["target_value"] > 0:
                goal["progress_percentage"] = min(100, (goal["current_value"] / goal["target_value"]) * 100)
            return goal
    
    raise HTTPException(status_code=404, detail="Goal not found")


@router.put("/goals/{goal_id}", response_model=HealthGoal)
async def update_health_goal(
    goal_id: str,
    goal_data: HealthGoalUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update a health goal"""
    user_goals = health_goals_db.get(current_user.id, [])
    
    for i, goal in enumerate(user_goals):
        if goal["id"] == goal_id:
            update_data = goal_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                goal[key] = value
            goal["updated_at"] = datetime.utcnow()
            
            if goal["target_value"] > 0:
                goal["progress_percentage"] = min(100, (goal["current_value"] / goal["target_value"]) * 100)
            
            # Check if goal is completed
            if goal["current_value"] >= goal["target_value"]:
                goal["status"] = GoalStatus.COMPLETED
            
            health_goals_db[current_user.id][i] = goal
            return goal
    
    raise HTTPException(status_code=404, detail="Goal not found")


@router.delete("/goals/{goal_id}")
async def delete_health_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Delete a health goal"""
    user_goals = health_goals_db.get(current_user.id, [])
    
    for i, goal in enumerate(user_goals):
        if goal["id"] == goal_id:
            health_goals_db[current_user.id].pop(i)
            return {"message": "Goal deleted successfully"}
    
    raise HTTPException(status_code=404, detail="Goal not found")


@router.post("/goals/{goal_id}/log-progress")
async def log_goal_progress(
    goal_id: str,
    progress: GoalProgressLog,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Log progress for a health goal"""
    user_goals = health_goals_db.get(current_user.id, [])
    
    for goal in user_goals:
        if goal["id"] == goal_id:
            # Update current value
            goal["current_value"] += progress.value
            goal["updated_at"] = datetime.utcnow()
            
            # Update progress percentage
            if goal["target_value"] > 0:
                goal["progress_percentage"] = min(100, (goal["current_value"] / goal["target_value"]) * 100)
            
            # Check completion
            if goal["current_value"] >= goal["target_value"]:
                goal["status"] = GoalStatus.COMPLETED
            
            # Log the progress entry
            if goal_id not in goal_progress_db:
                goal_progress_db[goal_id] = []
            
            goal_progress_db[goal_id].append({
                "value": progress.value,
                "notes": progress.notes,
                "logged_at": progress.logged_at or datetime.utcnow().isoformat()
            })
            
            # Update streak
            goal["streak_days"] = goal.get("streak_days", 0) + 1
            
            return {
                "message": "Progress logged successfully",
                "current_value": goal["current_value"],
                "progress_percentage": goal["progress_percentage"],
                "streak_days": goal["streak_days"]
            }
    
    raise HTTPException(status_code=404, detail="Goal not found")


@router.get("/goals/{goal_id}/history")
async def get_goal_progress_history(
    goal_id: str,
    days: int = 30,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get progress history for a goal"""
    return {
        "goal_id": goal_id,
        "history": goal_progress_db.get(goal_id, [])
    }


# ==================== Daily Wellness Log ====================

@router.post("/daily-log")
async def log_daily_wellness(
    log_data: DailyWellnessLog,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Log daily wellness data"""
    if current_user.id not in wellness_logs_db:
        wellness_logs_db[current_user.id] = {}
    
    log_entry = log_data.model_dump()
    log_entry["logged_at"] = datetime.utcnow().isoformat()
    
    wellness_logs_db[current_user.id][log_data.date] = log_entry
    
    return {"message": "Wellness log saved successfully", "date": log_data.date}


@router.get("/daily-log/{date_str}")
async def get_daily_wellness_log(
    date_str: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get wellness log for a specific date"""
    user_logs = wellness_logs_db.get(current_user.id, {})
    
    if date_str in user_logs:
        return user_logs[date_str]
    
    return {
        "date": date_str,
        "mood": None,
        "energy_level": None,
        "stress_level": None,
        "sleep_hours": None,
        "sleep_quality": None,
        "water_intake_liters": None,
        "steps": None,
        "exercise_minutes": None,
        "meditation_minutes": None,
        "notes": None
    }


@router.get("/daily-log/range/{start_date}/{end_date}")
async def get_wellness_log_range(
    start_date: str,
    end_date: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get wellness logs for a date range"""
    user_logs = wellness_logs_db.get(current_user.id, {})
    
    logs = []
    for date_str, log in user_logs.items():
        if start_date <= date_str <= end_date:
            logs.append(log)
    
    return {"logs": sorted(logs, key=lambda x: x["date"])}


@router.get("/wellness-stats")
async def get_wellness_stats(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get wellness statistics for the past N days"""
    user_logs = wellness_logs_db.get(current_user.id, {})
    
    # Calculate averages
    total_logs = len(user_logs)
    
    if total_logs == 0:
        return {
            "days_logged": 0,
            "avg_mood": None,
            "avg_energy": None,
            "avg_stress": None,
            "avg_sleep_hours": None,
            "avg_sleep_quality": None,
            "total_steps": 0,
            "total_exercise_minutes": 0,
            "avg_water_intake": None
        }
    
    moods = [l["mood"] for l in user_logs.values() if l.get("mood")]
    energies = [l["energy_level"] for l in user_logs.values() if l.get("energy_level")]
    stresses = [l["stress_level"] for l in user_logs.values() if l.get("stress_level")]
    sleep_hours = [l["sleep_hours"] for l in user_logs.values() if l.get("sleep_hours")]
    sleep_quality = [l["sleep_quality"] for l in user_logs.values() if l.get("sleep_quality")]
    steps = [l["steps"] for l in user_logs.values() if l.get("steps")]
    exercise = [l["exercise_minutes"] for l in user_logs.values() if l.get("exercise_minutes")]
    water = [l["water_intake_liters"] for l in user_logs.values() if l.get("water_intake_liters")]
    
    return {
        "days_logged": total_logs,
        "avg_mood": sum(moods) / len(moods) if moods else None,
        "avg_energy": sum(energies) / len(energies) if energies else None,
        "avg_stress": sum(stresses) / len(stresses) if stresses else None,
        "avg_sleep_hours": sum(sleep_hours) / len(sleep_hours) if sleep_hours else None,
        "avg_sleep_quality": sum(sleep_quality) / len(sleep_quality) if sleep_quality else None,
        "total_steps": sum(steps),
        "total_exercise_minutes": sum(exercise),
        "avg_water_intake": sum(water) / len(water) if water else None
    }


# ==================== Preventive Screenings ====================

@router.get("/screenings", response_model=List[PreventiveScreening])
async def get_preventive_screenings(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get recommended preventive screenings"""
    # Initialize user screenings if not exists
    if current_user.id not in screenings_db:
        screenings_db[current_user.id] = []
        
        # Add default screenings
        for screening in DEFAULT_SCREENINGS:
            screenings_db[current_user.id].append({
                "id": str(uuid.uuid4()),
                **screening,
                "last_done_date": None,
                "next_due_date": None,
                "status": ScreeningStatus.DUE,
                "risk_factors": [],
                "notes": None
            })
    
    user_screenings = screenings_db[current_user.id]
    
    if category:
        user_screenings = [s for s in user_screenings if s["category"] == category]
    
    return user_screenings


@router.put("/screenings/{screening_id}")
async def update_screening(
    screening_id: str,
    last_done_date: Optional[str] = None,
    next_due_date: Optional[str] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update a screening record"""
    user_screenings = screenings_db.get(current_user.id, [])
    
    for screening in user_screenings:
        if screening["id"] == screening_id:
            if last_done_date:
                screening["last_done_date"] = last_done_date
                screening["status"] = ScreeningStatus.COMPLETED
            if next_due_date:
                screening["next_due_date"] = next_due_date
            if notes:
                screening["notes"] = notes
            
            return {"message": "Screening updated", "screening": screening}
    
    raise HTTPException(status_code=404, detail="Screening not found")


@router.get("/screenings/due")
async def get_due_screenings(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get screenings that are due or overdue"""
    user_screenings = screenings_db.get(current_user.id, [])
    
    due_screenings = [
        s for s in user_screenings 
        if s["status"] in [ScreeningStatus.DUE, ScreeningStatus.OVERDUE]
    ]
    
    return {"due_screenings": due_screenings, "count": len(due_screenings)}


# ==================== Health Risk Assessment ====================

@router.get("/risk-assessment", response_model=HealthRiskAssessment)
async def get_health_risk_assessment(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get personalized health risk assessment"""
    # Get user's wellness logs
    user_logs = wellness_logs_db.get(current_user.id, {})
    user_screenings = screenings_db.get(current_user.id, [])
    
    risk_factors = []
    recommendations = []
    
    # Analyze wellness data
    if user_logs:
        recent_logs = list(user_logs.values())[-7:]  # Last 7 days
        
        avg_sleep = sum(l.get("sleep_hours", 7) for l in recent_logs) / len(recent_logs)
        avg_stress = sum(l.get("stress_level", 3) for l in recent_logs) / len(recent_logs)
        
        if avg_sleep < 6:
            risk_factors.append({
                "factor": "Inadequate Sleep",
                "severity": "moderate",
                "description": f"Average sleep of {avg_sleep:.1f} hours is below recommended 7-8 hours"
            })
            recommendations.append("Aim for 7-8 hours of sleep each night")
        
        if avg_stress > 3.5:
            risk_factors.append({
                "factor": "High Stress",
                "severity": "moderate",
                "description": "Your stress levels are above average"
            })
            recommendations.append("Consider stress management techniques like meditation")
    
    # Check overdue screenings
    screenings_due = []
    for screening in user_screenings:
        if screening["status"] in [ScreeningStatus.DUE, ScreeningStatus.OVERDUE]:
            screenings_due.append(screening["name"])
    
    if screenings_due:
        risk_factors.append({
            "factor": "Overdue Screenings",
            "severity": "low",
            "description": f"{len(screenings_due)} preventive screenings are due"
        })
        recommendations.append("Schedule your overdue health screenings")
    
    # Calculate overall risk score
    risk_score = min(100, len(risk_factors) * 15 + 20)
    
    risk_level = RiskLevel.LOW
    if risk_score > 60:
        risk_level = RiskLevel.HIGH
    elif risk_score > 40:
        risk_level = RiskLevel.MODERATE
    
    # Calculate lifestyle score
    lifestyle_score = max(0, 100 - risk_score)
    
    return HealthRiskAssessment(
        overall_risk_score=risk_score,
        risk_level=risk_level,
        risk_factors=risk_factors,
        recommendations=recommendations,
        screenings_due=screenings_due,
        lifestyle_score=lifestyle_score,
        last_assessed=datetime.utcnow()
    )


# ==================== Wellness Tips ====================

@router.get("/tips", response_model=List[WellnessTip])
async def get_wellness_tips(
    category: Optional[str] = None,
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get personalized wellness tips"""
    tips = WELLNESS_TIPS.copy()
    
    if category:
        tips = [t for t in tips if t["category"] == category]
    
    # Add IDs and shuffle
    result = []
    for i, tip in enumerate(tips[:limit]):
        result.append(WellnessTip(
            id=str(i + 1),
            category=tip["category"],
            title=tip["title"],
            content=tip["content"],
            source=tip.get("source"),
            image_url=tip.get("image_url"),
            is_personalized=False
        ))
    
    random.shuffle(result)
    return result[:limit]


@router.get("/tip-of-the-day", response_model=WellnessTip)
async def get_tip_of_the_day(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get the tip of the day"""
    # Use date to get consistent tip for the day
    day_index = date.today().toordinal() % len(WELLNESS_TIPS)
    tip = WELLNESS_TIPS[day_index]
    
    return WellnessTip(
        id=str(day_index),
        category=tip["category"],
        title=tip["title"],
        content=tip["content"],
        is_personalized=True
    )


# ==================== Wellness Challenges ====================

@router.get("/challenges", response_model=List[WellnessChallenge])
async def get_wellness_challenges(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get available wellness challenges"""
    # Sample challenges
    today = date.today()
    
    challenges = [
        WellnessChallenge(
            id="1",
            title="10K Steps Challenge",
            description="Walk 10,000 steps every day for a week",
            category=GoalCategory.STEPS,
            duration_days=7,
            daily_target=10000,
            unit="steps",
            participants_count=1250,
            start_date=today.isoformat(),
            end_date=(today + timedelta(days=7)).isoformat(),
            reward_points=100,
            is_joined=False
        ),
        WellnessChallenge(
            id="2",
            title="Hydration Hero",
            description="Drink 3 liters of water daily for 5 days",
            category=GoalCategory.HYDRATION,
            duration_days=5,
            daily_target=3,
            unit="liters",
            participants_count=890,
            start_date=today.isoformat(),
            end_date=(today + timedelta(days=5)).isoformat(),
            reward_points=75,
            is_joined=False
        ),
        WellnessChallenge(
            id="3",
            title="Mindfulness Month",
            description="Meditate for 10 minutes every day",
            category=GoalCategory.MEDITATION,
            duration_days=30,
            daily_target=10,
            unit="minutes",
            participants_count=2100,
            start_date=today.isoformat(),
            end_date=(today + timedelta(days=30)).isoformat(),
            reward_points=200,
            is_joined=False
        ),
        WellnessChallenge(
            id="4",
            title="Sleep Better Week",
            description="Get 7+ hours of sleep for 7 consecutive nights",
            category=GoalCategory.SLEEP,
            duration_days=7,
            daily_target=7,
            unit="hours",
            participants_count=1580,
            start_date=today.isoformat(),
            end_date=(today + timedelta(days=7)).isoformat(),
            reward_points=100,
            is_joined=False
        )
    ]
    
    return challenges


@router.post("/challenges/{challenge_id}/join")
async def join_challenge(
    challenge_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Join a wellness challenge"""
    return {
        "message": "Successfully joined the challenge!",
        "challenge_id": challenge_id,
        "start_date": date.today().isoformat()
    }


@router.post("/challenges/{challenge_id}/log")
async def log_challenge_progress(
    challenge_id: str,
    value: float,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Log progress for a challenge"""
    return {
        "message": "Progress logged",
        "challenge_id": challenge_id,
        "value": value,
        "logged_at": datetime.utcnow().isoformat()
    }


# ==================== Wellness Dashboard ====================

@router.get("/dashboard")
async def get_wellness_dashboard(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get comprehensive wellness dashboard"""
    user_goals = health_goals_db.get(current_user.id, [])
    user_logs = wellness_logs_db.get(current_user.id, {})
    user_screenings = screenings_db.get(current_user.id, [])
    
    # Today's log
    today = date.today().isoformat()
    today_log = user_logs.get(today, {})
    
    # Active goals
    active_goals = [g for g in user_goals if g.get("status") == GoalStatus.ACTIVE]
    
    # Due screenings
    due_screenings = [s for s in user_screenings if s.get("status") in [ScreeningStatus.DUE, ScreeningStatus.OVERDUE]]
    
    # Calculate streak
    streak = 0
    check_date = date.today()
    while check_date.isoformat() in user_logs:
        streak += 1
        check_date -= timedelta(days=1)
    
    return {
        "today_log": today_log,
        "logging_streak": streak,
        "active_goals_count": len(active_goals),
        "active_goals": active_goals[:3],  # Top 3
        "due_screenings_count": len(due_screenings),
        "due_screenings": due_screenings[:3],
        "tip_of_the_day": WELLNESS_TIPS[date.today().toordinal() % len(WELLNESS_TIPS)],
        "wellness_score": max(0, 100 - len(due_screenings) * 5)
    }
