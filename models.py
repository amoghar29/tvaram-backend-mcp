from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Verdict(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    RISKY = "risky"


class VerifyEmailRequest(BaseModel):
    address: str


class VerifyEmailResult(BaseModel):
    address: str = Field(description="The address that was checked, lowercased.")
    verdict: Verdict = Field(
        description=(
            "valid: syntax is well formed and the address looks deliverable. "
            "invalid: syntax is malformed, the address cannot receive mail. "
            "risky: syntax is well formed but the domain is a disposable "
            "provider, so delivery is unreliable."
        )
    )
    reason: str = Field(description="Which rule produced the verdict.")


class TokenRequest(BaseModel):
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
