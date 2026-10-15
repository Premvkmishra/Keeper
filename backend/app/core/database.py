import logging
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from .config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

def get_database_url() -> str:
    if settings.SUPABASE_DB_URL:
        # Normalize postgres:// to postgresql+psycopg://
        url = settings.SUPABASE_DB_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    if settings.APP_ENV.lower() not in ("testing", "test") and not settings.ALLOW_LOCAL_SQLITE:
        raise RuntimeError(
            "SUPABASE_DB_URL is required. Set ALLOW_LOCAL_SQLITE=true only for isolated local development."
        )

    dev_db = (Path(__file__).resolve().parent.parent.parent / "keeper_dev.db").as_posix()
    return f"sqlite:///{dev_db}"

db_url = get_database_url()
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_health() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
