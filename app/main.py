import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import create_tables
from app.routers import auth, posts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()  # local-development convenience; see README
    yield


app = FastAPI(
    title="Blogging Platform API",
    description="A REST API with JWT authentication and blog post CRUD with ownership checks.",
    version="1.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(posts.router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Blogging Platform API is running"}
