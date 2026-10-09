"""Session-token authentication for the e-boekhouden API.

The API token is exchanged for a short-lived session token via `POST /v1/session`.
The session token is cached, refreshed shortly before it expires, and refreshed once
more if the API answers 401. The session request is sent through the same client
(as part of the auth flow), so it shares its transport, timeouts and hooks.
"""

import asyncio
import time
from collections.abc import AsyncGenerator

import httpx2
from pydantic import SecretStr

SESSION_PATH = "/v1/session"
# Refresh this many seconds before the session token actually expires.
EXPIRY_MARGIN = 60


class SessionError(Exception):
    """Starting an e-boekhouden session failed (e.g. invalid or expired API token)."""


class SessionAuth(httpx2.Auth):
    def __init__(self, api_token: SecretStr, source: str) -> None:
        self._api_token = api_token
        self._source = source
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def token(self) -> str | None:
        return self._token

    async def async_auth_flow(
        self, request: httpx2.Request
    ) -> AsyncGenerator[httpx2.Request, httpx2.Response]:
        async with self._lock:
            if self._token is None or time.monotonic() >= self._expires_at:
                session_response = yield self._session_request(request)
                await self._store(session_response)
        used = self._current_token()
        request.headers["Authorization"] = used
        response = yield request

        if response.status_code == 401:
            async with self._lock:
                # Skip refreshing if a concurrent request already did.
                if self._token == used:
                    session_response = yield self._session_request(request)
                    await self._store(session_response)
            request.headers["Authorization"] = self._current_token()
            yield request

    def _current_token(self) -> str:
        if self._token is None:
            raise SessionError("No e-boekhouden session token available")
        return self._token

    def _session_request(self, request: httpx2.Request) -> httpx2.Request:
        return httpx2.Request(
            "POST",
            request.url.copy_with(path=SESSION_PATH, query=None),
            json={"accessToken": self._api_token.get_secret_value(), "source": self._source},
        )

    async def _store(self, response: httpx2.Response) -> None:
        await response.aread()
        if response.is_error:
            raise SessionError(
                f"Could not start e-boekhouden session ({response.status_code}): {response.text}"
            )
        data = response.json()
        self._token = str(data["token"])
        self._expires_at = time.monotonic() + int(data["expiresIn"]) - EXPIRY_MARGIN
