from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from sqlalchemy import select

from ..core.database import SessionLocal
from ..core.security import decrypt_secret
from ..models import DigitalCertificate
from .storage import storage


class CertificateMaterialError(RuntimeError):
    pass


@asynccontextmanager
async def temporary_mtls_material(
    *,
    tenant_id: UUID,
    certificate_id: UUID,
    legal_entity_id: UUID | None = None,
):
    async with SessionLocal() as db:
        certificate = await db.scalar(
            select(DigitalCertificate).where(
                DigitalCertificate.id == certificate_id,
                DigitalCertificate.tenant_id == tenant_id,
                DigitalCertificate.status == "active",
            )
        )
        if certificate is None:
            raise CertificateMaterialError("Certificado A1 não encontrado ou inativo")
        if legal_entity_id and certificate.legal_entity_id not in {None, legal_entity_id}:
            raise CertificateMaterialError("Certificado não pertence ao CNPJ selecionado")
        encrypted_pfx = await storage.get(certificate.storage_key)
        pfx = decrypt_secret(encrypted_pfx)
        password = decrypt_secret(certificate.encrypted_password)

    try:
        key, cert, chain = pkcs12.load_key_and_certificates(pfx, password)
    except Exception as exc:
        raise CertificateMaterialError("Não foi possível abrir o certificado A1 armazenado") from exc
    if key is None or cert is None:
        raise CertificateMaterialError("Certificado A1 sem chave privada ou certificado público")

    with tempfile.TemporaryDirectory(prefix="hubfiscal-mtls-") as directory:
        root = Path(directory)
        cert_path = root / "certificate.pem"
        key_path = root / "private-key.pem"
        certificate_pem = cert.public_bytes(serialization.Encoding.PEM)
        for item in chain or []:
            certificate_pem += item.public_bytes(serialization.Encoding.PEM)
        cert_path.write_bytes(certificate_pem)
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        os.chmod(cert_path, 0o600)
        os.chmod(key_path, 0o600)
        yield str(cert_path), str(key_path)
