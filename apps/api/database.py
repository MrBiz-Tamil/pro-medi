from sqlmodel import SQLModel, create_engine, Session
import os
import logging

logger = logging.getLogger(__name__)

# Use SQLite for development if DATABASE_URL is not set or if USE_SQLITE is true
USE_SQLITE = os.getenv("USE_SQLITE", "true").lower() == "true"

# SECURITY: Disable SQL echo in production to prevent sensitive data leakage
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"

if USE_SQLITE:
    # SQLite database for development
    SQLITE_FILE = os.path.join(os.path.dirname(__file__), "medhub_dev.db")
    DATABASE_URL = f"sqlite:///{SQLITE_FILE}"
    engine = create_engine(DATABASE_URL, echo=DB_ECHO, connect_args={"check_same_thread": False})
else:
    # PostgreSQL for production - MUST be set via environment variable
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL environment variable must be set for PostgreSQL. "
            "Example: postgresql://user:password@host:5432/dbname"
        )
    # Production configuration with connection pooling
    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Handle stale connections
        pool_recycle=300,  # Recycle connections every 5 minutes
    )

def get_session():
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
