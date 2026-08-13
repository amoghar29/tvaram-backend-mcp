import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.auth import ClientRegistrationOptions

import config
from client import EmailVerifierClient, VerifierError
from models import VerifyEmailResult
from oauth_provider import ConsentOAuthProvider

logger = logging.getLogger(__name__)

verifier: EmailVerifierClient | None = None


def build_verifier() -> EmailVerifierClient:
    return EmailVerifierClient(
        client_id=config.VERIFIER_CLIENT_ID,
        client_secret=config.VERIFIER_CLIENT_SECRET,
        http=httpx.AsyncClient(base_url=config.VERIFIER_BASE_URL),
    )


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    global verifier
    verifier = build_verifier()
    try:
        yield
    finally:
        await verifier.aclose()
        verifier = None


def build_auth() -> ConsentOAuthProvider | None:
    if not config.MCP_AUTH_ENABLED:
        return None

    return ConsentOAuthProvider(
        base_url=config.MCP_BASE_URL,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[config.MCP_SCOPE],
            default_scopes=[config.MCP_SCOPE],
        ),
    )


mcp = FastMCP("tvram-email-verification", lifespan=lifespan, auth=build_auth())


@mcp.tool
async def verify_email(address: str) -> VerifyEmailResult:
    """Check whether an email address is well formed and likely deliverable.

    Use this before sending mail to an address the user supplied, or when asked
    whether an address is real. Returns a verdict of valid, invalid, or risky
    (well formed but a disposable provider), with the rule that decided it.

    Args:
        address: The single email address to check, e.g. "alice@example.com".
    """
    if verifier is None:
        logger.error("verify_email was called before the client was initialised")
        raise ToolError("the email verification client is not initialised")

    try:
        return await verifier.verify(address)
    except VerifierError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:

        logger.error("verify_email failed unexpectedly: %s", type(exc).__name__)
        raise ToolError("email verification failed for an unexpected reason") from exc


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=config.MCP_HOST,
        port=config.MCP_PORT,
        uvicorn_config={"access_log": False},
    )
