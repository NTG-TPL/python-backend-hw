from fastapi import APIRouter, HTTPException, Query, status, Response, Depends
from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import CartDB, CartItemDB, ItemDB
from ..schemas import Cart, CartItem

router = APIRouter(prefix="/cart", tags=["carts"])

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_cart(response: Response, session: AsyncSession = Depends(get_db)):
    cart = CartDB()
    session.add(cart)
    await session.commit()
    await session.refresh(cart)
    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}

@router.get("/{cart_id}", response_model=Cart)
async def get_cart(cart_id: int, session: AsyncSession = Depends(get_db)):
    stmt = (
        select(CartDB, CartItemDB, ItemDB)
        .outerjoin(CartItemDB, CartDB.id == CartItemDB.cart_id)
        .outerjoin(ItemDB, CartItemDB.item_id == ItemDB.id)
        .where(CartDB.id == cart_id)
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows or not rows[0][0]:
        raise HTTPException(status_code=404, detail="Cart not found")

    cart_db = rows[0][0]
    items = []
    total_price = 0.0

    for _, cart_item, item in rows:
        if cart_item is None:
            continue
        available = bool(item and not item.deleted)
        name = item.name if available else "Unknown Item"
        price = item.price if available else 0.0
        total_price += cart_item.quantity * price
        items.append(
            CartItem(
                id=cart_item.item_id,
                name=name,
                quantity=cart_item.quantity,
                available=available
            )
        )

    return Cart(id=cart_db.id, items=items, price=total_price)

@router.get("/", response_model=List[Cart])
async def list_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0),
    session: AsyncSession = Depends(get_db),
):
    subq = (
        select(
            CartItemDB.cart_id,
            func.sum(CartItemDB.quantity).label("total_quantity"),
            func.sum(CartItemDB.quantity * ItemDB.price).label("computed_price")
        )
        .join(ItemDB, and_(CartItemDB.item_id == ItemDB.id, ItemDB.deleted == False))
        .group_by(CartItemDB.cart_id)
        .subquery()
    )

    query = (
        select(CartDB, subq.c.total_quantity, subq.c.computed_price)
        .outerjoin(subq, CartDB.id == subq.c.cart_id)
        .order_by(CartDB.id)
    )

    if min_price is not None:
        if min_price > 0:
            query = query.where(subq.c.computed_price.is_not(None)).where(subq.c.computed_price >= min_price)
        else:
            query = query.where((subq.c.computed_price >= min_price) | subq.c.computed_price.is_(None))

    if max_price is not None:
        query = query.where((subq.c.computed_price <= max_price) | subq.c.computed_price.is_(None))

    if min_quantity is not None:
        if min_quantity > 0:
            query = query.where(subq.c.total_quantity.is_not(None)).where(subq.c.total_quantity >= min_quantity)
        else:
            query = query.where((subq.c.total_quantity >= min_quantity) | subq.c.total_quantity.is_(None))

    if max_quantity is not None:
        query = query.where((subq.c.total_quantity <= max_quantity) | subq.c.total_quantity.is_(None))

    result = await session.execute(query.offset(offset).limit(limit))
    rows = result.all()

    if not rows:
        return []

    cart_ids = [row[0].id for row in rows]

    if cart_ids:
        cart_items_stmt = (
            select(CartItemDB, ItemDB)
            .outerjoin(ItemDB, CartItemDB.item_id == ItemDB.id)
            .where(CartItemDB.cart_id.in_(cart_ids))
        )
        cart_items_result = await session.execute(cart_items_stmt)
        all_cart_items = cart_items_result.all()

        items_by_cart = {}
        for ci, item in all_cart_items:
            if ci.cart_id not in items_by_cart:
                items_by_cart[ci.cart_id] = []
            available = bool(item and not item.deleted)
            name = item.name if available else "Unknown Item"
            items_by_cart[ci.cart_id].append(
                CartItem(
                    id=ci.item_id,
                    name=name,
                    quantity=ci.quantity,
                    available=available
                )
            )
    else:
        items_by_cart = {}

    carts = []
    for cart_db, total_qty, computed_price in rows:
        items = items_by_cart.get(cart_db.id, [])
        price = float(computed_price) if computed_price is not None else 0.0
        carts.append(Cart(id=cart_db.id, items=items, price=price))

    return carts

@router.post("/{cart_id}/add/{item_id}")
async def add_item_to_cart(
    cart_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_db)
):
    if item_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid item_id")

    cart = await session.get(CartDB, cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    item_result = await session.execute(
        select(ItemDB).where(and_(ItemDB.id == item_id, ItemDB.deleted == False))
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found or unavailable")

    cart_item_result = await session.execute(
        select(CartItemDB).where(
            CartItemDB.cart_id == cart_id,
            CartItemDB.item_id == item_id
        )
    )
    cart_item = cart_item_result.scalar_one_or_none()

    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItemDB(cart_id=cart_id, item_id=item_id, quantity=1)
        session.add(cart_item)

    await session.commit()
    return {"message": "Item added to cart"}