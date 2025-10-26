import pytest
import pytest_asyncio
from sqlalchemy import select
from shop_api.models import ItemDB


class TestItems:

    @pytest.mark.asyncio
    async def test_create_item_returns_201_and_created_item(self, client, test_db_session):
        item_data = {"name": "Тестовый товар", "price": 100.0}

        response = await client.post("/item/", json=item_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == item_data["name"]
        assert data["price"] == item_data["price"]
        assert "id" in data
        assert data["deleted"] is False

        db_item = await test_db_session.get(ItemDB, data["id"])
        assert db_item is not None
        assert db_item.name == item_data["name"]


    @pytest.mark.asyncio
    async def test_get_item_returns_404_if_not_found(self, client):
        response = await client.get("/item/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found or deleted"}

    @pytest.mark.asyncio
    async def test_get_item_returns_404_if_deleted(self, client, test_db_session):
        deleted_item = ItemDB(name="Удалённый", price=10.0, deleted=True)
        test_db_session.add(deleted_item)
        await test_db_session.commit()

        response = await client.get(f"/item/{deleted_item.id}")

        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found or deleted"}

    @pytest.mark.asyncio
    async def test_get_item_returns_item_if_found(self, client, test_db_session):
        item = ItemDB(name="Найденный товар", price=99.99, deleted=False)
        test_db_session.add(item)
        await test_db_session.commit()
        await test_db_session.refresh(item)

        response = await client.get(f"/item/{item.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item.id
        assert data["name"] == item.name
        assert data["price"] == item.price
        assert data["deleted"] == item.deleted

    @pytest.mark.asyncio
    async def test_list_items_filters_by_price_and_show_deleted(self, client, test_db_session):
        item1 = ItemDB(name="Товар 1", price=10.0, deleted=False)
        item2 = ItemDB(name="Товар 2", price=20.0, deleted=False)
        deleted_item = ItemDB(name="Удалённый", price=5.0, deleted=True)
        test_db_session.add_all([item1, item2, deleted_item])
        await test_db_session.commit()

        response = await client.get("/item/", params={"min_price": 15, "max_price": 25})
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == item2.name

        response = await client.get("/item/", params={"show_deleted": True})
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_list_items_applies_pagination(self, client, test_db_session):
        items = [
            ItemDB(name=f"Товар {i}", price=float(i), deleted=False) for i in range(1, 6)
        ]
        test_db_session.add_all(items)
        await test_db_session.commit()

        response = await client.get("/item/", params={"offset": 1, "limit": 2})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Товар 2"
        assert data[1]["name"] == "Товар 3"

    @pytest.mark.asyncio
    async def test_replace_item_returns_404_if_not_found(self, client):
        new_data = {"name": "Новое имя", "price": 200.0}
        response = await client.put("/item/999", json=new_data)

        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found"}

    @pytest.mark.asyncio
    async def test_replace_item_updates_all_fields(self, client, test_db_session):
        item = ItemDB(name="Старое имя", price=100.0, deleted=False)
        test_db_session.add(item)
        await test_db_session.commit()
        await test_db_session.refresh(item)

        new_data = {"name": "Новое имя", "price": 200.0}
        response = await client.put(f"/item/{item.id}", json=new_data)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item.id
        assert data["name"] == new_data["name"]
        assert data["price"] == new_data["price"]

        await test_db_session.refresh(item)
        assert item.name == new_data["name"]

    @pytest.mark.asyncio
    async def test_update_item_returns_404_if_not_found(self, client):
        update_data = {"price": 75.5}
        response = await client.patch("/item/999", json=update_data)

        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found or deleted"}

    @pytest.mark.asyncio
    async def test_update_item_returns_404_if_deleted(self, client, test_db_session):
        deleted_item = ItemDB(name="Удалённый", price=10.0, deleted=True)
        test_db_session.add(deleted_item)
        await test_db_session.commit()

        update_data = {"price": 75.5}
        response = await client.patch(f"/item/{deleted_item.id}", json=update_data)

        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found or deleted"}

    @pytest.mark.asyncio
    async def test_update_item_partially_updates_fields(self, client, test_db_session):
        item = ItemDB(name="Имя для обновления", price=50.0, deleted=False)
        test_db_session.add(item)
        await test_db_session.commit()
        await test_db_session.refresh(item)

        update_data = {"price": 75.5}
        response = await client.patch(f"/item/{item.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item.id
        assert data["name"] == item.name
        assert data["price"] == update_data["price"]

        # Проверка в БД
        await test_db_session.refresh(item)
        assert item.price == update_data["price"]


    @pytest.mark.asyncio
    async def test_delete_item_returns_404_if_not_found(self, client):
        response = await client.delete("/item/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found"}

    @pytest.mark.asyncio
    async def test_delete_item_marks_item_as_deleted(self, client, test_db_session):
        item = ItemDB(name="Товар для удаления", price=10.0, deleted=False)
        test_db_session.add(item)
        await test_db_session.commit()
        await test_db_session.refresh(item)

        response = await client.delete(f"/item/{item.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"]