from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...core.database import get_db
from ...core.security import create_access_token, create_refresh_token, hash_password, verify_password
from ...dependencies import AuthContext, current_context
from ...models import ApiClient, Membership, Tenant, User
from ...schemas import BootstrapAdminRequest, BootstrapStatus, ClientCredentialsRequest, LoginRequest, TokenResponse, UserOut
from ...services.audit import audit

router = APIRouter(tags=["Autenticação"])
settings = get_settings()


@router.get("/bootstrap/status", response_model=BootstrapStatus)
async def bootstrap_status(db: AsyncSession = Depends(get_db)):
    count = await db.scalar(select(func.count()).select_from(User))
    return BootstrapStatus(required=(count or 0) == 0)


@router.post("/bootstrap/admin", response_model=UserOut, status_code=201)
async def bootstrap_admin(payload: BootstrapAdminRequest, db: AsyncSession = Depends(get_db)):
    count = await db.scalar(select(func.count()).select_from(User))
    if count:
        raise HTTPException(status_code=409, detail="Bootstrap já concluído")
    if payload.token != settings.bootstrap_token:
        raise HTTPException(status_code=403, detail="Token de bootstrap inválido")
    user = User(
        name=payload.name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        is_platform_admin=True,
    )
    db.add(user)
    await db.flush()
    await audit(db, action="platform.bootstrap", resource_type="user", resource_id=str(user.id), user_id=user.id)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/oauth/token", response_model=TokenResponse)
async def client_credentials(payload: ClientCredentialsRequest, db: AsyncSession = Depends(get_db)):
    client = await db.scalar(select(ApiClient).where(ApiClient.client_id == payload.client_id, ApiClient.active.is_(True)))
    if client is None or not verify_password(payload.client_secret, client.secret_hash):
        raise HTTPException(status_code=401, detail="Credenciais de integração inválidas")
    access = create_access_token(
        client.id,
        principal="api_client",
        tenant_id=str(client.tenant_id),
        scopes=client.scopes,
    )
    return TokenResponse(access_token=access, refresh_token="")


@router.get("/auth/tenants")
async def my_tenants(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.user.is_platform_admin:
        items = (await db.scalars(select(Tenant).order_by(Tenant.name))).all()
        return [{"id": str(t.id), "name": t.name, "slug": t.slug, "type": t.type, "status": t.status} for t in items]
    stmt = select(Tenant).join(Membership).where(Membership.user_id == context.user.id).order_by(Tenant.name)
    items = (await db.scalars(stmt)).all()
    return [{"id": str(t.id), "name": t.name, "slug": t.slug, "type": t.type, "status": t.status} for t in items]


@router.get("/auth/me", response_model=UserOut)
async def me(context: AuthContext = Depends(current_context)):
    return context.user
