from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from .core.database import get_db
from .core.security import decode_token
from .dependencies import bearer
from .models import ApiClient

@dataclass(slots=True)
class ApiClientContext:
    client: ApiClient
    tenant_id: UUID
    scopes: list[str]

async def api_client_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> ApiClientContext:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Token ausente")
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("principal") != "api_client":
            raise InvalidTokenError("Principal inválido")
        client_id = UUID(payload["sub"])
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Token de integração inválido") from exc
    client = await db.get(ApiClient, client_id)
    if client is None or not client.active:
        raise HTTPException(status_code=401, detail="Cliente de API inativo")
    return ApiClientContext(client=client, tenant_id=client.tenant_id, scopes=client.scopes)

def require_scope(scope: str):
    async def dependency(ctx: ApiClientContext = Depends(api_client_context)) -> ApiClientContext:
        if scope not in ctx.scopes and "*" not in ctx.scopes:
            raise HTTPException(status_code=403, detail=f"Escopo obrigatório: {scope}")
        return ctx
    return dependency
