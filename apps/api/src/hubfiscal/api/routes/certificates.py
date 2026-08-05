import hashlib
from uuid import UUID

from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import encrypt_secret
from ...dependencies import AuthContext, current_context
from ...models import DigitalCertificate
from ...services.audit import audit
from ...services.storage import storage

router = APIRouter(prefix="/certificates", tags=["Certificados"])


def serialize(cert: DigitalCertificate) -> dict:
    return {
        "id": str(cert.id), "name": cert.name, "certificate_type": cert.certificate_type,
        "subject_document": cert.subject_document, "serial_number": cert.serial_number,
        "valid_from": cert.valid_from, "valid_until": cert.valid_until,
        "fingerprint_sha256": cert.fingerprint_sha256, "status": cert.status,
        "legal_entity_id": str(cert.legal_entity_id) if cert.legal_entity_id else None,
    }


@router.get("")
async def list_certificates(context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if context.tenant_id is None: return []
    items = (await db.scalars(select(DigitalCertificate).where(DigitalCertificate.tenant_id == context.tenant_id).order_by(DigitalCertificate.valid_until))).all()
    return [serialize(item) for item in items]


@router.post("", status_code=201)
async def upload_certificate(
    name: str = Form(...), password: str = Form(...), legal_entity_id: UUID | None = Form(None),
    file: UploadFile = File(...), context: AuthContext = Depends(current_context), db: AsyncSession = Depends(get_db),
):
    if context.tenant_id is None: raise HTTPException(status_code=400, detail="Selecione um tenant")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024: raise HTTPException(status_code=413, detail="Certificado muito grande")
    try:
        _, cert, _ = pkcs12.load_key_and_certificates(data, password.encode())
        if cert is None: raise ValueError("Certificado ausente")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="PFX/P12 ou senha inválidos") from exc
    # O hash do arquivo é usado como identidade estável sem expor o conteúdo.
    fp = hashlib.sha256(data).hexdigest()
    if await db.scalar(select(DigitalCertificate).where(DigitalCertificate.fingerprint_sha256 == fp)):
        raise HTTPException(status_code=409, detail="Certificado já cadastrado")
    storage_key = f"tenant/{context.tenant_id}/certificates/{fp}.pfx.enc"
    await storage.put(storage_key, encrypt_secret(data), "application/octet-stream")
    subject = cert.subject.rfc4514_string()
    serial = format(cert.serial_number, "x")
    item = DigitalCertificate(
        tenant_id=context.tenant_id, legal_entity_id=legal_entity_id, name=name,
        certificate_type="A1", subject_document=None, serial_number=serial,
        valid_from=cert.not_valid_before_utc, valid_until=cert.not_valid_after_utc,
        fingerprint_sha256=fp, storage_key=storage_key, encrypted_password=encrypt_secret(password.encode()),
    )
    db.add(item); await db.flush()
    await audit(db, action="certificate.upload", resource_type="certificate", resource_id=str(item.id), tenant_id=context.tenant_id, user_id=context.user.id, details={"subject": subject})
    await db.commit(); await db.refresh(item)
    return serialize(item)
