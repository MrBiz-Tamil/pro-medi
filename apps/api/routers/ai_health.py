from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import uuid
import json

from database import get_session
from models import (
    User, DoctorProfile,
    SymptomCheck, AIConversation, AIMessage, HealthRecommendation,
    WellnessRecommendation, CommonSymptom,
    UrgencyLevel, RecommendationType, SymptomSeverity, AIMessageRole
)
from dependencies import get_current_user

# Import enhanced AI chat response generator directly
from services.ai_chat_data import generate_ai_response, get_specialist_for_symptom

router = APIRouter(prefix="/api/ai", tags=["ai-health"])


# ==================== PYDANTIC SCHEMAS ====================

class SymptomCheckRequest(BaseModel):
    primary_symptom: str
    symptoms: List[str]
    duration: str
    severity: str = "moderate"
    additional_notes: Optional[str] = None

class SymptomCheckResponse(BaseModel):
    id: int
    session_id: str
    primary_symptom: str
    symptoms: List[str]
    urgency_level: str
    ai_assessment: str
    recommended_specialization: Optional[str]
    recommendations: List[Dict[str, Any]]
    created_at: datetime

class ChatMessageRequest(BaseModel):
    session_id: Optional[str] = None
    message: str

class ChatMessageResponse(BaseModel):
    session_id: str
    message: str
    response: str
    urgency_detected: Optional[str] = None
    suggestions: List[str] = []

class RecommendationResponse(BaseModel):
    id: int
    recommendation_type: str
    title: str
    details: str
    instructions: Optional[str]
    warnings: Optional[str]
    specialization: Optional[str]
    follow_up_required: bool
    created_at: datetime

class DoctorRouteRequest(BaseModel):
    symptom_check_id: Optional[int] = None
    conversation_id: Optional[int] = None
    specialization: Optional[str] = None
    urgency_level: Optional[str] = None

class DoctorRouteResponse(BaseModel):
    recommended_doctors: List[Dict[str, Any]]
    specialization: str
    urgency_level: str
    appointment_suggestion: str

class WellnessRecommendationResponse(BaseModel):
    id: int
    wellness_type: str
    category: str
    title: str
    description: str
    benefits: Optional[str]
    dosage_or_duration: Optional[str]
    precautions: Optional[str]

class CommonSymptomResponse(BaseModel):
    id: int
    name: str
    category: str
    description: Optional[str]
    common_causes: Optional[List[str]]
    associated_symptoms: Optional[List[str]]


# ==================== AI SIMULATION FUNCTIONS ====================

def analyze_symptoms(symptoms: List[str], severity: str, duration: str) -> Dict[str, Any]:
    """
    Simulate AI symptom analysis.
    In production, this would call an actual AI model (GPT-4, Claude, custom model).
    """
    # Map common symptoms to urgency and specializations
    symptom_mapping = {
        "chest pain": {"urgency": "emergency", "specialty": "Cardiology", "emergency_if": "radiating to arm or jaw"},
        "severe headache": {"urgency": "high", "specialty": "Neurology", "emergency_if": "sudden onset, worst ever"},
        "shortness of breath": {"urgency": "high", "specialty": "Pulmonology", "emergency_if": "at rest or severe"},
        "fever": {"urgency": "moderate", "specialty": "General Medicine", "emergency_if": "above 104°F or with confusion"},
        "abdominal pain": {"urgency": "moderate", "specialty": "Gastroenterology", "emergency_if": "severe with rigidity"},
        "skin rash": {"urgency": "low", "specialty": "Dermatology"},
        "joint pain": {"urgency": "low", "specialty": "Orthopedics"},
        "anxiety": {"urgency": "low", "specialty": "Psychiatry"},
        "fatigue": {"urgency": "low", "specialty": "General Medicine"},
        "cough": {"urgency": "low", "specialty": "Pulmonology"},
        "dizziness": {"urgency": "moderate", "specialty": "ENT"},
        "nausea": {"urgency": "low", "specialty": "Gastroenterology"},
        "back pain": {"urgency": "low", "specialty": "Orthopedics"},
        "sore throat": {"urgency": "low", "specialty": "ENT"},
        "eye irritation": {"urgency": "low", "specialty": "Ophthalmology"},
    }
    
    # Determine urgency based on symptoms and severity
    max_urgency = "low"
    recommended_specialty = "General Medicine"
    urgency_order = ["low", "moderate", "high", "emergency"]
    
    for symptom in symptoms:
        symptom_lower = symptom.lower()
        for key, info in symptom_mapping.items():
            if key in symptom_lower:
                symptom_urgency = info["urgency"]
                if urgency_order.index(symptom_urgency) > urgency_order.index(max_urgency):
                    max_urgency = symptom_urgency
                    recommended_specialty = info["specialty"]
                break
    
    # Adjust urgency based on severity
    if severity == "severe" and max_urgency in ["low", "moderate"]:
        max_urgency = "high" if max_urgency == "moderate" else "moderate"
    
    # Generate assessment
    assessment_templates = {
        "emergency": f"⚠️ URGENT: Your symptoms ({', '.join(symptoms)}) require immediate medical attention. Please visit the nearest emergency room or call emergency services immediately.",
        "high": f"Your symptoms ({', '.join(symptoms)}) suggest you should see a doctor today. I recommend consulting a {recommended_specialty} specialist as soon as possible.",
        "moderate": f"Based on your symptoms ({', '.join(symptoms)}), I recommend scheduling an appointment with a {recommended_specialty} specialist within the next few days.",
        "low": f"Your symptoms ({', '.join(symptoms)}) appear to be manageable. Self-care measures may help, but consider consulting a {recommended_specialty} specialist if symptoms persist or worsen."
    }
    
    return {
        "urgency_level": max_urgency,
        "recommended_specialization": recommended_specialty,
        "assessment": assessment_templates[max_urgency],
        "confidence": 0.85
    }


def generate_recommendations(symptoms: List[str], urgency: str, specialty: str) -> List[Dict[str, Any]]:
    """Generate health recommendations based on symptoms"""
    recommendations = []
    
    # Self-care recommendations
    self_care_tips = {
        "fever": ["Rest and stay hydrated", "Take over-the-counter fever reducers as directed", "Monitor temperature regularly"],
        "headache": ["Rest in a quiet, dark room", "Stay hydrated", "Apply cold or warm compress to forehead"],
        "cough": ["Stay hydrated with warm fluids", "Use honey to soothe throat", "Consider using a humidifier"],
        "fatigue": ["Ensure adequate sleep (7-9 hours)", "Stay hydrated", "Consider stress management techniques"],
        "nausea": ["Eat small, bland meals", "Stay hydrated with clear fluids", "Avoid strong odors"],
        "back pain": ["Apply ice or heat", "Gentle stretching exercises", "Maintain good posture"],
    }
    
    for symptom in symptoms:
        symptom_lower = symptom.lower()
        for key, tips in self_care_tips.items():
            if key in symptom_lower:
                recommendations.append({
                    "type": "self_care",
                    "title": f"Self-Care for {symptom}",
                    "details": "; ".join(tips),
                    "warning": "Seek medical attention if symptoms worsen"
                })
                break
    
    # Add specialist recommendation if needed
    if urgency in ["moderate", "high", "emergency"]:
        recommendations.append({
            "type": "specialist" if urgency != "emergency" else "emergency",
            "title": f"Consult a {specialty} Specialist",
            "details": f"Based on your symptoms, I recommend consulting a {specialty} specialist for proper evaluation and treatment.",
            "warning": "Do not delay medical consultation" if urgency == "high" else None
        })
    
    return recommendations


def generate_chat_response(message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
    """
    Generate AI chat response using the enhanced AI chat data module.
    Uses comprehensive pattern matching for healthcare conversations.
    """
    # Use the enhanced AI response generator from services
    return generate_ai_response(message, conversation_history)


def get_siddha_recommendations(symptoms: List[str] = None, condition: str = None) -> List[Dict[str, Any]]:
    """Get traditional Siddha medicine recommendations"""
    recommendations = [
        {
            "wellness_type": "siddha",
            "category": "herbal",
            "title": "Nilavembu Kudineer",
            "description": "A traditional Siddha decoction effective for fever, body pain, and viral infections. Made from 9 herbs including Nilavembu (Andrographis paniculata).",
            "benefits": "Antipyretic, anti-inflammatory, immunity boosting",
            "dosage_or_duration": "50ml twice daily before food for 7 days",
            "precautions": "Not recommended during pregnancy. Consult a Siddha practitioner for chronic conditions.",
            "traditional_reference": "Siddha Maruthuvam"
        },
        {
            "wellness_type": "siddha",
            "category": "diet",
            "title": "Pathiya Sapadu (Diet Regimen)",
            "description": "Traditional dietary guidelines for healing. Emphasis on easily digestible foods, warm soups, and specific foods based on body constitution (thathu).",
            "benefits": "Supports digestion, promotes healing, balances body elements",
            "dosage_or_duration": "Follow during illness and recovery period",
            "precautions": "Avoid incompatible food combinations. Eat fresh, warm food.",
            "traditional_reference": "Theraiyar Gunam"
        },
        {
            "wellness_type": "varma",
            "category": "therapy",
            "title": "Varma Therapy Points",
            "description": "Ancient Tamil healing art using vital energy points. Effective for pain management, nerve issues, and energy imbalances.",
            "benefits": "Pain relief, improved circulation, energy balance",
            "dosage_or_duration": "Sessions with trained Varma practitioner",
            "precautions": "Must be performed by trained practitioner only. Not for acute injuries.",
            "traditional_reference": "Varma Cuttiram"
        },
        {
            "wellness_type": "siddha",
            "category": "lifestyle",
            "title": "Pranayama & Yoga Asanas",
            "description": "Siddha-recommended breathing exercises and yoga postures for overall wellness. Includes Nadi Shodhana, Kapalabhati, and specific asanas.",
            "benefits": "Stress reduction, improved breathing, mental clarity",
            "dosage_or_duration": "15-30 minutes daily, preferably morning",
            "precautions": "Start slowly, avoid strain. Consult doctor if you have respiratory conditions.",
            "traditional_reference": "Thirumoolar Thirumanthiram"
        },
        {
            "wellness_type": "siddha",
            "category": "herbal",
            "title": "Thippili Rasayanam",
            "description": "A rejuvenating preparation made with long pepper (Thippili). Used for respiratory health and immune support.",
            "benefits": "Respiratory health, immunity boost, anti-aging",
            "dosage_or_duration": "As prescribed by Siddha practitioner",
            "precautions": "Not for those with gastric issues. Avoid during acute fever.",
            "traditional_reference": "Agathiyar Gunavagadam"
        }
    ]
    
    return recommendations


# ==================== API ENDPOINTS ====================

@router.post("/symptom-check", response_model=SymptomCheckResponse)
async def submit_symptom_check(
    request: SymptomCheckRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Submit symptoms for AI analysis"""
    session_id = str(uuid.uuid4())
    
    # Analyze symptoms
    analysis = analyze_symptoms(
        request.symptoms,
        request.severity,
        request.duration
    )
    
    # Create symptom check record
    symptom_check = SymptomCheck(
        patient_id=current_user.id,
        session_id=session_id,
        primary_symptom=request.primary_symptom,
        symptoms=json.dumps(request.symptoms),
        duration=request.duration,
        severity=SymptomSeverity(request.severity),
        additional_notes=request.additional_notes,
        ai_assessment=analysis["assessment"],
        urgency_level=UrgencyLevel(analysis["urgency_level"]),
        recommended_specialization=analysis["recommended_specialization"],
        confidence_score=analysis["confidence"]
    )
    
    session.add(symptom_check)
    session.commit()
    session.refresh(symptom_check)
    
    # Generate recommendations
    recommendations = generate_recommendations(
        request.symptoms,
        analysis["urgency_level"],
        analysis["recommended_specialization"]
    )
    
    # Store recommendations
    for rec in recommendations:
        db_rec = HealthRecommendation(
            patient_id=current_user.id,
            symptom_check_id=symptom_check.id,
            recommendation_type=RecommendationType(rec["type"]),
            title=rec["title"],
            details=rec["details"],
            warnings=rec.get("warning"),
            specialization=analysis["recommended_specialization"],
            follow_up_required=analysis["urgency_level"] in ["high", "emergency"]
        )
        session.add(db_rec)
    
    session.commit()
    
    return SymptomCheckResponse(
        id=symptom_check.id,
        session_id=session_id,
        primary_symptom=request.primary_symptom,
        symptoms=request.symptoms,
        urgency_level=analysis["urgency_level"],
        ai_assessment=analysis["assessment"],
        recommended_specialization=analysis["recommended_specialization"],
        recommendations=recommendations,
        created_at=symptom_check.created_at
    )


@router.post("/chat", response_model=ChatMessageResponse)
async def chat_with_ai(
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Chat with AI health assistant"""
    # Get or create conversation
    if request.session_id:
        conversation = session.query(AIConversation).filter(
            AIConversation.session_id == request.session_id,
            AIConversation.patient_id == current_user.id
        ).first()
    else:
        conversation = None
    
    if not conversation:
        session_id = str(uuid.uuid4())
        conversation = AIConversation(
            patient_id=current_user.id,
            session_id=session_id,
            title="Health Consultation",
            is_active=True
        )
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
    
    # Store user message
    user_message = AIMessage(
        conversation_id=conversation.id,
        role=AIMessageRole.USER,
        content=request.message
    )
    session.add(user_message)
    
    # Get conversation history for context
    history = session.query(AIMessage).filter(
        AIMessage.conversation_id == conversation.id
    ).order_by(AIMessage.timestamp.desc()).limit(10).all()
    
    # Generate AI response
    ai_response = generate_chat_response(
        request.message,
        [{"role": m.role, "content": m.content} for m in reversed(history)]
    )
    
    # Store AI response
    assistant_message = AIMessage(
        conversation_id=conversation.id,
        role=AIMessageRole.ASSISTANT,
        content=ai_response["response"]
    )
    session.add(assistant_message)
    
    # Update conversation
    conversation.message_count += 2
    conversation.last_message_at = datetime.utcnow()
    conversation.updated_at = datetime.utcnow()
    
    # If emergency detected, escalate
    if ai_response.get("urgency_detected") == "emergency":
        conversation.is_escalated = True
    
    session.commit()
    
    return ChatMessageResponse(
        session_id=conversation.session_id,
        message=request.message,
        response=ai_response["response"],
        urgency_detected=ai_response.get("urgency_detected"),
        suggestions=ai_response.get("suggestions", [])
    )


@router.get("/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get chat history for a session"""
    conversation = session.query(AIConversation).filter(
        AIConversation.session_id == session_id,
        AIConversation.patient_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = session.query(AIMessage).filter(
        AIMessage.conversation_id == conversation.id
    ).order_by(AIMessage.timestamp.asc()).all()
    
    return {
        "session_id": session_id,
        "title": conversation.title,
        "messages": [{
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp.isoformat()
        } for m in messages],
        "created_at": conversation.created_at.isoformat(),
        "is_escalated": conversation.is_escalated
    }


@router.get("/chat/sessions")
async def get_chat_sessions(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get user's chat sessions"""
    conversations = session.query(AIConversation).filter(
        AIConversation.patient_id == current_user.id
    ).order_by(AIConversation.updated_at.desc()).offset(offset).limit(limit).all()
    
    return [{
        "session_id": c.session_id,
        "title": c.title or "Health Consultation",
        "summary": c.summary,
        "message_count": c.message_count,
        "is_escalated": c.is_escalated,
        "action_taken": c.action_taken,
        "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        "created_at": c.created_at.isoformat()
    } for c in conversations]


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(
    recommendation_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get a specific health recommendation"""
    recommendation = session.query(HealthRecommendation).filter(
        HealthRecommendation.id == recommendation_id,
        HealthRecommendation.patient_id == current_user.id
    ).first()
    
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    
    return RecommendationResponse(
        id=recommendation.id,
        recommendation_type=recommendation.recommendation_type,
        title=recommendation.title,
        details=recommendation.details,
        instructions=recommendation.instructions,
        warnings=recommendation.warnings,
        specialization=recommendation.specialization,
        follow_up_required=recommendation.follow_up_required,
        created_at=recommendation.created_at
    )


@router.get("/recommendations")
async def get_my_recommendations(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get user's health recommendations"""
    recommendations = session.query(HealthRecommendation).filter(
        HealthRecommendation.patient_id == current_user.id
    ).order_by(HealthRecommendation.created_at.desc()).limit(limit).all()
    
    return [{
        "id": r.id,
        "recommendation_type": r.recommendation_type,
        "title": r.title,
        "details": r.details,
        "specialization": r.specialization,
        "follow_up_required": r.follow_up_required,
        "is_acknowledged": r.is_acknowledged,
        "created_at": r.created_at.isoformat()
    } for r in recommendations]


@router.post("/route-to-doctor", response_model=DoctorRouteResponse)
async def route_to_doctor(
    request: DoctorRouteRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Route patient to appropriate doctor based on symptoms"""
    specialization = request.specialization
    urgency = request.urgency_level or "moderate"
    
    # If symptom check provided, get specialization from it
    if request.symptom_check_id:
        symptom_check = session.query(SymptomCheck).filter(
            SymptomCheck.id == request.symptom_check_id
        ).first()
        if symptom_check:
            specialization = specialization or symptom_check.recommended_specialization
            urgency = symptom_check.urgency_level or urgency
    
    # Default to general medicine
    if not specialization:
        specialization = "General Medicine"
    
    # Find matching doctors
    doctors = session.query(User, DoctorProfile).join(
        DoctorProfile, User.id == DoctorProfile.user_id
    ).filter(
        User.role == "doctor",
        User.is_active == True,
        DoctorProfile.is_verified == True
    ).all()
    
    # Filter by specialization (partial match)
    matching_doctors = []
    for user, profile in doctors:
        if specialization.lower() in profile.specialization.lower():
            matching_doctors.append({
                "id": user.id,
                "name": user.full_name,
                "specialization": profile.specialization,
                "experience_years": profile.years_of_experience,
                "consultation_fee": profile.consultation_fee,
                "is_online": profile.is_online,
                "qualification": profile.qualification
            })
    
    # Sort by online status and experience
    matching_doctors.sort(key=lambda d: (-d["is_online"], -d["experience_years"]))
    
    # Generate appointment suggestion based on urgency
    appointment_suggestions = {
        "emergency": "Please visit the nearest emergency room immediately or book an emergency consultation now.",
        "high": "We recommend booking a same-day appointment with one of these specialists.",
        "moderate": "You can schedule an appointment within the next 2-3 days.",
        "low": "You can book a convenient appointment at your preferred time."
    }
    
    return DoctorRouteResponse(
        recommended_doctors=matching_doctors[:5],  # Top 5 matches
        specialization=specialization,
        urgency_level=urgency,
        appointment_suggestion=appointment_suggestions.get(urgency, appointment_suggestions["moderate"])
    )


@router.get("/wellness/siddha")
async def get_siddha_wellness(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get Siddha/traditional wellness recommendations"""
    recommendations = get_siddha_recommendations()
    
    if category:
        recommendations = [r for r in recommendations if r["category"] == category]
    
    # Store recommendations for the user
    for rec in recommendations:
        existing = session.query(WellnessRecommendation).filter(
            WellnessRecommendation.patient_id == current_user.id,
            WellnessRecommendation.title == rec["title"]
        ).first()
        
        if not existing:
            wellness_rec = WellnessRecommendation(
                patient_id=current_user.id,
                wellness_type=rec["wellness_type"],
                category=rec["category"],
                title=rec["title"],
                description=rec["description"],
                benefits=rec.get("benefits"),
                dosage_or_duration=rec.get("dosage_or_duration"),
                precautions=rec.get("precautions"),
                traditional_reference=rec.get("traditional_reference")
            )
            session.add(wellness_rec)
    
    session.commit()
    
    return {
        "wellness_type": "siddha",
        "recommendations": recommendations,
        "categories": ["herbal", "diet", "lifestyle", "therapy"]
    }


@router.get("/wellness/my-recommendations")
async def get_my_wellness_recommendations(
    wellness_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get user's saved wellness recommendations"""
    query = session.query(WellnessRecommendation).filter(
        WellnessRecommendation.patient_id == current_user.id,
        WellnessRecommendation.is_active == True
    )
    
    if wellness_type:
        query = query.filter(WellnessRecommendation.wellness_type == wellness_type)
    
    recommendations = query.order_by(WellnessRecommendation.created_at.desc()).all()
    
    return [{
        "id": r.id,
        "wellness_type": r.wellness_type,
        "category": r.category,
        "title": r.title,
        "description": r.description,
        "benefits": r.benefits,
        "dosage_or_duration": r.dosage_or_duration,
        "precautions": r.precautions,
        "created_at": r.created_at.isoformat()
    } for r in recommendations]


@router.get("/symptoms/common")
async def get_common_symptoms(
    category: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Get list of common symptoms for quick selection"""
    # Pre-defined common symptoms
    common_symptoms = [
        {"name": "Headache", "category": "head", "description": "Pain in any region of the head"},
        {"name": "Fever", "category": "general", "description": "Body temperature above normal"},
        {"name": "Cough", "category": "chest", "description": "Forceful expulsion of air from lungs"},
        {"name": "Sore throat", "category": "head", "description": "Pain or irritation in the throat"},
        {"name": "Runny nose", "category": "head", "description": "Excess nasal mucus"},
        {"name": "Fatigue", "category": "general", "description": "Extreme tiredness"},
        {"name": "Body aches", "category": "general", "description": "Muscle pain throughout the body"},
        {"name": "Nausea", "category": "abdomen", "description": "Feeling of wanting to vomit"},
        {"name": "Diarrhea", "category": "abdomen", "description": "Loose or watery stools"},
        {"name": "Chest pain", "category": "chest", "description": "Pain in the chest area"},
        {"name": "Shortness of breath", "category": "chest", "description": "Difficulty breathing"},
        {"name": "Dizziness", "category": "head", "description": "Feeling lightheaded or unsteady"},
        {"name": "Skin rash", "category": "skin", "description": "Changes in skin color or texture"},
        {"name": "Joint pain", "category": "general", "description": "Pain in joints"},
        {"name": "Back pain", "category": "general", "description": "Pain in the back region"},
        {"name": "Abdominal pain", "category": "abdomen", "description": "Pain in the stomach area"},
        {"name": "Vomiting", "category": "abdomen", "description": "Forceful expulsion of stomach contents"},
        {"name": "Loss of appetite", "category": "general", "description": "Reduced desire to eat"},
        {"name": "Insomnia", "category": "general", "description": "Difficulty sleeping"},
        {"name": "Anxiety", "category": "mental", "description": "Feeling of worry or unease"},
    ]
    
    if category:
        common_symptoms = [s for s in common_symptoms if s["category"] == category]
    
    return {
        "symptoms": common_symptoms,
        "categories": ["head", "chest", "abdomen", "skin", "general", "mental"]
    }


@router.post("/symptom-check/{id}/acknowledge")
async def acknowledge_symptom_check(
    id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Acknowledge receipt of symptom check recommendations"""
    symptom_check = session.query(SymptomCheck).filter(
        SymptomCheck.id == id,
        SymptomCheck.patient_id == current_user.id
    ).first()
    
    if not symptom_check:
        raise HTTPException(status_code=404, detail="Symptom check not found")
    
    # Acknowledge all related recommendations
    recommendations = session.query(HealthRecommendation).filter(
        HealthRecommendation.symptom_check_id == id
    ).all()
    
    for rec in recommendations:
        rec.is_acknowledged = True
        rec.acknowledged_at = datetime.utcnow()
    
    session.commit()
    
    return {"success": True, "message": "Recommendations acknowledged"}


@router.get("/history")
async def get_health_history(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get user's AI health assistant history"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get symptom checks
    symptom_checks = session.query(SymptomCheck).filter(
        SymptomCheck.patient_id == current_user.id,
        SymptomCheck.created_at >= start_date
    ).order_by(SymptomCheck.created_at.desc()).all()
    
    # Get conversations
    conversations = session.query(AIConversation).filter(
        AIConversation.patient_id == current_user.id,
        AIConversation.created_at >= start_date
    ).order_by(AIConversation.created_at.desc()).all()
    
    # Get recommendations
    recommendations = session.query(HealthRecommendation).filter(
        HealthRecommendation.patient_id == current_user.id,
        HealthRecommendation.created_at >= start_date
    ).order_by(HealthRecommendation.created_at.desc()).all()
    
    return {
        "period_days": days,
        "symptom_checks": [{
            "id": s.id,
            "primary_symptom": s.primary_symptom,
            "urgency_level": s.urgency_level,
            "recommended_specialization": s.recommended_specialization,
            "created_at": s.created_at.isoformat()
        } for s in symptom_checks],
        "conversations": [{
            "session_id": c.session_id,
            "title": c.title,
            "message_count": c.message_count,
            "is_escalated": c.is_escalated,
            "created_at": c.created_at.isoformat()
        } for c in conversations],
        "recommendations_count": len(recommendations),
        "statistics": {
            "total_symptom_checks": len(symptom_checks),
            "total_conversations": len(conversations),
            "escalated_count": sum(1 for c in conversations if c.is_escalated)
        }
    }
