from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...dependencies import AuthContext, current_context
from ...models import FiscalDocument, LegalEntity
from ...schemas import DocumentOut
from ...services.documents import persist_parsed_document
from ...services.storage import storage
from ...services.xml import extract_xml_files, parse_xml

router = APIRouter(prefix="/documents", tags=["Documentos fiscais"])
DOCUMENT_TYPE_RESOURCES = {"nfe", "nfce", "cte", "mdfe", "nfse", "dfe"}


def _require_document_access(context: AuthContext, document_type: str | None = None) -> None:
    if "documents" in context.enabled_resources:
        return
    if document_type and document_type in DOCUMENT_TYPE_RESOURCES and document_type in context.enabled_resources:
        return
    raise HTTPException(status_code=403, detail="Recurso documental não habilitado para este perfil")


async def _document_entity_ids(db: AsyncSession, context: AuthContext, document_type: str | None) -> list[UUID]:
    if context.tenant_id is None:
        return []
    entity_resource = document_type if document_type in DOCUMENT_TYPE_RESOURCES else "documents"
    stmt = select(LegalEntity.id).where(
        LegalEntity.tenant_id == context.tenant_id,
        or_(
            LegalEntity.enabled_resources.contains(["documents"]),
            LegalEntity.enabled_resources.contains([entity_resource]),
        ),
    )
    if context.entity_scope:
        try:
            stmt = stmt.where(LegalEntity.id.in_([UUID(value) for value in context.entity_scope]))
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Escopo de CNPJ inválido") from exc
    return list((await db.scalars(stmt)).all())


async def _validate_document_entity(
    db: AsyncSession,
    context: AuthContext,
    legal_entity_id: UUID | None,
    *,
    allow_unassigned: bool,
    document_type: str | None = None,
) -> LegalEntity | None:
    if legal_entity_id is None:
        if context.entity_scope or not allow_unassigned:
            raise HTTPException(status_code=403, detail="Selecione um CNPJ permitido pelo seu escopo")
        return None
    entity = await db.scalar(
        select(LegalEntity).where(
            LegalEntity.id == legal_entity_id,
            LegalEntity.tenant_id == context.tenant_id,
        )
    )
    if entity is None:
        raise HTTPException(status_code=422, detail="CNPJ não pertence ao tenant")
    if context.entity_scope and str(entity.id) not in context.entity_scope:
        raise HTTPException(status_code=403, detail="Usuário não possui acesso ao CNPJ informado")
    entity_resources = set(entity.enabled_resources or [])
    required = document_type if document_type in DOCUMENT_TYPE_RESOURCES else "documents"
    if "documents" not in entity_resources and required not in entity_resources:
        raise HTTPException(status_code=403, detail=f"Recurso {required} não habilitado para este CNPJ")
    return entity


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    document_type: str | None = None,
    search: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        return []
    _require_document_access(context, document_type)
    entity_ids = await _document_entity_ids(db, context, document_type)
    stmt = select(FiscalDocument).where(FiscalDocument.tenant_id == context.tenant_id)
    if context.entity_scope:
        if not entity_ids:
            return []
        stmt = stmt.where(FiscalDocument.legal_entity_id.in_(entity_ids))
    else:
        stmt = stmt.where(or_(FiscalDocument.legal_entity_id.is_(None), FiscalDocument.legal_entity_id.in_(entity_ids)))
    if document_type:
        stmt = stmt.where(FiscalDocument.document_type == document_type)
    if search:
        stmt = stmt.where(FiscalDocument.access_key.ilike(f"%{search}%"))
    stmt = stmt.order_by(FiscalDocument.created_at.desc()).limit(limit).offset(offset)
    return list((await db.scalars(stmt)).all())


@router.post("/import", status_code=201)
async def import_documents(
    legal_entity_id: UUID | None = None,
    file: UploadFile = File(...),
    context: AuthContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")
    if "documents" not in context.enabled_resources:
        raise HTTPException(status_code=403, detail="Recurso Documentos/XML não habilitado para importação")
    await _validate_document_entity(db, context, legal_entity_id, allow_unassigned=True, document_type=None)
    data = await file.read()
    try:
        files = extract_xml_files(data, file.filename or "upload.xml")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    imported, errors = [], []
    for name, xml in files:
        try:
            parsed = parse_xml(xml)
            doc = await persist_parsed_document(
                db,
                tenant_id=context.tenant_id,
                legal_entity_id=legal_entity_id,
                parsed=parsed,
                source_key="manual-upload",
                source_metadata={"filename": name},
            )
            imported.append({"id": str(doc.id), "access_key": doc.access_key, "type": doc.document_type})
        except Exception as exc:
            errors.append({"filename": name, "error": str(exc)})
    await db.commit()
    return {"imported": imported, "errors": errors, "total": len(files)}


@router.get("/{document_id}/download")
async def download(document_id: UUID, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    doc = await db.scalar(
        select(FiscalDocument).where(
            FiscalDocument.id == document_id,
            FiscalDocument.tenant_id == context.tenant_id,
        )
    )
    if doc is None or not doc.storage_key:
        raise HTTPException(status_code=404, detail="XML não encontrado")
    _require_document_access(context, doc.document_type)
    await _validate_document_entity(
        db,
        context,
        doc.legal_entity_id,
        allow_unassigned=not bool(context.entity_scope),
        document_type=doc.document_type,
    )
    return Response(
        content=await storage.get(doc.storage_key),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{doc.access_key}.xml"'},
    )
