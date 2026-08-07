from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.resources import ALL_RESOURCES
from ...core.security import hash_password
from ...dependencies import AuthContext, current_context
from ...models import AccessProfile, LegalEntity, Membership, User
from ...schemas import TenantUserOut, UserCreate, UserMembershipUpdate
from ...services.access_profiles import ensure_default_access_profiles
from ...services.audit import audit

router = APIRouter(prefix="/users", tags=["Usuários"])


def _require_access_admin(context: AuthContext) -> UUID:
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    if not context.user.is_platform_admin and context.role not in {"tenant_owner", "tenant_admin"}:
        raise HTTPException(status_code=403, detail="Perfil sem permissão para administrar usuários")
    return context.tenant_id


async def _profile_for_payload(
    db: AsyncSession,
    tenant_id: UUID,
    profile_id: UUID | None,
    role: str,
) -> AccessProfile:
    await ensure_default_access_profiles(db, tenant_id)
    if profile_id:
        profile = await db.scalar(select(AccessProfile).where(AccessProfile.id == profile_id, AccessProfile.tenant_id == tenant_id))
    else:
        profile = await db.scalar(select(AccessProfile).where(AccessProfile.tenant_id == tenant_id, AccessProfile.key == role))
    if profile is None:
        raise HTTPException(status_code=422, detail="Perfil de acesso inválido")
    return profile


async def _validated_scope(db: AsyncSession, tenant_id: UUID, scope: list[str]) -> list[str]:
    if not scope:
        return []
    try:
        ids = [UUID(value) for value in scope]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Escopo de CNPJ contém identificador inválido") from exc
    found = set((await db.scalars(select(LegalEntity.id).where(LegalEntity.tenant_id == tenant_id, LegalEntity.id.in_(ids)))).all())
    missing = [str(value) for value in ids if value not in found]
    if missing:
        raise HTTPException(status_code=422, detail=f"CNPJs não pertencem ao tenant: {', '.join(missing)}")
    return [str(value) for value in ids]


def _tenant_user(user: User, membership: Membership, profile: AccessProfile | None) -> TenantUserOut:
    resources = list(profile.enabled_resources if profile else ALL_RESOURCES)
    return TenantUserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        status=user.status,
        is_platform_admin=user.is_platform_admin,
        role=profile.key if profile else membership.role,
        profile_id=profile.id if profile else None,
        profile_name=profile.name if profile else None,
        entity_scope=list(membership.entity_scope or []),
        enabled_resources=resources,
    )


@router.get("", response_model=list[TenantUserOut])
async def list_users(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None:
        users = list((await db.scalars(select(User).order_by(User.name))).all())
        return [
            TenantUserOut(
                id=user.id,
                name=user.name,
                email=user.email,
                status=user.status,
                is_platform_admin=user.is_platform_admin,
                role="platform_admin" if user.is_platform_admin else "sem_tenant",
                enabled_resources=list(ALL_RESOURCES) if user.is_platform_admin else [],
            )
            for user in users
        ]
    stmt = (
        select(User, Membership, AccessProfile)
        .join(Membership, Membership.user_id == User.id)
        .outerjoin(AccessProfile, AccessProfile.id == Membership.profile_id)
        .where(Membership.tenant_id == context.tenant_id)
        .order_by(User.name)
    )
    rows = (await db.execute(stmt)).all()
    return [_tenant_user(user, membership, profile) for user, membership, profile in rows]


@router.post("", response_model=TenantUserOut, status_code=201)
async def create_user(payload: UserCreate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    tenant_id = _require_access_admin(context)
    profile = await _profile_for_payload(db, tenant_id, payload.profile_id, payload.role)
    entity_scope = await _validated_scope(db, tenant_id, payload.entity_scope)
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None:
        user = User(name=payload.name, email=payload.email.lower(), password_hash=hash_password(payload.password))
        db.add(user)
        await db.flush()
    if await db.scalar(select(Membership.id).where(Membership.tenant_id == tenant_id, Membership.user_id == user.id)):
        raise HTTPException(status_code=409, detail="Usuário já pertence ao cliente")
    membership = Membership(
        tenant_id=tenant_id,
        user_id=user.id,
        profile_id=profile.id,
        role=profile.key,
        permissions=list(profile.permissions),
        entity_scope=entity_scope,
    )
    db.add(membership)
    await db.flush()
    await audit(
        db,
        action="user.create",
        resource_type="user",
        resource_id=str(user.id),
        tenant_id=tenant_id,
        user_id=context.user.id,
        details={"profile": profile.key, "entity_scope": entity_scope},
    )
    await db.commit()
    return _tenant_user(user, membership, profile)


@router.patch("/{user_id}/membership", response_model=TenantUserOut)
async def update_user_membership(
    user_id: UUID,
    payload: UserMembershipUpdate,
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = _require_access_admin(context)
    membership = await db.scalar(select(Membership).where(Membership.tenant_id == tenant_id, Membership.user_id == user_id))
    user = await db.scalar(select(User).where(User.id == user_id))
    if membership is None or user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado neste tenant")
    profile = await _profile_for_payload(db, tenant_id, payload.profile_id, membership.role)
    entity_scope = await _validated_scope(db, tenant_id, payload.entity_scope)
    membership.profile_id = profile.id
    membership.role = profile.key
    membership.permissions = list(profile.permissions)
    membership.entity_scope = entity_scope
    await audit(
        db,
        action="user.membership.update",
        resource_type="membership",
        resource_id=str(membership.id),
        tenant_id=tenant_id,
        user_id=context.user.id,
        details={"target_user": str(user.id), "profile": profile.key, "entity_scope": entity_scope},
    )
    await db.commit()
    return _tenant_user(user, membership, profile)
