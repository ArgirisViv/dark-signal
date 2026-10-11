from datetime import timedelta
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient, WebSocketDisconnect

from app.api import websocket
from app.core.security import create_access_token
from app.db.base import Base
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User


class FakeWebSocket:
    def __init__(self, token):
        self.query_params = {"token": token}
        self.close_code = None

    async def close(self, code):
        self.close_code = code


def test_operational_websocket_rejects_anonymous_connections():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/ws/analytics"):
                pass

    assert error.value.code == 1008


def test_operational_websocket_rejects_trainee_connections(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'websocket-auth.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    tenant = Tenant(name="WebSocket Workspace", slug="websocket-workspace")
    session.add(tenant)
    session.flush()
    tenant_id = tenant.id
    session.add(User(email="trainee@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id))
    session.commit()
    session.close()
    monkeypatch.setattr(websocket, "SessionLocal", session_factory)

    token = create_access_token(
        {"sub": "trainee@example.com", "tenant_id": tenant_id, "role": "trainee"},
        expires_delta=timedelta(minutes=5),
    )
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(f"/ws/analytics?token={token}"):
                pass

    assert error.value.code == 1008


def test_operational_websocket_accepts_admin_connections(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'websocket-admin.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    tenant = Tenant(name="Admin Workspace", slug="admin-workspace")
    session.add(tenant)
    session.flush()
    tenant_id = tenant.id
    session.add(User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id))
    session.commit()
    session.close()
    monkeypatch.setattr(websocket, "SessionLocal", session_factory)

    token = create_access_token(
        {"sub": "admin@example.com", "tenant_id": tenant_id, "role": "admin"},
        expires_delta=timedelta(minutes=5),
    )
    socket = FakeWebSocket(token)
    user = asyncio.run(websocket.get_websocket_user(socket))

    assert user.email == "admin@example.com"
    assert socket.close_code is None