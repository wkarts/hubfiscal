import pytest
from httpx import ASGITransport, AsyncClient

from hubfiscal.main import app


@pytest.mark.asyncio
async def test_live_health_is_not_broken_by_metrics() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "hubfiscal-api"


@pytest.mark.asyncio
async def test_metrics_endpoint_is_available() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.get("/api/v1/health/live")
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "hubfiscal_http_requests_total" in response.text
    assert "hubfiscal_http_request_duration_seconds" in response.text
