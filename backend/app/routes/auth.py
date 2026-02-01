"""Authentication routes."""

from fastapi import APIRouter, Depends

from ..auth import create_token, verify_token
from ..models import LoginRequest, LoginResponse

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    token = create_token(body.pin)
    return LoginResponse(token=token)


@router.get("/auth/verify")
async def verify(user: str = Depends(verify_token)):
    return {"status": "authenticated", "user": user}
