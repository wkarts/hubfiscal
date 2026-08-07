from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.resources import ALL_RESOURCES
from ...dependencies import AuthContext, current_context
from ...models import LegalEntity
from ...schemas import LegalEntityCreate, LegalEntityOut, LegalEntityUpdateResources
from ...services.audit import audit
from ...services.company_lookup import (
    CompanyLookupError,
    lookup_company,
    normalize_tax_document,
    validate_cnpj,
    validate_tax_document,
)

router = APIRouter(prefix="/legal-entities", tags=["Empresas e CNPJs"])


def _validate_resources(resources: list[str]) -> list[str]:
    invalid = sorted(set(resources) - set(ALL_RESOURCES))
    if invalid:
        raise HTTPException(status_code=422, detail=f"Recursos desconhecidos: {', '.join(invalid)}")
    return list(dict.fromkeys(resources))


@router.get("", response_model=list[LegalEntityOut])
async def list_entities(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None:
        return []
    stmt = select(LegalEntity).where(LegalEntity.tenant_id == context.tenant_id).order_by(LegalEntity.is_primary.desc(), LegalEntity.legal_name)
    if context.entity_scope:
        try:
            scoped_ids = [UUID(value) for value in context.entity_scope]
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Escopo de empresa inválido") from exc
        stmt = stmt.where(LegalEntity.id.in_(scoped_ids))
    return list((await db.scalars(stmt)).all())


@router.post("", response_model=LegalEntityOut, status_code=201)
async def create_entity(payload: LegalEntityCreate, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")

    document = normalize_tax_document(payload.document)
    if not validate_tax_document(document):
        raise HTTPException(status_code=422, detail="CPF/CNPJ inválido")
    if await db.scalar(select(LegalEntity.id).where(LegalEntity.tenant_id == context.tenant_id, LegalEntity.document == document)):
        raise HTTPException(status_code=409, detail="CPF/CNPJ já cadastrado neste tenant")

    lookup_data = None
    lookup_warning = None
    if len(document) == 14 and validate_cnpj(document) and payload.lookup_company:
        try:
            lookup_data = await lookup_company(document)
        except CompanyLookupError as exc:
            lookup_warning = str(exc)

    legal_name = payload.legal_name or (lookup_data.legal_name if lookup_data else None)
    if not legal_name:
        raise HTTPException(status_code=422, detail="Informe a razão social quando a consulta externa não retornar dados")

    resources = _validate_resources(payload.enabled_resources or list(ALL_RESOURCES))
    entity = LegalEntity(
        tenant_id=context.tenant_id,
        document=document,
        legal_name=legal_name,
        trade_name=payload.trade_name or (lookup_data.trade_name if lookup_data else None),
        state_registration=payload.state_registration or (lookup_data.state_registration if lookup_data else None),
        municipal_registrations=payload.municipal_registrations,
        city_ibge_code=payload.city_ibge_code or (lookup_data.city_ibge_code if lookup_data else None),
        relationship_type=payload.relationship_type,
        is_primary=False,
        enabled_resources=resources,
        metadata_json={
            "company_lookup": lookup_data.as_dict() if lookup_data else {},
            "company_lookup_warning": lookup_warning,
        },
    )
    db.add(entity)
    await db.flush()
    await audit(
        db,
        action="legal_entity.create",
        resource_type="legal_entity",
        resource_id=str(entity.id),
        tenant_id=context.tenant_id,
        user_id=context.user.id,
        details={"document": document, "resources": resources, "lookup_providers": lookup_data.providers if lookup_data else []},
    )
    await db.commit()
    await db.refresh(entity)
    return entity


@router.patch("/{entity_id}/resources", response_model=LegalEntityOut)
async def update_entity_resources(
    entity_id: UUID,
    payload: LegalEntityUpdateResources,
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    entity = await db.scalar(select(LegalEntity).where(LegalEntity.id == entity_id, LegalEntity.tenant_id == context.tenant_id))
    if entity is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    entity.enabled_resources = _validate_resources(payload.enabled_resources)
    await audit(
        db,
        action="legal_entity.resources.update",
        resource_type="legal_entity",
        resource_id=str(entity.id),
        tenant_id=context.tenant_id,
        user_id=context.user.id,
        details={"enabled_resources": entity.enabled_resources},
    )
    await db.commit()
    await db.refresh(entity)
    return entity
