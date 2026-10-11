"""
Database migration utility script.
Initialize Alembic for database version control and schema migrations.
"""

import os
import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent.parent


def init_migrations():
    """Initialize Alembic for the project"""
    migrations_dir = BACKEND_DIR / "app" / "migrations"
    
    if migrations_dir.exists():
        print("Migrations directory already exists.")
        return
    
    print("Initializing Alembic migrations...")
    
    os.chdir(BACKEND_DIR)
    
    # Initialize Alembic
    subprocess.run(["alembic", "init", "app/migrations"], check=True)
    
    print("Alembic initialized successfully!")
    print(f"Migrations directory created at: {migrations_dir}")
    print("\nNext steps:")
    print("1. Update alembic.ini with your database connection string")
    print("2. Create your first migration: alembic revision --autogenerate -m 'Initial migration'")
    print("3. Apply migrations: alembic upgrade head")


def create_migration(message: str):
    """Create a new migration"""
    print(f"Creating migration: {message}")
    subprocess.run(["alembic", "revision", "--autogenerate", "-m", message], check=True)
    print("Migration created successfully!")


def apply_migrations():
    """Apply all pending migrations"""
    print("Applying migrations...")
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    print("Migrations applied successfully!")


def rollback_migration():
    """Rollback the last migration"""
    print("Rolling back last migration...")
    subprocess.run(["alembic", "downgrade", "-1"], check=True)
    print("Rollback completed!")


def get_migration_status():
    """Get current migration status"""
    print("Migration status:")
    subprocess.run(["alembic", "current"], check=True)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python manage_migrations.py <command>")
        print("Commands:")
        print("  init - Initialize Alembic")
        print("  create <message> - Create a new migration")
        print("  apply - Apply all pending migrations")
        print("  rollback - Rollback last migration")
        print("  status - Show migration status")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "init":
        init_migrations()
    elif command == "create":
        if len(sys.argv) < 3:
            print("Usage: python manage_migrations.py create <message>")
            sys.exit(1)
        create_migration(" ".join(sys.argv[2:]))
    elif command == "apply":
        apply_migrations()
    elif command == "rollback":
        rollback_migration()
    elif command == "status":
        get_migration_status()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
