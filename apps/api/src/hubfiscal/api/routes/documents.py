from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...dependencies import AuthContext, current_context
from ...models import FiscalDocument
from ...schemas import DocumentOut
from ...services.documents import persist_parsed_document
from ...services.storage import storage
from ...services.xml import extract_xml_files, parse_xml

router = APIRouter(prefix="/documents", tags=["Documentos fiscais"])


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    document_type: str | None = None, search: str | None = None, limit: int = Query(50, le=200), offset: int = 0,
    context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None: return []
    stmt = select(FiscalDocument).where(FiscalDocument.tenant_id == context.tenant_id)
    if document_type: stmt = stmt.where(FiscalDocument.document_type == document_type)
    if search: stmt = stmt.where(FiscalDocument.access_key.ilike(f"%{search}%"))
    stmt = stmt.order_by(FiscalDocument.created_at.desc()).limit(limit).offset(offset)
    return list((await db.scalars(stmt)).all())


@router.post("/import", status_code=201)
async def import_documents(
    legal_entity_id: UUID | None = None, file: UploadFile = File(...),
    context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None: raise HTTPException(status_code=400, detail="Selecione um tenant")
    data = await file.read()
    try: files = extract_xml_files(data, file.filename or "upload.xml")
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    imported, errors = [], []
    for name, xml in files:
        try:
            parsed = parse_xml(xml)
            doc = await persist_parsed_document(db, tenant_id=context.tenant_id, legal_entity_id=legal_entity_id, parsed=parsed, source_key="manual-upload", source_metadata={"filename": name})
            imported.append({"id": str(doc.id), "access_key": doc.access_key, "type": doc.document_type})
        except Exception as exc: errors.append({"filename": name, "error": str(exc)})
    await db.commit()
    return {"imported": imported, "errors": errors, "total": len(files)}


@router.get("/{document_id}/download")
async def download(document_id: UUID, context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    doc = await db.scalar(select(FiscalDocument).where(FiscalDocument.id == document_id, FiscalDocument.tenant_id == context.tenant_id))
    if doc is None or not doc.storage_key: raise HTTPException(status_code=404, detail="XML não encontrado")
    return Response(content=await storage.get(doc.storage_key), media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{doc.access_key}.xml"'})
