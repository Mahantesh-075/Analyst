from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppException, ErrorCode
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.repositories.user import UserRepository
from app.db.session import async_session_factory

if TYPE_CHECKING:
    RedisClient = aioredis.Redis[Any]
    ConnectionPoolType = aioredis.ConnectionPool[Any]
else:
    RedisClient = Any
    ConnectionPoolType = Any

_redis_pool: ConnectionPoolType | None = None


def get_redis_pool() -> ConnectionPoolType:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis() -> AsyncGenerator[RedisClient, None]:
    pool = get_redis_pool()
    client = aioredis.Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.close()


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppException(
            code=ErrorCode.UNAUTHORIZED,
            message="Missing or malformed Authorization header",
            status_code=401,
        )

    token = authorization[7:].strip()
    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AppException(
            code=ErrorCode.UNAUTHORIZED,
            message="Invalid token payload",
            status_code=401,
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError as e:
        raise AppException(
            code=ErrorCode.UNAUTHORIZED,
            message="Invalid user identifier in token",
            status_code=401,
        ) from e

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise AppException(
            code=ErrorCode.UNAUTHORIZED,
            message="User account not found or has been disabled",
            status_code=401,
        )

    return user
