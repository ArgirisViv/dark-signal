from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class CampaignRecipientSnapshot(Base):
    __tablename__ = "campaign_recipient_snapshots"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    email = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    department = Column(String, nullable=True)
    interaction_token = Column(String, nullable=True, index=True)
    executed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
