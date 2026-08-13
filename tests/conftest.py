from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastmcp import Client

import config
import mcp_server
import mock_server
from client import EmailVerifierClient


@asynccontextmanager
async def mock_verifier() -> AsyncIterator[EmailVerifierClient]:
    async with mock_server.app.router.lifespan_context(mock_server.app):
        transport = httpx.ASGITransport(app=mock_server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://mock") as http:
            yield EmailVerifierClient(
                client_id=config.VERIFIER_CLIENT_ID,
                client_secret=config.VERIFIER_CLIENT_SECRET,
                http=http,
            )


@asynccontextmanager
async def connect(
    verifier: EmailVerifierClient, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Client]:
    monkeypatch.setattr(mcp_server, "build_verifier", lambda: verifier)
    async with Client(mcp_server.mcp) as client:
        yield client


@pytest.fixture
async def agent(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Client]:
    async with mock_verifier() as verifier, connect(verifier, monkeypatch) as client:
        yield client


class ScriptedBackend:
    def __init__(self, *verify_statuses: int) -> None:
        self._verify_statuses = list(verify_statuses)
        self.token_requests = 0
        self.verify_requests = 0

    def _respond(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            self.token_requests += 1
            return httpx.Response(
                200,
                json={
                    "access_token": f"token-{self.token_requests}",
                    "token_type": "bearer",
                    "expires_in": 300,
                },
            )

        self.verify_requests += 1
        status = self._verify_statuses.pop(0) if self._verify_statuses else 200

        if status != 200:
            return httpx.Response(status, json={"detail": "scripted failure"})

        return httpx.Response(
            200,
            json={
                "address": "alice@example.com",
                "verdict": "valid",
                "reason": "syntax is well formed and the domain is not flagged",
            },
        )

    @asynccontextmanager
    async def verifier(self) -> AsyncIterator[EmailVerifierClient]:
        transport = httpx.MockTransport(self._respond)
        async with httpx.AsyncClient(transport=transport, base_url="http://backend") as http:
            yield EmailVerifierClient(client_id="id", client_secret="secret", http=http)
