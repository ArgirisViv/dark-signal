from pathlib import Path

from app.api.stats_schemas import ExportRequest


def test_export_request_accepts_numeric_campaign_and_scenario_filters():
    request = ExportRequest(format="csv", campaign_id=4, scenario_id=9)
    assert request.campaign_id == 4
    assert request.scenario_id == 9


def test_nginx_proxies_frontend_api_websocket_route():
    project_root = Path(__file__).resolve().parents[2]
    nginx_config = (project_root / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    websocket_location = nginx_config.split("location /api/ws", 1)[1].split("location /api/", 1)[0]

    assert "proxy_pass http://backend:8000/ws;" in websocket_location
    assert "proxy_set_header Upgrade $http_upgrade;" in websocket_location
    assert 'proxy_set_header Connection "upgrade";' in websocket_location
