from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from .api.router import api_router
from .bootstrap.seed import seed
from .core.config import get_settings
from .core.logging import configure_logging

configure_logging()
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed()
    yield

app = FastAPI(
    title="Hub Fiscal API",
    description="Plataforma fiscal multiempresa orientada a plugins",
    version="0.1.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

@app.get("/", include_in_schema=False)
async def root():
    return {"name": "Hub Fiscal API", "version": "0.1.0", "docs": "/docs"}
