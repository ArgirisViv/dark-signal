from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr = Field(..., description="User email address", examples=["alex@company.com"])
    password: str = Field(..., min_length=8, max_length=128, description="User password", examples=["Str0ngP@ssw0rd"])
    role: Optional[str] = Field(default="viewer", description="Application account role")
    full_name: Optional[str] = Field(None, description="Full name")
    department: Optional[str] = Field(None, description="Department")
    risk: Optional[str] = Field(None, description="Risk level")



class UserUpdate(BaseModel):
    email: Optional[EmailStr] = Field(None, description="User email address")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="User password")
    role: Optional[str] = Field(None, description="User role")
    full_name: Optional[str] = Field(None, description="Full name")
    department: Optional[str] = Field(None, description="Department")
    risk: Optional[str] = Field(None, description="Risk level")



class UserOut(BaseModel):
    id: int = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email address")
    role: str = Field(..., description="User role")
    full_name: Optional[str] = Field(None, description="Full name")
    department: Optional[str] = Field(None, description="Department")
    risk: Optional[str] = Field(None, description="Risk level")
    last_activity: Optional[datetime] = Field(None, description="Most recent activity timestamp")

    class Config:
        from_attributes = True


class UserCsvImportRow(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    department: Optional[str] = None
    risk: Optional[str] = "Low"


class UserCsvImportRequest(BaseModel):
    users: List[UserCsvImportRow] = Field(..., min_length=1, max_length=1000)


class UserRiskProfile(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    department: Optional[str] = None
    recorded_risk: Optional[str] = None
    computed_risk: str
    awareness_score: int
    exposures: int
    clicks: int
    reports: int
    last_activity: Optional[datetime] = None
    recent_activity: List[Dict[str, Any]] = Field(default_factory=list)


class UserRiskTrendPoint(BaseModel):
    date: str
    awareness_score: int
    computed_risk: str
    clicks: int
    reports: int


class TrainingAssignmentCreate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=160)
    assignment_type: str = Field(default="Micro-learning", min_length=1, max_length=80)
    module_id: Optional[int] = None


class TrainingAssignmentUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=40)
    completion_score: Optional[int] = Field(None, ge=0, le=100)


class TrainingAssignmentOut(BaseModel):
    id: int
    user_id: int
    module_id: Optional[int] = None
    title: str
    assignment_type: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    completion_score: Optional[int] = None

    class Config:
        from_attributes = True


class TrainingModuleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)
    module_type: str = Field(default="Micro-learning", min_length=1, max_length=80)
    estimated_minutes: int = Field(default=10, ge=1, le=480)
    required_score: int = Field(default=80, ge=0, le=100)


class TrainingModuleOut(TrainingModuleCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(..., description="Token type", examples=["bearer"])


class TokenRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class BootstrapRequest(BaseModel):
    token: Optional[str] = Field(None, description="Bootstrap token (optional if provided via header)")
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, max_length=128, description="Admin password")
    full_name: Optional[str] = Field(None, description="Admin full name")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="Account email address")


class ForgotPasswordResponse(BaseModel):
    message: str = Field(..., description="Request status message")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Password reset token")
    password: str = Field(..., min_length=8, max_length=128, description="New password")


class ResetPasswordResponse(BaseModel):
    message: str = Field(..., description="Reset result message")


class ScenarioBase(BaseModel):
    title: str = Field(..., description="Scenario title")
    difficulty: str = Field(..., description="Scenario difficulty")
    indicators: Dict[str, Any] = Field(default_factory=dict, description="Extra scenario metadata")
    campaign_id: Optional[int] = Field(None, description="Campaign ID containing this scenario")


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Scenario title")
    difficulty: Optional[str] = Field(None, description="Scenario difficulty")
    indicators: Optional[Dict[str, Any]] = Field(None, description="Extra scenario metadata")
    campaign_id: Optional[int] = Field(None, description="Campaign ID containing this scenario")


class ScenarioOut(ScenarioBase):
    id: int = Field(..., description="Scenario ID")

    class Config:
        from_attributes = True


class CampaignBase(BaseModel):
    name: str = Field(..., description="Campaign name")
    description: Optional[str] = Field(None, description="Campaign description")
    status: str = Field(default="Draft", description="Campaign status")


class CampaignCreate(CampaignBase):
    scenario_ids: List[int] = Field(default_factory=list, description="Existing scenario IDs to attach")


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Campaign name")
    description: Optional[str] = Field(None, description="Campaign description")
    status: Optional[str] = Field(None, description="Campaign status")


class CampaignOut(CampaignBase):
    id: int = Field(..., description="Campaign ID")
    scenario_count: int = Field(default=0, description="Number of scenarios in the campaign")
    scenarios: List[ScenarioOut] = Field(default_factory=list, description="Campaign scenarios")

    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    items: List[CampaignOut]
    total: int = Field(..., description="Total number of campaigns for the query")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Offset into the full result set")
    has_more: bool = Field(..., description="Whether more items are available")


class CampaignAttachScenariosRequest(BaseModel):
    scenario_ids: List[int] = Field(..., min_length=1, description="Scenario IDs to attach to the campaign")


class ScenarioListResponse(BaseModel):
    items: List[ScenarioOut]
    total: int = Field(..., description="Total number of scenarios for the query")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Offset into the full result set")
    has_more: bool = Field(..., description="Whether more items are available")


class MockPhishingSendResponse(BaseModel):
    message: str = Field(..., description="Mock send status message")
    scenario: ScenarioOut
    recipients: int = Field(..., description="Number of recipients targeted")
    audience: str = Field(..., description="Audience used for targeting")


class ScenarioResults(BaseModel):
    scenario_id: int
    scenario_title: str
    campaign_id: Optional[int] = None
    campaign_name: Optional[str] = None
    deliveries: int
    unique_recipients: int
    opens: int
    clicks: int
    reports: int
    open_rate: float
    click_rate: float
    report_rate: float
    latest_run_recipients: List[Dict[str, Any]] = Field(default_factory=list)
    recent_responses: List[Dict[str, Any]] = Field(default_factory=list)


class EventCreate(BaseModel):
    action: str = Field(..., description="Event action")
    user_id: Optional[int] = Field(None, description="User ID")
    scenario_id: Optional[int] = Field(None, description="Scenario ID")
    campaign_id: Optional[int] = Field(None, description="Campaign ID")


class EventOut(BaseModel):
    id: int = Field(..., description="Event ID")
    action: str = Field(..., description="Event action")
    user_id: Optional[int] = Field(None, description="User ID")
    user_email: Optional[str] = Field(None, description="User email")
    campaign_id: Optional[int] = Field(None, description="Campaign ID")
    scenario_id: Optional[int] = Field(None, description="Scenario ID")
    scenario_title: Optional[str] = Field(None, description="Scenario title")
    created_at: Optional[datetime] = Field(None, description="Timestamp")

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: List[UserOut]
    total: int = Field(..., description="Total number of users for the query")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Offset into the full result set")
    has_more: bool = Field(..., description="Whether more items are available")
    role_counts: Dict[str, int] = Field(default_factory=dict, description="Application account totals by role")


class EmailTemplateBase(BaseModel):
    key: str = Field(..., description="Template key")
    name: str = Field(..., description="Template name")
    subject: str = Field(..., description="Email subject")
    body_text: Optional[str] = Field(None, description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    category: str = Field(default="General", max_length=80)
    topic: str = Field(default="Security awareness", max_length=120)
    psychological_technique: str = Field(default="urgency", max_length=40)


class EmailTemplateCreate(BaseModel):
    key: str = Field(..., description="Template key")
    name: str = Field(..., description="Template name")
    subject: str = Field(..., description="Email subject")
    body_text: Optional[str] = Field(None, description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    category: str = Field(default="General", max_length=80)
    topic: str = Field(default="Security awareness", max_length=120)
    psychological_technique: str = Field(default="urgency", max_length=40)


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Template name")
    subject: Optional[str] = Field(None, description="Email subject")
    body_text: Optional[str] = Field(None, description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body")
    difficulty: Optional[str] = Field(None, pattern="^(easy|medium|hard)$")
    category: Optional[str] = Field(None, max_length=80)
    topic: Optional[str] = Field(None, max_length=120)
    psychological_technique: Optional[str] = Field(None, max_length=40)


class EmailTemplateOut(EmailTemplateBase):
    id: int = Field(..., description="Template ID")
    approval_status: str = Field(default="approved", description="Template approval status")
    approved_by: Optional[str] = Field(None, description="Approver identifier")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    origin: str = Field(default="manual", description="Template origin")
    assistant_metadata: Optional[str] = Field(None, description="Assistant generation metadata as JSON string")
    created_at: Optional[datetime] = Field(None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(None, description="Updated timestamp")

    class Config:
        from_attributes = True


class TenantCreate(BaseModel):
    name: str = Field(..., description="Tenant name")
    slug: Optional[str] = Field(None, description="Tenant slug (optional)")


class TenantOut(BaseModel):
    id: int = Field(..., description="Tenant ID")
    name: str = Field(..., description="Tenant name")
    slug: str = Field(..., description="Tenant slug")
    created_at: Optional[datetime] = Field(None, description="Created timestamp")

    class Config:
        from_attributes = True


class AssistantTemplateRequest(BaseModel):
    language: str = Field(..., min_length=2, max_length=40)
    organization_category: str = Field(..., min_length=2, max_length=80)
    recipient_role: str = Field(..., min_length=2, max_length=80)
    topic: str = Field(..., min_length=2, max_length=120)
    difficulty: str = Field(..., min_length=2, max_length=30)
    psychological_technique: str = Field(..., min_length=2, max_length=40)
    template_name: Optional[str] = Field(None, min_length=2, max_length=120)


class AssistantVariant(BaseModel):
    difficulty: str
    subject: str
    body_text: str
    body_html: str


class AssistantTemplateResponse(BaseModel):
    template: EmailTemplateOut
    suspicious_points: List[str] = Field(default_factory=list)
    alternative_variant: AssistantVariant
    safety_notes: List[str] = Field(default_factory=list)
    generator: str = Field(default="rule_based_fallback")
    provider: str
    model: Optional[str] = None
    request_id: Optional[str] = None


class AssistantStatusResponse(BaseModel):
    configured: bool
    provider: str
    api: str
    model: str


class AdaptiveBaselineRequest(BaseModel):
    source_scenario_ids: List[int] = Field(..., min_length=1, description="Scenario ids used as baseline input")


class AdaptiveStageDispatchRequest(BaseModel):
    source_scenario_ids: List[int] = Field(..., min_length=1, description="Previous-stage scenario ids used for classification")
    easier_scenario_id: int = Field(..., ge=1)
    same_scenario_id: int = Field(..., ge=1)
    harder_scenario_id: int = Field(..., ge=1)
    targeted_repetition_scenario_id: Optional[int] = Field(None, ge=1)
    slight_easier_scenario_id: Optional[int] = Field(None, ge=1)
    stage_label: str = Field(default="adaptive", min_length=1, max_length=40)
    assign_training_for_low_readiness: bool = Field(default=True)


class AdaptiveFinalEvaluationRequest(BaseModel):
    baseline_scenario_id: int = Field(..., ge=1)
    final_scenario_id: int = Field(..., ge=1)


class AdaptiveProgramCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    campaign_id: int = Field(..., ge=1)
    baseline_scenario_id: int = Field(..., ge=1)
    final_scenario_id: int = Field(..., ge=1)
    easier_scenario_id: int = Field(..., ge=1)
    same_scenario_id: int = Field(..., ge=1)
    harder_scenario_id: int = Field(..., ge=1)
    targeted_repetition_scenario_id: Optional[int] = Field(None, ge=1)
    slight_easier_scenario_id: Optional[int] = Field(None, ge=1)
    adaptive_rounds: int = Field(default=2, ge=1, le=6)
    baseline_scheduled_at: Optional[datetime] = None
    adaptive_scheduled_at: Optional[datetime] = None
    final_scheduled_at: Optional[datetime] = None


class AdaptiveProgramOut(BaseModel):
    id: int
    name: str
    status: str
    campaign_id: Optional[int] = None
    baseline_scenario_id: int
    final_scenario_id: int
    easier_scenario_id: int
    same_scenario_id: int
    harder_scenario_id: int
    targeted_repetition_scenario_id: Optional[int] = None
    slight_easier_scenario_id: Optional[int] = None
    adaptive_rounds: int
    adaptive_round_index: int
    source_scenario_ids: List[int] = Field(default_factory=list)
    latest_summary: Optional[Dict[str, Any]] = None
    latest_campaigns: List[Dict[str, Any]] = Field(default_factory=list)
    final_evaluation: Optional[Dict[str, Any]] = None
    baseline_scheduled_at: Optional[datetime] = None
    adaptive_scheduled_at: Optional[datetime] = None
    final_scheduled_at: Optional[datetime] = None
    baseline_executed_at: Optional[datetime] = None
    adaptive_executed_at: Optional[datetime] = None
    final_executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AdaptiveProgramAdvanceResponse(BaseModel):
    stage: str
    program: AdaptiveProgramOut
    payload: Dict[str, Any] = Field(default_factory=dict)
