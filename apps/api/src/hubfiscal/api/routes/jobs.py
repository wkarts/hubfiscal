from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...dependencies import AuthContext, current_context, require_resource
from ...models import DfeCursor, LegalEntity, PluginDefinition, PluginInstallation, RetrievalBatch, RetrievalJob
from ...operational_schemas import (
    DfeCursorOut,
    DfeDistributionRequest,
    RetrievalBatchCreate,
    RetrievalBatchDetail,
    RetrievalBatchOut,
    RetrievalJobRequest,
    RetrievalJobResponse,
)
from ...worker import execute_retrieval_task

router = APIRouter(tags=["Consultas e jobs"])
query_context = require_resource("query")
DOCUMENT_RESOURCES = {"nfe", "nfce", "cte", "mdfe", "nfse", "dfe"}
TERMINAL_STATUSES = {"completed", "partial", "not_found", "failed", "human_action_required"}


def _scope_ids(context: AuthContext) -> list[UUID]:
    try:
        return [UUID(value) for value in context.entity_scope]
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Escopo de CNPJ inválido") from exc


def _require_query_or_jobs(context: AuthContext) -> None:
    if context.user.is_platform_admin and context.tenant_id:
        return
    if "query" in context.enabled_resources or "jobs" in context.enabled_resources:
        return
    raise HTTPException(status_code=403, detail="Perfil sem acesso a Consultas ou Jobs")


async def _validate_entity(
    db: AsyncSession,
    context: AuthContext,
    entity_id: UUID | None,
    document_type: str,
) -> LegalEntity | None:
    if entity_id is None:
        return None
    entity = await db.scalar(
        select(LegalEntity).where(
            LegalEntity.id == entity_id,
            LegalEntity.tenant_id == context.tenant_id,
        )
    )
    if entity is None:
        raise HTTPException(status_code=422, detail="CNPJ não pertence ao tenant")
    if context.entity_scope and str(entity.id) not in context.entity_scope:
        raise HTTPException(status_code=403, detail="Usuário não possui acesso ao CNPJ informado")
    required = {"query", document_type}
    missing = sorted(required - set(entity.enabled_resources or []))
    if missing:
        raise HTTPException(status_code=403, detail=f"CNPJ não possui os recursos habilitados: {', '.join(missing)}")
    return entity


async def _validate_source(
    db: AsyncSession,
    context: AuthContext,
    installation_id: UUID | None,
    *,
    legal_entity_id: UUID | None = None,
) -> PluginInstallation | None:
    if installation_id is None:
        return None
    installation = await db.scalar(
        select(PluginInstallation).where(
            PluginInstallation.id == installation_id,
            PluginInstallation.tenant_id == context.tenant_id,
            PluginInstallation.enabled.is_(True),
        )
    )
    if installation is None:
        raise HTTPException(status_code=422, detail="Fonte/conector não encontrado ou desativado")
    if installation.legal_entity_id and legal_entity_id and installation.legal_entity_id != legal_entity_id:
        raise HTTPException(status_code=422, detail="Fonte configurada para outro CNPJ")
    return installation


def _validate_document_resource(context: AuthContext, document_type: str) -> None:
    if document_type in DOCUMENT_RESOURCES and document_type not in context.enabled_resources:
        raise HTTPException(status_code=403, detail=f"Recurso {document_type.upper()} não habilitado para o perfil")


@router.get("/query/sources")
async def query_sources(
    context: AuthContext = Depends(query_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        return []
    installations = list(
        (
            await db.scalars(
                select(PluginInstallation)
                .where(
                    PluginInstallation.tenant_id == context.tenant_id,
                    PluginInstallation.enabled.is_(True),
                )
                .order_by(PluginInstallation.priority, PluginInstallation.name)
            )
        ).all()
    )
    definitions = {
        item.key: item
        for item in (await db.scalars(select(PluginDefinition))).all()
    }
    return [
        {
            "id": str(item.id),
            "plugin_key": item.plugin_key,
            "name": item.name,
            "legal_entity_id": str(item.legal_entity_id) if item.legal_entity_id else None,
            "priority": item.priority,
            "health_status": item.health_status,
            "capabilities": (definitions.get(item.plugin_key).capabilities if definitions.get(item.plugin_key) else {}),
            "definition_name": (definitions.get(item.plugin_key).name if definitions.get(item.plugin_key) else item.plugin_key),
        }
        for item in installations
        if not context.entity_scope or item.legal_entity_id is None or str(item.legal_entity_id) in context.entity_scope
    ]


@router.get("/retrieval-jobs", response_model=list[RetrievalJobResponse])
async def list_jobs(
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    _require_query_or_jobs(context)
    if context.tenant_id is None:
        return []
    stmt = select(RetrievalJob).where(RetrievalJob.tenant_id == context.tenant_id)
    if context.entity_scope:
        stmt = stmt.where(RetrievalJob.legal_entity_id.in_(_scope_ids(context)))
    return list((await db.scalars(stmt.order_by(RetrievalJob.created_at.desc()).limit(300))).all())


@router.post("/retrieval-jobs", response_model=RetrievalJobResponse, status_code=202)
async def create_job(
    payload: RetrievalJobRequest,
    context: AuthContext = Depends(query_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    _validate_document_resource(context, payload.document_type)
    await _validate_entity(db, context, payload.legal_entity_id, payload.document_type)
    await _validate_source(db, context, payload.plugin_installation_id, legal_entity_id=payload.legal_entity_id)
    item = RetrievalJob(
        tenant_id=context.tenant_id,
        requested_by=context.user.id,
        legal_entity_id=payload.legal_entity_id,
        plugin_installation_id=payload.plugin_installation_id,
        document_type=payload.document_type,
        access_key=payload.access_key.strip(),
        environment=payload.environment,
        operation=payload.operation,
        parameters=payload.parameters,
        mode=payload.mode,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    execute_retrieval_task.delay(str(item.id))
    return item


@router.get("/retrieval-jobs/{job_id}", response_model=RetrievalJobResponse)
async def get_job(
    job_id: UUID,
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    _require_query_or_jobs(context)
    stmt = select(RetrievalJob).where(RetrievalJob.id == job_id, RetrievalJob.tenant_id == context.tenant_id)
    if context.entity_scope:
        stmt = stmt.where(RetrievalJob.legal_entity_id.in_(_scope_ids(context)))
    item = await db.scalar(stmt)
    if item is None:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return item


@router.post("/retrieval-batches", response_model=RetrievalBatchOut, status_code=202)
async def create_batch(
    payload: RetrievalBatchCreate,
    context: AuthContext = Depends(query_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    _validate_document_resource(context, payload.document_type)
    await _validate_entity(db, context, payload.legal_entity_id, payload.document_type)
    installation = await _validate_source(db, context, payload.plugin_installation_id, legal_entity_id=payload.legal_entity_id)
    if installation and installation.plugin_key == "nfe-distribution" and len(payload.access_keys) > 20:
        raise HTTPException(
            status_code=422,
            detail="O Ambiente Nacional limita consultas pontuais consChNFe. Para grandes volumes use Distribuição DF-e (distNSU).",
        )
    batch = RetrievalBatch(
        tenant_id=context.tenant_id,
        legal_entity_id=payload.legal_entity_id,
        requested_by=context.user.id,
        plugin_installation_id=payload.plugin_installation_id,
        document_type=payload.document_type,
        environment=payload.environment,
        mode=payload.mode,
        total_count=len(payload.access_keys),
    )
    db.add(batch)
    await db.flush()
    jobs: list[RetrievalJob] = []
    for access_key in payload.access_keys:
        job = RetrievalJob(
            tenant_id=context.tenant_id,
            legal_entity_id=payload.legal_entity_id,
            requested_by=context.user.id,
            plugin_installation_id=payload.plugin_installation_id,
            batch_id=batch.id,
            document_type=payload.document_type,
            access_key=access_key,
            environment=payload.environment,
            operation="retrieve_by_key",
            mode=payload.mode,
        )
        db.add(job)
        jobs.append(job)
    await db.flush()
    job_ids = [str(job.id) for job in jobs]
    await db.commit()
    await db.refresh(batch)
    for job_id in job_ids:
        execute_retrieval_task.delay(job_id)
    return batch


@router.get("/retrieval-batches", response_model=list[RetrievalBatchOut])
async def list_batches(
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    _require_query_or_jobs(context)
    if context.tenant_id is None:
        return []
    stmt = select(RetrievalBatch).where(RetrievalBatch.tenant_id == context.tenant_id)
    if context.entity_scope:
        stmt = stmt.where(RetrievalBatch.legal_entity_id.in_(_scope_ids(context)))
    return list((await db.scalars(stmt.order_by(RetrievalBatch.created_at.desc()).limit(100))).all())


@router.get("/retrieval-batches/{batch_id}", response_model=RetrievalBatchDetail)
async def get_batch(
    batch_id: UUID,
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    _require_query_or_jobs(context)
    stmt = select(RetrievalBatch).where(RetrievalBatch.id == batch_id, RetrievalBatch.tenant_id == context.tenant_id)
    if context.entity_scope:
        stmt = stmt.where(RetrievalBatch.legal_entity_id.in_(_scope_ids(context)))
    batch = await db.scalar(stmt)
    if batch is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    jobs = list((await db.scalars(select(RetrievalJob).where(RetrievalJob.batch_id == batch.id).order_by(RetrievalJob.created_at))).all())
    data = RetrievalBatchOut.model_validate(batch).model_dump()
    return {**data, "jobs": jobs}


@router.get("/dfe/cursors", response_model=list[DfeCursorOut])
async def list_dfe_cursors(
    context: AuthContext = Depends(query_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        return []
    stmt = select(DfeCursor).where(DfeCursor.tenant_id == context.tenant_id)
    if context.entity_scope:
        stmt = stmt.where(DfeCursor.legal_entity_id.in_(_scope_ids(context)))
    return list((await db.scalars(stmt.order_by(DfeCursor.updated_at.desc()))).all())


@router.post("/dfe/distribution", response_model=RetrievalJobResponse, status_code=202)
async def create_dfe_distribution(
    payload: DfeDistributionRequest,
    context: AuthContext = Depends(query_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    _validate_document_resource(context, "dfe")
    await _validate_entity(db, context, payload.legal_entity_id, "nfe")
    installation = await _validate_source(db, context, payload.plugin_installation_id, legal_entity_id=payload.legal_entity_id)
    if installation is None or installation.plugin_key != "nfe-distribution":
        raise HTTPException(status_code=422, detail="Selecione uma instalação do conector Distribuição DF-e NF-e")
    cursor = await db.scalar(
        select(DfeCursor).where(
            DfeCursor.tenant_id == context.tenant_id,
            DfeCursor.legal_entity_id == payload.legal_entity_id,
            DfeCursor.plugin_installation_id == payload.plugin_installation_id,
            DfeCursor.environment == payload.environment,
        )
    )
    if cursor is None:
        cursor = DfeCursor(
            tenant_id=context.tenant_id,
            legal_entity_id=payload.legal_entity_id,
            plugin_installation_id=payload.plugin_installation_id,
            environment=payload.environment,
        )
        db.add(cursor)
        await db.flush()
    now = datetime.now(UTC)
    if cursor.blocked_until and cursor.blocked_until > now:
        raise HTTPException(
            status_code=429,
            detail=f"Ambiente Nacional em janela de espera até {cursor.blocked_until.isoformat()}",
        )
    parameters: dict[str, str] = {}
    access_key = payload.access_key
    if payload.operation == "distNSU":
        parameters["ult_nsu"] = cursor.last_nsu or "000000000000000"
        access_key = None
    elif payload.operation == "consNSU":
        if not payload.nsu:
            raise HTTPException(status_code=422, detail="Informe o NSU")
        parameters["nsu"] = payload.nsu
        access_key = None
    elif payload.operation == "consChNFe":
        if not payload.access_key:
            raise HTTPException(status_code=422, detail="Informe a chave da NF-e")
    item = RetrievalJob(
        tenant_id=context.tenant_id,
        legal_entity_id=payload.legal_entity_id,
        requested_by=context.user.id,
        plugin_installation_id=payload.plugin_installation_id,
        document_type="nfe",
        access_key=access_key,
        environment=payload.environment,
        operation=payload.operation,
        parameters=parameters,
        mode="specific_source",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    execute_retrieval_task.delay(str(item.id))
    return item
