import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import hash_password
from ...dependencies import AuthContext, current_context
from ...models import ApiClient
from ...schemas import ApiClientCreate, ApiClientCreated

router = APIRouter(prefix="/api-clients", tags=["Clientes de API"])


@router.get("")
async def list_clients(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: return []
    items = (await db.scalars(select(ApiClient).where(ApiClient.tenant_id == context.tenant_id).order_by(ApiClient.name))).all()
    return [{"id": str(i.id), "name": i.name, "client_id": i.client_id, "scopes": i.scopes, "entity_scope": i.entity_scope, "active": i.active} for i in items]


@router.post("", response_model=ApiClientCreated, status_code=201)
async def create_client(payload: ApiClientCreate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: raise HTTPException(status_code=400, detail="Selecione um tenant")
    client_id = f"hf_{secrets.token_urlsafe(16)}"; secret = secrets.token_urlsafe(48)
    item = ApiClient(tenant_id=context.tenant_id, name=payload.name, client_id=client_id, secret_hash=hash_password(secret), scopes=payload.scopes, entity_scope=payload.entity_scope)
    db.add(item); await db.commit(); await db.refresh(item)
    return ApiClientCreated(id=item.id, name=item.name, client_id=client_id, client_secret=secret, scopes=item.scopes)
