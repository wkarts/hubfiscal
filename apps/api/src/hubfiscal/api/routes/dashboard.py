from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...dependencies import AuthContext, current_context
from ...models import DigitalCertificate, FiscalDocument, JobStatus, LegalEntity, PluginInstallation, RetrievalJob
from ...schemas import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("", response_model=DashboardResponse)
async def dashboard(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    tenant_id = context.tenant_id
    if tenant_id is None:
        return DashboardResponse(totals={"documents":0,"companies":0,"plugins":0,"pending_jobs":0}, documents_by_type=[], jobs_by_status=[], recent_jobs=[], service_health=[])
    doc_total = await db.scalar(select(func.count()).select_from(FiscalDocument).where(FiscalDocument.tenant_id == tenant_id)) or 0
    companies = await db.scalar(select(func.count()).select_from(LegalEntity).where(LegalEntity.tenant_id == tenant_id)) or 0
    plugins = await db.scalar(select(func.count()).select_from(PluginInstallation).where(PluginInstallation.tenant_id == tenant_id, PluginInstallation.enabled.is_(True))) or 0
    pending = await db.scalar(select(func.count()).select_from(RetrievalJob).where(RetrievalJob.tenant_id == tenant_id, RetrievalJob.status.in_(["queued","running","human_action_required"]))) or 0
    docs = (await db.execute(select(FiscalDocument.document_type, func.count()).where(FiscalDocument.tenant_id == tenant_id).group_by(FiscalDocument.document_type))).all()
    jobs = (await db.execute(select(RetrievalJob.status, func.count()).where(RetrievalJob.tenant_id == tenant_id).group_by(RetrievalJob.status))).all()
    recent = (await db.scalars(select(RetrievalJob).where(RetrievalJob.tenant_id == tenant_id).order_by(RetrievalJob.created_at.desc()).limit(8))).all()
    installations = (await db.scalars(select(PluginInstallation).where(PluginInstallation.tenant_id == tenant_id).order_by(PluginInstallation.priority))).all()
    return DashboardResponse(
        totals={"documents": doc_total, "companies": companies, "plugins": plugins, "pending_jobs": pending},
        documents_by_type=[{"name": k.upper(), "value": v} for k,v in docs],
        jobs_by_status=[{"name": k, "value": v} for k,v in jobs],
        recent_jobs=[{"id": str(j.id), "access_key": j.access_key, "status": j.status, "progress": j.progress, "created_at": j.created_at.isoformat()} for j in recent],
        service_health=[{"name": i.name, "status": i.health_status, "plugin": i.plugin_key} for i in installations],
    )
