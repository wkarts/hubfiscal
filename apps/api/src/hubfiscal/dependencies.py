from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .core.database import get_db
from .core.security import decode_token
from .models import Membership, User

bearer = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthContext:
    user: User
    tenant_id: UUID | None
    role: str | None
    permissions: list[str]


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
        return AuthContext(user=user, tenant_id=None, role="platform_admin", permissions=["*"])

    tenant_id = x_tenant_id or payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Informe X-Tenant-ID")
    tenant_uuid = UUID(str(tenant_id))
    membership = await db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.tenant_id == tenant_uuid)
    )
    if membership is None and not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Sem acesso ao tenant")
    return AuthContext(
        user=user,
        tenant_id=tenant_uuid,
        role=membership.role if membership else "platform_admin",
        permissions=membership.permissions if membership else ["*"],
    )


def require_platform_admin(context: AuthContext = Depends(current_context)) -> AuthContext:
    if not context.user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Acesso exclusivo da plataforma")
    return context
