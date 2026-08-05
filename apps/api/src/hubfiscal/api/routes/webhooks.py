import secrets
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import encrypt_secret
from ...dependencies import AuthContext, current_context
from ...models import Webhook

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

class WebhookCreate(BaseModel):
    name: str
    url: HttpUrl
    events: list[str]

@router.get("")
async def list_webhooks(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: return []
    items = (await db.scalars(select(Webhook).where(Webhook.tenant_id == context.tenant_id))).all()
    return [{"id": str(i.id), "name": i.name, "url": i.url, "events": i.events, "active": i.active} for i in items]

@router.post("", status_code=201)
async def create_webhook(payload: WebhookCreate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: raise HTTPException(status_code=400, detail="Selecione um tenant")
    secret = secrets.token_urlsafe(32)
    item = Webhook(tenant_id=context.tenant_id, name=payload.name, url=str(payload.url), events=payload.events, secret_encrypted=encrypt_secret(secret.encode()))
    db.add(item); await db.commit(); await db.refresh(item)
    return {"id": str(item.id), "secret": secret}
