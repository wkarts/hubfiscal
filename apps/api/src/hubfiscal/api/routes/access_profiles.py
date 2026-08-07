from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.resources import ALL_RESOURCES
from ...dependencies import AuthContext, current_context
from ...models import AccessProfile, Membership
from ...schemas import AccessProfileCreate, AccessProfileOut, AccessProfileUpdate
from ...services.access_profiles import ensure_default_access_profiles
from ...services.audit import audit

router = APIRouter(prefix="/access-profiles", tags=["Perfis e permissões"])

RESOURCE_LABELS = {
    "dashboard": "Visão geral", "companies": "Empresas e CNPJs", "users": "Usuários",
    "profiles": "Perfis e permissões", "certificates": "Certificados", "documents": "Documentos/XML",
    "query": "Consultas", "nfe": "NF-e", "nfce": "NFC-e", "cte": "CT-e", "mdfe": "MDF-e",
    "nfse": "NFS-e", "dfe": "Distribuição DF-e", "plugins": "Plugins/conectores",
    "policies": "Políticas de consulta", "jobs": "Jobs e lotes", "integrations": "Integrações",
    "api_clients": "API e credenciais", "webhooks": "Webhooks", "reports": "Relatórios", "audit": "Auditoria",
}


def _require_tenant_admin(context: AuthContext) -> UUID:
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    if not context.user.is_platform_admin and "*" not in context.permissions and "manage" not in context.permissions:
        raise HTTPException(status_code=403, detail="Perfil sem permissão para administrar acessos")
    return context.tenant_id


def _validate_resources(resources: list[str]) -> list[str]:
    invalid = sorted(set(resources) - set(ALL_RESOURCES))
    if invalid:
        raise HTTPException(status_code=422, detail=f"Recursos desconhecidos: {', '.join(invalid)}")
    return list(dict.fromkeys(resources))


@router.get("/resources")
async def list_resources(_: AuthContext = Depends(current_context)):
    return [{"key": key, "label": RESOURCE_LABELS.get(key, key)} for key in ALL_RESOURCES]


@router.get("", response_model=list[AccessProfileOut])
async def list_profiles(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    tenant_id = _require_tenant_admin(context)
    await ensure_default_access_profiles(db, tenant_id)
    await db.commit()
    return list((await db.scalars(select(AccessProfile).where(AccessProfile.tenant_id == tenant_id).order_by(AccessProfile.name))).all())


@router.post("", response_model=AccessProfileOut, status_code=201)
async def create_profile(payload: AccessProfileCreate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    tenant_id = _require_tenant_admin(context)
    if await db.scalar(select(AccessProfile).where(AccessProfile.tenant_id == tenant_id, AccessProfile.key == payload.key)):
        raise HTTPException(status_code=409, detail="Já existe um perfil com esta chave")
    profile = AccessProfile(
        tenant_id=tenant_id,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        permissions=list(dict.fromkeys(payload.permissions)),
        enabled_resources=_validate_resources(payload.enabled_resources),
        entity_scope_mode=payload.entity_scope_mode,
        system=False,
    )
    db.add(profile)
    await db.flush()
    await audit(db, action="access_profile.create", resource_type="access_profile", resource_id=str(profile.id), tenant_id=tenant_id, user_id=context.user.id)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.patch("/{profile_id}", response_model=AccessProfileOut)
async def update_profile(profile_id: UUID, payload: AccessProfileUpdate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    tenant_id = _require_tenant_admin(context)
    profile = await db.scalar(select(AccessProfile).where(AccessProfile.id == profile_id, AccessProfile.tenant_id == tenant_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")
    data = payload.model_dump(exclude_unset=True)
    if "enabled_resources" in data:
        data["enabled_resources"] = _validate_resources(data["enabled_resources"])
    for key, value in data.items():
        setattr(profile, key, value)
    await audit(db, action="access_profile.update", resource_type="access_profile", resource_id=str(profile.id), tenant_id=tenant_id, user_id=context.user.id)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: UUID, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    tenant_id = _require_tenant_admin(context)
    profile = await db.scalar(select(AccessProfile).where(AccessProfile.id == profile_id, AccessProfile.tenant_id == tenant_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")
    if profile.system:
        raise HTTPException(status_code=409, detail="Perfis padrão não podem ser excluídos; edite os recursos se necessário")
    in_use = await db.scalar(select(Membership.id).where(Membership.profile_id == profile.id).limit(1))
    if in_use:
        raise HTTPException(status_code=409, detail="Perfil está associado a usuários")
    await db.delete(profile)
    await audit(db, action="access_profile.delete", resource_type="access_profile", resource_id=str(profile.id), tenant_id=tenant_id, user_id=context.user.id)
    await db.commit()
    return Response(status_code=204)
