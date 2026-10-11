from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from pathlib import Path
from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BACKEND_DIR / "test.db"
LEGACY_DB_PATH = BACKEND_DIR.parent / "test.db"

if settings.DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL
else:
    # Prefer backend-local SQLite for predictable behavior across local and container runs.
    # Fall back to legacy root-level database when it already exists.
    selected_path = DEFAULT_DB_PATH
    if not DEFAULT_DB_PATH.exists() and LEGACY_DB_PATH.exists():
        selected_path = LEGACY_DB_PATH
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{selected_path.as_posix()}"

database_url = make_url(SQLALCHEMY_DATABASE_URL)
engine_options = {}
if database_url.get_backend_name() == "sqlite":
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency that provides a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
