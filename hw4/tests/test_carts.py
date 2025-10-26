import pytest
import pytest_asyncio
from sqlalchemy import select
from shop_api.models import CartDB, ItemDB, CartItemDB


class TestCarts:

    @pytest.mark.asyncio
    async def test_create_cart_returns_201_and_location_header(self, client):
        """Проверяет, что создание корзины возвращает статус 201, заголовок Location и тело."""
        response = await client.post("/cart/")

        assert response.status_code == 201
        data = response.json()
        cart_id = data["id"]
        assert response.headers.get("Location") == f"/cart/{cart_id}"
        assert data == {"id": cart_id}

    @pytest.mark.asyncio
    async def test_get_cart_returns_404_if_not_found(self, client):
        non_existent_id = 999
        response = await client.get(f"/cart/{non_existent_id}")

        assert response.status_code == 404
        assert response.json() == {"detail": "Cart not found"}

    @pytest.mark.asyncio
    async def test_get_cart_returns_empty_cart_if_found(self, client, test_db_session):
        cart = CartDB()
        test_db_session.add(cart)
        await test_db_session.commit()
        await test_db_session.refresh(cart)

        response = await client.get(f"/cart/{cart.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cart.id
        assert data["items"] == []
        assert data["price"] == 0.0

    @pytest.mark.asyncio
    async def test_get_cart_returns_cart_with_items(self, client, test_db_session):
        cart = CartDB()
        item1 = ItemDB(name="Товар 1", price=10.0, deleted=False)
        item2 = ItemDB(name="Товар 2", price=20.0, deleted=False)
        test_db_session.add_all([cart, item1, item2])
        await test_db_session.commit()
        await test_db_session.refresh(cart)
        await test_db_session.refresh(item1)
        await test_db_session.refresh(item2)

        cart_item1 = CartItemDB(cart_id=cart.id, item_id=item1.id, quantity=2)
        cart_item2 = CartItemDB(cart_id=cart.id, item_id=item2.id, quantity=1)
        test_db_session.add_all([cart_item1, cart_item2])
        await test_db_session.commit()

        response = await client.get(f"/cart/{cart.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cart.id
        assert len(data["items"]) == 2
        assert data["price"] == 40.0

        items = {item["id"]: item for item in data["items"]}
        assert items[item1.id] == {
            "id": item1.id,
            "name": item1.name,
            "quantity": 2,
            "available": True,
        }
        assert items[item2.id] == {
            "id": item2.id,
            "name": item2.name,
            "quantity": 1,
            "available": True,
        }

    @pytest.mark.asyncio
    async def test_get_cart_marks_deleted_items_as_unavailable(self, client, test_db_session):
        cart = CartDB()
        deleted_item = ItemDB(name="Удалённый товар", price=5.0, deleted=True)
        test_db_session.add_all([cart, deleted_item])
        await test_db_session.commit()
        await test_db_session.refresh(cart)
        await test_db_session.refresh(deleted_item)

        cart_item = CartItemDB(cart_id=cart.id, item_id=deleted_item.id, quantity=1)
        test_db_session.add(cart_item)
        await test_db_session.commit()

        response = await client.get(f"/cart/{cart.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["price"] == 0.0

        item_in_cart = data["items"][0]
        assert item_in_cart == {
            "id": deleted_item.id,
            "name": "Unknown Item",
            "quantity": 1,
            "available": False,
        }

    @pytest.mark.asyncio
    async def test_list_carts_returns_empty_list_if_no_carts(self, client):
        response = await client.get("/cart/")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_carts_filters_by_price_range(self, client, test_db_session):
        cart1 = CartDB()
        cart2 = CartDB()
        cart3 = CartDB()
        item1 = ItemDB(name="Т1", price=10.0, deleted=False)
        item2 = ItemDB(name="Т2", price=20.0, deleted=False)
        item3 = ItemDB(name="Удалённый", price=5.0, deleted=True)
        test_db_session.add_all([cart1, cart2, cart3, item1, item2, item3])
        await test_db_session.commit()
        await test_db_session.refresh(cart1)
        await test_db_session.refresh(cart2)
        await test_db_session.refresh(cart3)

        test_db_session.add_all([
            CartItemDB(cart_id=cart1.id, item_id=item1.id, quantity=1),
            CartItemDB(cart_id=cart2.id, item_id=item2.id, quantity=2),
            CartItemDB(cart_id=cart2.id, item_id=item3.id, quantity=1),
        ])
        await test_db_session.commit()

        response = await client.get("/cart/", params={"min_price": 15, "max_price": 45})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == cart2.id
        assert data[0]["price"] == 40.0

    @pytest.mark.asyncio
    async def test_list_carts_filters_by_quantity_range(self, client, test_db_session):
        cart1 = CartDB()
        cart2 = CartDB()
        cart3 = CartDB()
        item1 = ItemDB(name="Т1", price=10.0, deleted=False)
        item2 = ItemDB(name="Т2", price=20.0, deleted=False)
        item3 = ItemDB(name="Удалённый", price=5.0, deleted=True)
        test_db_session.add_all([cart1, cart2, cart3, item1, item2, item3])
        await test_db_session.commit()
        await test_db_session.refresh(cart1)
        await test_db_session.refresh(cart2)
        await test_db_session.refresh(cart3)

        test_db_session.add_all([
            CartItemDB(cart_id=cart1.id, item_id=item1.id, quantity=1),
            CartItemDB(cart_id=cart2.id, item_id=item2.id, quantity=2),
            CartItemDB(cart_id=cart2.id, item_id=item3.id, quantity=1),
        ])
        await test_db_session.commit()

        response = await client.get("/cart/", params={"min_quantity": 2})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == cart2.id

    @pytest.mark.asyncio
    async def test_list_carts_applies_pagination(self, client, test_db_session):
        carts = [CartDB() for _ in range(5)]
        test_db_session.add_all(carts)
        await test_db_session.commit()
        for cart in carts:
            await test_db_session.refresh(cart)

        response = await client.get("/cart/", params={"offset": 2, "limit": 2})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == carts[2].id
        assert data[1]["id"] == carts[3].id

    @pytest.mark.asyncio
    async def test_list_carts_handles_edge_case_min_price_zero(self, client, test_db_session):
        empty_cart = CartDB()
        test_db_session.add(empty_cart)
        await test_db_session.commit()

        response = await client.get("/cart/", params={"min_price": 0})

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_list_carts_handles_edge_case_min_quantity_zero(self, client, test_db_session):
        empty_cart = CartDB()
        test_db_session.add(empty_cart)
        await test_db_session.commit()

        response = await client.get("/cart/", params={"min_quantity": 0})

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_list_carts_handles_max_quantity_filter(self, client, test_db_session):
        cart = CartDB()
        item = ItemDB(name="Товар", price=10.0, deleted=False)
        test_db_session.add_all([cart, item])
        await test_db_session.commit()
        await test_db_session.refresh(cart)
        await test_db_session.refresh(item)

        test_db_session.add(CartItemDB(cart_id=cart.id, item_id=item.id, quantity=5))
        await test_db_session.commit()

        response = await client.get("/cart/", params={"max_quantity": 3})
        assert response.status_code == 200
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_list_carts_returns_empty_list_for_impossible_filter(self, client, test_db_session):
        cart = CartDB()
        item = ItemDB(name="Товар", price=10.0, deleted=False)
        test_db_session.add_all([cart, item])
        await test_db_session.commit()

        test_db_session.add(CartItemDB(cart_id=cart.id, item_id=item.id, quantity=1))
        await test_db_session.commit()

        response = await client.get("/cart/", params={"min_price": 999999})
        assert response.status_code == 200
        assert response.json() == []


    @pytest.mark.asyncio
    async def test_add_item_to_cart_returns_400_for_invalid_item_id(self, client, test_db_session):
        cart = CartDB()
        test_db_session.add(cart)
        await test_db_session.commit()
        await test_db_session.refresh(cart)

        response = await client.post(f"/cart/{cart.id}/add/0")

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid item_id"}

    @pytest.mark.asyncio
    async def test_add_item_to_cart_returns_404_if_cart_not_found(self, client, test_db_session):
        item = ItemDB(name="Товар", price=10.0, deleted=False)
        test_db_session.add(item)
        await test_db_session.commit()

        response = await client.post(f"/cart/999/add/{item.id}")

        assert response.status_code == 404
        assert response.json() == {"detail": "Cart not found"}

    @pytest.mark.asyncio
    async def test_add_item_to_cart_returns_404_if_item_not_found_or_deleted(self, client, test_db_session):
        cart = CartDB()
        deleted_item = ItemDB(name="Удалённый", price=10.0, deleted=True)
        test_db_session.add_all([cart, deleted_item])
        await test_db_session.commit()
        await test_db_session.refresh(cart)

        response = await client.post(f"/cart/{cart.id}/add/{deleted_item.id}")

        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found or unavailable"}

    @pytest.mark.asyncio
    async def test_add_item_to_cart_creates_new_cart_item_if_not_exists(self, client, test_db_session):
        cart = CartDB()
        item = ItemDB(name="Новый товар", price=100.0, deleted=False)
        test_db_session.add_all([cart, item])
        await test_db_session.commit()
        await test_db_session.refresh(cart)
        await test_db_session.refresh(item)

        response = await client.post(f"/cart/{cart.id}/add/{item.id}")

        assert response.status_code == 200
        assert response.json() == {"message": "Item added to cart"}

        cart_items = await test_db_session.execute(
            select(CartItemDB).where(CartItemDB.cart_id == cart.id)
        )
        items = cart_items.scalars().all()
        assert len(items) == 1
        assert items[0].item_id == item.id
        assert items[0].quantity == 1

    @pytest.mark.asyncio
    async def test_add_item_to_cart_increases_quantity_if_item_exists(self, client, test_db_session):
        cart = CartDB()
        item = ItemDB(name="Существующий товар", price=50.0, deleted=False)
        test_db_session.add_all([cart, item])
        await test_db_session.commit()
        await test_db_session.refresh(cart)
        await test_db_session.refresh(item)

        initial_cart_item = CartItemDB(cart_id=cart.id, item_id=item.id, quantity=5)
        test_db_session.add(initial_cart_item)
        await test_db_session.commit()

        response = await client.post(f"/cart/{cart.id}/add/{item.id}")

        assert response.status_code == 200
        assert response.json() == {"message": "Item added to cart"}

        await test_db_session.refresh(initial_cart_item)
        assert initial_cart_item.quantity == 6