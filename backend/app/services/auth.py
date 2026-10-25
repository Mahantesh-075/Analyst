from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppException, ErrorCode
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.models.user import User
from app.db.repositories.token import RefreshTokenRepository
from app.db.repositories.user import UserRepository

logger = structlog.get_logger("service.auth")


class AuthService:
    def __init__(self, session: AsyncSession, redis_client: aioredis.Redis[Any] | None = None) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.token_repo = RefreshTokenRepository(session)
        self.redis = redis_client

    async def check_login_rate_limit(self, client_ip: str) -> None:
        """Enforce 5 login attempts per 60 seconds per client IP."""
        if not self.redis:
            return
        key = f"ratelimit:login:{client_ip}"
        try:
            current = await self.redis.incr(key)
            if current == 1:
                await self.redis.expire(key, 60)
            if current > 5:
                logger.warning("login_rate_limit_exceeded", client_ip=client_ip, attempts=current)
                raise AppException(
                    code=ErrorCode.RATE_LIMITED,
                    message="Too many login attempts. Please try again in 1 minute.",
                    status_code=429,
                )
        except AppException:
            raise
        except Exception as e:
            logger.error("redis_rate_limit_error", error=str(e))

    async def register(
        self, email: str, password: str, display_name: str | None = None
    ) -> tuple[User, str, str]:
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise AppException(
                code=ErrorCode.VALIDATION_FAILED,
                message="An account with this email address already exists.",
                status_code=409,
            )

        hashed = hash_password(password)
        user = await self.user_repo.create_user(
            email=email, password_hash=hashed, display_name=display_name
        )

        access_token = create_access_token(user_id=user.id, email=user.email)
        refresh_str = generate_refresh_token()
        refresh_hash = hash_token(refresh_str)
        expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_DAYS)
        await self.token_repo.create_token(
            user_id=user.id, token_hash=refresh_hash, expires_at=expires_at
        )

        logger.info("user_registered", user_id=str(user.id), email=user.email)
        return user, access_token, refresh_str

    async def login(
        self, email: str, password: str, client_ip: str = "unknown"
    ) -> tuple[User, str, str]:
        await self.check_login_rate_limit(client_ip)

        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            logger.warning("login_failed", email=email, client_ip=client_ip)
            raise AppException(
                code=ErrorCode.UNAUTHORIZED,
                message="Invalid email or password",
                status_code=401,
            )

        access_token = create_access_token(user_id=user.id, email=user.email)
        refresh_str = generate_refresh_token()
        refresh_hash = hash_token(refresh_str)
        expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_DAYS)
        await self.token_repo.create_token(
            user_id=user.id, token_hash=refresh_hash, expires_at=expires_at
        )

        logger.info("user_logged_in", user_id=str(user.id), email=user.email)
        return user, access_token, refresh_str

    async def refresh_tokens(self, refresh_token_str: str) -> tuple[str, str]:
        token_hash = hash_token(refresh_token_str)
        stored_token = await self.token_repo.get_by_hash(token_hash)

        if not stored_token:
            logger.warning("refresh_token_not_found")
            raise AppException(
                code=ErrorCode.UNAUTHORIZED,
                message="Invalid refresh token",
                status_code=401,
            )

        now = datetime.now(UTC)

        # Detect token reuse (replay attack)
        if stored_token.revoked_at is not None:
            logger.error(
                "refresh_token_reuse_detected",
                user_id=str(stored_token.user_id),
                token_id=str(stored_token.id),
            )
            # Revoke all sessions for this user immediately and commit
            await self.token_repo.revoke_all_for_user(stored_token.user_id)
            await self.session.commit()
            raise AppException(
                code=ErrorCode.UNAUTHORIZED,
                message="Refresh token reuse detected. All sessions revoked.",
                status_code=401,
            )

        if stored_token.expires_at < now:
            raise AppException(
                code=ErrorCode.TOKEN_EXPIRED,
                message="Refresh token has expired. Please log in again.",
                status_code=401,
            )

        user = await self.user_repo.get_by_id(stored_token.user_id)
        if not user:
            raise AppException(
                code=ErrorCode.UNAUTHORIZED,
                message="User no longer exists",
                status_code=401,
            )

        # Generate new token pair (rotation)
        new_refresh_str = generate_refresh_token()
        new_refresh_hash = hash_token(new_refresh_str)
        expires_at = now + timedelta(days=settings.REFRESH_TOKEN_DAYS)
        new_token = await self.token_repo.create_token(
            user_id=user.id,
            token_hash=new_refresh_hash,
            expires_at=expires_at,
        )

        # Revoke old token and link to replacement
        await self.token_repo.revoke_token(
            token_id=stored_token.id, replaced_by=new_token.id
        )

        new_access_token = create_access_token(user_id=user.id, email=user.email)
        logger.info("tokens_rotated", user_id=str(user.id))
        return new_access_token, new_refresh_str

    async def logout(self, refresh_token_str: str) -> None:
        token_hash = hash_token(refresh_token_str)
        stored_token = await self.token_repo.get_by_hash(token_hash)
        if stored_token and stored_token.revoked_at is None:
            await self.token_repo.revoke_token(token_id=stored_token.id)
            logger.info("user_logged_out", user_id=str(stored_token.user_id))
