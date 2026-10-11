"""
Statistics and analytics schemas for API responses.
Provides Pydantic models for structured data validation and documentation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class StatisticsSummary(BaseModel):
    """Overall statistics summary for the platform"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total_users": 150,
            "total_scenarios": 25,
            "total_campaigns": 12,
            "total_events": 3500,
            "average_click_rate": 32.5,
            "average_report_rate": 8.2,
            "updated_at": "2026-01-20T10:30:00"
        }
    })
    
    total_users: int = Field(..., description="Total number of registered users")
    total_scenarios: int = Field(..., description="Total number of phishing scenarios created")
    total_campaigns: int = Field(..., description="Total number of campaigns created")
    total_events: int = Field(..., description="Total number of recorded events")
    email_recipients: int = Field(default=0, description="Unique users who received at least one simulation email")
    delivered_count: int = Field(default=0, description="Unique delivered user/scenario pairs")
    opened_count: int = Field(default=0, description="Unique recipients who opened an email")
    clicked_count: int = Field(default=0, description="Unique recipients who clicked a link")
    reported_count: int = Field(default=0, description="Unique recipients who reported an email")
    average_click_rate: float = Field(..., description="Average click-through rate percentage")
    average_report_rate: float = Field(..., description="Average phishing report rate percentage")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")


class ScenarioMetrics(BaseModel):
    """Metrics for a specific scenario"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "scenario_id": "scenario_123",
            "scenario_name": "Password Reset Phishing",
            "total_recipients": 50,
            "click_count": 15,
            "report_count": 3,
            "click_rate": 30.0,
            "report_rate": 6.0
        }
    })
    
    scenario_id: str = Field(..., description="Unique scenario identifier")
    scenario_name: str = Field(..., description="Human-readable scenario name")
    total_recipients: int = Field(..., description="Number of recipients")
    click_count: int = Field(..., description="Number of clicks")
    report_count: int = Field(..., description="Number of phishing reports")
    click_rate: float = Field(..., description="Click-through rate percentage")
    report_rate: float = Field(..., description="Reporting rate percentage")


class CampaignMetrics(BaseModel):
    """Metrics for a specific campaign"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "campaign_id": "campaign_123",
            "campaign_name": "Quarterly awareness campaign",
            "scenario_count": 4,
            "total_recipients": 120,
            "click_count": 35,
            "report_count": 8,
            "click_rate": 29.2,
            "report_rate": 6.7,
        }
    })

    campaign_id: str = Field(..., description="Unique campaign identifier")
    campaign_name: str = Field(..., description="Human-readable campaign name")
    scenario_count: int = Field(..., description="Number of scenarios inside the campaign")
    total_recipients: int = Field(..., description="Total recipients across the campaign")
    click_count: int = Field(..., description="Number of clicks")
    report_count: int = Field(..., description="Number of phishing reports")
    open_count: int = Field(default=0, description="Unique recipients who opened the campaign")
    click_rate: float = Field(..., description="Click-through rate percentage")
    report_rate: float = Field(..., description="Reporting rate percentage")
    open_rate: float = Field(default=0.0, description="Open rate percentage")
    awareness_score: float = Field(default=0.0, description="Transparent awareness score from 0 to 100")
    score_explanation: str = Field(default="", description="Human-readable reason for the campaign score")


class UserPerformance(BaseModel):
    """Performance metrics for a specific user"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user_id": "user_123",
            "username": "john.doe",
            "total_scenarios_exposed": 5,
            "clicks": 1,
            "reports": 0,
            "click_rate": 20.0,
            "report_rate": 0.0,
            "training_score": 85.0
        }
    })
    
    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    recipient_id: Optional[str] = Field(None, description="Imported email recipient identifier")
    recipient_email: Optional[str] = Field(None, description="Imported email recipient address")
    total_scenarios_exposed: int = Field(..., description="Total phishing scenarios user was exposed to")
    clicks: int = Field(..., description="Number of times user clicked phishing links")
    reports: int = Field(..., description="Number of times user reported phishing")
    click_rate: float = Field(..., description="User's click-through rate percentage")
    report_rate: float = Field(..., description="User's reporting rate percentage")
    training_score: float = Field(..., description="User's awareness training score (0-100)")
    score_explanation: str = Field(default="", description="Human-readable reason for the user score")


class DashboardData(BaseModel):
    """Complete dashboard data for analytics view"""
    summary: StatisticsSummary = Field(..., description="Platform-wide statistics")
    top_campaigns: List[CampaignMetrics] = Field(default_factory=list, description="Top campaigns by engagement")
    top_scenarios: List[ScenarioMetrics] = Field(..., description="Top phishing scenarios by engagement")
    user_rankings: List[UserPerformance] = Field(..., description="User performance rankings")
    recipient_rankings: List[UserPerformance] = Field(
        default_factory=list,
        description="Awareness rankings calculated only from imported email recipients with recorded deliveries",
    )
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Data refresh timestamp")


class OperationalAlert(BaseModel):
    id: str
    severity: str
    title: str
    description: str
    action_label: str
    action_path: str


class OperationalAlertsResponse(BaseModel):
    alerts: List[OperationalAlert]


class DepartmentBreakdown(BaseModel):
    name: str = Field(..., description="Department name")
    users: int = Field(..., description="Users in department")
    clicks: int = Field(..., description="Total clicks")
    reports: int = Field(..., description="Total reports")
    total_events: int = Field(..., description="Total events")
    click_rate: float = Field(..., description="Click-through rate percentage")
    report_rate: float = Field(..., description="Report rate percentage")
    high_risk_users: int = Field(..., description="Users with elevated computed simulation risk")
    training_assignments: int = Field(..., description="Training assignments for the department")
    completed_training_assignments: int = Field(..., description="Completed training assignments for the department")
    training_completion_rate: float = Field(..., description="Completed training assignment percentage")


class RiskBreakdown(BaseModel):
    risk: str = Field(..., description="Risk level")
    users: int = Field(..., description="Users in risk band")
    clicks: int = Field(..., description="Total clicks")
    reports: int = Field(..., description="Total reports")
    total_events: int = Field(..., description="Total events")
    click_rate: float = Field(..., description="Click-through rate percentage")
    report_rate: float = Field(..., description="Report rate percentage")


class BreakdownsResponse(BaseModel):
    departments: List[DepartmentBreakdown]
    risks: List[RiskBreakdown]


class TrendPoint(BaseModel):
    date: str = Field(..., description="UTC date in YYYY-MM-DD format")
    events: int = Field(..., description="Total events")
    clicks: int = Field(..., description="Total clicks")
    reports: int = Field(..., description="Total reports")
    click_rate: float = Field(..., description="Click-through rate percentage")
    report_rate: float = Field(..., description="Report rate percentage")


class TrendsResponse(BaseModel):
    points: List[TrendPoint]


class GeoPoint(BaseModel):
    city: str = Field(..., description="City name (mock)")
    country: str = Field(..., description="Country name (mock)")
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")
    count: int = Field(..., description="Number of click events mapped to this location")


class GeoEventSample(BaseModel):
    event_id: int = Field(..., description="Event identifier")
    ip: str = Field(..., description="Mock IP address")
    city: str = Field(..., description="City name (mock)")
    country: str = Field(..., description="Country name (mock)")
    created_at: datetime = Field(..., description="Event timestamp")


class GeoResponse(BaseModel):
    points: List[GeoPoint]
    samples: List[GeoEventSample]


class ExportFormat(str):
    """Supported export formats"""
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"


class ExportRequest(BaseModel):
    """Request model for data export"""
    format: str = Field(..., description="Export format (csv, json, pdf)", pattern="^(csv|json|pdf)$")
    include_users: bool = Field(default=True, description="Include user data")
    include_scenarios: bool = Field(default=True, description="Include scenario data")
    include_events: bool = Field(default=False, description="Include detailed event logs")
    scenario_id: Optional[int] = Field(None, ge=1, description="Optional scenario filter")
    campaign_id: Optional[int] = Field(None, ge=1, description="Optional campaign filter")
    date_from: Optional[datetime] = Field(None, description="Filter data from this date")
    date_to: Optional[datetime] = Field(None, description="Filter data to this date")


class BatchOperation(BaseModel):
    """Batch operation request"""
    operation: str = Field(..., description="Operation type (activate, deactivate, delete, email_alert)")
    user_ids: List[str] = Field(..., description="List of user IDs to operate on")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Additional operation parameters")


class BatchOperationResult(BaseModel):
    """Result of batch operation"""
    operation: str = Field(..., description="Operation type that was performed")
    total_users: int = Field(..., description="Total users processed")
    successful: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")
    errors: Optional[List[str]] = Field(None, description="Error messages from failed operations")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Operation completion time")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""
    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(50, ge=1, le=100, description="Number of items to return (max 100)")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: str = Field("asc", pattern="^(asc|desc)$", description="Sort order (asc or desc)")


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper"""
    total: int = Field(..., description="Total number of items")
    skip: int = Field(..., description="Items skipped")
    limit: int = Field(..., description="Items returned")
    items: List[Dict[str, Any]] = Field(..., description="Page items")
    has_more: bool = Field(..., description="Whether there are more items available")
