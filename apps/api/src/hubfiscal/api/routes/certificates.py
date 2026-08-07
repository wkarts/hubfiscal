import hashlib
from uuid import UUID

import structlog
from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import encrypt_secret
from ...dependencies import AuthContext, require_resource
from ...models import DigitalCertificate, LegalEntity
from ...services.audit import audit
from ...services.storage import ObjectStorageError, storage

router = APIRouter(prefix="/certificates", tags=["Certificados"])
certificate_context = require_resource("certificates")
logger = structlog.get_logger(__name__)


def serialize(cert: DigitalCertificate) -> dict:
    return {
        "id": str(cert.id),
        "name": cert.name,
        "certificate_type": cert.certificate_type,
        "subject_document": cert.subject_document,
        "serial_number": cert.serial_number,
        "valid_from": cert.valid_from,
        "valid_until": cert.valid_until,
        "fingerprint_sha256": cert.fingerprint_sha256,
        "status": cert.status,
        "legal_entity_id": str(cert.legal_entity_id) if cert.legal_entity_id else None,
    }


@router.get("")
async def list_certificates(
    context: AuthContext = Depends(certificate_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        return []
    entities = list(
        (
            await db.scalars(
                select(LegalEntity).where(
                    LegalEntity.tenant_id == context.tenant_id
                )
            )
        ).all()
    )
    enabled_entities = {
        entity.id
        for entity in entities
        if "certificates" in (entity.enabled_resources or [])
        and (not context.entity_scope or str(entity.id) in context.entity_scope)
    }
    items = list(
        (
            await db.scalars(
                select(DigitalCertificate)
                .where(DigitalCertificate.tenant_id == context.tenant_id)
                .order_by(DigitalCertificate.valid_until)
            )
        ).all()
    )
    return [
        serialize(item)
        for item in items
        if item.legal_entity_id is None or item.legal_entity_id in enabled_entities
    ]


@router.post("", status_code=201)
async def upload_certificate(
    name: str = Form(...),
    password: str = Form(...),
    legal_entity_id: UUID | None = Form(None),
    file: UploadFile = File(...),
    context: AuthContext = Depends(certificate_context),
    db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None:
        raise HTTPException(status_code=400, detail="Selecione um tenant")

    entity = None
    if legal_entity_id:
        entity = await db.scalar(
            select(LegalEntity).where(
                LegalEntity.id == legal_entity_id,
                LegalEntity.tenant_id == context.tenant_id,
            )
        )
        if entity is None:
            raise HTTPException(status_code=422, detail="CNPJ não pertence ao tenant")
        if context.entity_scope and str(legal_entity_id) not in context.entity_scope:
            raise HTTPException(
                status_code=403,
                detail="Usuário não possui acesso ao CNPJ informado",
            )
        if "certificates" not in (entity.enabled_resources or []):
            raise HTTPException(
                status_code=403,
                detail="Recurso Certificados não habilitado para este CNPJ",
            )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Arquivo PFX/P12 vazio")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Certificado muito grande")

    try:
        _, cert, _ = pkcs12.load_key_and_certificates(data, password.encode())
        if cert is None:
            raise ValueError("Certificado ausente")
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="PFX/P12 ou senha inválidos",
        ) from exc

    fingerprint = hashlib.sha256(data).hexdigest()
    if await db.scalar(
        select(DigitalCertificate).where(
            DigitalCertificate.fingerprint_sha256 == fingerprint
        )
    ):
        raise HTTPException(status_code=409, detail="Certificado já cadastrado")

    storage_key = (
        f"tenant/{context.tenant_id}/certificates/{fingerprint}.pfx.enc"
    )
    encrypted_file = encrypt_secret(data)
    try:
        await storage.put(
            storage_key,
            encrypted_file,
            "application/octet-stream",
        )
    except ObjectStorageError as exc:
        logger.exception(
            "certificate.storage_failed",
            tenant_id=str(context.tenant_id),
            legal_entity_id=str(legal_entity_id) if legal_entity_id else None,
            storage_key=storage_key,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Não foi possível gravar o certificado no cofre MinIO. "
                "Verifique a configuração do armazenamento."
            ),
        ) from exc

    subject = cert.subject.rfc4514_string()
    serial = format(cert.serial_number, "x")
    item = DigitalCertificate(
        tenant_id=context.tenant_id,
        legal_entity_id=legal_entity_id,
        name=name,
        certificate_type="A1",
        subject_document=entity.document if entity else None,
        serial_number=serial,
        valid_from=cert.not_valid_before_utc,
        valid_until=cert.not_valid_after_utc,
        fingerprint_sha256=fingerprint,
        storage_key=storage_key,
        encrypted_password=encrypt_secret(password.encode()),
    )

    try:
        db.add(item)
        await db.flush()
        await audit(
            db,
            action="certificate.upload",
            resource_type="certificate",
            resource_id=str(item.id),
            tenant_id=context.tenant_id,
            user_id=context.user.id,
            details={
                "subject": subject,
                "legal_entity_id": (
                    str(legal_entity_id) if legal_entity_id else None
                ),
            },
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        try:
            await storage.delete(storage_key)
        except ObjectStorageError:
            logger.exception(
                "certificate.orphan_cleanup_failed",
                tenant_id=str(context.tenant_id),
                storage_key=storage_key,
            )
        logger.exception(
            "certificate.database_failed",
            tenant_id=str(context.tenant_id),
            legal_entity_id=str(legal_entity_id) if legal_entity_id else None,
        )
        raise HTTPException(
            status_code=500,
            detail="Falha ao registrar o certificado no banco de dados",
        ) from exc

    await db.refresh(item)
    return serialize(item)
