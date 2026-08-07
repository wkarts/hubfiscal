import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import decrypt_secret, encrypt_secret
from ...dependencies import AuthContext, current_context
from ...models import DigitalCertificate, LegalEntity, PluginDefinition, PluginInstallation
from ...operational_schemas import PluginInstallationUpdate, PluginInstallRequest
from ...plugins.registry import registry
from ...services.audit import audit

router = APIRouter(prefix="/plugins", tags=["Plugins"])


def _ensure_manage(context: AuthContext) -> None:
    if context.user.is_platform_admin or "*" in context.permissions or "manage" in context.permissions:
        return
    raise HTTPException(status_code=403, detail="Perfil sem permissão para administrar conectores")


def _decode_secrets(item: PluginInstallation) -> dict:
    if not item.encrypted_secrets:
        return {}
    try:
        return json.loads(decrypt_secret(item.encrypted_secrets).decode())
    except Exception:
        return {}


async def _definition(db: AsyncSession, plugin_key: str) -> PluginDefinition:
    definition = await db.scalar(select(PluginDefinition).where(PluginDefinition.key == plugin_key, PluginDefinition.enabled.is_(True)))
    if definition is None:
        raise HTTPException(status_code=422, detail=f"Plugin não disponível no catálogo: {plugin_key}")
    try:
        registry.get(plugin_key)
    except LookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return definition


async def _validate_entity(
    db: AsyncSession,
    context: AuthContext,
    legal_entity_id: UUID | None,
) -> None:
    if legal_entity_id is None:
        return
    entity = await db.scalar(
        select(LegalEntity).where(
            LegalEntity.id == legal_entity_id,
            LegalEntity.tenant_id == context.tenant_id,
        )
    )
    if entity is None:
        raise HTTPException(status_code=422, detail="CNPJ não pertence ao tenant")
    if context.entity_scope and str(entity.id) not in context.entity_scope:
        raise HTTPException(status_code=403, detail="CNPJ fora do escopo do usuário")


async def _validate_form(
    db: AsyncSession,
    context: AuthContext,
    definition: PluginDefinition,
    config: dict,
    secrets: dict,
    *,
    existing_secrets: dict | None = None,
) -> None:
    schema = definition.config_schema or {}
    for field in schema.get("config_fields", []):
        key = field.get("key")
        if not key:
            continue
        value = config.get(key)
        if field.get("required") and (value is None or str(value).strip() == ""):
            raise HTTPException(status_code=422, detail=f"Campo obrigatório: {field.get('label') or key}")
        options = field.get("options") or []
        allowed = {str(option.get("value")) for option in options if option.get("value") is not None}
        if value not in {None, ""} and allowed and str(value) not in allowed:
            raise HTTPException(status_code=422, detail=f"Valor inválido para {field.get('label') or key}")
        if field.get("type") == "certificate" and value:
            try:
                certificate_id = UUID(str(value))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Certificado A1 inválido") from exc
            certificate = await db.scalar(
                select(DigitalCertificate).where(
                    DigitalCertificate.id == certificate_id,
                    DigitalCertificate.tenant_id == context.tenant_id,
                    DigitalCertificate.status == "active",
                )
            )
            if certificate is None:
                raise HTTPException(status_code=422, detail="Certificado A1 não encontrado no tenant")
    combined_secrets = {**(existing_secrets or {}), **secrets}
    for field in schema.get("secret_fields", []):
        key = field.get("key")
        if key and field.get("required") and not combined_secrets.get(key):
            raise HTTPException(status_code=422, detail=f"Credencial obrigatória: {field.get('label') or key}")


def _serialize_installation(item: PluginInstallation, definition: PluginDefinition | None = None) -> dict:
    configured_secrets = sorted(_decode_secrets(item).keys())
    return {
        "id": str(item.id),
        "plugin_key": item.plugin_key,
        "name": item.name,
        "legal_entity_id": str(item.legal_entity_id) if item.legal_entity_id else None,
        "enabled": item.enabled,
        "priority": item.priority,
        "config": item.config or {},
        "health_status": item.health_status,
        "last_healthcheck_at": item.last_healthcheck_at,
        "configured_secret_keys": configured_secrets,
        "authorized": bool(configured_secrets) or not bool((definition.config_schema if definition else {}).get("secret_fields")),
        "definition": {
            "name": definition.name,
            "description": definition.description,
            "version": definition.version,
            "capabilities": definition.capabilities,
            "config_schema": definition.config_schema,
        } if definition else None,
    }


@router.get("/catalog")
async def catalog(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    definitions = list((await db.scalars(select(PluginDefinition).where(PluginDefinition.enabled.is_(True)).order_by(PluginDefinition.name))).all())
    counts: dict[str, int] = {}
    if context.tenant_id:
        rows = (
            await db.execute(
                select(PluginInstallation.plugin_key, func.count(PluginInstallation.id))
                .where(PluginInstallation.tenant_id == context.tenant_id)
                .group_by(PluginInstallation.plugin_key)
            )
        ).all()
        counts = {key: count for key, count in rows}
    return [
        {
            "key": item.key,
            "name": item.name,
            "version": item.version,
            "description": item.description,
            "capabilities": item.capabilities,
            "config_schema": item.config_schema,
            "installed_count": counts.get(item.key, 0),
        }
        for item in definitions
    ]


@router.get("/installations")
async def installations(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None:
        return []
    items = list(
        (
            await db.scalars(
                select(PluginInstallation)
                .where(PluginInstallation.tenant_id == context.tenant_id)
                .order_by(PluginInstallation.enabled.desc(), PluginInstallation.priority, PluginInstallation.name)
            )
        ).all()
    )
    definitions = {
        definition.key: definition
        for definition in (await db.scalars(select(PluginDefinition))).all()
    }
    return [_serialize_installation(item, definitions.get(item.plugin_key)) for item in items]


@router.get("/installations/{installation_id}")
async def get_installation(
    installation_id: UUID,
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(
        select(PluginInstallation).where(
            PluginInstallation.id == installation_id,
            PluginInstallation.tenant_id == context.tenant_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Instalação não encontrada")
    definition = await _definition(db, item.plugin_key)
    return _serialize_installation(item, definition)


@router.post("/installations", status_code=201)
async def install(
    payload: PluginInstallRequest,
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    _ensure_manage(context)
    definition = await _definition(db, payload.plugin_key)
    await _validate_entity(db, context, payload.legal_entity_id)
    await _validate_form(db, context, definition, payload.config, payload.secrets)
    item = PluginInstallation(
        tenant_id=context.tenant_id,
        legal_entity_id=payload.legal_entity_id,
        plugin_key=payload.plugin_key,
        name=payload.name,
        enabled=payload.enabled,
        priority=payload.priority,
        config=payload.config,
        encrypted_secrets=encrypt_secret(json.dumps(payload.secrets).encode()) if payload.secrets else None,
    )
    db.add(item)
    await db.flush()
    await audit(
        db,
        action="plugin.install",
        resource_type="plugin_installation",
        resource_id=str(item.id),
        tenant_id=context.tenant_id,
        user_id=context.user.id,
        details={"plugin_key": item.plugin_key, "legal_entity_id": str(item.legal_entity_id) if item.legal_entity_id else None},
    )
    await db.commit()
    await db.refresh(item)
    return _serialize_installation(item, definition)


@router.patch("/installations/{installation_id}")
async def update_installation(
    installation_id: UUID,
    payload: PluginInstallationUpdate,
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    _ensure_manage(context)
    item = await db.scalar(
        select(PluginInstallation).where(
            PluginInstallation.id == installation_id,
            PluginInstallation.tenant_id == context.tenant_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Instalação não encontrada")
    definition = await _definition(db, item.plugin_key)
    legal_entity_id = payload.legal_entity_id if "legal_entity_id" in payload.model_fields_set else item.legal_entity_id
    await _validate_entity(db, context, legal_entity_id)
    existing_secrets = _decode_secrets(item)
    incoming_secrets = payload.secrets or {}
    next_config = payload.config if payload.config is not None else (item.config or {})
    next_secrets = {} if payload.clear_secrets else {**existing_secrets, **incoming_secrets}
    await _validate_form(db, context, definition, next_config, incoming_secrets, existing_secrets={} if payload.clear_secrets else existing_secrets)
    if payload.name is not None:
        item.name = payload.name
    if "legal_entity_id" in payload.model_fields_set:
        item.legal_entity_id = payload.legal_entity_id
    if payload.priority is not None:
        item.priority = payload.priority
    if payload.enabled is not None:
        item.enabled = payload.enabled
    if payload.config is not None:
        item.config = payload.config
    if payload.clear_secrets or payload.secrets is not None:
        item.encrypted_secrets = encrypt_secret(json.dumps(next_secrets).encode()) if next_secrets else None
    item.health_status = "unknown"
    await audit(
        db,
        action="plugin.update",
        resource_type="plugin_installation",
        resource_id=str(item.id),
        tenant_id=context.tenant_id,
        user_id=context.user.id,
        details={"plugin_key": item.plugin_key, "enabled": item.enabled, "priority": item.priority},
    )
    await db.commit()
    await db.refresh(item)
    return _serialize_installation(item, definition)


@router.delete("/installations/{installation_id}", status_code=204)
async def uninstall(
    installation_id: UUID,
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    _ensure_manage(context)
    item = await db.scalar(
        select(PluginInstallation).where(
            PluginInstallation.id == installation_id,
            PluginInstallation.tenant_id == context.tenant_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Instalação não encontrada")
    await audit(
        db,
        action="plugin.uninstall",
        resource_type="plugin_installation",
        resource_id=str(item.id),
        tenant_id=context.tenant_id,
        user_id=context.user.id,
        details={"plugin_key": item.plugin_key, "name": item.name},
    )
    await db.delete(item)
    await db.commit()
    return Response(status_code=204)


@router.post("/installations/{installation_id}/healthcheck")
async def healthcheck(
    installation_id: UUID,
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(
        select(PluginInstallation).where(
            PluginInstallation.id == installation_id,
            PluginInstallation.tenant_id == context.tenant_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Instalação não encontrada")
    secrets = _decode_secrets(item)
    ok, message = await registry.get(item.plugin_key).healthcheck(item.config or {}, secrets)
    item.health_status = "healthy" if ok else "unhealthy"
    item.last_healthcheck_at = datetime.now(UTC)
    await db.commit()
    return {"healthy": ok, "message": message, "checked_at": item.last_healthcheck_at}
