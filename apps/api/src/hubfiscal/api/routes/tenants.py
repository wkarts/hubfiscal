from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.resources import ALL_RESOURCES, TENANT_RESOURCE_PRESETS, preset_resources
from ...core.security import hash_password
from ...dependencies import AuthContext, require_platform_admin
from ...models import LegalEntity, Membership, PluginInstallation, RoutingPolicy, Tenant, User
from ...schemas import TenantCreate, TenantOut
from ...services.access_profiles import ensure_default_access_profiles
from ...services.audit import audit
from ...services.company_lookup import CompanyLookupError, lookup_company, normalize_tax_document, validate_cnpj

router = APIRouter(prefix="/tenants", tags=["Clientes"])


class TenantResourcesUpdate(BaseModel):
    enabled_resources: list[str] = Field(default_factory=list)
    resource_preset: str | None = None


def _validated_resources(resources: list[str]) -> list[str]:
    invalid = sorted(set(resources) - set(ALL_RESOURCES))
    if invalid:
        raise HTTPException(status_code=422, detail=f"Recursos desconhecidos: {', '.join(invalid)}")
    return list(dict.fromkeys(resources))


@router.get("/resource-presets")
async def list_resource_presets(_: AuthContext = Depends(require_platform_admin)):
    return [
        {"key": key, "name": value["name"], "description": value["description"], "resources": value["resources"]}
        for key, value in TENANT_RESOURCE_PRESETS.items()
    ]


@router.get("", response_model=list[TenantOut])
async def list_tenants(_: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(Tenant).order_by(Tenant.name))).all())


@router.post("", response_model=TenantOut, status_code=201)
async def create_tenant(payload: TenantCreate, context: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(Tenant).where(Tenant.slug == payload.slug)):
        raise HTTPException(status_code=409, detail="Slug já cadastrado")

    resources = _validated_resources(payload.enabled_resources or preset_resources(payload.resource_preset))
    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
        type=payload.type,
        settings={
            "resource_preset": payload.resource_preset,
            "enabled_resources": resources,
            "primary_document": None,
        },
    )
    db.add(tenant)
    await db.flush()

    profiles = await ensure_default_access_profiles(db, tenant.id)

    if payload.document:
        document = normalize_tax_document(payload.document)
        if not validate_cnpj(document):
            raise HTTPException(status_code=422, detail="CNPJ principal inválido")
        lookup_data = None
        lookup_warning = None
        if payload.lookup_company:
            try:
                lookup_data = await lookup_company(document)
            except CompanyLookupError as exc:
                lookup_warning = str(exc)
        entity = LegalEntity(
            tenant_id=tenant.id,
            document=document,
            legal_name=(lookup_data.legal_name if lookup_data else None) or payload.name,
            trade_name=lookup_data.trade_name if lookup_data else None,
            city_ibge_code=lookup_data.city_ibge_code if lookup_data else None,
            relationship_type="tenant",
            is_primary=True,
            enabled_resources=list(resources),
            metadata_json={
                "company_lookup": lookup_data.as_dict() if lookup_data else {},
                "company_lookup_warning": lookup_warning,
            },
        )
        db.add(entity)
        tenant.settings = {**tenant.settings, "primary_document": document, "primary_legal_entity_id": str(entity.id)}

    db.add(PluginInstallation(tenant_id=tenant.id, plugin_key="repository", name="Repositório principal", priority=10, config={}))
    db.add(PluginInstallation(tenant_id=tenant.id, plugin_key="simulated-source", name="Fonte de demonstração", priority=900, config={"enabled_for_demo": False}))
    db.add(PluginInstallation(tenant_id=tenant.id, plugin_key="portal-assisted", name="Portal assistido", priority=1000, config={}))
    db.add(RoutingPolicy(
        tenant_id=tenant.id,
        name="Roteamento padrão NF-e",
        document_type="nfe",
        operation="retrieve_by_key",
        steps=[
            {"plugin_key": "repository", "priority": 10},
            {"plugin_key": "generic-http-xml", "priority": 100},
            {"plugin_key": "simulated-source", "priority": 900},
            {"plugin_key": "portal-assisted", "priority": 1000},
        ],
        settings={"stop_when": "complete_valid_xml"},
    ))

    if payload.owner_email and payload.owner_name and payload.owner_password:
        user = await db.scalar(select(User).where(User.email == payload.owner_email.lower()))
        if user is None:
            user = User(name=payload.owner_name, email=payload.owner_email.lower(), password_hash=hash_password(payload.owner_password))
            db.add(user)
            await db.flush()
        owner_profile = profiles["tenant_owner"]
        db.add(Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            profile_id=owner_profile.id,
            role="tenant_owner",
            permissions=["*"],
            entity_scope=[],
        ))

    await audit(
        db,
        action="tenant.create",
        resource_type="tenant",
        resource_id=str(tenant.id),
        user_id=context.user.id,
        details={"name": tenant.name, "resources": resources, "document": tenant.settings.get("primary_document")},
    )
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.patch("/{tenant_id}/resources", response_model=TenantOut)
async def update_tenant_resources(
    tenant_id: str,
    payload: TenantResourcesUpdate,
    context: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    resources = _validated_resources(payload.enabled_resources)
    tenant.settings = {
        **(tenant.settings or {}),
        "enabled_resources": resources,
        "resource_preset": payload.resource_preset or "custom",
    }
    await audit(
        db,
        action="tenant.resources.update",
        resource_type="tenant",
        resource_id=str(tenant.id),
        user_id=context.user.id,
        details={"enabled_resources": resources},
    )
    await db.commit()
    await db.refresh(tenant)
    return tenant
