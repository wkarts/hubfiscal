from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DocumentSource, FiscalDocument
from .storage import storage
from .xml import ParsedDocument


async def persist_parsed_document(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    legal_entity_id: UUID | None,
    parsed: ParsedDocument,
    source_key: str,
    source_metadata: dict | None = None,
) -> FiscalDocument:
    existing = await db.scalar(
        select(FiscalDocument).where(
            FiscalDocument.tenant_id == tenant_id,
            FiscalDocument.document_type == parsed.document_type,
            FiscalDocument.access_key == parsed.access_key,
        )
    )
    storage_key = f"tenant/{tenant_id}/{parsed.document_type}/{parsed.access_key}/{parsed.sha256}.xml"
    if existing is None:
        document = FiscalDocument(
            tenant_id=tenant_id,
            legal_entity_id=legal_entity_id,
            document_type=parsed.document_type,
            access_key=parsed.access_key,
            schema_name=parsed.schema_name,
            document_level=parsed.document_level,
            issuer_document=parsed.issuer_document,
            recipient_document=parsed.recipient_document,
            issued_at=parsed.issued_at,
            total_amount=parsed.total_amount,
            storage_key=storage_key,
            sha256=parsed.sha256,
            signature_valid=parsed.signature_present,
            protocol_valid=parsed.protocol_present,
            metadata_json=parsed.metadata,
        )
        db.add(document)
        await db.flush()
    else:
        document = existing
        if document.sha256 != parsed.sha256 or not document.storage_key:
            document.storage_key = storage_key
            document.sha256 = parsed.sha256
            document.schema_name = parsed.schema_name
            document.document_level = parsed.document_level
            document.signature_valid = parsed.signature_present
            document.protocol_valid = parsed.protocol_present
    await storage.put(storage_key, parsed.xml, "application/xml")
    db.add(
        DocumentSource(
            tenant_id=tenant_id,
            document_id=document.id,
            source_key=source_key,
            authenticity="original" if parsed.document_level == "complete" else parsed.document_level,
            metadata_json=source_metadata or {},
        )
    )
    await db.flush()
    return document
