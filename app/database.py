from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def normalize_database_url(url: str) -> str:
    """Render suele dar postgres:// o postgresql://; usamos psycopg2 (requirements)."""
    u = (url or "").strip()
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://") :]
    if u.startswith("postgresql+psycopg://"):
        u = "postgresql+psycopg2://" + u[len("postgresql+psycopg://") :]
    elif u.startswith("postgresql://"):
        u = "postgresql+psycopg2://" + u[len("postgresql://") :]
    return u


engine = create_engine(normalize_database_url(settings.database_url))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
