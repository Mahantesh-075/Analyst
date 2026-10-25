import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.dataset import Dataset
from app.db.repositories.base import ScopedRepository


class DummyModelWithoutOwner(Base):
    __tablename__ = "dummy_no_owner"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


def test_scoped_repository_rejects_unscoped_model() -> None:
    session = AsyncMock()
    owner_id = uuid.uuid4()
    with pytest.raises(TypeError, match="does not have an owner_id column"):
        ScopedRepository(DummyModelWithoutOwner, session, owner_id)


@pytest.mark.asyncio
async def test_scoped_repository_query_filtering() -> None:
    session = AsyncMock()
    owner_a = uuid.uuid4()
    owner_b = uuid.uuid4()
    dataset_id = uuid.uuid4()

    repo_a = ScopedRepository(Dataset, session, owner_a)
    repo_b = ScopedRepository(Dataset, session, owner_b)
    assert repo_b.owner_id == owner_b

    # Mock execute result
    mock_result = MagicMock()
    dataset_a = Dataset(
        id=dataset_id,
        owner_id=owner_a,
        name="Sales Data",
        source_filename="sales.csv",
        status="uploaded",
    )

    session.execute.return_value = mock_result
    mock_result.scalar_one_or_none.return_value = dataset_a

    res = await repo_a.get_by_id(dataset_id)
    assert res is not None
    assert res.owner_id == owner_a

    # Verify session.execute was called with a query containing owner_a
    called_query = session.execute.call_args[0][0]
    query_str = str(called_query.compile(compile_kwargs={"literal_binds": True}))
    assert owner_a.hex in query_str or str(owner_a) in query_str
    assert dataset_id.hex in query_str or str(dataset_id) in query_str

    # Test list_items also filters by owner_a
    await repo_a.list_items()
    list_query = session.execute.call_args[0][0]
    list_query_str = str(list_query.compile(compile_kwargs={"literal_binds": True}))
    assert owner_a.hex in list_query_str or str(owner_a) in list_query_str


@pytest.mark.asyncio
async def test_scoped_repository_add_enforces_owner_id() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    owner_id = uuid.uuid4()
    repo = ScopedRepository(Dataset, session, owner_id)

    # Create dataset without explicit owner_id
    new_dataset = Dataset(
        id=uuid.uuid4(),
        name="NGO Survey",
        source_filename="survey.xlsx",
        status="uploaded",
    )

    persisted = await repo.add(new_dataset)
    assert persisted.owner_id == owner_id
    session.add.assert_called_once_with(new_dataset)
    session.flush.assert_called_once()
