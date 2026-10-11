import sys
import os
import asyncio
import html
from contextlib import suppress
from app.core.config import settings
from app.core.logging_config import setup_logging, security_logger
from app.core.security_middleware import RateLimitMiddleware, SecurityHeadersMiddleware, InputValidationMiddleware
from app.services.campaign_scheduler import run_campaign_scheduler

# Setup logging
setup_logging(settings.LOG_LEVEL)


from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.responses import JSONResponse, FileResponse, Response, RedirectResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import text
import logging
import time
import json
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

from app.api import auth, scenarios, campaigns, events, analytics, users, email_templates, tenants, directory_integrations
from app.api import stats
from app.api import websocket
from app.db.session import engine
from app.db.session import get_db
from app.db.base import Base
from app.models.campaign import Campaign
from app.models.campaign_recipient_snapshot import CampaignRecipientSnapshot
from app.models.adaptive_program import AdaptiveProgram
from app.models.scenario import Scenario
from app.models.user import User
from app.models.directory_integration import DirectoryIntegration
from app.services.audit import record_event
from sqlalchemy.orm import Session

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
  # Local SQLite development can bootstrap automatically; deployed environments use Alembic.
  if settings.AUTO_CREATE_SCHEMA:
    Base.metadata.create_all(bind=engine)
    # Lightweight migration for new user fields (SQLite)
    with engine.connect() as connection:
        tenant_rows = connection.execute(text("SELECT id FROM tenants LIMIT 1")).fetchall()
        if not tenant_rows:
            connection.execute(
                text("INSERT INTO tenants (name, slug, created_at) VALUES (:name, :slug, :created_at)"),
                {"name": "Default Workspace", "slug": "default", "created_at": datetime.now(timezone.utc)},
            )
        default_tenant_id = connection.execute(
            text("SELECT id FROM tenants WHERE slug = :slug LIMIT 1"),
            {"slug": "default"},
        ).scalar()

        columns = [row[1] for row in connection.execute(text("PRAGMA table_info(users)")).fetchall()]
        if "full_name" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR"))
        if "department" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN department VARCHAR"))
        if "risk" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN risk VARCHAR"))
        if "reset_token_hash" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN reset_token_hash VARCHAR"))
        if "reset_token_expires_at" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN reset_token_expires_at DATETIME"))
        if "tenant_id" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN tenant_id INTEGER"))
        if default_tenant_id is not None:
            connection.execute(
                text("UPDATE users SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
                {"tenant_id": default_tenant_id},
            )
        event_columns = [
            row[1] for row in connection.execute(text("PRAGMA table_info(events)")).fetchall()
        ]
        if "created_at" not in event_columns:
            connection.execute(text("ALTER TABLE events ADD COLUMN created_at DATETIME"))
        if "tenant_id" not in event_columns:
            connection.execute(text("ALTER TABLE events ADD COLUMN tenant_id INTEGER"))
        if "campaign_id" not in event_columns:
          connection.execute(text("ALTER TABLE events ADD COLUMN campaign_id INTEGER"))
        if default_tenant_id is not None:
            connection.execute(
                text("UPDATE events SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
                {"tenant_id": default_tenant_id},
            )
        scenario_columns = [
            row[1] for row in connection.execute(text("PRAGMA table_info(scenarios)")).fetchall()
        ]
        if "tenant_id" not in scenario_columns:
            connection.execute(text("ALTER TABLE scenarios ADD COLUMN tenant_id INTEGER"))
        if "campaign_id" not in scenario_columns:
          connection.execute(text("ALTER TABLE scenarios ADD COLUMN campaign_id INTEGER"))
        if default_tenant_id is not None:
            connection.execute(
                text("UPDATE scenarios SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
                {"tenant_id": default_tenant_id},
            )
        assignment_columns = [
          row[1] for row in connection.execute(text("PRAGMA table_info(training_assignments)")).fetchall()
        ]
        if "module_id" not in assignment_columns:
          connection.execute(text("ALTER TABLE training_assignments ADD COLUMN module_id INTEGER"))
        if "completion_score" not in assignment_columns:
          connection.execute(text("ALTER TABLE training_assignments ADD COLUMN completion_score INTEGER"))
        template_columns = [
          row[1] for row in connection.execute(text("PRAGMA table_info(email_templates)")).fetchall()
        ]
        if "approval_status" not in template_columns:
          connection.execute(text("ALTER TABLE email_templates ADD COLUMN approval_status VARCHAR DEFAULT 'approved'"))
        if "approved_by" not in template_columns:
          connection.execute(text("ALTER TABLE email_templates ADD COLUMN approved_by VARCHAR"))
        if "approved_at" not in template_columns:
          connection.execute(text("ALTER TABLE email_templates ADD COLUMN approved_at DATETIME"))
        if "origin" not in template_columns:
          connection.execute(text("ALTER TABLE email_templates ADD COLUMN origin VARCHAR DEFAULT 'manual'"))
        if "assistant_metadata" not in template_columns:
          connection.execute(text("ALTER TABLE email_templates ADD COLUMN assistant_metadata TEXT"))
        snapshot_columns = [
          row[1] for row in connection.execute(text("PRAGMA table_info(campaign_recipient_snapshots)")).fetchall()
        ]
        if "campaign_id" not in snapshot_columns:
          connection.execute(text("ALTER TABLE campaign_recipient_snapshots ADD COLUMN campaign_id INTEGER"))
        if "interaction_token" not in snapshot_columns:
          connection.execute(text("ALTER TABLE campaign_recipient_snapshots ADD COLUMN interaction_token VARCHAR"))
        adaptive_program_columns = [
          row[1] for row in connection.execute(text("PRAGMA table_info(adaptive_programs)")).fetchall()
        ]
        if "campaign_id" not in adaptive_program_columns:
          connection.execute(text("ALTER TABLE adaptive_programs ADD COLUMN campaign_id INTEGER"))
        adaptive_datetime_columns = (
          "baseline_scheduled_at",
          "adaptive_scheduled_at",
          "final_scheduled_at",
          "baseline_executed_at",
          "adaptive_executed_at",
          "final_executed_at",
          "completed_at",
        )
        for column_name in adaptive_datetime_columns:
          if column_name not in adaptive_program_columns:
            connection.execute(text(f"ALTER TABLE adaptive_programs ADD COLUMN {column_name} DATETIME"))

        index_statements = [
            ("idx_campaigns_name", "CREATE INDEX IF NOT EXISTS idx_campaigns_name ON campaigns (name)"),
            ("idx_campaigns_status", "CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns (status)"),
            ("idx_campaigns_tenant_id", "CREATE INDEX IF NOT EXISTS idx_campaigns_tenant_id ON campaigns (tenant_id)"),
            ("idx_users_email", "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)"),
            ("idx_users_role", "CREATE INDEX IF NOT EXISTS idx_users_role ON users (role)"),
            ("idx_users_department", "CREATE INDEX IF NOT EXISTS idx_users_department ON users (department)"),
            ("idx_users_risk", "CREATE INDEX IF NOT EXISTS idx_users_risk ON users (risk)"),
            ("idx_users_tenant_id", "CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users (tenant_id)"),
            ("idx_scenarios_title", "CREATE INDEX IF NOT EXISTS idx_scenarios_title ON scenarios (title)"),
            ("idx_scenarios_difficulty", "CREATE INDEX IF NOT EXISTS idx_scenarios_difficulty ON scenarios (difficulty)"),
            ("idx_scenarios_tenant_id", "CREATE INDEX IF NOT EXISTS idx_scenarios_tenant_id ON scenarios (tenant_id)"),
            ("idx_scenarios_campaign_id", "CREATE INDEX IF NOT EXISTS idx_scenarios_campaign_id ON scenarios (campaign_id)"),
            ("idx_events_user_id", "CREATE INDEX IF NOT EXISTS idx_events_user_id ON events (user_id)"),
            ("idx_events_scenario_id", "CREATE INDEX IF NOT EXISTS idx_events_scenario_id ON events (scenario_id)"),
            ("idx_events_campaign_id", "CREATE INDEX IF NOT EXISTS idx_events_campaign_id ON events (campaign_id)"),
            ("idx_events_action", "CREATE INDEX IF NOT EXISTS idx_events_action ON events (action)"),
            ("idx_events_created_at", "CREATE INDEX IF NOT EXISTS idx_events_created_at ON events (created_at)"),
            ("idx_events_tenant_id", "CREATE INDEX IF NOT EXISTS idx_events_tenant_id ON events (tenant_id)"),
            ("idx_campaign_snapshots_campaign_id", "CREATE INDEX IF NOT EXISTS idx_campaign_snapshots_campaign_id ON campaign_recipient_snapshots (campaign_id)"),
            ("idx_adaptive_programs_campaign_id", "CREATE INDEX IF NOT EXISTS idx_adaptive_programs_campaign_id ON adaptive_programs (campaign_id)"),
        ]
        for name, statement in index_statements:
            try:
                connection.execute(text(statement))
            except Exception as exc:
                logger.warning("Index %s not created: %s", name, exc)

                connection.commit()

  scheduler_task = asyncio.create_task(run_campaign_scheduler())

  try:
    yield
  finally:
    scheduler_task.cancel()
    with suppress(asyncio.CancelledError):
      await scheduler_task


app = FastAPI(
    title="Dark Signal (Educational)",
    description="Ethical phishing simulation platform for cybersecurity awareness training & behavior analysis. Designed to help organizations understand and mitigate phishing threats through controlled simulations.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {
            "name": "Auth",
            "description": "Authentication and authorization endpoints (login, logout, token refresh)",
        },
        {
            "name": "Users",
            "description": "User management endpoints (CRUD operations, profile management)",
        },
        {
            "name": "Scenarios",
            "description": "Phishing scenario management (create, update, delete, list simulations)",
        },
        {
          "name": "Campaigns",
          "description": "Campaign grouping and scenario aggregation endpoints",
        },
        {
            "name": "Events",
            "description": "Event tracking and logging (user interactions, email opens, link clicks)",
        },
        {
            "name": "Analytics",
            "description": "Analytics and reporting endpoints (statistics, metrics, dashboards)",
        },
        {
            "name": "Health",
            "description": "System health and status checks",
        },
    ],
    lifespan=lifespan,
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["info"]["contact"] = {
        "name": "Dark Signal Team",
        "url": "https://example.com",
    }
    schema["info"]["license"] = {
        "name": "Educational Use Only",
    }
    schema["info"]["x-logo"] = {
        "url": "/static/src/assets/dark-signal-logo.svg"
    }
    schema["servers"] = [
        {"url": "http://127.0.0.1:8000", "description": "Local development"},
    ]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

app.include_router(auth.router, prefix="/auth", tags=["Auth"], responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
app.include_router(scenarios.router, prefix="/scenarios", tags=["Scenarios"], responses={404: {"description": "Scenario not found"}})
app.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"], responses={404: {"description": "Campaign not found"}})
app.include_router(events.router, prefix="/events", tags=["Events"], responses={400: {"description": "Invalid event data"}})
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"], responses={503: {"description": "Analytics service unavailable"}})
app.include_router(users.router, prefix="/users", tags=["Users"], responses={409: {"description": "Conflict - User already exists"}})
app.include_router(email_templates.router, prefix="/email-templates", tags=["Email Templates"], responses={404: {"description": "Template not found"}})
app.include_router(tenants.router, prefix="/tenants", tags=["Tenants"], responses={409: {"description": "Tenant already exists"}})
app.include_router(directory_integrations.router, prefix="/directory-integration", tags=["Directory Integration"])
app.include_router(stats.router, prefix="/stats", tags=["Statistics"], responses={400: {"description": "Invalid parameters"}})
app.include_router(websocket.router, tags=["WebSocket"])


@app.get("/docs", include_in_schema=False)
def redirect_docs():
    return RedirectResponse(url="/api/docs")


@app.get("/redoc", include_in_schema=False)
def custom_redoc():
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{app.title} - ReDoc</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Orbitron:wght@500;600;700&display=swap" rel="stylesheet">
        <style>
          :root {{
            color-scheme: dark;
            --bg: #0b1220;
            --panel: #0f172a;
            --panel-2: #111827;
            --text: #e2e8f0;
            --muted: #94a3b8;
            --primary: #38bdf8;
            --accent: #6366f1;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
          }}
          html, body {{
            height: 100%;
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family: "Inter", system-ui, -apple-system, sans-serif;
          }}
          body::before {{
            content: "";
            position: fixed;
            inset: 0;
            z-index: -1;
            background:
              radial-gradient(circle at 12% 15%, rgba(56, 189, 248, 0.18), transparent 38%),
              radial-gradient(circle at 88% 12%, rgba(99, 102, 241, 0.16), transparent 40%),
              radial-gradient(circle at 50% 90%, rgba(16, 185, 129, 0.12), transparent 45%);
            opacity: 0.75;
          }}
          .hero {{
            padding: 28px 40px;
            background: linear-gradient(90deg, rgba(14, 165, 233, 0.25), rgba(99, 102, 241, 0.25));
            border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          }}
          .hero h1 {{
            margin: 0 0 6px;
            font-size: 26px;
            color: #fff;
            letter-spacing: 0.5px;
            font-family: "Orbitron", "Inter", sans-serif;
          }}
          .hero p {{
            margin: 0;
            color: var(--muted);
          }}
          #redoc {{
            padding: 16px 24px 48px;
          }}
        </style>
      </head>
      <body>
        <div class="hero">
          <h1>{app.title}</h1>
          <p>API reference for Dark Signal backend services.</p>
        </div>
        <div id="redoc"></div>
        <script src="https://unpkg.com/redoc@2/bundles/redoc.standalone.js"></script>
        <script>
          Redoc.init("{app.openapi_url}", {{
            scrollYOffset: 64,
            hideDownloadButton: false,
            expandResponses: "200,201",
            theme: {{
              colors: {{
                primary: {{ main: "#38bdf8" }},
                success: {{ main: "#10b981" }},
                warning: {{ main: "#f59e0b" }},
                error: {{ main: "#ef4444" }}
              }},
              typography: {{
                fontFamily: "Inter, system-ui, -apple-system, sans-serif",
                headings: {{
                  fontFamily: "Orbitron, Inter, sans-serif",
                  fontWeight: "600"
                }},
                code: {{
                  fontFamily: "JetBrains Mono, SFMono-Regular, Menlo, monospace"
                }}
              }},
              sidebar: {{
                backgroundColor: "#0f172a",
                textColor: "#cbd5f5"
              }},
              rightPanel: {{
                backgroundColor: "#0b1220",
                textColor: "#e2e8f0"
              }}
            }}
          }}, document.getElementById("redoc"));
        </script>
      </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/openapi.json", include_in_schema=False)
def redirect_openapi():
    return RedirectResponse(url=app.openapi_url)


@app.get("/api/docs", include_in_schema=False)
def custom_swagger_ui():
    schema_json = json.dumps(app.openapi()).replace("</", "<\\/")
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{app.title} - API Docs</title>
        <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
        <style>
          :root {{
            color-scheme: dark;
            --bg: #0b1220;
            --panel: #0f172a;
            --panel-2: #111827;
            --text: #e2e8f0;
            --muted: #94a3b8;
            --primary: #38bdf8;
            --accent: #6366f1;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
          }}
          html, body {{ background: var(--bg); color: var(--text); }}
          body {{
            font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
            margin: 0;
          }}
          body::before {{
            content: "";
            position: fixed;
            inset: 0;
            z-index: -1;
            background:
              radial-gradient(circle at 10% 10%, rgba(56, 189, 248, 0.18), transparent 35%),
              radial-gradient(circle at 90% 15%, rgba(99, 102, 241, 0.16), transparent 40%),
              radial-gradient(circle at 50% 90%, rgba(16, 185, 129, 0.14), transparent 45%);
            opacity: 0.7;
          }}
          .hero {{
            padding: 36px 48px;
            background: linear-gradient(90deg, rgba(14, 165, 233, 0.25), rgba(99, 102, 241, 0.25));
            border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          }}
          .hero h1 {{
            margin: 0 0 8px;
            font-size: 28px;
            color: #fff;
            letter-spacing: 0.5px;
          }}
          .hero p {{
            margin: 0;
            color: var(--muted);
          }}
          #swagger-ui {{
            padding: 24px 32px 48px;
          }}
          .swagger-ui .topbar {{ display: none; }}
          .swagger-ui .info {{
            background: var(--panel);
            padding: 24px;
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.2);
            box-shadow: 0 12px 32px rgba(2, 6, 23, 0.45);
          }}
          .swagger-ui .info .title {{ color: #fff; font-weight: 700; }}
          .swagger-ui .info .title small,
          .swagger-ui .info .title .version-stamp {{
            display: none;
          }}
          .swagger-ui .info a,
          .swagger-ui .info .url,
          .swagger-ui .info .base-url,
          .swagger-ui .info .link,
          .swagger-ui .info .link a {{
            display: none !important;
          }}
          .swagger-ui .info p, .swagger-ui .info li {{ color: var(--muted); }}
          .swagger-ui .scheme-container {{
            background: var(--panel);
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.2);
            box-shadow: 0 12px 32px rgba(2, 6, 23, 0.45);
          }}
          .swagger-ui .opblock {{
            border-radius: 16px;
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.95), rgba(2, 6, 23, 0.95));
            box-shadow: 0 10px 24px rgba(2, 6, 23, 0.45);
          }}
          .swagger-ui .opblock .opblock-summary {{
            background: linear-gradient(90deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.9));
            border-radius: 16px 16px 0 0;
          }}
          .swagger-ui .opblock .opblock-summary-path,
          .swagger-ui .opblock .opblock-summary-description {{
            color: var(--text);
          }}
          .swagger-ui .opblock-tag {{
            color: #e2e8f0;
            font-size: 1.05rem;
            background: rgba(2, 6, 23, 0.5);
            padding: 0.4rem 0.9rem;
            border-radius: 999px;
            display: inline-block;
            margin-bottom: 0.5rem;
          }}
          .swagger-ui .opblock.opblock-get {{ border-color: var(--success); }}
          .swagger-ui .opblock.opblock-post {{ border-color: var(--primary); }}
          .swagger-ui .opblock.opblock-put {{ border-color: var(--accent); }}
          .swagger-ui .opblock.opblock-delete {{ border-color: var(--danger); }}
          .swagger-ui .btn.authorize {{
            border-color: var(--primary);
            color: var(--primary);
            background: rgba(56, 189, 248, 0.1);
          }}
          .swagger-ui .btn {{ border-radius: 999px; }}
          .swagger-ui input, .swagger-ui select, .swagger-ui textarea {{
            background: #0b1220;
            color: var(--text);
            border: 1px solid #1f2937;
          }}
          .swagger-ui .responses-inner {{
            background: #0b1220;
            border-radius: 12px;
          }}
          .swagger-ui .model {{ color: var(--text); }}
          .swagger-ui .model .property.primitive {{ color: var(--primary); }}
          .swagger-ui .renderedMarkdown code {{ background: rgba(2, 6, 23, 0.6); }}
        </style>
      </head>
      <body>
        <section class="hero">
          <h1>{app.title} — API Explorer</h1>
          <p>Interactive documentation for the cybersecurity training platform.</p>
        </section>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
        <script>
          window.onload = () => {{
            SwaggerUIBundle({{
              spec: {schema_json},
              dom_id: "#swagger-ui",
              presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
              layout: "BaseLayout",
              docExpansion: "none",
              defaultModelsExpandDepth: -1,
              filter: true,
              displayRequestDuration: true,
              persistAuthorization: true
            }});
            const hideLink = () => {{
              const info = document.querySelector(".swagger-ui .info");
              if (!info) return;
              const links = info.querySelectorAll("a");
              links.forEach((link) => {{
                if (link.textContent.includes("/api/openapi.json")) {{
                  const wrapper = link.closest("p") || link;
                  wrapper.remove();
                }}
              }});
            }};
            setTimeout(hideLink, 300);
            setTimeout(hideLink, 1000);
          }};
        </script>
      </body>
    </html>
    """
    return Response(content=html, media_type="text/html")


@app.get("/api/redoc", include_in_schema=False)
def custom_redoc():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API Reference",
        redoc_js_url="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js",
        redoc_favicon_url="https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/1f6e1.svg",
    )


@app.get("/api/docs/swagger.css", include_in_schema=False)
def swagger_custom_css():
    return Response(content="", media_type="text/css")


# Static files serving
BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Mount static files if frontend directory exists
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# Serve frontend pages
@app.get("/", tags=["Frontend"], summary="Landing Page", response_description="Interactive landing page")
async def serve_landing():
    """Serve the main landing page with platform information and features."""
    landing_file = FRONTEND_DIR / "index.html"
    if landing_file.exists():
        return FileResponse(str(landing_file), media_type="text/html")
    return {"message": "Welcome to Dark Signal"}


@app.get("/dashboard", tags=["Frontend"], summary="Analytics Dashboard", response_description="Real-time analytics dashboard")
async def serve_dashboard():
    """Serve the interactive analytics dashboard with real-time charts."""
    dashboard_file = FRONTEND_DIR / "dashboard.html"
    if dashboard_file.exists():
        return FileResponse(str(dashboard_file), media_type="text/html")
    return {"message": "Dashboard page not available"}


@app.get("/api-tester", tags=["Frontend"], summary="API Tester", response_description="Interactive API testing interface")
async def serve_api_tester():
    """Serve the interactive API tester for endpoint experimentation."""
    api_tester_file = FRONTEND_DIR / "api-tester.html"
    if api_tester_file.exists():
        return FileResponse(str(api_tester_file), media_type="text/html")
    return {"message": "API tester not available"}


@app.get("/websocket-demo", tags=["Frontend"], summary="WebSocket activity", response_description="WebSocket real-time activity view")
async def serve_websocket_demo():
    """Serve the WebSocket activity page for live monitoring."""
    ws_demo_file = FRONTEND_DIR / "websocket-demo.html"
    if ws_demo_file.exists():
        return FileResponse(str(ws_demo_file), media_type="text/html")
    return {"message": "WebSocket activity page not available"}


def _resolve_simulation_recipient(
  db: Session,
  *,
  token: str | None,
  scenario_id: int | None,
  user_id: int | None,
) -> tuple[Scenario, User | None]:
  if token:
    snapshot = (
      db.query(CampaignRecipientSnapshot)
      .filter(CampaignRecipientSnapshot.interaction_token == token)
      .first()
    )
    if not snapshot:
      raise HTTPException(status_code=404, detail="Recipient snapshot not found")
    scenario = db.query(Scenario).filter(Scenario.id == snapshot.scenario_id).first()
    if not scenario:
      raise HTTPException(status_code=404, detail="Scenario not found")

    recipient = None
    if snapshot.user_id is not None:
      recipient = (
        db.query(User)
        .filter(User.id == snapshot.user_id)
        .filter(User.tenant_id == scenario.tenant_id)
        .first()
      )
    return scenario, recipient

  if scenario_id is None:
    raise HTTPException(status_code=400, detail="scenario_id or token is required")

  scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
  if not scenario:
    raise HTTPException(status_code=404, detail="Scenario not found")

  recipient = None
  if user_id is not None:
    recipient = (
      db.query(User)
      .filter(User.id == user_id)
      .filter(User.tenant_id == scenario.tenant_id)
      .first()
    )
  return scenario, recipient


@app.get("/simulate/phishing-link", include_in_schema=False)
def phishing_click_training_feedback(
  scenario_id: int | None = Query(None, ge=1),
  token: str | None = Query(None, min_length=8),
  user_id: int | None = Query(None, ge=1),
  preview: bool = Query(False),
  db: Session = Depends(get_db),
):
  """Record a click event and immediately show a micro-learning feedback page."""
  scenario, recipient = _resolve_simulation_recipient(
    db,
    token=token,
    scenario_id=scenario_id,
    user_id=user_id,
  )

  indicators = dict(scenario.indicators or {})
  sender_name = indicators.get("sender_name") or "IT Support Team"
  sender_email = indicators.get("sender_email") or "it-security@companny-support.com"
  claimed_domain = indicators.get("claimed_domain") or "company.com"
  urgency_phrase = (
    indicators.get("urgency_phrase")
    or "Your access will be suspended in 15 minutes unless you act now."
  )
  suspicious_link = indicators.get("link_url") or "http://secure-company-login.example.com/verify"
  credential_request = (
    indicators.get("credential_request")
    or "Confirm your username, password, and MFA code to keep access."
  )
  subject = indicators.get("email_subject") or "Urgent account verification required"
  simulated_body = indicators.get("email_body_text") or (
    "We detected unusual sign-in activity. "
    "Use the secure link below to verify your account immediately."
  )

  if not preview:
    record_event(
      db,
      action="click",
      user_id=recipient.id if recipient else user_id,
      scenario_id=scenario.id,
      tenant_id=scenario.tenant_id,
    )
    db.commit()

  html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Phishing Simulation Feedback</title>
        <style>
          :root {{
            color-scheme: dark;
            --bg: #060913;
            --surface: rgba(15, 23, 42, 0.92);
            --surface-2: rgba(17, 28, 50, 0.9);
            --text: #e2e8f0;
            --muted: #94a3b8;
            --primary: #38bdf8;
            --accent: #6366f1;
            --success: #34d399;
            --warning: #fbbf24;
            --danger: #fb7185;
            --border: rgba(148, 163, 184, 0.2);
          }}
          * {{ box-sizing: border-box; }}
          html {{ min-height: 100%; }}
          body {{
            margin: 0;
            min-height: 100vh;
            font-family: Inter, "Segoe UI", system-ui, -apple-system, sans-serif;
            background:
              radial-gradient(circle at 12% 8%, rgba(56, 189, 248, 0.17), transparent 34%),
              radial-gradient(circle at 88% 5%, rgba(99, 102, 241, 0.16), transparent 36%),
              linear-gradient(145deg, #060913, #0b1220 60%, #070b16);
            color: var(--text);
          }}
          body::before {{
            content: "";
            position: fixed;
            inset: 0;
            z-index: -1;
            background-image:
              linear-gradient(rgba(56, 189, 248, 0.045) 1px, transparent 1px),
              linear-gradient(90deg, rgba(56, 189, 248, 0.045) 1px, transparent 1px);
            background-size: 54px 54px;
            mask-image: linear-gradient(to bottom, black, transparent 86%);
          }}
          .topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            min-height: 68px;
            padding: 0 30px;
            border-bottom: 1px solid var(--border);
            background: rgba(6, 9, 19, 0.78);
            backdrop-filter: blur(16px);
          }}
          .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
          }}
          .brand-mark {{
            position: relative;
            display: grid;
            width: 38px;
            height: 38px;
            place-items: center;
            border: 1px solid rgba(56, 189, 248, 0.55);
            border-radius: 11px;
            background: linear-gradient(145deg, rgba(56, 189, 248, 0.2), rgba(99, 102, 241, 0.16));
            color: #7dd3fc;
            font-size: 18px;
            box-shadow: 0 0 24px rgba(56, 189, 248, 0.18);
          }}
          .brand strong,
          .brand small {{
            display: block;
          }}
          .brand strong {{
            font-family: Orbitron, "Segoe UI", sans-serif;
            font-size: 13px;
            letter-spacing: 0.12em;
          }}
          .brand small {{
            margin-top: 2px;
            color: var(--muted);
            font-size: 11px;
          }}
          .topbar-status {{
            padding: 6px 10px;
            border: 1px solid rgba(52, 211, 153, 0.35);
            border-radius: 999px;
            background: rgba(52, 211, 153, 0.08);
            color: #86efac;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
          }}
          .layout {{
            max-width: 1180px;
            margin: 0 auto;
            padding: 34px 24px 48px;
            display: grid;
            gap: 18px;
            grid-template-columns: minmax(0, 1.15fr) minmax(330px, 0.85fr);
          }}
          .panel {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 18px;
            box-shadow: 0 22px 60px rgba(2, 6, 23, 0.38);
            backdrop-filter: blur(12px);
          }}
          .hero {{
            position: relative;
            overflow: hidden;
            padding: 28px;
            background:
              radial-gradient(circle at 100% 0%, rgba(251, 191, 36, 0.13), transparent 34%),
              linear-gradient(145deg, rgba(15, 23, 42, 0.96), rgba(17, 28, 50, 0.88));
          }}
          .hero::after {{
            content: "";
            position: absolute;
            right: -55px;
            bottom: -85px;
            width: 220px;
            height: 220px;
            border: 1px solid rgba(56, 189, 248, 0.12);
            border-radius: 999px;
            box-shadow: 0 0 0 30px rgba(56, 189, 248, 0.025), 0 0 0 65px rgba(99, 102, 241, 0.02);
          }}
          .hero-heading {{
            position: relative;
            z-index: 1;
            display: flex;
            gap: 16px;
            align-items: flex-start;
          }}
          .status-icon {{
            display: grid;
            flex: 0 0 48px;
            width: 48px;
            height: 48px;
            place-items: center;
            border: 1px solid rgba(251, 191, 36, 0.5);
            border-radius: 14px;
            background: rgba(251, 191, 36, 0.1);
            color: var(--warning);
            font-size: 24px;
            font-weight: 900;
            box-shadow: 0 0 28px rgba(251, 191, 36, 0.12);
          }}
          .eyebrow {{
            display: block;
            margin-bottom: 5px;
            color: #7dd3fc;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.1em;
            text-transform: uppercase;
          }}
          .hero h1 {{
            margin: 0 0 9px;
            max-width: 650px;
            color: #f8fafc;
            font-size: clamp(1.45rem, 3vw, 2rem);
            line-height: 1.18;
          }}
          .hero p {{ margin: 0; color: var(--muted); line-height: 1.6; }}
          .quick-facts {{
            position: relative;
            z-index: 1;
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin-top: 24px;
          }}
          .quick-fact {{
            padding: 12px;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: rgba(2, 6, 23, 0.35);
          }}
          .quick-fact strong,
          .quick-fact span {{ display: block; }}
          .quick-fact strong {{ color: #f8fafc; font-size: 15px; }}
          .quick-fact span {{ margin-top: 3px; color: var(--muted); font-size: 10px; text-transform: uppercase; }}
          .badge {{
            display: inline-block;
            margin-top: 18px;
            background: rgba(251, 113, 133, 0.1);
            color: #fda4af;
            border: 1px solid rgba(251, 113, 133, 0.35);
            border-radius: 999px;
            padding: 6px 11px;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.03em;
            text-transform: uppercase;
          }}
          .risk-list {{ padding: 22px; }}
          .risk-list h2 {{ margin: 0 0 5px; color: #f8fafc; font-size: 1.05rem; }}
          .risk-list > p {{ margin: 0 0 15px; color: var(--muted); font-size: 12px; }}
          .risk-item {{
            border: 1px solid var(--border);
            border-left: 3px solid var(--danger);
            border-radius: 11px;
            padding: 11px 12px;
            margin-bottom: 8px;
            background: rgba(2, 6, 23, 0.3);
          }}
          .risk-item h3 {{ margin: 0 0 5px; color: #f8fafc; font-size: 0.82rem; }}
          .risk-item p {{ margin: 0; color: var(--muted); line-height: 1.45; font-size: 0.76rem; }}
          .risk-item strong {{ color: #cbd5e1; }}
          .email {{
            overflow: hidden;
            padding: 0;
          }}
          .email-client-bar {{
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            align-items: center;
            min-height: 50px;
            padding: 0 16px;
            border-bottom: 1px solid var(--border);
            background: linear-gradient(90deg, #0b1220, #111c32);
          }}
          .window-controls {{ display: flex; gap: 6px; }}
          .window-controls i {{
            width: 9px;
            height: 9px;
            border-radius: 999px;
            background: #fb7185;
          }}
          .window-controls i:nth-child(2) {{ background: #fbbf24; }}
          .window-controls i:nth-child(3) {{ background: #34d399; }}
          .email-client-bar strong {{
            font-family: Orbitron, "Segoe UI", sans-serif;
            font-size: 11px;
            letter-spacing: 0.06em;
          }}
          .email-client-bar span {{
            justify-self: end;
            color: var(--muted);
            font-size: 10px;
            text-transform: uppercase;
          }}
          .email-content {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(310px, 0.72fr);
            gap: 16px;
            padding: 20px;
          }}
          .message-snapshot {{
            overflow: hidden;
            border: 1px solid var(--border);
            border-radius: 14px;
            background: rgba(2, 6, 23, 0.34);
          }}
          .message-head {{
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 12px;
            align-items: center;
            padding: 16px;
            border-bottom: 1px solid var(--border);
          }}
          .sender-avatar {{
            display: grid;
            width: 42px;
            height: 42px;
            place-items: center;
            border-radius: 999px;
            background: linear-gradient(145deg, #0ea5e9, #4f46e5);
            color: white;
            font-weight: 900;
          }}
          .message-head strong,
          .message-head span {{ display: block; }}
          .message-head strong {{ color: #f8fafc; font-size: 13px; }}
          .message-head span {{ margin-top: 2px; color: var(--muted); font-size: 11px; }}
          .email-lines {{ padding: 16px; }}
          .email-line {{
            display: grid;
            grid-template-columns: 72px 1fr;
            gap: 10px;
            margin: 0;
            padding: 9px 0;
            border-bottom: 1px solid rgba(148, 163, 184, 0.11);
            color: #cbd5e1;
            font-size: 12px;
            line-height: 1.5;
          }}
          .email-line:last-child {{ border-bottom: 0; }}
          .email-line strong {{
            color: var(--muted);
            font-size: 10px;
            letter-spacing: 0.05em;
            text-transform: uppercase;
          }}
          .annotated-mail {{
            margin: 0;
            background: rgba(15, 23, 42, 0.72);
            border: 1px solid rgba(56, 189, 248, 0.22);
            border-radius: 14px;
            padding: 16px;
            color: #cbd5e1;
            font-size: 12px;
            line-height: 1.5;
          }}
          .annotated-mail h3 {{
            margin: 0 0 13px;
            color: #f8fafc;
            font-size: 13px;
          }}
          .marker {{
            background: rgba(251, 113, 133, 0.12);
            border: 1px solid rgba(251, 113, 133, 0.32);
            border-radius: 5px;
            padding: 1px 4px;
            color: #fda4af;
            font-weight: 700;
          }}
          .callout {{
            display: inline-block;
            margin-left: 6px;
            background: rgba(56, 189, 248, 0.13);
            color: #7dd3fc;
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 999px;
            padding: 2px 6px;
            font-size: 9px;
            font-weight: 800;
          }}
          .next-step {{
            margin-top: 15px;
            padding: 13px;
            border-radius: 12px;
            background: rgba(52, 211, 153, 0.09);
            border: 1px solid rgba(52, 211, 153, 0.32);
            color: #a7f3d0;
            font-size: 12px;
            font-weight: 700;
            line-height: 1.5;
          }}
          .learning-footer {{
            grid-column: 1 / -1;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            padding: 20px 22px;
            border: 1px solid rgba(52, 211, 153, 0.25);
            border-radius: 16px;
            background: linear-gradient(90deg, rgba(52, 211, 153, 0.1), rgba(56, 189, 248, 0.08));
          }}
          .learning-footer strong,
          .learning-footer span {{ display: block; }}
          .learning-footer strong {{ color: #d1fae5; font-size: 14px; }}
          .learning-footer span {{ margin-top: 3px; color: var(--muted); font-size: 12px; }}
          .complete-badge {{
            flex: 0 0 auto;
            padding: 7px 11px;
            border: 1px solid rgba(52, 211, 153, 0.35);
            border-radius: 999px;
            color: #86efac;
            background: rgba(52, 211, 153, 0.08);
            font-size: 10px;
            font-weight: 800;
            text-transform: uppercase;
          }}
          @media (max-width: 900px) {{
            .layout {{ grid-template-columns: 1fr; padding: 16px; }}
            .email-content {{ grid-template-columns: 1fr; }}
            .quick-facts {{ grid-template-columns: 1fr; }}
            .learning-footer {{ align-items: flex-start; flex-direction: column; }}
          }}
          @media (max-width: 560px) {{
            .topbar {{ padding: 0 16px; }}
            .topbar-status {{ display: none; }}
            .hero {{ padding: 20px; }}
            .hero-heading {{ flex-direction: column; }}
            .email-client-bar {{ grid-template-columns: 1fr auto; }}
            .email-client-bar strong {{ display: none; }}
          }}
        </style>
      </head>
      <body>
        <header class="topbar">
          <div class="brand">
            <div class="brand-mark">◆</div>
            <div>
              <strong>DARK SIGNAL</strong>
              <small>Human Risk Training</small>
            </div>
          </div>
          <span class="topbar-status">Controlled simulation</span>
        </header>
        <main class="layout">
          <section class="panel hero">
            <div class="hero-heading">
              <div class="status-icon">!</div>
              <div>
                <span class="eyebrow">Immediate learning moment</span>
                <h1>This was a simulated phishing message.</h1>
                <p>No harm was done. Review the signals that could have warned you, then use the same checks on future messages.</p>
              </div>
            </div>
            <div class="quick-facts">
              <div class="quick-fact"><strong>5</strong><span>Risk signals found</span></div>
              <div class="quick-fact"><strong>0</strong><span>Credentials collected</span></div>
              <div class="quick-fact"><strong>100%</strong><span>Training safe</span></div>
            </div>
            <span class="badge">{html.escape('Preview mode (no event logged)' if preview else 'Immediate learning feedback')}</span>
          </section>

          <section class="panel risk-list">
            <h2>What to notice next time</h2>
            <p>Use these five checks before opening a link or sharing sensitive information.</p>
            <article class="risk-item">
              <h3>1. Suspicious sender address</h3>
              <p>The sender used <strong>{html.escape(sender_email)}</strong>, which should be validated before clicking any link.</p>
            </article>
            <article class="risk-item">
              <h3>2. Time-pressure tactic</h3>
              <p>The message creates urgency: "{html.escape(urgency_phrase)}" to force quick, unsafe decisions.</p>
            </article>
            <article class="risk-item">
              <h3>3. Name-domain mismatch</h3>
              <p>The sender name <strong>{html.escape(sender_name)}</strong> suggests {html.escape(claimed_domain)}, but the email domain differs.</p>
            </article>
            <article class="risk-item">
              <h3>4. Suspicious link destination</h3>
              <p>The visible link points to <strong>{html.escape(suspicious_link)}</strong>. Always inspect full URLs before opening.</p>
            </article>
            <article class="risk-item">
              <h3>5. Request for personal credentials</h3>
              <p>This message asks for sensitive data: "{html.escape(credential_request)}". Legitimate teams do not request credentials this way.</p>
            </article>
            <div class="next-step">Safe action: report suspicious messages to your security team before taking any action.</div>
          </section>

          <section class="panel email" style="grid-column: 1 / -1;">
            <div class="email-client-bar">
              <div class="window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
              <strong>MESSAGE ANALYSIS</strong>
              <span>Dark Signal secure viewer</span>
            </div>
            <div class="email-content">
              <div class="message-snapshot">
                <div class="message-head">
                  <div class="sender-avatar">{html.escape(sender_name[:2].upper())}</div>
                  <div>
                    <strong>{html.escape(sender_name)}</strong>
                    <span>&lt;{html.escape(sender_email)}&gt; · to you</span>
                  </div>
                </div>
                <div class="email-lines">
                  <div class="email-line"><strong>Subject</strong><span>{html.escape(subject)}</span></div>
                  <div class="email-line"><strong>Message</strong><span>{html.escape(simulated_body)}</span></div>
                  <div class="email-line"><strong>Link</strong><span>{html.escape(suspicious_link)}</span></div>
                  <div class="email-line"><strong>Request</strong><span>{html.escape(credential_request)}</span></div>
                </div>
              </div>

              <div class="annotated-mail">
                <h3>Signal analysis</h3>
                <p><strong>From:</strong> {html.escape(sender_name)} &lt;<span class="marker">{html.escape(sender_email)}</span><span class="callout">Sender check</span>&gt;</p>
                <p><strong>Subject:</strong> {html.escape(subject)} <span class="callout">Pressure cue</span></p>
                <p>
                  {html.escape(simulated_body)}
                  <br /><br />
                  <span class="marker">{html.escape(urgency_phrase)}</span><span class="callout">Urgency</span>
                </p>
                <p><strong>Link:</strong> <span class="marker">{html.escape(suspicious_link)}</span><span class="callout">URL mismatch</span></p>
                <p><strong>Request:</strong> <span class="marker">{html.escape(credential_request)}</span><span class="callout">Credential bait</span></p>
              </div>
            </div>
          </section>

          <section class="learning-footer">
            <div>
              <strong>Pause. Inspect. Report.</strong>
              <span>Verify the sender, hover over links, and report uncertainty before interacting with a suspicious message.</span>
            </div>
            <div class="complete-badge">Learning review complete</div>
          </section>
        </main>
      </body>
    </html>
    """
  return HTMLResponse(content=html_content)


@app.get("/simulate/phishing-open", include_in_schema=False)
def phishing_open_tracking(
    token: str = Query(..., min_length=8),
    db: Session = Depends(get_db),
):
  scenario, recipient = _resolve_simulation_recipient(
    db,
    token=token,
    scenario_id=None,
    user_id=None,
  )
  record_event(
    db,
    action="email.open",
    user_id=recipient.id if recipient else None,
    scenario_id=scenario.id,
    tenant_id=scenario.tenant_id,
  )
  db.commit()
  return Response(status_code=204)


@app.get("/simulate/phishing-report", include_in_schema=False)
def phishing_report_feedback(
    token: str = Query(..., min_length=8),
    db: Session = Depends(get_db),
):
  scenario, recipient = _resolve_simulation_recipient(
    db,
    token=token,
    scenario_id=None,
    user_id=None,
  )
  record_event(
    db,
    action="report",
    user_id=recipient.id if recipient else None,
    scenario_id=scenario.id,
    tenant_id=scenario.tenant_id,
  )
  db.commit()
  return HTMLResponse(
    content=(
      "<html><body style='font-family:Segoe UI,Arial,sans-serif;padding:24px;'>"
      "<h1>Phishing report recorded</h1>"
      "<p>Your security report was logged for this simulated message.</p>"
      "<p>You should continue reporting suspicious messages through the approved channel.</p>"
      "</body></html>"
    )
  )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "message": "Validation error",
            "details": exc.errors(),
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path)
        }
    )


@app.get("/health", tags=["Health"], summary="Health Check", response_description="System health status")
def health_check():
    """
    Check the health status of the Dark Signal API.
    
    Returns information about the system status, version, and operation mode.
    """
    return {
        "status": "ok",
        "mode": settings.APP_MODE,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected"
    }


# Security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(InputValidationMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)


# Request/Response logging middleware
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_body = await request.body()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time * 1000, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info(json.dumps(log_data))
        
        return response


app.add_middleware(LoggingMiddleware)

# CORS middleware configuration (keep outermost for preflight handling)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
