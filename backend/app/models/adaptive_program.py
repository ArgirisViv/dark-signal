from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class AdaptiveProgram(Base):
    __tablename__ = "adaptive_programs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="created")
    baseline_scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False)
    final_scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False)
    easier_scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False)
    same_scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False)
    harder_scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False)
    targeted_repetition_scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)
    slight_easier_scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)
    adaptive_rounds = Column(Integer, nullable=False, default=2)
    adaptive_round_index = Column(Integer, nullable=False, default=0)
    source_scenario_ids = Column(JSON, nullable=True)
    latest_summary = Column(JSON, nullable=True)
    latest_campaigns = Column(JSON, nullable=True)
    final_evaluation = Column(JSON, nullable=True)
    baseline_scheduled_at = Column(DateTime, nullable=True)
    adaptive_scheduled_at = Column(DateTime, nullable=True)
    final_scheduled_at = Column(DateTime, nullable=True)
    baseline_executed_at = Column(DateTime, nullable=True)
    adaptive_executed_at = Column(DateTime, nullable=True)
    final_executed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
