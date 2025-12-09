from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file FIRST
load_dotenv()

from database import create_db_and_tables, get_session
import models  # Import models to register them with SQLModel
from routers import auth, doctors, patients, admin, appointments, prescriptions, medical_records, pharmacy, billing, chat, video, notifications, activity_logs
from middleware.activity_logger import ActivityLoggingMiddleware
from middleware.security_headers import SecurityHeadersMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="MedHub API",
    description="API for MedHub Integrated Healthcare Platform",
    version="0.1.0",
    lifespan=lifespan
)

# Set up rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration - SECURE for production
origins = [
    "http://localhost:3000",  # Development frontend
    "http://localhost:8000",  # Development API
    os.getenv("FRONTEND_URL", "http://localhost:3000"),  # Production frontend from env
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept", "Origin"],
    expose_headers=["X-Total-Count", "X-Page", "X-Per-Page"],
)

# Add activity logging middleware
app.add_middleware(ActivityLoggingMiddleware, db_session_factory=get_session)

# Add security headers middleware (should be first to apply to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# Include routers
app.include_router(auth.router)
app.include_router(doctors.router)
app.include_router(patients.router)
app.include_router(admin.router)
app.include_router(appointments.router)
app.include_router(prescriptions.router)
app.include_router(medical_records.router)
app.include_router(pharmacy.router)
app.include_router(billing.router)
app.include_router(chat.router)
app.include_router(video.router)
app.include_router(notifications.router)
app.include_router(activity_logs.router)

# Import and include additional routers (some may have import issues - commented out for now)
try:
    from routers import ratings
    app.include_router(ratings.router)
except ImportError as e:
    print(f"Warning: Could not load ratings router: {e}")

try:
    from routers import payments
    app.include_router(payments.router)
except ImportError as e:
    print(f"Warning: Could not load payments router: {e}")

try:
    from routers import shipments
    app.include_router(shipments.router)
except ImportError as e:
    print(f"Warning: Could not load shipments router: {e}")

# Try to load AI health router
try:
    from routers import ai_health
    app.include_router(ai_health.router)
except ImportError as e:
    print(f"Warning: Could not load ai_health router: {e}")
except Exception as e:
    print(f"Warning: Error loading ai_health router: {e}")

# Try to load pharmacy enhanced router
try:
    from routers import pharmacy_enhanced
    app.include_router(pharmacy_enhanced.router)
except ImportError as e:
    print(f"Warning: Could not load pharmacy_enhanced router: {e}")
except Exception as e:
    print(f"Warning: Error loading pharmacy_enhanced router: {e}")

# Try to load blog router
try:
    from routers import blog
    app.include_router(blog.router)
except ImportError as e:
    print(f"Warning: Could not load blog router: {e}")
except Exception as e:
    print(f"Warning: Error loading blog router: {e}")

# Load earnings router
try:
    from routers import earnings
    app.include_router(earnings.router)
except ImportError as e:
    print(f"Warning: Could not load earnings router: {e}")
except Exception as e:
    print(f"Warning: Error loading earnings router: {e}")

# Load users router
try:
    from routers import users
    app.include_router(users.router)
except ImportError as e:
    print(f"Warning: Could not load users router: {e}")
except Exception as e:
    print(f"Warning: Error loading users router: {e}")

# Load family router (Phase 12)
try:
    from routers import family
    app.include_router(family.router)
except ImportError as e:
    print(f"Warning: Could not load family router: {e}")
except Exception as e:
    print(f"Warning: Error loading family router: {e}")

# Load wellness router (Phase 13)
try:
    from routers import wellness
    app.include_router(wellness.router)
except ImportError as e:
    print(f"Warning: Could not load wellness router: {e}")
except Exception as e:
    print(f"Warning: Error loading wellness router: {e}")

# Load address router (Phase 13 - Address & Postal Code Verification)
try:
    from routers import address
    app.include_router(address.router)
except ImportError as e:
    print(f"Warning: Could not load address router: {e}")
except Exception as e:
    print(f"Warning: Error loading address router: {e}")

# These routers have known import issues - disabled for now
# from routers import hospital, billing_enhanced, notifications_enhanced, productivity, admin_dashboard, livekit

@app.get("/")
def read_root():
    return {"message": "Welcome to MedHub API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
