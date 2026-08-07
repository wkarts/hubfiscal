from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .core.database import get_db
from .core.resources import ALL_RESOURCES
from .core.security import decode_token
from .models import AccessProfile, Membership, Tenant, User

bearer = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthContext:
    user: User
    tenant_id: UUID | None
    role: str | None
    permissions: list[str]
    enabled_resources: list[str]
    entity_scope: list[str]
    profile_id: UUID | None = None
    profile_name: str | None = None


def _ordered_intersection(left: list[str], right: list[str]) -> list[str]:
    allowed = set(right)
    return [item for item in left if item in allowed]


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente")
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("principal", "user") != "user":
            raise ValueError("principal inválido")
        user_id = UUID(payload["sub"])
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Token inválido") from exc
    user = await db.scalar(select(User).where(User.id == user_id, User.status == "active"))
    if user is None:
        raise HTTPException(status_code=401, detail="Usuário inválido")
    return user


async def current_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_tenant_id: UUID | None = Header(default=None, alias="X-Tenant-ID"),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente")
    try:
        payload = decode_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Token inválido") from exc

    user = await db.scalar(select(User).where(User.id == user_id, User.status == "active"))
    if user is None:
        raise HTTPException(status_code=401, detail="Usuário inválido")

    if user.is_platform_admin and x_tenant_id is None:
        return AuthContext(
            user=user,
            tenant_id=None,
            role="platform_admin",
            permissions=["*"],
            enabled_resources=list(ALL_RESOURCES),
            entity_scope=[],
        )

    tenant_id = x_tenant_id or payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Informe X-Tenant-ID")
    try:
        tenant_uuid = UUID(str(tenant_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Tenant inválido") from exc

    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_uuid, Tenant.status == "active"))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant não encontrado ou inativo")

    membership = await db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.tenant_id == tenant_uuid)
    )
    if membership is None and not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Sem acesso ao tenant")

    tenant_resources = list((tenant.settings or {}).get("enabled_resources") or ALL_RESOURCES)
    if user.is_platform_admin and membership is None:
        return AuthContext(
            user=user,
            tenant_id=tenant_uuid,
            role="platform_admin",
            permissions=["*"],
            enabled_resources=tenant_resources,
            entity_scope=[],
        )

    assert membership is not None
    profile = None
    if membership.profile_id:
        profile = await db.scalar(
            select(AccessProfile).where(
                AccessProfile.id == membership.profile_id,
                AccessProfile.tenant_id == tenant_uuid,
            )
        )

    permissions = list(profile.permissions if profile else membership.permissions)
    if "*" in permissions:
        effective_resources = tenant_resources
    else:
        profile_resources = list(profile.enabled_resources if profile else ALL_RESOURCES)
        effective_resources = _ordered_intersection(tenant_resources, profile_resources)

    return AuthContext(
        user=user,
        tenant_id=tenant_uuid,
        role=profile.key if profile else membership.role,
        permissions=permissions,
        enabled_resources=effective_resources,
        entity_scope=list(membership.entity_scope or []),
        profile_id=profile.id if profile else None,
        profile_name=profile.name if profile else None,
    )


def require_platform_admin(context: AuthContext = Depends(current_context)) -> AuthContext:
    if not context.user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Acesso exclusivo da plataforma")
    return context


def require_resource(resource: str) -> Callable:
    def dependency(context: AuthContext = Depends(current_context)) -> AuthContext:
        if context.user.is_platform_admin and context.tenant_id is None:
            return context
        if resource not in context.enabled_resources:
            raise HTTPException(status_code=403, detail=f"Recurso '{resource}' não habilitado para este perfil/tenant")
        return context

    return dependency
