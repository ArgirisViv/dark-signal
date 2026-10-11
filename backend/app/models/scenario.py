from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.campaign import Campaign

class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String)
    difficulty = Column(String)
    indicators = Column(JSON)

    campaign = relationship("Campaign", back_populates="scenarios")
