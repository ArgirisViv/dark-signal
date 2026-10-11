from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import settings


def test_clean_database_migrates_to_latest_schema(tmp_path):
    database_path = tmp_path / "clean-migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "app" / "migrations"))
    previous_database_url = settings.DATABASE_URL
    settings.DATABASE_URL = database_url
    try:
        command.upgrade(config, "heads")
    finally:
        settings.DATABASE_URL = previous_database_url

    inspector = inspect(create_engine(database_url))
    expected_tables = {
        "adaptive_programs",
        "alert_acknowledgements",
        "campaign_recipient_snapshots",
        "campaigns",
        "email_templates",
        "events",
        "scenarios",
        "tenants",
        "training_assignments",
        "training_modules",
        "users",
    }

    assert expected_tables.issubset(set(inspector.get_table_names()))

