import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base


class ScopedRepository[T: Base]:
    """Base repository that strictly scopes all database queries by owner_id.

    Prevents Insecure Direct Object References (IDOR) by construction.
    Any attempt to access another user's resource results in None (which translates
    to 404 NOT_FOUND at the API layer, never 403, preventing enumeration).
    """

    def __init__(self, model_cls: type[T], session: AsyncSession, owner_id: uuid.UUID) -> None:
        if not hasattr(model_cls, "owner_id"):
            raise TypeError(f"Model {model_cls.__name__} does not have an owner_id column.")
        self.model_cls = model_cls
        self.session = session
        self.owner_id = owner_id

    def _scope_query(self, query: Select[tuple[T]]) -> Select[tuple[T]]:
        """Applies mandatory owner_id filter to a select query."""
        model_any: Any = self.model_cls
        owner_col = model_any.owner_id
        return query.where(owner_col == self.owner_id)

    async def get_by_id(self, item_id: uuid.UUID) -> T | None:
        """Fetch a single record by ID, strictly filtered by owner_id."""
        model_any: Any = self.model_cls
        id_col = model_any.id
        owner_col = model_any.owner_id
        query = select(self.model_cls).where(and_(id_col == item_id, owner_col == self.owner_id))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_items(
        self,
        offset: int = 0,
        limit: int = 50,
        extra_filters: Sequence[Any] = (),
    ) -> Sequence[T]:
        """List records with pagination, strictly filtered by owner_id."""
        model_any: Any = self.model_cls
        owner_col = model_any.owner_id
        query = select(self.model_cls).where(owner_col == self.owner_id)
        for f in extra_filters:
            query = query.where(f)
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def add(self, entity: T) -> T:
        """Persist a new record, automatically enforcing owner_id assignment."""
        setattr(entity, "owner_id", self.owner_id)  # noqa: B010
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, item_id: uuid.UUID) -> bool:
        """Delete a record by ID, only if owned by owner_id."""
        item = await self.get_by_id(item_id)
        if item is None:
            return False
        await self.session.delete(item)
        await self.session.flush()
        return True
