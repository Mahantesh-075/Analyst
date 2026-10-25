from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.json_utils import sanitize_for_json
from app.db.models.profile import ColumnProfile, Profile


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_version_id(self, version_id: UUID) -> Profile | None:
        query = (
            select(Profile)
            .where(Profile.version_id == version_id)
            .options(selectinload(Profile.column_profiles))
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def create_profile(
        self,
        version_id: UUID,
        engine_version: str,
        summary: dict[str, Any],
        columns_data: list[dict[str, Any]],
    ) -> Profile:
        # Delete existing profile for version if present
        existing = await self.get_by_version_id(version_id)
        if existing:
            await self.session.delete(existing)
            await self.session.flush()

        profile = Profile(
            version_id=version_id,
            engine_version=engine_version,
            summary=sanitize_for_json(summary),
        )
        self.session.add(profile)
        try:
            async with self.session.begin_nested():
                await self.session.flush()
        except IntegrityError:
            # If concurrent creation already created it, return the existing profile
            found = await self.get_by_version_id(version_id)
            if found:
                return found
            raise

        for c in columns_data:
            col_prof = ColumnProfile(
                profile_id=profile.id,
                position=c["position"],
                name=c["name"],
                inferred_dtype=c["inferred_dtype"],
                semantic_type=c.get("semantic_type"),
                semantic_desc=c.get("semantic_desc"),
                semantic_confidence=c.get("semantic_confidence"),
                null_count=c["null_count"],
                null_pct=c["null_pct"],
                distinct_count=c.get("distinct_count"),
                stats=sanitize_for_json(c.get("stats", {})),
                missing_tokens=c.get("missing_tokens", []),
                pii_types=c.get("pii_types", []),
                is_pii=c.get("is_pii", False),
            )
            self.session.add(col_prof)

        await self.session.flush()
        return await self.get_by_version_id(version_id)  # type: ignore[return-value]
