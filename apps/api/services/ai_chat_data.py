"""
AI Health Assistant Training Data and Response Generation
This module contains comprehensive healthcare conversation patterns
for the MedHub AI chatbot.

SPECIALIZED AREAS:
1. Rheumatoid Arthritis (RA)
2. Psoriasis
3. Aspermia & Male Infertility
4. Gynecology & Women's Health

STRICT RULES:
- Does NOT diagnose diseases
- Does NOT prescribe medicines
- Does NOT mention brand drugs
- Provides only educational information and wellness suggestions
- Always asks clarifying questions before giving guidance
- Advises immediate doctor visit for severe symptoms
"""

from typing import Dict, List, Any, Optional
import re
import random

# ============================================================================
# MANDATORY DISCLAIMER
# ============================================================================

MEDICAL_DISCLAIMER = """
---
📋 **Disclaimer**: This information is for educational purposes only and is not a substitute for professional medical diagnosis or treatment. Please consult a qualified healthcare provider for personalized medical advice.
"""

# ============================================================================
# TRIAGE SYSTEM CONFIGURATION
# ============================================================================

TRIAGE_CONFIG = {
    "ask_questions_first": True,
    "max_questions_before_response": 3,
    "always_include_disclaimer": True,
    "response_format": {
        "summary": True,
        "possible_conditions": True,
        "questions": True,
        "lifestyle_diet": True,
        "when_to_see_doctor": True,
        "disclaimer": True
    }
}

# ============================================================================
# EMERGENCY KEYWORDS AND RESPONSES
# ============================================================================

EMERGENCY_PATTERNS = {
    "heart_attack": {
        "keywords": ["heart attack", "chest pain radiating", "crushing chest pain", "chest tightness spreading to arm"],
        "response": "🚨 **EMERGENCY - Possible Heart Attack**\n\nThis could be a cardiac emergency. IMMEDIATELY:\n\n1. **Call 108/112** right now\n2. Chew an aspirin (if not allergic)\n3. Sit upright to ease breathing\n4. Loosen tight clothing\n5. Stay calm and don't move around\n\n**DO NOT drive yourself to the hospital.**\n\nIs someone with you who can help?" + MEDICAL_DISCLAIMER,
        "urgency": "emergency"
    },
    "stroke": {
        "keywords": ["stroke", "face drooping", "arm weakness", "speech difficulty", "sudden numbness one side"],
        "response": "🚨 **EMERGENCY - Possible Stroke**\n\nUse FAST check:\n- **F**ace: Ask to smile - is one side drooping?\n- **A**rms: Can they raise both arms?\n- **S**peech: Is speech slurred?\n- **T**ime: Call 108/112 NOW!\n\nEvery minute counts. Note the time symptoms started.\n\n**Do not give food or water.**" + MEDICAL_DISCLAIMER,
        "urgency": "emergency"
    },
    "breathing_emergency": {
        "keywords": ["can't breathe", "difficulty breathing severe", "choking", "turning blue", "gasping for air"],
        "response": "🚨 **EMERGENCY - Breathing Crisis**\n\n1. **Call 108/112 immediately**\n2. Sit upright (don't lie down)\n3. Loosen any tight clothing\n4. Open windows for fresh air\n5. If choking: perform Heimlich maneuver\n\nIs this a known condition like asthma? Do you have an inhaler?" + MEDICAL_DISCLAIMER,
        "urgency": "emergency"
    },
    "severe_bleeding": {
        "keywords": ["severe bleeding", "won't stop bleeding", "losing lot of blood", "deep cut"],
        "response": "🚨 **EMERGENCY - Severe Bleeding**\n\n1. **Call 108/112**\n2. Apply firm pressure with clean cloth\n3. Keep pressure on - don't remove cloth\n4. Elevate injured area above heart if possible\n5. Keep the person calm and warm\n\nDo not use a tourniquet unless trained. Help is on the way." + MEDICAL_DISCLAIMER,
        "urgency": "emergency"
    },
    "unconscious": {
        "keywords": ["unconscious", "unresponsive", "passed out not waking", "fainted not responding"],
        "response": "🚨 **EMERGENCY - Unconsciousness**\n\n1. **Call 108/112 now**\n2. Check if breathing\n3. If breathing: recovery position (on their side)\n4. If NOT breathing: start CPR if trained\n5. Don't give anything to eat or drink\n\nStay with them and keep talking to them." + MEDICAL_DISCLAIMER,
        "urgency": "emergency"
    },
    "allergic_reaction": {
        "keywords": ["severe allergic", "anaphylaxis", "throat swelling", "can't swallow", "allergic reaction severe"],
        "response": "🚨 **EMERGENCY - Severe Allergic Reaction**\n\n1. **Call 108/112 immediately**\n2. Use EpiPen if available (inject into outer thigh)\n3. Have them lie down with legs elevated\n4. Loosen tight clothing\n5. Be prepared to perform CPR\n\nDo they have a known allergy? Any EpiPen available?" + MEDICAL_DISCLAIMER,
        "urgency": "emergency"
    },
    "suicide": {
        "keywords": ["want to die", "kill myself", "suicide", "end my life", "better off dead"],
        "response": "🆘 **I'm very concerned about you right now.**\n\nPlease know that you matter and there is help available:\n\n📞 **iCALL**: 9152987821\n📞 **Vandrevala Foundation**: 1860-2662-345\n📞 **AASRA**: 91-22-27546669\n\nYou're not alone in this. Would you like to talk about what's going on? I'm here to listen without judgment.\n\nIf you're in immediate danger, please call 112.",
        "urgency": "emergency"
    }
}

# ============================================================================
# SPECIALIZED MEDICAL AREAS - TRIAGE SYSTEM
# ============================================================================

# ----------------------------------------------------------------------------
# 1. RHEUMATOID ARTHRITIS (RA)
# ----------------------------------------------------------------------------

RHEUMATOID_ARTHRITIS_DATA = {
    "keywords": [
        "rheumatoid arthritis", "ra arthritis", "ra symptoms", "ra pain",
        "joint swelling morning", "morning stiffness joints", "multiple joint pain",
        "symmetrical joint pain", "joint deformity", "finger joint swelling",
        "wrist joint pain", "autoimmune arthritis", "inflammatory arthritis"
    ],
    "red_flags": [
        "sudden severe joint swelling", "high fever with joint pain",
        "unable to move joint", "joint looks red and hot",
        "numbness in hands", "vision changes with joint pain"
    ],
    "assessment_questions": [
        "Which joints are affected? (hands, wrists, knees, ankles)",
        "Is the stiffness worse in the morning? How long does it last?",
        "Are joints on both sides affected symmetrically?",
        "Have you noticed any swelling, warmth, or redness?",
        "Do you have a family history of autoimmune conditions?",
        "Have you experienced fatigue, low-grade fever, or weight loss?"
    ],
    "initial_response": """I understand you're experiencing joint-related concerns that may be related to inflammatory conditions.

**📋 To help you better, I need to understand:**

1. **Location**: Which joints are affected? (fingers, wrists, knees, feet)
2. **Duration**: How long have you had these symptoms?
3. **Morning stiffness**: Do your joints feel stiff in the morning? For how long?
4. **Pattern**: Are the same joints affected on both sides of your body?
5. **Medical history**: Any family history of arthritis or autoimmune conditions?

Please share these details so I can provide better guidance.""",
    "pattern_analysis": {
        "classic_ra_signs": {
            "pattern": ["morning stiffness >30 min", "symmetrical", "small joints", "swelling"],
            "response": """**📊 Summary of Your Symptoms:**
Based on what you've described, your symptoms may be related to inflammatory joint conditions.

**🔍 Possible Related Conditions (Not a Diagnosis):**
These symptoms can be associated with:
- Inflammatory arthritis patterns
- Autoimmune joint involvement
- Other rheumatic conditions

This is NOT a diagnosis - only a qualified rheumatologist can properly evaluate your condition.

**❓ Recommended Questions for You:**
- Have you had any blood tests (RF factor, anti-CCP, ESR, CRP)?
- Is the stiffness affecting your daily activities?
- Any other symptoms like dry eyes, skin rashes, or breathing issues?"""
        }
    },
    "lifestyle_guidance": """**🌿 Lifestyle & Wellness Suggestions:**

**Diet Recommendations:**
- Anti-inflammatory foods: turmeric, ginger, omega-3 rich fish
- Colorful vegetables and fruits (antioxidants)
- Whole grains and legumes
- Avoid: processed foods, excess sugar, red meat

**Stress Management:**
- Deep breathing exercises daily
- Gentle yoga (Sukshma Vyayama - subtle exercises)
- Adequate sleep (7-8 hours)
- Meditation for pain management

**Physical Activity:**
- Gentle range-of-motion exercises
- Swimming or water exercises (low impact)
- Avoid high-impact activities during flares
- Hand exercises for finger flexibility

**Siddha/Yoga Wellness:**
- Warm oil massage (sesame oil) on affected joints
- Warm water soaks for hands/feet
- Pranayama (breathing exercises)
- Gentle stretching in the morning""",
    "when_to_see_doctor": """**⚠️ When to See a Doctor:**
- Morning stiffness lasting more than 30 minutes
- Joint swelling that doesn't improve
- Symptoms affecting daily activities
- Any new or worsening symptoms
- Need for proper blood tests and diagnosis

**👨‍⚕️ Recommended Specialist:** Rheumatologist""",
    "specialist": "Rheumatologist"
}

# ----------------------------------------------------------------------------
# 2. PSORIASIS
# ----------------------------------------------------------------------------

PSORIASIS_DATA = {
    "keywords": [
        "psoriasis", "skin patches", "scaly skin", "silvery scales",
        "red patches skin", "itchy scales", "plaque psoriasis",
        "scalp psoriasis", "nail psoriasis", "psoriatic", "skin flaking",
        "elbow patches", "knee patches", "thick skin patches"
    ],
    "red_flags": [
        "widespread skin involvement suddenly", "fever with skin rash",
        "pustules all over body", "severe joint pain with skin patches",
        "skin infection signs (pus, spreading redness)"
    ],
    "assessment_questions": [
        "Where are the patches located? (elbows, knees, scalp, nails)",
        "How long have you had these skin changes?",
        "Are the patches itchy, painful, or burning?",
        "Have you noticed any joint pain or swelling?",
        "Any triggers you've noticed? (stress, infections, weather)",
        "Family history of psoriasis or skin conditions?"
    ],
    "initial_response": """I understand you're dealing with skin concerns that may involve scaling or patches.

**📋 To provide helpful guidance, please tell me:**

1. **Location**: Where are the patches? (scalp, elbows, knees, nails, other)
2. **Appearance**: Are they red with silvery scales? Thick? Raised?
3. **Symptoms**: Any itching, burning, or pain?
4. **Duration**: How long have you had these?
5. **Triggers**: Have you noticed anything that makes it worse? (stress, illness, weather)
6. **Joint involvement**: Any joint pain or stiffness?

Please share so I can guide you better.""",
    "pattern_analysis": {
        "classic_psoriasis": {
            "pattern": ["silvery scales", "well-defined patches", "elbows/knees/scalp"],
            "response": """**📊 Summary of Your Symptoms:**
Your description suggests skin involvement that may be related to inflammatory skin conditions.

**🔍 Possible Related Conditions (Not a Diagnosis):**
These symptoms can be associated with:
- Plaque-type inflammatory skin conditions
- Scalp involvement patterns
- Nail changes related to skin conditions

This is NOT a diagnosis - a dermatologist can properly evaluate and confirm.

**❓ Questions to Consider:**
- Any family history of similar skin conditions?
- Have you noticed improvement or worsening with seasons?
- Any new medications or recent illnesses before symptoms started?"""
        }
    },
    "lifestyle_guidance": """**🌿 Lifestyle & Wellness Suggestions:**

**Skin Care:**
- Moisturize regularly (fragrance-free, thick creams)
- Lukewarm baths (not hot) with colloidal oatmeal
- Pat skin dry gently, don't rub
- Avoid harsh soaps and chemicals

**Diet Recommendations:**
- Anti-inflammatory diet (fish, vegetables, whole grains)
- Avoid: alcohol, processed foods, excess dairy
- Stay well hydrated
- Consider reducing gluten if you notice correlation

**Stress Management (Important Trigger):**
- Regular meditation/pranayama
- Gentle yoga practice
- Adequate sleep
- Reduce work stress where possible

**Natural Care Options:**
- Aloe vera gel on patches (cooling effect)
- Coconut oil moisturizing
- Sunlight exposure (10-15 min, avoid burning)
- Neem-based products for gentle cleansing

**Avoid:**
- Skin picking or scratching
- Tight clothing over affected areas
- Extreme hot or cold temperatures
- Smoking (can worsen condition)""",
    "when_to_see_doctor": """**⚠️ When to See a Doctor:**
- Patches spreading rapidly
- Joint pain accompanying skin symptoms
- Signs of infection (pus, increased redness, warmth)
- Severe itching affecting sleep
- Not improving with basic care
- Need for proper diagnosis and treatment plan

**👨‍⚕️ Recommended Specialist:** Dermatologist
(If joint pain present: Also consult Rheumatologist for psoriatic arthritis evaluation)""",
    "specialist": "Dermatologist"
}

# ----------------------------------------------------------------------------
# 3. ASPERMIA & MALE INFERTILITY
# ----------------------------------------------------------------------------

MALE_INFERTILITY_DATA = {
    "keywords": [
        "aspermia", "no sperm", "azoospermia", "low sperm count",
        "male infertility", "can't conceive", "trying for baby",
        "sperm problem", "sperm motility", "sperm test", "semen analysis",
        "erectile dysfunction", "fertility problem male", "oligospermia",
        "male fertility", "varicocele", "not getting pregnant male"
    ],
    "red_flags": [
        "testicular pain or swelling", "blood in semen",
        "lump in testicle", "severe groin pain",
        "sudden loss of libido with depression"
    ],
    "assessment_questions": [
        "How long have you been trying to conceive?",
        "Have you had a semen analysis done? What were the results?",
        "Any history of infections, surgeries, or injuries in that area?",
        "Do you experience any pain or swelling?",
        "Any lifestyle factors? (smoking, alcohol, occupation, stress)",
        "Medical history: diabetes, hormonal issues, medications?"
    ],
    "initial_response": """I understand this is a sensitive and personal concern. Thank you for trusting me with this.

**📋 To provide appropriate guidance, I need to understand:**

1. **Duration**: How long have you been trying to conceive?
2. **Tests done**: Have you had a semen analysis? Any results to share?
3. **Symptoms**: Any pain, swelling, or discomfort in the testicular area?
4. **Medical history**: Any past surgeries, infections, or health conditions?
5. **Lifestyle**: Work environment, stress levels, habits (smoking/alcohol)?

Your privacy is respected. Please share what you're comfortable with.""",
    "pattern_analysis": {
        "general_inquiry": {
            "pattern": ["trying", "conceive", "fertility"],
            "response": """**📊 Understanding Your Concern:**
Male fertility involves multiple factors including sperm production, quality, and delivery.

**🔍 Possible Related Factors (Not a Diagnosis):**
Fertility challenges can be related to:
- Hormonal factors
- Structural issues
- Lifestyle factors
- Medical conditions
- Idiopathic (unknown) causes

A proper evaluation by an andrologist/urologist is essential.

**❓ Important Questions:**
- Has your partner also been evaluated?
- Any varicocele (enlarged veins) detected?
- Recent fever or illness (can temporarily affect sperm)?
- Occupational exposure to heat, chemicals, or radiation?"""
        }
    },
    "lifestyle_guidance": """**🌿 Lifestyle & Wellness Suggestions:**

**Dietary Support:**
- Zinc-rich foods: pumpkin seeds, nuts, legumes
- Antioxidant-rich foods: berries, vegetables, citrus
- Omega-3 fatty acids: fish, flaxseeds, walnuts
- Folic acid sources: leafy greens, fortified foods
- Avoid: processed foods, excess soy, trans fats

**Lifestyle Modifications:**
- Avoid excessive heat to testicular area
- Wear loose, comfortable underwear
- Limit hot baths and saunas
- Maintain healthy weight (BMI 20-25)
- Regular moderate exercise (avoid overtraining)

**Stress & Mental Health:**
- Stress can affect hormone levels and fertility
- Practice relaxation techniques
- Open communication with partner
- Consider counseling if needed - this journey can be emotional

**Avoid:**
- Smoking (significantly reduces sperm quality)
- Excessive alcohol
- Anabolic steroids
- Recreational drugs
- Environmental toxins where possible

**Yoga & Wellness:**
- Ashwagandha (adaptogen - consult doctor first)
- Yoga poses for reproductive health
- Meditation for stress management
- Adequate sleep (7-8 hours)""",
    "when_to_see_doctor": """**⚠️ When to See a Doctor:**
- Trying to conceive for >12 months (or >6 months if wife >35)
- Any testicular pain, swelling, or lumps
- History of undescended testes or surgeries
- Known hormonal issues
- For proper semen analysis and evaluation

**👨‍⚕️ Recommended Specialist:** 
- Andrologist (specialist in male reproductive health)
- Urologist
- Reproductive Endocrinologist (for both partners)

**Note:** Both partners should be evaluated together for comprehensive assessment.""",
    "specialist": "Andrologist/Urologist"
}

# ----------------------------------------------------------------------------
# 4. GYNECOLOGY & WOMEN'S HEALTH
# ----------------------------------------------------------------------------

GYNECOLOGY_DATA = {
    "keywords": [
        "period problem", "irregular periods", "menstrual", "pcos", "pcod",
        "heavy bleeding", "period pain", "missed period", "vaginal discharge",
        "vaginal infection", "white discharge", "fertility female",
        "can't get pregnant", "ovulation", "menopause", "hot flashes",
        "breast pain", "pelvic pain", "endometriosis", "fibroids",
        "yeast infection", "period cramps", "amenorrhea", "dysmenorrhea",
        "premenstrual", "pms", "pmdd", "women health", "female health"
    ],
    "red_flags": [
        "heavy bleeding soaking pad hourly", "severe pelvic pain sudden",
        "fever with pelvic pain", "missed period with severe pain",
        "postmenopausal bleeding", "foul smelling discharge with fever",
        "breast lump"
    ],
    "assessment_questions": [
        "What is your main concern? (periods, discharge, pain, fertility)",
        "How old are you and at what age did your periods start?",
        "When was your last period? Is your cycle regular?",
        "Any pain? Where exactly and how severe (1-10)?",
        "Any unusual discharge? (color, smell, consistency)",
        "Are you trying to conceive or using any contraception?"
    ],
    "initial_response": """I understand you have a concern related to women's health. Thank you for reaching out.

**📋 To provide helpful guidance, please tell me:**

1. **Main concern**: Is it about periods, discharge, pain, or something else?
2. **Age & History**: Your age and when periods started
3. **Menstrual pattern**: Regular/irregular? Last period date?
4. **Symptoms**: Any pain, unusual discharge, or other symptoms?
5. **Reproductive status**: Trying to conceive? Any contraception?
6. **Medical history**: Any known conditions like PCOS, thyroid issues?

Please share what you're comfortable with - your privacy is respected.""",
    "subcategories": {
        "irregular_periods": {
            "keywords": ["irregular period", "missed period", "late period", "no period", "amenorrhea"],
            "response": """**📊 Understanding Irregular Periods:**

**🔍 This may be related to:**
- Hormonal imbalances (PCOS is common)
- Thyroid dysfunction
- Stress and lifestyle factors
- Weight changes
- Perimenopause (if age appropriate)

**❓ Questions to Consider:**
- Any recent weight changes?
- High stress levels?
- Other symptoms like acne, hair growth, or hair loss?

**🌿 Supportive Measures:**
- Maintain healthy weight
- Regular exercise
- Stress management
- Track your cycle
- Balanced nutrition"""
        },
        "pcos_pcod": {
            "keywords": ["pcos", "pcod", "polycystic", "ovary cysts"],
            "response": """**📊 Understanding PCOS Concerns:**

PCOS (Polycystic Ovary Syndrome) involves hormonal imbalance and can present with multiple symptoms.

**🔍 Common Associated Features:**
- Irregular or missed periods
- Excess hair growth (hirsutism)
- Acne or oily skin
- Weight management difficulties
- Difficulty conceiving

**🌿 Lifestyle Management:**
- Weight management (even 5-10% loss helps)
- Low glycemic index diet
- Regular exercise (30 min daily)
- Stress management
- Adequate sleep

**Diet Tips:**
- Reduce refined carbs and sugars
- Include fiber-rich foods
- Anti-inflammatory foods
- Small, frequent meals

**Yoga & Wellness:**
- Butterfly pose (Baddha Konasana)
- Bridge pose (Setu Bandhasana)
- Regular pranayama
- Meditation for hormonal balance"""
        },
        "period_pain": {
            "keywords": ["period pain", "cramps", "dysmenorrhea", "painful period"],
            "response": """**📊 Understanding Period Pain:**

**🔍 Types:**
- Primary: Common, starts with periods, no underlying cause
- Secondary: Due to conditions like endometriosis, fibroids

**❓ Important to Note:**
- Severity: Mild discomfort vs. debilitating pain
- Duration: First 1-2 days vs. entire period
- Impact on daily life

**🌿 Natural Pain Management:**
- Heat application on lower abdomen
- Gentle stretching and yoga
- Stay hydrated
- Reduce salt intake before periods
- Ginger or chamomile tea
- Light walking

**Yoga for Relief:**
- Child's pose (Balasana)
- Cat-cow stretch
- Knee-to-chest pose
- Supine twist

⚠️ See doctor if pain is severe, worsening, or affecting daily life."""
        },
        "vaginal_discharge": {
            "keywords": ["discharge", "white discharge", "vaginal discharge", "leucorrhea"],
            "response": """**📊 Understanding Vaginal Discharge:**

**Normal vs. Concerning:**
- **Normal**: Clear to white, mild odor, varies with cycle
- **Concerning**: Yellow/green, foul smell, itching, pain

**🔍 This may be related to:**
- Normal physiological discharge
- Yeast overgrowth
- Bacterial changes
- Infections (need proper evaluation)

**🌿 General Care:**
- Wear cotton underwear
- Keep area clean and dry
- Avoid douching
- Avoid scented products
- Change out of wet clothes promptly

**When Concerning:**
- Unusual color (yellow, green, grey)
- Strong, unpleasant odor
- Itching, burning, or irritation
- Pain during urination

⚠️ Any concerning discharge needs proper medical evaluation."""
        },
        "menopause": {
            "keywords": ["menopause", "hot flash", "perimenopause", "night sweats"],
            "response": """**📊 Understanding Menopause:**

Menopause is a natural transition, typically occurring between 45-55 years.

**Common Experiences:**
- Hot flashes and night sweats
- Mood changes
- Sleep disturbances
- Vaginal dryness
- Bone health changes

**🌿 Supportive Measures:**

**For Hot Flashes:**
- Dress in layers
- Keep room cool
- Identify triggers (spicy food, caffeine, alcohol)
- Deep breathing when flash begins

**Diet & Nutrition:**
- Calcium and Vitamin D rich foods
- Phytoestrogens (soy, flaxseeds)
- Plenty of water
- Reduce caffeine and alcohol

**Exercise:**
- Weight-bearing exercises for bones
- Yoga for flexibility and mood
- Regular walking

**Mental Wellness:**
- This is a natural life stage
- Connect with others going through similar
- Practice self-compassion
- Seek support if mood changes are significant"""
        },
        "fertility_female": {
            "keywords": ["can't get pregnant", "trying to conceive", "fertility female", "ovulation", "infertility female"],
            "response": """**📊 Understanding Fertility Concerns:**

**🔍 Factors That May Affect Fertility:**
- Age (fertility naturally declines after 35)
- Ovulation irregularities
- Hormonal imbalances
- Structural issues
- Lifestyle factors

**❓ Important Information:**
- How long have you been trying?
- Is your cycle regular?
- Any known conditions (PCOS, thyroid)?
- Has your partner been evaluated?

**🌿 Supportive Measures:**
- Track ovulation (cycle days 12-16 typically)
- Maintain healthy weight
- Reduce stress
- Balanced nutrition
- Avoid smoking and limit alcohol
- Regular moderate exercise

**When to Seek Help:**
- Trying >12 months (if <35 years)
- Trying >6 months (if >35 years)
- Known issues with periods or ovulation
- History of pelvic conditions

Both partners should be evaluated together."""
        }
    },
    "lifestyle_guidance": """**🌿 General Women's Wellness:**

**Nutrition:**
- Iron-rich foods (leafy greens, dates, jaggery)
- Calcium for bone health
- B-vitamins for energy
- Omega-3 for hormonal health
- Plenty of water

**Exercise:**
- Regular physical activity
- Yoga for hormonal balance
- Walking daily
- Pelvic floor exercises

**Stress Management:**
- Deep breathing practices
- Meditation
- Adequate sleep (7-8 hours)
- Work-life balance

**Preventive Care:**
- Regular gynecological checkups
- Pap smear as recommended
- Breast self-examination monthly
- Bone density check if indicated""",
    "when_to_see_doctor": """**⚠️ When to See a Doctor:**
- Very heavy or prolonged bleeding
- Severe pain not relieved by basic measures
- Unusual discharge with fever or pain
- Any breast lumps or changes
- Irregular periods persisting >3 months
- Fertility concerns (trying >12 months, or >6 if 35+)
- Any postmenopausal bleeding

**👨‍⚕️ Recommended Specialist:** Gynecologist/Obstetrician""",
    "specialist": "Gynecologist"
}

# ============================================================================
# COMBINED SPECIALIZED RESPONSES
# ============================================================================

SPECIALIZED_HEALTH_DATA = {
    "rheumatoid_arthritis": RHEUMATOID_ARTHRITIS_DATA,
    "psoriasis": PSORIASIS_DATA,
    "male_infertility": MALE_INFERTILITY_DATA,
    "gynecology": GYNECOLOGY_DATA
}

# ============================================================================
# SYMPTOM-BASED CONVERSATIONS
# ============================================================================

SYMPTOM_RESPONSES = {
    "headache": {
        "keywords": ["headache", "head hurts", "head pain", "migraine", "head pounding", "head throbbing"],
        "initial_response": "I understand you're dealing with head pain. Let me help you assess this.\n\n**Quick questions:**\n1. Where exactly is the pain? (front, back, sides, one side only)\n2. How would you rate the pain from 1-10?\n3. When did it start?\n4. Any other symptoms like nausea, light sensitivity, or fever?",
        "follow_ups": {
            "severe": "A severe headache especially if sudden ('thunderclap') needs immediate attention. Please consult a doctor today. Want me to help you book an appointment?",
            "migraine": "This sounds like it could be a migraine. Here's what can help:\n- Rest in a quiet, dark room\n- Apply cold compress to forehead\n- Stay hydrated\n- Consider OTC pain relief like paracetamol\n\nIf migraines are frequent, you should see a neurologist.",
            "tension": "This seems like a tension headache, often caused by stress or posture. Try:\n- Gentle neck stretches\n- Warm compress on neck/shoulders\n- Take breaks from screens\n- Practice deep breathing"
        },
        "suggestions": ["Track pain triggers", "Stay hydrated", "Book neurologist if recurring"],
        "specialist": "Neurologist"
    },
    "fever": {
        "keywords": ["fever", "high temperature", "feeling hot", "chills", "body temperature high"],
        "initial_response": "Fever is your body's way of fighting infection. Let me gather some information:\n\n**Please tell me:**\n1. What is your current temperature?\n2. How long have you had the fever?\n3. Any other symptoms? (cough, cold, body aches, rash)\n4. Any recent travel or sick contacts?",
        "follow_ups": {
            "high_fever": "A temperature above 103°F (39.4°C) needs medical attention. Please see a doctor soon. Meanwhile:\n- Take paracetamol as directed\n- Stay hydrated\n- Use lukewarm sponging\n- Rest well",
            "with_symptoms": "Fever with your symptoms could indicate an infection. Here's what to do:\n- Monitor your temperature every 4-6 hours\n- Stay hydrated with water, ORS, coconut water\n- Rest and avoid exertion\n- If fever persists beyond 3 days, see a doctor",
            "dengue_risk": "Given your symptoms, we should rule out dengue. Please get a CBC and dengue test done. Watch for warning signs like:\n- Severe stomach pain\n- Persistent vomiting\n- Bleeding gums\n- Blood in stool"
        },
        "suggestions": ["Monitor temperature", "Stay hydrated", "Get blood tests if persistent"],
        "specialist": "General Physician"
    },
    "cough": {
        "keywords": ["cough", "coughing", "dry cough", "wet cough", "phlegm", "mucus"],
        "initial_response": "Let me understand your cough better:\n\n1. Is it a dry cough or with phlegm?\n2. If phlegm, what color? (clear, yellow, green, blood-tinged)\n3. How long have you been coughing?\n4. Any fever, breathlessness, or chest pain?",
        "follow_ups": {
            "dry": "A dry cough can be irritating. Here are some remedies:\n- Honey with warm water\n- Steam inhalation\n- Stay hydrated\n- Avoid irritants like dust and smoke\n- Elevate head while sleeping",
            "productive": "A cough with colored phlegm may indicate infection. Please:\n- Continue steam inhalation with turmeric\n- Drink warm fluids\n- If phlegm is green/yellow for >5 days, see a doctor\n- Avoid cold drinks",
            "chronic": "A cough lasting more than 3 weeks needs investigation. Please see a doctor for:\n- Chest X-ray\n- Sputum test if needed\n- Lung function test if indicated"
        },
        "suggestions": ["Steam inhalation", "Warm fluids", "Avoid irritants"],
        "specialist": "Pulmonologist"
    },
    "stomach": {
        "keywords": ["stomach pain", "abdominal pain", "stomach ache", "tummy pain", "belly pain", "gastric", "stomach hurts", "tummy hurts", "nausea", "vomiting", "vomit", "indigestion", "acidity", "bloating"],
        "initial_response": "I'm sorry you're having stomach trouble. Let me ask a few questions:\n\n1. Where exactly is the pain? (upper, lower, left, right, around navel)\n2. Is it constant or comes and goes?\n3. Related to eating? (before/after meals)\n4. Any vomiting, loose stools, or blood in stool?",
        "follow_ups": {
            "acidity": "This sounds like acidity/GERD. Here's what helps:\n- Avoid spicy, oily, and citrus foods\n- Don't lie down right after eating\n- Eat smaller, frequent meals\n- Take an antacid as needed\n- Elevate head while sleeping",
            "gastritis": "These symptoms suggest gastritis. Please:\n- Avoid NSAIDs (aspirin, ibuprofen)\n- Eat bland foods\n- Avoid alcohol and smoking\n- Consider a course of antacids/PPIs\n- See a gastroenterologist if persistent",
            "acute": "Severe abdominal pain needs immediate evaluation. Please:\n- Don't take painkillers before seeing a doctor\n- Don't eat until evaluated\n- If pain is in right lower area with fever, it could be appendicitis - go to ER"
        },
        "suggestions": ["Eat light meals", "Avoid spicy food", "Track food triggers"],
        "specialist": "Gastroenterologist"
    },
    "cold_flu": {
        "keywords": ["cold", "flu", "runny nose", "blocked nose", "sneezing", "congestion"],
        "initial_response": "Common cold and flu are quite manageable at home. Tell me more:\n\n1. How many days have you had symptoms?\n2. Do you have fever with it?\n3. Any body aches or fatigue?\n4. Sore throat or ear pain?",
        "follow_ups": {
            "common_cold": "This sounds like a common cold. Home remedies that help:\n- Rest well\n- Drink warm fluids (soup, tea with honey)\n- Steam inhalation 2-3 times daily\n- Saltwater gargle for sore throat\n- Use nasal saline drops\n\nMost colds resolve in 7-10 days.",
            "flu": "Flu symptoms are more severe than cold. Please:\n- Rest completely\n- Stay hydrated\n- Take paracetamol for fever/body aches\n- Isolate to prevent spread\n- See a doctor if fever >3 days or breathing difficulty",
            "chronic": "If you get frequent colds, consider:\n- Boosting immunity (vitamin C, zinc)\n- Regular exercise\n- Good sleep hygiene\n- Annual flu vaccination"
        },
        "suggestions": ["Rest well", "Stay hydrated", "Steam inhalation"],
        "specialist": "ENT Specialist"
    },
    "skin": {
        "keywords": ["skin rash", "itching", "redness", "skin problem", "pimples", "acne", "eczema", "skin bumps"],
        "initial_response": "Skin issues can be concerning. Let me understand better:\n\n1. Where is the rash/problem located?\n2. Is it itchy, painful, or neither?\n3. When did it start?\n4. Any new products, foods, or medications recently?\n5. Does it spread or stay in one place?",
        "follow_ups": {
            "allergic": "This could be an allergic reaction. Please:\n- Stop any new products/medications\n- Take an antihistamine like cetirizine\n- Apply calamine lotion for itching\n- Keep the area clean and dry\n- If spreading or with swelling, see a doctor today",
            "acne": "For acne management:\n- Wash face twice daily with gentle cleanser\n- Don't pick or squeeze\n- Use non-comedogenic products\n- Consider benzoyl peroxide or salicylic acid products\n- See a dermatologist for severe or persistent acne",
            "infection": "If you see pus, increasing redness, or warmth, it could be infected. Please:\n- Keep area clean\n- Don't scratch\n- See a doctor for possible antibiotics\n- Watch for fever"
        },
        "suggestions": ["Keep area clean", "Avoid scratching", "Note new products"],
        "specialist": "Dermatologist"
    },
    "joint_pain": {
        "keywords": ["joint pain", "knee pain", "back pain", "shoulder pain", "body ache", "muscle pain", "arthritis"],
        "initial_response": "Joint and muscle pain can really affect daily life. Let me understand:\n\n1. Which joints/muscles are affected?\n2. Is there swelling, redness, or warmth?\n3. Is it worse in the morning or after activity?\n4. Any recent injury or overexertion?\n5. How long have you had this?",
        "follow_ups": {
            "acute": "For recent onset pain:\n- Rest the affected area\n- Apply ice pack (20 min on/off)\n- Take OTC painkiller if needed\n- Gentle stretching once pain subsides\n- If no improvement in 3-5 days, see a doctor",
            "chronic": "For long-standing joint issues:\n- Regular gentle exercise\n- Maintain healthy weight\n- Hot/cold therapy\n- Consider physiotherapy\n- Get evaluated for arthritis if not done",
            "inflammatory": "Signs of inflammation (swelling, warmth, redness) need evaluation:\n- Could be inflammatory arthritis\n- Get blood tests (RA factor, CRP, uric acid)\n- See a rheumatologist for proper diagnosis"
        },
        "suggestions": ["Rest and ice initially", "Gentle exercises", "Maintain healthy weight"],
        "specialist": "Orthopedic Specialist"
    },
    "diabetes": {
        "keywords": ["diabetes", "blood sugar", "sugar level", "frequent urination", "excessive thirst", "diabetic"],
        "initial_response": "Managing diabetes is important for long-term health. Tell me:\n\n1. Are you diagnosed with diabetes or suspecting symptoms?\n2. If diagnosed, are you on medication?\n3. What are your recent blood sugar readings?\n4. Any symptoms like excessive thirst, urination, or tiredness?",
        "follow_ups": {
            "suspected": "If you're experiencing symptoms of diabetes, please get tested:\n- Fasting blood sugar\n- HbA1c test\n- Post-meal sugar\n\nEarly detection helps manage it better.",
            "management": "For better diabetes management:\n- Monitor sugar regularly\n- Take medications as prescribed\n- Follow a balanced diet (low sugar, high fiber)\n- Exercise 30 min daily\n- Regular eye, kidney, and foot checkups\n- Keep follow-up appointments",
            "high_sugar": "If your blood sugar is consistently high:\n- Review your diet and medication adherence\n- Check for infections (can raise sugar)\n- Don't skip meals or medications\n- Contact your doctor for medication adjustment"
        },
        "suggestions": ["Monitor sugar regularly", "Follow diet plan", "Regular checkups"],
        "specialist": "Diabetologist/Endocrinologist"
    },
    "blood_pressure": {
        "keywords": ["blood pressure", "bp high", "bp low", "hypertension", "dizziness", "headache morning"],
        "initial_response": "Blood pressure management is crucial. Let me know:\n\n1. Are you diagnosed with BP issues or checking for the first time?\n2. What are your recent BP readings?\n3. Any symptoms like headache, dizziness, or palpitations?\n4. Are you on any BP medications?",
        "follow_ups": {
            "high": "For high BP (>140/90):\n- Take prescribed medications regularly\n- Reduce salt intake\n- Exercise regularly\n- Manage stress\n- Limit alcohol and quit smoking\n- Monitor BP at home\n\nVery high BP (>180/120) needs immediate attention.",
            "low": "For low BP (<90/60) with symptoms:\n- Drink plenty of fluids\n- Increase salt intake slightly\n- Wear compression stockings if standing long\n- Get up slowly from sitting/lying\n- If persistent, see a doctor",
            "monitoring": "Tips for accurate BP monitoring:\n- Rest 5 min before checking\n- Sit with feet flat, arm supported\n- No caffeine or exercise 30 min before\n- Take 2-3 readings, note average"
        },
        "suggestions": ["Take medications regularly", "Reduce salt", "Exercise daily"],
        "specialist": "Cardiologist"
    },
    "sleep": {
        "keywords": ["can't sleep", "insomnia", "sleep problem", "not sleeping", "sleeping too much", "fatigue"],
        "initial_response": "Sleep issues can affect your overall health. Let me understand:\n\n1. Trouble falling asleep or staying asleep?\n2. How many hours are you sleeping?\n3. Do you feel rested when you wake up?\n4. Any stress, pain, or medication changes?\n5. Snoring or breathing pauses noted by others?",
        "follow_ups": {
            "insomnia": "For better sleep:\n- Fixed sleep and wake times (even weekends)\n- No screens 1 hour before bed\n- Avoid caffeine after 2 PM\n- Keep bedroom cool and dark\n- Try relaxation techniques\n- No heavy meals before bed",
            "apnea": "If you snore heavily or have breathing pauses, you may need:\n- Sleep study evaluation\n- Weight management\n- Avoiding alcohol before bed\n- Possibly CPAP therapy",
            "fatigue": "Persistent fatigue despite sleep could indicate:\n- Anemia\n- Thyroid issues\n- Depression\n- Sleep apnea\n\nPlease get basic blood work done."
        },
        "suggestions": ["Maintain sleep schedule", "No screens before bed", "Relaxation techniques"],
        "specialist": "Sleep Specialist/Psychiatrist"
    },
    "mental_health": {
        "keywords": ["anxiety", "anxious", "depression", "depressed", "stressed", "stress", "worried", "worry", "panic", "sad", "hopeless", "overwhelmed", "mental health", "nervous", "tension", "feeling low", "mood"],
        "initial_response": "Thank you for sharing how you're feeling. Mental health is just as important as physical health.\n\n1. How long have you been feeling this way?\n2. Has something specific triggered this?\n3. Is it affecting your daily activities, sleep, or appetite?\n4. Have you spoken to anyone about this?",
        "follow_ups": {
            "anxiety": "For managing anxiety:\n- Deep breathing exercises (4-7-8 technique)\n- Grounding techniques (5-4-3-2-1 method)\n- Regular exercise\n- Limit caffeine and alcohol\n- Talk to someone you trust\n- Consider professional counseling",
            "depression": "If you're feeling persistently sad or hopeless:\n- Reach out to loved ones\n- Keep a routine\n- Gentle exercise can help\n- Don't isolate yourself\n- Professional help makes a big difference\n- You don't have to face this alone",
            "stress": "For stress management:\n- Identify stress triggers\n- Practice mindfulness/meditation\n- Physical activity\n- Good sleep hygiene\n- Set boundaries\n- Take breaks from work"
        },
        "suggestions": ["Talk to someone", "Practice self-care", "Consider counseling"],
        "specialist": "Psychiatrist/Psychologist"
    },
    "pregnancy": {
        "keywords": ["pregnant", "pregnancy", "expecting", "prenatal", "morning sickness", "baby"],
        "initial_response": "Congratulations if you're expecting! Let me help with your query:\n\n1. How many weeks/months pregnant are you?\n2. Is this your first pregnancy?\n3. Any specific symptoms or concerns?\n4. Are you on prenatal vitamins?",
        "follow_ups": {
            "general": "Important pregnancy tips:\n- Regular prenatal checkups\n- Take folic acid and prenatal vitamins\n- Balanced diet with fruits, vegetables, protein\n- Stay hydrated\n- Moderate exercise (walking, prenatal yoga)\n- Avoid alcohol, smoking, and raw foods",
            "symptoms": "Some common pregnancy symptoms:\n- Morning sickness: Eat small, frequent meals\n- Fatigue: Rest when needed\n- Back pain: Proper posture, prenatal exercises\n- Heartburn: Small meals, don't lie down after eating\n\nReport any bleeding, severe pain, or reduced baby movement immediately.",
            "warning_signs": "Seek immediate care for:\n- Vaginal bleeding\n- Severe headache or vision changes\n- Severe abdominal pain\n- Significantly reduced baby movement\n- Leaking fluid\n- Fever"
        },
        "suggestions": ["Regular checkups", "Take prenatal vitamins", "Stay active safely"],
        "specialist": "Obstetrician/Gynecologist"
    },
    "child_health": {
        "keywords": ["child", "baby", "kid", "toddler", "infant", "pediatric", "my son", "my daughter", "child sick", "baby sick", "kid sick", "child fever", "baby fever", "my child", "my baby", "child has fever", "baby has fever", "kid has fever", "child is sick", "baby is sick", "son has", "daughter has", "child not eating", "baby not eating"],
        "initial_response": "I understand you're concerned about your child. Let me help:\n\n1. How old is your child?\n2. What symptoms are they showing?\n3. How long have they had these symptoms?\n4. Any fever, rash, or change in appetite/behavior?",
        "follow_ups": {
            "fever_child": "For a child with fever:\n- Give age-appropriate dose of paracetamol\n- Light clothing, not bundled up\n- Plenty of fluids\n- Tepid sponging if high fever\n- See doctor if: <3 months with any fever, fever >3 days, not drinking, very lethargic, rash",
            "common_illness": "Common childhood illness care:\n- Rest and hydration are key\n- Monitor symptoms closely\n- Keep them comfortable\n- Follow up if not improving\n- Don't share medications between children",
            "vaccination": "Vaccination is important for your child's health:\n- Follow the recommended schedule\n- Keep vaccination records\n- Mild fever/fussiness after vaccines is normal\n- Contact doctor if severe reaction"
        },
        "suggestions": ["Monitor closely", "Keep hydrated", "See pediatrician if worried"],
        "specialist": "Pediatrician"
    },
    "eye": {
        "keywords": ["eye pain", "vision problem", "blurry vision", "red eye", "eye infection", "can't see clearly"],
        "initial_response": "Eye problems need attention. Please tell me:\n\n1. Which eye is affected (or both)?\n2. Any pain, redness, or discharge?\n3. Vision changes (blurry, double, loss)?\n4. Any recent injury or foreign body?\n5. Do you wear glasses/contacts?",
        "follow_ups": {
            "infection": "For eye infection symptoms:\n- Don't rub your eyes\n- Clean with cooled boiled water\n- Don't share towels or makeup\n- Remove contact lenses if worn\n- See an eye doctor for proper treatment",
            "strain": "For eye strain:\n- 20-20-20 rule (every 20 min, look 20 ft away for 20 sec)\n- Adjust screen brightness\n- Ensure proper lighting\n- Use artificial tears if dry\n- Get regular eye checkups",
            "urgent": "Seek immediate care for:\n- Sudden vision loss\n- Chemical in eye (rinse immediately)\n- Eye injury\n- Sudden flashes or floaters\n- Severe pain"
        },
        "suggestions": ["Don't rub eyes", "Use clean water", "See ophthalmologist"],
        "specialist": "Ophthalmologist"
    },
    "dental": {
        "keywords": ["tooth pain", "toothache", "dental", "gum", "teeth", "cavity", "wisdom tooth"],
        "initial_response": "Dental pain can be quite distressing. Let me know:\n\n1. Where is the pain? (specific tooth, gums, jaw)\n2. Is it constant or triggered by hot/cold/sweet?\n3. Any swelling, bleeding, or pus?\n4. How long have you had this?",
        "follow_ups": {
            "cavity": "For tooth decay symptoms:\n- Rinse with warm salt water\n- OTC pain relief if needed\n- Avoid very hot/cold foods\n- See a dentist soon for treatment\n- Don't delay as it can worsen",
            "gum": "For gum problems:\n- Gentle brushing with soft brush\n- Floss carefully\n- Salt water rinses\n- Antiseptic mouthwash\n- See dentist if bleeding persists or gums are swollen",
            "emergency": "Seek immediate dental care for:\n- Severe pain not relieved by painkillers\n- Significant swelling (especially if spreading)\n- Knocked out tooth (keep in milk, go immediately)\n- Bleeding that won't stop"
        },
        "suggestions": ["Salt water rinse", "Gentle brushing", "See dentist soon"],
        "specialist": "Dentist"
    }
}

# ============================================================================
# GENERAL HEALTH TOPICS
# ============================================================================

GENERAL_TOPICS = {
    "diet": {
        "keywords": ["diet", "nutrition", "healthy eating", "weight loss", "weight gain", "food"],
        "response": "Good nutrition is the foundation of health! Here are general guidelines:\n\n**Balanced Diet:**\n- Half plate vegetables/fruits\n- Quarter plate protein (dal, eggs, chicken, fish)\n- Quarter plate whole grains\n- Healthy fats in moderation\n\n**Tips:**\n- Eat home-cooked meals\n- Reduce processed foods\n- Stay hydrated (8+ glasses water)\n- Regular meal times\n\nWould you like specific diet advice for any health condition?",
        "suggestions": ["Track your meals", "Plan weekly menu", "Consult nutritionist"]
    },
    "exercise": {
        "keywords": ["exercise", "workout", "fitness", "gym", "yoga", "physical activity"],
        "response": "Regular exercise is vital for health! Recommendations:\n\n**Weekly Goals:**\n- 150 min moderate OR 75 min vigorous activity\n- Strength training 2x/week\n- Flexibility exercises\n\n**Getting Started:**\n- Start slow, progress gradually\n- Choose activities you enjoy\n- Morning walks are great\n- Yoga for flexibility and stress\n\n**Safety:**\n- Warm up and cool down\n- Stay hydrated\n- Rest between intense sessions\n\nNeed exercise suggestions for a specific condition?",
        "suggestions": ["Start with walking", "Try yoga", "Build gradually"]
    },
    "preventive_care": {
        "keywords": ["health checkup", "screening", "preventive", "annual checkup", "routine tests"],
        "response": "Preventive care helps catch problems early! Recommended screenings:\n\n**Annual:**\n- Blood pressure check\n- Blood sugar (if >30 or at risk)\n- Lipid profile (if >30)\n- BMI assessment\n\n**Women:**\n- Pap smear (21-65 years)\n- Mammogram (40+ years)\n- Breast self-exam monthly\n\n**Men:**\n- Prostate check (50+ years)\n- Testicular self-exam\n\n**All Adults:**\n- Eye exam every 2 years\n- Dental checkup every 6 months\n\nWant to schedule a health checkup?",
        "suggestions": ["Schedule annual checkup", "Track health metrics", "Update vaccinations"]
    },
    "vaccination": {
        "keywords": ["vaccine", "vaccination", "immunization", "flu shot", "covid vaccine"],
        "response": "Vaccinations protect you and your community!\n\n**Adult Vaccinations:**\n- Annual flu vaccine\n- COVID-19 and boosters\n- Tetanus booster every 10 years\n- Hepatitis B if at risk\n- Pneumonia vaccine (65+)\n\n**Travel Vaccines:**\n- Yellow fever for endemic areas\n- Typhoid for high-risk areas\n- Hepatitis A for travelers\n\n**Pregnancy:**\n- Flu and Tdap vaccines recommended\n\nWant information on specific vaccines?",
        "suggestions": ["Get annual flu shot", "Stay updated on boosters", "Check before travel"]
    },
    "first_aid": {
        "keywords": ["first aid", "injury", "burn", "cut", "wound", "sprain"],
        "response": "Basic first aid knowledge is important!\n\n**Common Situations:**\n\n**Cuts:** Clean with water, apply pressure, cover with bandage\n**Burns:** Cool water 10+ min (NOT ice), don't pop blisters\n**Sprains:** RICE - Rest, Ice, Compress, Elevate\n**Choking:** Back blows and abdominal thrusts\n**Nosebleed:** Lean forward, pinch soft part 10 min\n\n**When to Seek Help:**\n- Deep wounds needing stitches\n- Burns larger than palm\n- Signs of infection\n- Severe sprains with deformity\n\nWhat type of injury are you dealing with?",
        "suggestions": ["Keep first aid kit", "Learn CPR", "Know emergency numbers"]
    }
}

# ============================================================================
# APPOINTMENT & SERVICE QUERIES
# ============================================================================

SERVICE_RESPONSES = {
    "appointment": {
        "keywords": ["appointment", "book doctor", "schedule", "see a doctor", "consultation"],
        "response": "I can help you book an appointment! We offer:\n\n**Consultation Types:**\n- 🏥 In-person consultation\n- 📹 Video consultation\n- 💬 Chat consultation\n\n**Specialties Available:**\n- General Physician\n- Specialists (Cardiology, Dermatology, etc.)\n- Pediatrics\n- Gynecology\n- Mental Health\n\nWhat type of doctor would you like to see? I can show you available slots.",
        "suggestions": ["View doctors", "Book video call", "Check availability"]
    },
    "pharmacy": {
        "keywords": ["medicine", "pharmacy", "prescription", "order medicine", "buy medicine"],
        "response": "Our pharmacy services include:\n\n**Services:**\n- 💊 Upload prescription for medicines\n- 🛒 Order OTC products\n- 🚚 Home delivery available\n- 💉 Vaccination services\n\n**How to Order:**\n1. Upload your prescription OR\n2. Browse our pharmacy store\n3. Add items to cart\n4. Choose delivery/pickup\n\nDo you have a prescription to upload, or would you like to browse our store?",
        "suggestions": ["Upload prescription", "Browse pharmacy", "Track order"]
    },
    "lab_test": {
        "keywords": ["lab test", "blood test", "diagnostic", "test report", "health test"],
        "response": "We can help with lab tests!\n\n**Available Tests:**\n- Blood tests (CBC, Lipid, Sugar, Thyroid, etc.)\n- Urine tests\n- Imaging (X-ray, Ultrasound)\n- Specialized tests\n\n**Options:**\n- Home sample collection\n- Visit partnered labs\n- Quick digital reports\n\nWhich test do you need? I can help you book it.",
        "suggestions": ["Book home collection", "View test packages", "Upload existing report"]
    },
    "medical_records": {
        "keywords": ["medical records", "health records", "reports", "history", "past reports"],
        "response": "Your medical records are important for continuity of care.\n\n**You can:**\n- 📁 View all your health records\n- 📤 Upload external reports\n- 📥 Download records for reference\n- 🔗 Share with doctors during consultation\n\nAll your records are securely stored and accessible anytime.\n\nWould you like to view or upload any records?",
        "suggestions": ["View records", "Upload report", "Share with doctor"]
    },
    "emergency": {
        "keywords": ["emergency", "urgent", "immediate", "right now", "asap"],
        "response": "For medical emergencies:\n\n**Emergency Numbers:**\n- 🚑 Ambulance: 108\n- 🆘 Emergency: 112\n- 🏥 Nearest Hospital: Use our hospital finder\n\n**We Offer:**\n- Urgent video consultations (available doctors now)\n- Emergency guidance\n- Hospital directions\n\nIs this a medical emergency? I can help you get immediate assistance.",
        "suggestions": ["Call 108", "Find nearest hospital", "Urgent consultation"]
    },
    "insurance": {
        "keywords": ["insurance", "coverage", "claim", "cashless", "health insurance"],
        "response": "Health insurance queries:\n\n**We Accept:**\n- Most major insurance providers\n- Corporate health plans\n- Government health schemes\n\n**Services:**\n- Cashless facility at network hospitals\n- Claim assistance\n- Pre-authorization support\n\nFor specific insurance queries, please contact our support team with your policy details.\n\nWould you like to add your insurance information to your profile?",
        "suggestions": ["Add insurance", "Check network hospitals", "Contact support"]
    },
    "pricing": {
        "keywords": ["cost", "price", "fee", "charges", "how much"],
        "response": "Here's our pricing information:\n\n**Consultations:**\n- Video consultation: Starting ₹299\n- Chat consultation: Starting ₹199\n- In-person: Varies by doctor\n\n**Lab Tests:**\n- Individual tests starting ₹99\n- Health packages available\n- Home collection: Small additional fee\n\n**Pharmacy:**\n- MRP pricing\n- Free delivery above ₹500\n\nWhat service would you like detailed pricing for?",
        "suggestions": ["View doctor fees", "Test prices", "Pharmacy offers"]
    }
}

# ============================================================================
# CONVERSATIONAL PATTERNS
# ============================================================================

GREETING_RESPONSES = [
    "Hello! I'm MedHub's AI Health Assistant. How can I help you today?",
    "Hi there! I'm here to help with your health questions. What would you like to discuss?",
    "Welcome! I'm your health assistant. Feel free to ask me about symptoms, appointments, or general health advice.",
    "Namaste! I'm MedHub's health assistant. How may I assist you with your health concerns today?"
]

FAREWELL_RESPONSES = [
    "Take care! Remember, I'm here 24/7 if you have any health questions. Stay healthy! 🌟",
    "Goodbye! Don't hesitate to reach out if you need any health assistance. Take care of yourself!",
    "Wishing you good health! Feel free to chat anytime you need health guidance.",
    "Take care and stay healthy! Come back whenever you need help. 😊"
]

THANK_RESPONSES = [
    "You're welcome! Is there anything else I can help you with regarding your health?",
    "Happy to help! Don't hesitate to ask if you have more questions.",
    "Glad I could assist! Your health is important - feel free to reach out anytime.",
    "You're welcome! Take care of yourself, and remember I'm here if you need me."
]

UNCLEAR_RESPONSES = [
    "I want to make sure I understand you correctly. Could you tell me more about:\n- What symptoms are you experiencing?\n- How long have you had these issues?\n- What specific help do you need?",
    "I'd like to help you better. Could you please provide more details about your health concern?",
    "To give you the best guidance, could you describe your symptoms or concern in more detail?"
]

# ============================================================================
# HELPER FUNCTIONS FOR SPECIALIZED AREAS
# ============================================================================

def check_red_flags(message: str, red_flags: List[str]) -> bool:
    """Check if message contains any red flag symptoms"""
    message_lower = message.lower()
    for flag in red_flags:
        if flag.lower() in message_lower:
            return True
    return False


def format_triage_response(
    summary: str,
    possible_conditions: str,
    questions: str,
    lifestyle_diet: str,
    when_to_see_doctor: str,
    specialist: str,
    is_red_flag: bool = False
) -> str:
    """Format response according to triage structure"""
    response_parts = []
    
    if is_red_flag:
        response_parts.append("⚠️ **These symptoms require urgent medical attention.**\n")
    
    if summary:
        response_parts.append(summary)
    
    if possible_conditions:
        response_parts.append(possible_conditions)
    
    if questions:
        response_parts.append(questions)
    
    if lifestyle_diet and not is_red_flag:
        response_parts.append(lifestyle_diet)
    
    if when_to_see_doctor:
        response_parts.append(when_to_see_doctor)
    
    # Always add disclaimer
    response_parts.append(MEDICAL_DISCLAIMER)
    
    return "\n\n".join(response_parts)


def check_gynecology_subcategory(message: str) -> Optional[Dict]:
    """Check for specific gynecology subcategories"""
    message_lower = message.lower()
    
    for subcat_name, subcat_data in GYNECOLOGY_DATA.get("subcategories", {}).items():
        for keyword in subcat_data.get("keywords", []):
            if keyword in message_lower:
                return subcat_data
    return None


# ============================================================================
# MAIN RESPONSE GENERATOR
# ============================================================================

def generate_ai_response(message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
    """
    Generate an intelligent response based on the user message.
    Uses pattern matching and context analysis.
    
    This is a Verified Medical Triage & Wellness Assistant specialized in:
    1. Rheumatoid Arthritis (RA)
    2. Psoriasis
    3. Aspermia & Male Infertility
    4. Gynecology & Women's Health
    
    STRICT RULES:
    - Does NOT diagnose diseases
    - Does NOT prescribe medicines
    - Does NOT mention brand drugs
    - Provides only educational information and wellness suggestions
    """
    message_lower = message.lower().strip()
    
    # Check for emergency keywords first
    for pattern_name, pattern_data in EMERGENCY_PATTERNS.items():
        for keyword in pattern_data["keywords"]:
            if keyword in message_lower:
                return {
                    "response": pattern_data["response"] + MEDICAL_DISCLAIMER,
                    "urgency_detected": pattern_data["urgency"],
                    "suggestions": ["Call emergency services", "Seek immediate help"]
                }
    
    # Check for greetings (use word boundaries to avoid matching 'hi' in 'child')
    greeting_words = ["hello", "hey", "good morning", "good evening", "namaste"]
    words = message_lower.split()
    if len(words) <= 3 and any(word in ["hello", "hi", "hey", "namaste"] for word in words):
        return {
            "response": random.choice(GREETING_RESPONSES),
            "urgency_detected": None,
            "suggestions": ["Describe symptoms", "Book appointment", "Health advice"]
        }
    if any(greeting in message_lower for greeting in ["good morning", "good evening"]):
        return {
            "response": random.choice(GREETING_RESPONSES),
            "urgency_detected": None,
            "suggestions": ["Describe symptoms", "Book appointment", "Health advice"]
        }
    
    # Check for farewells
    if any(word in message_lower for word in ["bye", "goodbye", "thanks bye", "see you", "take care"]):
        return {
            "response": random.choice(FAREWELL_RESPONSES),
            "urgency_detected": None,
            "suggestions": []
        }
    
    # Check for thank you
    if any(word in message_lower for word in ["thank you", "thanks", "thank u", "thx"]):
        return {
            "response": random.choice(THANK_RESPONSES),
            "urgency_detected": None,
            "suggestions": ["Ask another question", "Book appointment", "Browse pharmacy"]
        }
    
    # ========================================================================
    # SPECIALIZED MEDICAL TRIAGE - Check specialized health areas first
    # ========================================================================
    
    # Check for Rheumatoid Arthritis related queries
    ra_data = SPECIALIZED_HEALTH_DATA.get("rheumatoid_arthritis")
    if ra_data:
        for keyword in ra_data["keywords"]:
            if keyword in message_lower:
                # Check for red flags first
                red_flag_response = check_red_flags(message_lower, ra_data["red_flags"])
                if red_flag_response:
                    return {
                        "response": red_flag_response + MEDICAL_DISCLAIMER,
                        "urgency_detected": "urgent",
                        "suggestions": ["Consult rheumatologist immediately", "Visit emergency if severe"],
                        "recommended_specialist": ra_data.get("specialist")
                    }
                
                # Format triage response
                response = format_triage_response(ra_data)
                return {
                    "response": response + MEDICAL_DISCLAIMER,
                    "urgency_detected": None,
                    "suggestions": ["Book rheumatologist appointment", "Ask about lifestyle tips", "Learn about joint care"],
                    "recommended_specialist": ra_data.get("specialist"),
                    "assessment_questions": ra_data.get("assessment_questions", [])
                }
    
    # Check for Psoriasis related queries
    psoriasis_data = SPECIALIZED_HEALTH_DATA.get("psoriasis")
    if psoriasis_data:
        for keyword in psoriasis_data["keywords"]:
            if keyword in message_lower:
                # Check for red flags first
                red_flag_response = check_red_flags(message_lower, psoriasis_data["red_flags"])
                if red_flag_response:
                    return {
                        "response": red_flag_response + MEDICAL_DISCLAIMER,
                        "urgency_detected": "urgent",
                        "suggestions": ["Consult dermatologist immediately", "Visit emergency if severe"],
                        "recommended_specialist": psoriasis_data.get("specialist")
                    }
                
                # Format triage response
                response = format_triage_response(psoriasis_data)
                return {
                    "response": response + MEDICAL_DISCLAIMER,
                    "urgency_detected": None,
                    "suggestions": ["Book dermatologist appointment", "Ask about skin care tips", "Learn about triggers"],
                    "recommended_specialist": psoriasis_data.get("specialist"),
                    "assessment_questions": psoriasis_data.get("assessment_questions", [])
                }
    
    # Check for Male Infertility / Aspermia related queries
    male_infertility_data = SPECIALIZED_HEALTH_DATA.get("male_infertility")
    if male_infertility_data:
        for keyword in male_infertility_data["keywords"]:
            if keyword in message_lower:
                # Check for red flags first
                red_flag_response = check_red_flags(message_lower, male_infertility_data["red_flags"])
                if red_flag_response:
                    return {
                        "response": red_flag_response + MEDICAL_DISCLAIMER,
                        "urgency_detected": "urgent",
                        "suggestions": ["Consult urologist/andrologist immediately", "Get evaluated soon"],
                        "recommended_specialist": male_infertility_data.get("specialist")
                    }
                
                # Format triage response
                response = format_triage_response(male_infertility_data)
                return {
                    "response": response + MEDICAL_DISCLAIMER,
                    "urgency_detected": None,
                    "suggestions": ["Book fertility specialist appointment", "Ask about lifestyle factors", "Learn about testing options"],
                    "recommended_specialist": male_infertility_data.get("specialist"),
                    "assessment_questions": male_infertility_data.get("assessment_questions", [])
                }
    
    # Check for Gynecology / Women's Health related queries
    gynecology_data = SPECIALIZED_HEALTH_DATA.get("gynecology")
    if gynecology_data:
        for keyword in gynecology_data["keywords"]:
            if keyword in message_lower:
                # Check for specific subcategory first (PCOS, irregular periods, etc.)
                subcategory = check_gynecology_subcategory(message_lower)
                
                if subcategory:
                    # Check subcategory red flags
                    red_flag_response = check_red_flags(message_lower, subcategory.get("red_flags", []))
                    if red_flag_response:
                        return {
                            "response": red_flag_response + MEDICAL_DISCLAIMER,
                            "urgency_detected": "urgent",
                            "suggestions": ["Consult gynecologist immediately", "Visit emergency if severe pain/bleeding"],
                            "recommended_specialist": subcategory.get("specialist", "Gynecologist")
                        }
                    
                    # Format subcategory triage response
                    response = format_triage_response(subcategory)
                    return {
                        "response": response + MEDICAL_DISCLAIMER,
                        "urgency_detected": None,
                        "suggestions": ["Book gynecologist appointment", "Track your cycle", "Learn about treatment options"],
                        "recommended_specialist": subcategory.get("specialist", "Gynecologist"),
                        "assessment_questions": subcategory.get("assessment_questions", [])
                    }
                
                # General gynecology response
                red_flag_response = check_red_flags(message_lower, gynecology_data.get("red_flags", []))
                if red_flag_response:
                    return {
                        "response": red_flag_response + MEDICAL_DISCLAIMER,
                        "urgency_detected": "urgent",
                        "suggestions": ["Consult gynecologist immediately", "Visit emergency if needed"],
                        "recommended_specialist": gynecology_data.get("specialist")
                    }
                
                response = format_triage_response(gynecology_data)
                return {
                    "response": response + MEDICAL_DISCLAIMER,
                    "urgency_detected": None,
                    "suggestions": ["Book gynecologist appointment", "Ask about women's health", "Learn about wellness"],
                    "recommended_specialist": gynecology_data.get("specialist"),
                    "assessment_questions": gynecology_data.get("assessment_questions", [])
                }
    
    # ========================================================================
    # GENERAL SYMPTOM MATCHING (Non-specialized areas)
    # ========================================================================
    
    # Check symptom patterns - prioritize multi-word keywords first
    best_match = None
    best_match_length = 0
    
    for symptom_name, symptom_data in SYMPTOM_RESPONSES.items():
        for keyword in symptom_data["keywords"]:
            if keyword in message_lower:
                # Prefer longer/more specific keyword matches
                if len(keyword) > best_match_length:
                    best_match_length = len(keyword)
                    best_match = (symptom_name, symptom_data)
    
    if best_match:
        symptom_name, symptom_data = best_match
        severity = analyze_severity(message_lower)
        response = symptom_data["initial_response"]
        
        # Add context-aware follow-up
        if severity == "severe" and "severe" in symptom_data.get("follow_ups", {}):
            response += "\n\n" + symptom_data["follow_ups"]["severe"]
        
        return {
            "response": response,
            "urgency_detected": "urgent" if severity == "severe" else None,
            "suggestions": symptom_data.get("suggestions", []),
            "recommended_specialist": symptom_data.get("specialist")
        }
    
    # Check service queries
    for service_name, service_data in SERVICE_RESPONSES.items():
        for keyword in service_data["keywords"]:
            if keyword in message_lower:
                return {
                    "response": service_data["response"],
                    "urgency_detected": None,
                    "suggestions": service_data.get("suggestions", [])
                }
    
    # Check general health topics
    for topic_name, topic_data in GENERAL_TOPICS.items():
        for keyword in topic_data["keywords"]:
            if keyword in message_lower:
                return {
                    "response": topic_data["response"],
                    "urgency_detected": None,
                    "suggestions": topic_data.get("suggestions", [])
                }
    
    # Default response for unclear messages
    return {
        "response": random.choice(UNCLEAR_RESPONSES),
        "urgency_detected": None,
        "suggestions": ["Describe symptoms", "Book appointment", "Ask health question"]
    }


def analyze_severity(message: str) -> str:
    """Analyze the severity of symptoms based on message content"""
    severe_keywords = [
        "severe", "extreme", "unbearable", "worst", "very bad", "intense",
        "can't move", "can't sleep", "days", "week", "weeks", "getting worse",
        "spreading", "blood", "swelling", "high fever"
    ]
    
    for keyword in severe_keywords:
        if keyword in message.lower():
            return "severe"
    
    moderate_keywords = ["moderate", "uncomfortable", "bothering", "few days"]
    for keyword in moderate_keywords:
        if keyword in message.lower():
            return "moderate"
    
    return "mild"


def get_specialist_for_symptom(symptoms: List[str]) -> Optional[str]:
    """Get the recommended specialist based on symptoms"""
    for symptom in symptoms:
        symptom_lower = symptom.lower()
        for symptom_name, symptom_data in SYMPTOM_RESPONSES.items():
            for keyword in symptom_data["keywords"]:
                if keyword in symptom_lower:
                    return symptom_data.get("specialist")
    return "General Physician"
