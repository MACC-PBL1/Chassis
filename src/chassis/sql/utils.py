from sqlalchemy import (
    Select, 
    Update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import (
    List,
    Optional,
    Tuple,
    Type,
    TypeVar
)

T = TypeVar("T")

async def get_list(db: AsyncSession, model: Type[T]) -> List[T]:
    """Retrieve a list of elements from database."""
    result = await db.execute(select(model))
    return list(result.unique().scalars().all())

async def get_list_statement_result(
    db: AsyncSession,
    stmt: Select[Tuple[T]],
) -> List[T]:
    """Execute given statement and return list of items."""
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())

async def get_element_statement_result(
    db: AsyncSession, 
    stmt: Select[Tuple[T]],
) -> Optional[T]:
    """Execute statement and return a single item."""
    result = await db.execute(stmt)
    return result.scalar()

async def get_element_by_id(
    db: AsyncSession, 
    model: Type[T], 
    element_id: int
) -> Optional[T]:
    """Retrieve any DB element by id."""
    return await db.get(model, element_id)

async def delete_element_by_id(
    db: AsyncSession, 
    model: Type[T], 
    element_id: int
) -> None:
    """Delete any DB element by id."""
    element = await get_element_by_id(db, model, element_id)
    if element is not None:
        await db.delete(element)
        await db.commit()
        await db.flush()

async def update_elements_statement_result(
    db: AsyncSession,
    stmt: Update
) -> None:
    _ = await db.execute(stmt)
    await db.commit()