import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please check your .env file.")

engine = create_async_engine(DATABASE_URL, echo=True)

async def init_test_data():
    async with engine.connect() as conn:
        await conn.execute(text("""
            INSERT INTO items (id, name, price, deleted)
            VALUES (1, 'Test Item', 100.0, false)
            ON CONFLICT (id) DO NOTHING
        """))
        await conn.commit()

async def test_non_repeatable_read():
    """READ COMMITTED позволяет non-repeatable read."""
    async with engine.connect() as conn1:
        await conn1.execution_options(isolation_level="READ COMMITTED")
        async with conn1.begin():
            r1 = await conn1.execute(text("SELECT price FROM items WHERE id = 1"))
            p1 = r1.scalar()
            print(f"T1: first read = {p1}")

            async with engine.connect() as conn2:
                async with conn2.begin():
                    await conn2.execute(text("UPDATE items SET price = 999.99 WHERE id = 1"))

            r2 = await conn1.execute(text("SELECT price FROM items WHERE id = 1"))
            p2 = r2.scalar()
            print(f"T1: second read = {p2}")
            if p1 != p2:
                print("✅ Non-repeatable read observed (as expected in READ COMMITTED)")

async def test_repeatable_read_prevents_it():
    """REPEATABLE READ предотвращает non-repeatable read."""
    async with engine.connect() as conn1:
        await conn1.execution_options(isolation_level="REPEATABLE READ")
        async with conn1.begin():
            r1 = await conn1.execute(text("SELECT price FROM items WHERE id = 1"))
            p1 = r1.scalar()
            print(f"T1: first read = {p1}")

            async with engine.connect() as conn2:
                async with conn2.begin():
                    await conn2.execute(text("UPDATE items SET price = 888.88 WHERE id = 1"))

            r2 = await conn1.execute(text("SELECT price FROM items WHERE id = 1"))
            p2 = r2.scalar()
            print(f"T1: second read = {p2}")
            if p1 == p2:
                print("✅ Non-repeatable read prevented (REPEATABLE READ works)")

async def run_all_tests():
    await init_test_data()
    await test_non_repeatable_read()
    await test_repeatable_read_prevents_it()

if __name__ == "__main__":
    asyncio.run(run_all_tests())