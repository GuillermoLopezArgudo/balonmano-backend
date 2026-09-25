from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def normalize_database_url(url: str) -> str:
    """
    Neon / Render suelen dar postgres:// o postgresql://.
    Usamos el driver psycopg3 (`psycopg`) — compatible con Python 3.12+ en Render.
    Neon exige SSL.
    """
    u = (url or "").strip()
    if not u:
        return u

    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://") :]

    if u.startswith("postgresql+psycopg2://"):
        u = "postgresql+psycopg://" + u[len("postgresql+psycopg2://") :]
    elif u.startswith("postgresql://"):
        u = "postgresql+psycopg://" + u[len("postgresql://") :]

    parsed = urlparse(u)
    host = (parsed.hostname or "").lower()
    qs = dict(parse_qsl(parsed.query, keep_blank_values=True))

    # Neon (y casi todo managed Postgres en la nube) necesita SSL
    if "neon.tech" in host or "render.com" in host or "amazonaws.com" in host:
        qs.setdefault("sslmode", "require")

    # Channel binding a veces viene en URLs Neon modernas; si molesta, Neon lo documenta
    new_query = urlencode(qs)
    u = urlunparse(parsed._replace(query=new_query))
    return u


_url = normalize_database_url(settings.database_url)

engine = create_engine(
    _url,
    pool_pre_ping=True,
    # Neon cierra conexiones idle; reciclar evita "server closed the connection"
    pool_recycle=280,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
