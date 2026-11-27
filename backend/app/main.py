from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models.user import User  # noqa: F401 - registers model metadata
from app.seed import create_default_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Convenient for this starter project. Use Alembic migrations in production.
    Base.metadata.create_all(bind=engine)
    create_default_admin()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Starter API with Admin/User roles, JWT authentication, PostgreSQL and Celery.",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
