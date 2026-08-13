import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import PlainTextResponse

import config
from routers import auth, email
from auth_middleware import require_bearer_token
from service.verification import EmailVerificationService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.email_service = EmailVerificationService()
    yield


app = FastAPI(title="Mock Email Verification API", lifespan=lifespan)
app.middleware("http")(require_bearer_token)


@app.exception_handler(Exception)
async def log_unhandled_error(request: Request, exc: Exception) -> PlainTextResponse:
    """Record that a request blew up, then hand back Starlette's own 500.

    The path is safe to log; the query string and body are not, so neither is
    read. Starlette re-raises exc after this returns, so the original traceback
    still reaches the server.
    """
    logger.error(
        "unhandled error on %s %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return PlainTextResponse("Internal Server Error", status_code=500)


v1 = APIRouter(prefix=config.API_VERSION)
v1.include_router(auth.router)
v1.include_router(email.router)

api = APIRouter(prefix=config.API_BASE)
api.include_router(v1)

app.include_router(api)


if __name__ == "__main__":
    uvicorn.run(app, host=config.MOCK_HOST, port=config.MOCK_PORT, access_log=False)
