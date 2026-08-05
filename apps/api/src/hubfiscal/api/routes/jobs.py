from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...dependencies import AuthContext, current_context
from ...models import RetrievalJob
from ...schemas import RetrievalJobCreate, RetrievalJobOut
from ...worker import execute_retrieval_task

router = APIRouter(prefix="/retrieval-jobs", tags=["Consultas e jobs"])


@router.get("", response_model=list[RetrievalJobOut])
async def list_jobs(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: return []
    return list((await db.scalars(select(RetrievalJob).where(RetrievalJob.tenant_id == context.tenant_id).order_by(RetrievalJob.created_at.desc()).limit(200))).all())


@router.post("", response_model=RetrievalJobOut, status_code=202)
async def create_job(payload: RetrievalJobCreate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: raise HTTPException(status_code=400, detail="Selecione um tenant")
    item = RetrievalJob(tenant_id=context.tenant_id, requested_by=context.user.id, **payload.model_dump())
    db.add(item); await db.commit(); await db.refresh(item)
    execute_retrieval_task.delay(str(item.id))
    return item


@router.get("/{job_id}", response_model=RetrievalJobOut)
async def get_job(job_id: UUID, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    item = await db.scalar(select(RetrievalJob).where(RetrievalJob.id == job_id, RetrievalJob.tenant_id == context.tenant_id))
    if item is None: raise HTTPException(status_code=404, detail="Job não encontrado")
    return item
