from fastapi import APIRouter

import config
from models import TokenRequest, TokenResponse
from auth_middleware import issue_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
def issue_access_token(payload: TokenRequest) -> TokenResponse:
    """Hand out a token to anyone who asks.

    The mock does not check the credentials it is given; the point of the
    endpoint is that the client has something to send on later calls.
    """
    return TokenResponse(
        access_token=issue_token(),
        expires_in=config.TOKEN_TTL_SECONDS,
    )
