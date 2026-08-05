from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...build_info import get_build_info
from ...core.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": "hubfiscal-api",
        "build": get_build_info().as_dict(),
    }


@router.get("/health/live")
async def live():
    return {
        "status": "ok",
        "service": "hubfiscal-api",
        "build": get_build_info().as_dict(),
    }
