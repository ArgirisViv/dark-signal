from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from app.db.base import Base


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    approval_status = Column(String, nullable=False, default="approved")
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    origin = Column(String, nullable=False, default="manual")
    assistant_metadata = Column(Text, nullable=True)
    difficulty = Column(String, nullable=False, default="medium")
    category = Column(String, nullable=False, default="General")
    topic = Column(String, nullable=False, default="Security awareness")
    psychological_technique = Column(String, nullable=False, default="urgency")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
