from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...dependencies import AuthContext, current_context
from ...models import AuditEvent

router = APIRouter(prefix="/audit-events", tags=["Auditoria"])

@router.get("")
async def list_events(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    stmt = select(AuditEvent)
    if context.tenant_id is not None: stmt = stmt.where(AuditEvent.tenant_id == context.tenant_id)
    items = (await db.scalars(stmt.order_by(AuditEvent.created_at.desc()).limit(500))).all()
    return [{"id": str(i.id), "action": i.action, "resource_type": i.resource_type, "resource_id": i.resource_id, "details": i.details, "created_at": i.created_at} for i in items]
