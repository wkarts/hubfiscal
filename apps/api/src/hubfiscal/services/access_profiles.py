from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.resources import DEFAULT_ACCESS_PROFILES
from ..models import AccessProfile


async def ensure_default_access_profiles(db: AsyncSession, tenant_id: UUID) -> dict[str, AccessProfile]:
    existing = list((await db.scalars(select(AccessProfile).where(AccessProfile.tenant_id == tenant_id))).all())
    by_key = {profile.key: profile for profile in existing}
    for template in DEFAULT_ACCESS_PROFILES:
        if template["key"] in by_key:
            continue
        profile = AccessProfile(
            tenant_id=tenant_id,
            key=template["key"],
            name=template["name"],
            description=template["description"],
            permissions=list(template["permissions"]),
            enabled_resources=list(template["enabled_resources"]),
            entity_scope_mode="all",
            system=bool(template["system"]),
        )
        db.add(profile)
        await db.flush()
        by_key[profile.key] = profile
    return by_key
