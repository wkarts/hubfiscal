import json
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import decrypt_secret, encrypt_secret
from ...dependencies import AuthContext, current_context
from ...models import PluginDefinition, PluginInstallation
from ...plugins.registry import registry
from ...schemas import PluginInstallCreate, PluginInstallationOut
from ...services.audit import audit

router = APIRouter(prefix="/plugins", tags=["Plugins"])


@router.get("/catalog")
async def catalog(_: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(PluginDefinition).order_by(PluginDefinition.name))).all())


@router.get("/installations", response_model=list[PluginInstallationOut])
async def installations(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: return []
    return list((await db.scalars(select(PluginInstallation).where(PluginInstallation.tenant_id == context.tenant_id).order_by(PluginInstallation.priority))).all())


@router.post("/installations", response_model=PluginInstallationOut, status_code=201)
async def install(payload: PluginInstallCreate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: raise HTTPException(status_code=400, detail="Selecione um tenant")
    try: registry.get(payload.plugin_key)
    except LookupError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    item = PluginInstallation(
        tenant_id=context.tenant_id, legal_entity_id=payload.legal_entity_id,
        plugin_key=payload.plugin_key, name=payload.name, priority=payload.priority,
        config=payload.config, encrypted_secrets=encrypt_secret(json.dumps(payload.secrets).encode()) if payload.secrets else None,
    )
    db.add(item); await db.flush()
    await audit(db, action="plugin.install", resource_type="plugin_installation", resource_id=str(item.id), tenant_id=context.tenant_id, user_id=context.user.id)
    await db.commit(); await db.refresh(item)
    return item


@router.post("/installations/{installation_id}/healthcheck")
async def healthcheck(installation_id: str, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    item = await db.scalar(select(PluginInstallation).where(PluginInstallation.id == installation_id, PluginInstallation.tenant_id == context.tenant_id))
    if item is None: raise HTTPException(status_code=404, detail="Instalação não encontrada")
    secrets = json.loads(decrypt_secret(item.encrypted_secrets).decode()) if item.encrypted_secrets else {}
    ok, message = await registry.get(item.plugin_key).healthcheck(item.config, secrets)
    item.health_status = "healthy" if ok else "unhealthy"; item.last_healthcheck_at = datetime.now(UTC)
    await db.commit()
    return {"healthy": ok, "message": message}
