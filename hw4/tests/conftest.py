import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from shop_api.main import app
from shop_api.database import get_db
from shop_api.models import Base


@pytest_asyncio.fixture(scope="session")
def anyio_backend():
    """Настройка для anyio (требуется для pytest-asyncio в strict mode)."""
    return 'asyncio'


@pytest_asyncio.fixture(scope="function")
async def test_db_session():
    """Фикстура для создания изолированной in-memory SQLite БД для каждого теста."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_db_session):
    transport = httpx.ASGITransport(app=app)

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()