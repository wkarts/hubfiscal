from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditEvent


async def audit(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    tenant_id: UUID | None = None,
    user_id: UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=tenant_id,
            user_id=user_id,
            details=details or {},
            ip_address=ip_address,
        )
    )
