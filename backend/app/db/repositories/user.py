from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        query = select(User).where(User.email == email.strip().lower())
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_id(self, user_id: UUID) -> User | None:
        query = select(User).where(User.id == user_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def create_user(
        self,
        email: str,
        password_hash: str,
        display_name: str | None = None,
        llm_enabled: bool = True,
    ) -> User:
        user = User(
            email=email.strip().lower(),
            password_hash=password_hash,
            display_name=display_name,
            llm_enabled=llm_enabled,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_user(self, user: User, **kwargs: Any) -> User:
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await self.session.flush()
        return user
