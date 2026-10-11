from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class TrainingModule(Base):
    __tablename__ = "training_modules"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    module_type = Column(String, nullable=False, default="Micro-learning")
    estimated_minutes = Column(Integer, nullable=False, default=10)
    required_score = Column(Integer, nullable=False, default=80)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)