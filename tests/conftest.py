import json
from collections.abc import Callable

import httpx2
import pytest

from eboekhouden_mcp.config import Settings

Handler = Callable[[httpx2.Request], httpx2.Response]


class FakeApi:
    """Records requests and answers like the e-boekhouden API."""

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        self.sessions = 0
        self.expires_in = 3600
        self.reject_tokens: set[str] = set()
        self.routes: dict[tuple[str, str], Handler] = {}

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if request.url.path == "/v1/session" and request.method == "POST":
            self.sessions += 1
            body = json.loads(request.content)
            if body["accessToken"] != "secret-api-token":
                return httpx2.Response(403, json={"Code": "API_SESSION_003"})
            return httpx2.Response(
                200, json={"token": f"session-{self.sessions}", "expiresIn": self.expires_in}
            )
        token = request.headers.get("Authorization")
        if not token or token in self.reject_tokens:
            return httpx2.Response(401)
        handler = self.routes.get((request.method, request.url.path))
        if handler is None:
            return httpx2.Response(404, json={"Title": "Not found"})
        return handler(request)

    @property
    def api_requests(self) -> list[httpx2.Request]:
        return [r for r in self.requests if r.url.path != "/v1/session"]


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def transport(api: FakeApi) -> httpx2.MockTransport:
    return httpx2.MockTransport(api)


@pytest.fixture
def settings() -> Settings:
    return Settings(api_token="secret-api-token", _env_file=None)  # pyright: ignore[reportCallIssue]
