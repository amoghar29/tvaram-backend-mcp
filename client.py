import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

import config
from models import TokenResponse, VerifyEmailResult

logger = logging.getLogger(__name__)


class VerifierError(Exception):
    pass


class AuthError(VerifierError):
    pass


class UpstreamError(VerifierError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def is_retryable(error: Exception) -> bool:
    if not isinstance(error, UpstreamError):
        return False
    return error.status_code is None or 500 <= error.status_code < 600


async def retry[T](operation: Callable[[], Awaitable[T]], description: str) -> T:
    attempt = 0
    while True:
        try:
            return await operation()
        except VerifierError as error:
            if attempt == config.MAX_RETRIES or not is_retryable(error):
                logger.error(
                    "%s failed after %d attempt(s): %s",
                    description,
                    attempt + 1,
                    type(error).__name__,
                )
                raise

            delay = config.BACKOFF_BASE_SECONDS * 2**attempt
            logger.warning(
                "retrying %s in %.2fs (attempt %d of %d)",
                description,
                delay,
                attempt + 1,
                config.MAX_RETRIES,
            )
            await asyncio.sleep(delay)
            attempt += 1


class EmailVerifierClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        http: httpx.AsyncClient,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http
        self._token_value: str | None = None
        self._token_expires_at = 0.0
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            return await self._http.post(
                path,
                json=payload,
                headers=headers,
                timeout=config.REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            logger.error("POST %s timed out after %.1fs", path, config.REQUEST_TIMEOUT_SECONDS)
            raise UpstreamError(
                f"{path} did not respond within {config.REQUEST_TIMEOUT_SECONDS}s"
            ) from exc
        except httpx.RequestError as exc:
            logger.error("POST %s could not be sent: %s", path, type(exc).__name__)
            raise UpstreamError(f"could not reach the verification backend: {exc}") from exc

    async def _request_token(self) -> str:
        path = f"{config.API_PREFIX}/auth/token"
        response = await self._post(
            path,
            {"client_id": self._client_id, "client_secret": self._client_secret},
        )
        if response.status_code == httpx.codes.UNAUTHORIZED:
            logger.error("%s rejected the configured client credentials", path)
            raise AuthError("the verification backend rejected the configured client credentials")

        if response.is_error:
            logger.error("%s returned HTTP %d", path, response.status_code)
            raise UpstreamError(
                f"token endpoint returned HTTP {response.status_code}", response.status_code
            )

        token = TokenResponse.model_validate(response.json())
        self._token_value = token.access_token
        self._token_expires_at = (
            time.monotonic() + token.expires_in - config.TOKEN_EXPIRY_MARGIN_SECONDS
        )
        return token.access_token

    async def _token(self) -> str:
        async with self._lock:
            if self._token_value is not None and self._token_expires_at > time.monotonic():
                return self._token_value
            return await self._request_token()

    def _discard_token(self, token: str) -> None:
        """Drop the cached token, unless another call already replaced it."""
        if self._token_value == token:
            self._token_value = None

    async def _verify_once(self, address: str) -> VerifyEmailResult:
        path = f"{config.API_PREFIX}/email/verify"
        payload = {"address": address}

        token = await self._token()
        response = await self._post(path, payload, {"Authorization": f"Bearer {token}"})

        if response.status_code == httpx.codes.UNAUTHORIZED:
            logger.warning("%s rejected the cached token, re-authenticating", path)
            self._discard_token(token)
            fresh = await self._token()
            response = await self._post(path, payload, {"Authorization": f"Bearer {fresh}"})

            if response.status_code == httpx.codes.UNAUTHORIZED:
                logger.error("%s rejected a freshly issued token", path)
                raise AuthError("the verification backend rejected a freshly issued token")

        if response.is_error:
            logger.error("%s returned HTTP %d", path, response.status_code)
            raise UpstreamError(
                f"verification failed with HTTP {response.status_code}",
                response.status_code,
            )

        return VerifyEmailResult.model_validate(response.json())

    async def verify(self, address: str) -> VerifyEmailResult:
        return await retry(lambda: self._verify_once(address), "email verification")
