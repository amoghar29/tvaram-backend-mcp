from fastapi import APIRouter

from models import VerifyEmailRequest, VerifyEmailResult
from service.verification import EmailServiceDep

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/verify")
def verify_email(
    payload: VerifyEmailRequest,
    service: EmailServiceDep,
) -> VerifyEmailResult:
    return service.classify(payload.address)
