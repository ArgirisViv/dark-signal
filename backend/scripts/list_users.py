from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import User

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def list_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            print("No users found in DB.")
            return
        for u in users:
            print(f"id={u.id} email={u.email} role={u.role}")
    finally:
        db.close()

if __name__ == '__main__':
    list_users()
