import secrets
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
import config



_PROTECTED_PREFIX = config.API_PREFIX
_PUBLIC_PREFIX = f"{config.API_PREFIX}/auth"


def issue_token() -> str:
    return secrets.token_urlsafe(32)


async def require_bearer_token(request: Request, call_next) -> Response:
    """Reject any non-auth request that arrives without a bearer token."""
    path = request.url.path
    if not path.startswith(_PROTECTED_PREFIX) or path.startswith(_PUBLIC_PREFIX):
        return await call_next(request)

    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        return JSONResponse(
            {"detail": "missing bearer token"},
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)
