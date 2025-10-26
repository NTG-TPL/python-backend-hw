from fastapi import APIRouter, HTTPException, Query, status, Depends
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import ItemDB
from ..schemas import Item, ItemCreate, ItemUpdate

router = APIRouter(prefix="/item", tags=["items"])

@router.post("/", response_model=Item, status_code=status.HTTP_201_CREATED)
async def create_item(item: ItemCreate, session: AsyncSession = Depends(get_db)):
    db_item = ItemDB(**item.model_dump())
    session.add(db_item)
    await session.commit()
    await session.refresh(db_item)
    return Item.model_validate(db_item)

@router.get("/{item_id}", response_model=Item)
async def get_item(item_id: int, session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(ItemDB).where(and_(ItemDB.id == item_id, ItemDB.deleted == False))
    )
    db_item = result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found or deleted")
    return Item.model_validate(db_item)

@router.get("/", response_model=List[Item])
async def list_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = False,
    session: AsyncSession = Depends(get_db),
):
    query = select(ItemDB)
    if not show_deleted:
        query = query.where(ItemDB.deleted == False)
    if min_price is not None:
        query = query.where(ItemDB.price >= min_price)
    if max_price is not None:
        query = query.where(ItemDB.price <= max_price)

    result = await session.execute(query.offset(offset).limit(limit))
    items = result.scalars().all()
    return [Item.model_validate(item) for item in items]

@router.put("/{item_id}", response_model=Item)
async def replace_item(item_id: int, item: ItemCreate, session: AsyncSession = Depends(get_db)):
    db_item = await session.get(ItemDB, item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    for key, value in item.model_dump().items():
        setattr(db_item, key, value)
    await session.commit()
    await session.refresh(db_item)
    return Item.model_validate(db_item)

@router.patch("/{item_id}", response_model=Item)
async def update_item(
    item_id: int,
    item_update: ItemUpdate,
    session: AsyncSession = Depends(get_db)
):
    result = await session.execute(
        select(ItemDB).where(and_(ItemDB.id == item_id, ItemDB.deleted == False))
    )
    db_item = result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found or deleted")
    for field, value in item_update.model_dump(exclude_unset=True).items():
        setattr(db_item, field, value)
    await session.commit()
    await session.refresh(db_item)
    return Item.model_validate(db_item)

@router.delete("/{item_id}", response_model=Item)
async def delete_item(item_id: int, session: AsyncSession = Depends(get_db)):
    db_item = await session.get(ItemDB, item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    db_item.deleted = True
    await session.commit()
    await session.refresh(db_item)
    return Item.model_validate(db_item)