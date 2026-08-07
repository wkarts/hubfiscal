from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...dependencies import AuthContext, require_resource
from ...models import LegalEntity, RetrievalJob
from ...schemas import RetrievalJobCreate, RetrievalJobOut
from ...worker import execute_retrieval_task

router = APIRouter(prefix="/retrieval-jobs", tags=["Consultas e jobs"])
jobs_context = require_resource("jobs")
query_context = require_resource("query")
DOCUMENT_RESOURCES = {"nfe", "nfce", "cte", "mdfe", "nfse", "dfe"}


def _scope_ids(context: AuthContext) -> list[UUID]:
    try:
        return [UUID(value) for value in context.entity_scope]
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Escopo de CNPJ inválido") from exc


@router.get("", response_model=list[RetrievalJobOut])
async def list_jobs(context: AuthContext = Depends(jobs_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None:
        return []
    stmt = select(RetrievalJob).where(RetrievalJob.tenant_id == context.tenant_id)
    if context.entity_scope:
        stmt = stmt.where(RetrievalJob.legal_entity_id.in_(_scope_ids(context)))
    return list((await db.scalars(stmt.order_by(RetrievalJob.created_at.desc()).limit(200))).all())


@router.post("", response_model=RetrievalJobOut, status_code=202)
async def create_job(payload: RetrievalJobCreate, context: AuthContext = Depends(query_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    if payload.document_type in DOCUMENT_RESOURCES and payload.document_type not in context.enabled_resources:
        raise HTTPException(status_code=403, detail=f"Recurso {payload.document_type.upper()} não habilitado para o perfil")

    if payload.legal_entity_id:
        entity = await db.scalar(
            select(LegalEntity).where(
                LegalEntity.id == payload.legal_entity_id,
                LegalEntity.tenant_id == context.tenant_id,
            )
        )
        if entity is None:
            raise HTTPException(status_code=422, detail="CNPJ não pertence ao tenant")
        if context.entity_scope and str(entity.id) not in context.entity_scope:
            raise HTTPException(status_code=403, detail="Usuário não possui acesso ao CNPJ informado")
        required = {"query", payload.document_type}
        missing = sorted(required - set(entity.enabled_resources or []))
        if missing:
            raise HTTPException(status_code=403, detail=f"CNPJ não possui os recursos habilitados: {', '.join(missing)}")

    item = RetrievalJob(tenant_id=context.tenant_id, requested_by=context.user.id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    execute_retrieval_task.delay(str(item.id))
    return item


@router.get("/{job_id}", response_model=RetrievalJobOut)
async def get_job(job_id: UUID, context: AuthContext = Depends(jobs_context), db: AsyncSession = Depends(get_db)):
    stmt = select(RetrievalJob).where(RetrievalJob.id == job_id, RetrievalJob.tenant_id == context.tenant_id)
    if context.entity_scope:
        stmt = stmt.where(RetrievalJob.legal_entity_id.in_(_scope_ids(context)))
    item = await db.scalar(stmt)
    if item is None:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return item
