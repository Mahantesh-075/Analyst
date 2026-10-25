from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RedisClient, get_current_user, get_db, get_redis
from app.db.models.user import User
from app.db.repositories.user import UserRepository
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    data: UserRegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[RedisClient, Depends(get_redis)],
) -> TokenResponse:
    service = AuthService(session, redis)
    _, access_token, refresh_token = await service.register(
        email=data.email,
        password=data.password,
        display_name=data.display_name,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in with email and password",
)
async def login(
    data: UserLoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[RedisClient, Depends(get_redis)],
) -> TokenResponse:
    client_ip = get_client_ip(request)
    service = AuthService(session, redis)
    _, access_token, refresh_token = await service.login(
        email=data.email,
        password=data.password,
        client_ip=client_ip,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and obtain new access token",
)
async def refresh_tokens(
    data: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[RedisClient, Depends(get_redis)],
) -> TokenResponse:
    service = AuthService(session, redis)
    access_token, new_refresh_token = await service.refresh_tokens(
        refresh_token_str=data.refresh_token
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Revoke refresh token session",
)
async def logout(
    data: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[RedisClient, Depends(get_redis)],
) -> dict[str, str]:
    service = AuthService(session, redis)
    await service.logout(refresh_token_str=data.refresh_token)
    return {"status": "logged_out"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
)
async def update_me(
    data: UserUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    repo = UserRepository(session)
    updates = data.model_dump(exclude_unset=True)
    updated_user = await repo.update_user(current_user, **updates)
    return UserResponse.model_validate(updated_user)
