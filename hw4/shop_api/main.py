from fastapi import FastAPI
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
from .routes import items, carts
from .database import engine
from .models import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title="Shop API", lifespan=lifespan)

app.include_router(items.router, tags=["items"])
app.include_router(carts.router, tags=["carts"])

Instrumentator().instrument(app).expose(app)

@app.get("/")
async def root():
    return {"message": "Shop API is running"}