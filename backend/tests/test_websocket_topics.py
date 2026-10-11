import asyncio
import json

from app.api.websocket import ConnectionManager, tenant_topic


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_text(self, message):
        self.messages.append(json.loads(message))


def test_tenant_scoped_topic_only_reaches_its_subscribers():
    manager = ConnectionManager()
    tenant_one_socket = FakeWebSocket()
    tenant_two_socket = FakeWebSocket()
    manager.subscribe(tenant_one_socket, tenant_topic(1, "analytics"))
    manager.subscribe(tenant_two_socket, tenant_topic(2, "analytics"))

    asyncio.run(manager.broadcast({"type": "analytics_update"}, topic=tenant_topic(1, "analytics")))

    assert [message["type"] for message in tenant_one_socket.messages] == ["analytics_update"]
    assert tenant_two_socket.messages == []