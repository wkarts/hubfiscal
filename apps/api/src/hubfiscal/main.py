from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from . import __version__
from .api.router import api_router
from .bootstrap.seed import seed
from .build_info import get_build_info
from .core.config import get_settings
from .core.logging import configure_logging
from .core.metrics import install_metrics

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed()
    yield


app = FastAPI(
    title="Hub Fiscal API",
    description="Plataforma fiscal multiempresa orientada a plugins",
    version=__version__,
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
install_metrics(app)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "Hub Fiscal API",
        "version": __version__,
        "build": get_build_info().as_dict(),
        "docs": "/docs",
    }
