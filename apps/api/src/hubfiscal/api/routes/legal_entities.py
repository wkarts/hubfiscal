import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...dependencies import AuthContext, current_context
from ...models import LegalEntity
from ...schemas import LegalEntityCreate, LegalEntityOut
from ...services.audit import audit

router = APIRouter(prefix="/legal-entities", tags=["Empresas e CNPJs"])


@router.get("", response_model=list[LegalEntityOut])
async def list_entities(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None:
        return []
    return list((await db.scalars(select(LegalEntity).where(LegalEntity.tenant_id == context.tenant_id).order_by(LegalEntity.legal_name))).all())


@router.post("", response_model=LegalEntityOut, status_code=201)
async def create_entity(payload: LegalEntityCreate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    document = re.sub(r"\D", "", payload.document)
    if len(document) not in {11, 14}:
        raise HTTPException(status_code=422, detail="CPF/CNPJ inválido")
    entity = LegalEntity(tenant_id=context.tenant_id, document=document, **payload.model_dump(exclude={"document"}))
    db.add(entity)
    await db.flush()
    await audit(db, action="legal_entity.create", resource_type="legal_entity", resource_id=str(entity.id), tenant_id=context.tenant_id, user_id=context.user.id)
    await db.commit()
    await db.refresh(entity)
    return entity
