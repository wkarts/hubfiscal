from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import hash_password
from ...dependencies import AuthContext, require_platform_admin
from ...models import Membership, PluginInstallation, RoutingPolicy, Tenant, User
from ...schemas import TenantCreate, TenantOut
from ...services.audit import audit

router = APIRouter(prefix="/tenants", tags=["Clientes"])


@router.get("", response_model=list[TenantOut])
async def list_tenants(_: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(Tenant).order_by(Tenant.name))).all())


@router.post("", response_model=TenantOut, status_code=201)
async def create_tenant(payload: TenantCreate, context: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(Tenant).where(Tenant.slug == payload.slug)):
        raise HTTPException(status_code=409, detail="Slug já cadastrado")
    tenant = Tenant(name=payload.name, slug=payload.slug, type=payload.type)
    db.add(tenant)
    await db.flush()
    db.add(PluginInstallation(tenant_id=tenant.id, plugin_key="repository", name="Repositório principal", priority=10, config={}))
    db.add(PluginInstallation(tenant_id=tenant.id, plugin_key="simulated-source", name="Fonte de demonstração", priority=900, config={"enabled_for_demo": False}))
    db.add(PluginInstallation(tenant_id=tenant.id, plugin_key="portal-assisted", name="Portal assistido", priority=1000, config={}))
    db.add(RoutingPolicy(
        tenant_id=tenant.id, name="Roteamento padrão NF-e", document_type="nfe", operation="retrieve_by_key",
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
        db.add(Membership(tenant_id=tenant.id, user_id=user.id, role="tenant_owner", permissions=["*"]))
    await audit(db, action="tenant.create", resource_type="tenant", resource_id=str(tenant.id), user_id=context.user.id, details={"name": tenant.name})
    await db.commit()
    await db.refresh(tenant)
    return tenant
