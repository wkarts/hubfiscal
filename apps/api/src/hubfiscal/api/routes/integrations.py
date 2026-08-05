from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...integration_dependencies import ApiClientContext, require_scope
from ...models import FiscalDocument, RetrievalJob
from ...schemas import DocumentOut, RetrievalJobCreate, RetrievalJobOut
from ...worker import execute_retrieval_task

router = APIRouter(prefix="/integrations", tags=["Integrações ERP"])

@router.get("/documents", response_model=list[DocumentOut])
async def documents(
    ctx: ApiClientContext = Depends(require_scope("documents:read")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(FiscalDocument).where(FiscalDocument.tenant_id == ctx.tenant_id).order_by(FiscalDocument.created_at.desc()).limit(200)
    return list((await db.scalars(stmt)).all())

@router.post("/retrieval-jobs", response_model=RetrievalJobOut, status_code=202)
async def retrieve(
    payload: RetrievalJobCreate,
    ctx: ApiClientContext = Depends(require_scope("documents:retrieve")),
    db: AsyncSession = Depends(get_db),
):
    if payload.legal_entity_id and ctx.client.entity_scope and str(payload.legal_entity_id) not in ctx.client.entity_scope:
        raise HTTPException(status_code=403, detail="CNPJ fora do escopo da credencial")
    item = RetrievalJob(tenant_id=ctx.tenant_id, requested_by=None, **payload.model_dump())
    db.add(item); await db.commit(); await db.refresh(item)
    execute_retrieval_task.delay(str(item.id))
    return item
