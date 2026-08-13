import re
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from models import Verdict, VerifyEmailResult

MAX_ADDRESS_LENGTH = 254
MAX_LOCAL_LENGTH = 64

ADDRESS_PATTERN = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,}"
)

DISPOSABLE_DOMAINS = frozenset(
    {
        "mailinator.com",
        "10minutemail.com",
        "guerrillamail.com",
        "yopmail.com",
        "tempmail.com",
        "throwaway.email",
    }
)


@dataclass(frozen=True, slots=True)
class EmailVerificationService:
    disposable_domains: frozenset[str] = DISPOSABLE_DOMAINS
    max_address_length: int = MAX_ADDRESS_LENGTH
    max_local_length: int = MAX_LOCAL_LENGTH

    def classify(self, address: str) -> VerifyEmailResult:
        normalized = address.strip().lower()

        if len(normalized) > self.max_address_length:
            return VerifyEmailResult(
                address=normalized,
                verdict=Verdict.INVALID,
                reason=f"address is longer than {self.max_address_length} characters",
            )

        if not ADDRESS_PATTERN.fullmatch(normalized):
            return VerifyEmailResult(
                address=normalized,
                verdict=Verdict.INVALID,
                reason="address does not match the expected email syntax",
            )

        local, domain = normalized.rsplit("@", 1)

        if len(local) > self.max_local_length:
            return VerifyEmailResult(
                address=normalized,
                verdict=Verdict.INVALID,
                reason=f"local part is longer than {self.max_local_length} characters",
            )

        if domain in self.disposable_domains:
            return VerifyEmailResult(
                address=normalized,
                verdict=Verdict.RISKY,
                reason=f"{domain} is a disposable email provider",
            )

        return VerifyEmailResult(
            address=normalized,
            verdict=Verdict.VALID,
            reason="syntax is well formed and the domain is not flagged",
        )


def get_email_service(request: Request) -> EmailVerificationService:
    """Hand out the singleton built by the application lifespan."""
    return request.app.state.email_service


EmailServiceDep = Annotated[EmailVerificationService, Depends(get_email_service)]
