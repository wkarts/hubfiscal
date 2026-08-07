from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...dependencies import AuthContext, current_context
from ...models import FiscalDocument, LegalEntity, PluginInstallation, RetrievalJob
from ...schemas import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _scope_ids(context: AuthContext) -> list[UUID]:
    try:
        return [UUID(value) for value in context.entity_scope]
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Escopo de CNPJ inválido") from exc


def _empty_dashboard() -> DashboardResponse:
    return DashboardResponse(
        totals={"documents": 0, "companies": 0, "plugins": 0, "pending_jobs": 0},
        documents_by_type=[],
        jobs_by_status=[],
        recent_jobs=[],
        service_health=[],
    )


@router.get("", response_model=DashboardResponse)
async def dashboard(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    tenant_id = context.tenant_id
    if tenant_id is None:
        return _empty_dashboard()

    scoped_ids = _scope_ids(context) if context.entity_scope else []
    totals: dict[str, int | float] = {"documents": 0, "companies": 0, "plugins": 0, "pending_jobs": 0}
    docs: list[tuple[str, int]] = []
    jobs: list[tuple[str, int]] = []
    recent_jobs: list[dict] = []
    service_health: list[dict] = []

    if "documents" in context.enabled_resources:
        doc_filter = [FiscalDocument.tenant_id == tenant_id]
        if scoped_ids:
            doc_filter.append(FiscalDocument.legal_entity_id.in_(scoped_ids))
        doc_total = await db.scalar(select(func.count()).select_from(FiscalDocument).where(*doc_filter)) or 0
        totals["documents"] = doc_total
        docs = list((await db.execute(
            select(FiscalDocument.document_type, func.count())
            .where(*doc_filter)
            .group_by(FiscalDocument.document_type)
        )).all())

    if "companies" in context.enabled_resources:
        company_filter = [LegalEntity.tenant_id == tenant_id]
        if scoped_ids:
            company_filter.append(LegalEntity.id.in_(scoped_ids))
        totals["companies"] = await db.scalar(select(func.count()).select_from(LegalEntity).where(*company_filter)) or 0

    if "plugins" in context.enabled_resources:
        plugin_filter = [PluginInstallation.tenant_id == tenant_id, PluginInstallation.enabled.is_(True)]
        if scoped_ids:
            plugin_filter.append(or_(PluginInstallation.legal_entity_id.is_(None), PluginInstallation.legal_entity_id.in_(scoped_ids)))
        totals["plugins"] = await db.scalar(select(func.count()).select_from(PluginInstallation).where(*plugin_filter)) or 0
        installations = list((await db.scalars(
            select(PluginInstallation).where(*plugin_filter).order_by(PluginInstallation.priority)
        )).all())
        service_health = [{"name": item.name, "status": item.health_status, "plugin": item.plugin_key} for item in installations]

    if "jobs" in context.enabled_resources or "query" in context.enabled_resources:
        job_filter = [RetrievalJob.tenant_id == tenant_id]
        if scoped_ids:
            job_filter.append(RetrievalJob.legal_entity_id.in_(scoped_ids))
        totals["pending_jobs"] = await db.scalar(
            select(func.count()).select_from(RetrievalJob).where(
                *job_filter,
                RetrievalJob.status.in_(["queued", "running", "human_action_required"]),
            )
        ) or 0
        jobs = list((await db.execute(
            select(RetrievalJob.status, func.count()).where(*job_filter).group_by(RetrievalJob.status)
        )).all())
        recent = list((await db.scalars(
            select(RetrievalJob).where(*job_filter).order_by(RetrievalJob.created_at.desc()).limit(8)
        )).all())
        recent_jobs = [
            {
                "id": str(item.id),
                "access_key": item.access_key,
                "status": item.status,
                "progress": item.progress,
                "created_at": item.created_at.isoformat(),
            }
            for item in recent
        ]

    return DashboardResponse(
        totals=totals,
        documents_by_type=[{"name": key.upper(), "value": value} for key, value in docs],
        jobs_by_status=[{"name": key, "value": value} for key, value in jobs],
        recent_jobs=recent_jobs,
        service_health=service_health,
    )
