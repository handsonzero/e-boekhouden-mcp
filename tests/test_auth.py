import httpx2
import pytest
from pydantic import SecretStr

from eboekhouden_mcp.auth import SessionAuth, SessionError
from tests.conftest import FakeApi


def ok(_: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(200, json={"items": [], "count": 0})


def client(api: FakeApi, token: str = "secret-api-token") -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        base_url="https://api.test",
        auth=SessionAuth(SecretStr(token), "MCP"),
        transport=httpx2.MockTransport(api),
    )


async def test_session_is_reused(api: FakeApi) -> None:
    api.routes[("GET", "/v1/unit")] = ok
    async with client(api) as c:
        for _ in range(3):
            assert (await c.get("/v1/unit")).status_code == 200
    assert api.sessions == 1
    assert all(r.headers["Authorization"] == "session-1" for r in api.api_requests)


async def test_session_refreshes_when_expired(api: FakeApi) -> None:
    api.routes[("GET", "/v1/unit")] = ok
    api.expires_in = 0  # Already within the expiry margin.
    async with client(api) as c:
        await c.get("/v1/unit")
        await c.get("/v1/unit")
    assert api.sessions == 2


async def test_retries_once_on_401(api: FakeApi) -> None:
    api.routes[("GET", "/v1/unit")] = ok
    async with client(api) as c:
        await c.get("/v1/unit")
        api.reject_tokens.add("session-1")  # Server revoked the session.
        response = await c.get("/v1/unit")
    assert response.status_code == 200
    assert api.sessions == 2
    assert api.api_requests[-1].headers["Authorization"] == "session-2"


async def test_invalid_api_token_raises(api: FakeApi) -> None:
    async with client(api, token="wrong") as c:
        with pytest.raises(SessionError, match="403"):
            await c.get("/v1/unit")
