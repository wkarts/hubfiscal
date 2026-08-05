from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from lxml import etree

XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
ACCESS_KEY_RE = re.compile(r"\d{44}")


@dataclass(slots=True)
class ParsedDocument:
    xml: bytes
    sha256: str
    document_type: str
    access_key: str
    schema_name: str
    document_level: str
    issuer_document: str | None
    recipient_document: str | None
    issued_at: datetime | None
    total_amount: Decimal | None
    signature_present: bool
    protocol_present: bool
    metadata: dict


def _local_name(element) -> str:
    return etree.QName(element).localname


def _first_text(root, names: list[str]) -> str | None:
    for name in names:
        nodes = root.xpath(f"//*[local-name()='{name}']/text()")
        if nodes:
            return str(nodes[0]).strip()
    return None


def parse_xml(xml: bytes) -> ParsedDocument:
    if len(xml) > 20 * 1024 * 1024:
        raise ValueError("XML excede 20 MB")
    root = etree.fromstring(xml, parser=XML_PARSER)
    root_name = _local_name(root)
    schema_map = {
        "nfeProc": ("nfe", "complete"),
        "NFe": ("nfe", "without_protocol"),
        "resNFe": ("nfe", "summary"),
        "cteProc": ("cte", "complete"),
        "CTe": ("cte", "without_protocol"),
        "mdfeProc": ("mdfe", "complete"),
        "MDFe": ("mdfe", "without_protocol"),
        "CompNfse": ("nfse", "complete"),
        "NFS-e": ("nfse", "complete"),
    }
    document_type, level = schema_map.get(root_name, ("unknown", "unknown"))
    access_key = _first_text(root, ["chNFe", "chCTe", "chMDFe", "chNFSe"])
    if not access_key:
        ids = root.xpath("//@Id")
        for value in ids:
            match = ACCESS_KEY_RE.search(str(value))
            if match:
                access_key = match.group(0)
                break
    if not access_key:
        digest = hashlib.sha256(xml).hexdigest()
        access_key = f"HASH-{digest[:44]}"

    issuer = _first_text(root, ["CNPJ", "CPF"])
    participants = root.xpath("//*[local-name()='dest']//*[local-name()='CNPJ']/text()")
    recipient = str(participants[0]) if participants else None
    issued_raw = _first_text(root, ["dhEmi", "dEmi", "dataEmissao"])
    issued_at = None
    if issued_raw:
        try:
            issued_at = datetime.fromisoformat(issued_raw.replace("Z", "+00:00"))
        except ValueError:
            issued_at = None
    amount_raw = _first_text(root, ["vNF", "vTPrest", "vCarga", "vLiq"])
    total = None
    if amount_raw:
        try:
            total = Decimal(amount_raw)
        except Exception:
            total = None
    signature = bool(root.xpath("//*[local-name()='Signature']"))
    protocol = bool(root.xpath("//*[local-name()='protNFe' or local-name()='protCTe' or local-name()='protMDFe']"))
    return ParsedDocument(
        xml=xml,
        sha256=hashlib.sha256(xml).hexdigest(),
        document_type=document_type,
        access_key=access_key,
        schema_name=root_name,
        document_level=level,
        issuer_document=issuer,
        recipient_document=recipient,
        issued_at=issued_at,
        total_amount=total,
        signature_present=signature,
        protocol_present=protocol,
        metadata={"root": root_name},
    )


def extract_xml_files(data: bytes, filename: str) -> list[tuple[str, bytes]]:
    if filename.lower().endswith(".xml"):
        return [(filename, data)]
    if not filename.lower().endswith(".zip"):
        raise ValueError("Somente XML ou ZIP são suportados")
    if len(data) > 100 * 1024 * 1024:
        raise ValueError("ZIP excede 100 MB")
    try:
        with ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 5000:
                raise ValueError("ZIP possui arquivos demais")
            total_uncompressed = sum(item.file_size for item in infos)
            if total_uncompressed > 500 * 1024 * 1024:
                raise ValueError("Conteúdo descompactado excede o limite")
            return [
                (item.filename, archive.read(item))
                for item in infos
                if not item.is_dir() and item.filename.lower().endswith(".xml")
            ]
    except BadZipFile as exc:
        raise ValueError("ZIP inválido") from exc
