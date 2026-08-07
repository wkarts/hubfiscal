from __future__ import annotations

import base64
import gzip
import ssl
from uuid import UUID

import httpx
from lxml import etree
from sqlalchemy import select

from ..core.database import SessionLocal
from ..models import FiscalDocument, LegalEntity
from ..services.mtls import CertificateMaterialError, temporary_mtls_material
from ..services.storage import storage
from .sdk import Capabilities, FiscalPlugin, PluginDocument, PluginRequest, PluginResult, PluginStatus

UF_TO_CUF = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
    "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27", "SE": "28", "BA": "29",
    "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41", "SC": "42", "RS": "43",
    "MS": "50", "MT": "51", "GO": "52", "DF": "53",
}
NFE_DISTRIBUTION_ENDPOINTS = {
    "production": "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
    "homologation": "https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
}
SOAP_ACTION = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe/nfeDistDFeInteresse"
XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)


class RepositoryPlugin(FiscalPlugin):
    key = "repository"
    name = "Repositório fiscal"
    capabilities = Capabilities(True, False, False, True, True, False, False, False, frozenset({"nfe", "nfce", "cte", "mdfe", "nfse"}))

    async def retrieve(self, request: PluginRequest) -> PluginResult:
        if not request.access_key:
            return PluginResult(self.key, PluginStatus.NOT_FOUND)
        async with SessionLocal() as db:
            doc = await db.scalar(
                select(FiscalDocument).where(
                    FiscalDocument.tenant_id == request.tenant_id,
                    FiscalDocument.access_key == request.access_key,
                    FiscalDocument.storage_key.is_not(None),
                )
            )
            if not doc or not doc.storage_key:
                return PluginResult(self.key, PluginStatus.NOT_FOUND, request.access_key)
            return PluginResult(
                self.key,
                PluginStatus.FOUND,
                request.access_key,
                xml=await storage.get(doc.storage_key),
                metadata={"document_id": str(doc.id), "cached": True},
            )


class SimulatedSourcePlugin(FiscalPlugin):
    key = "simulated-source"
    name = "Fonte simulada"
    capabilities = Capabilities(True, True, False, True, True, True, False, False, frozenset({"nfe", "nfse"}))

    async def retrieve(self, request: PluginRequest) -> PluginResult:
        if not request.config.get("enabled_for_demo", False):
            return PluginResult(self.key, PluginStatus.NOT_FOUND, request.access_key)
        key = (request.access_key or "0" * 44).zfill(44)[:44]
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe><infNFe Id="NFe{key}" versao="4.00"><ide><dhEmi>2026-08-05T00:00:00-03:00</dhEmi></ide><emit><CNPJ>12345678000190</CNPJ></emit><dest><CNPJ>98765432000100</CNPJ></dest><total><ICMSTot><vNF>150.00</vNF></ICMSTot></total></infNFe><Signature xmlns="http://www.w3.org/2000/09/xmldsig#"/></NFe>
  <protNFe versao="4.00"><infProt><chNFe>{key}</chNFe><cStat>100</cStat></infProt></protNFe>
</nfeProc>""".encode()
        return PluginResult(self.key, PluginStatus.FOUND, key, xml=xml, metadata={"demo": True})


class GenericHttpXmlPlugin(FiscalPlugin):
    key = "generic-http-xml"
    name = "API HTTP genérica de XML"
    capabilities = Capabilities(True, True, False, True, True, False, False, False, frozenset({"nfe", "nfce", "cte", "mdfe", "nfse"}))

    async def healthcheck(self, config: dict, secrets: dict) -> tuple[bool, str]:
        url = config.get("healthcheck_url") or config.get("url")
        if not url:
            return False, "URL não configurada"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=self._headers(config, secrets))
            return response.status_code < 500, f"HTTP {response.status_code}"
        except Exception as exc:
            return False, str(exc)

    def _headers(self, config: dict, secrets: dict) -> dict[str, str]:
        headers = {str(k): str(v) for k, v in config.get("headers", {}).items()}
        token = secrets.get("token") or secrets.get("api_key")
        if token:
            header_name = config.get("auth_header", "Authorization")
            prefix = config.get("auth_prefix", "Bearer")
            headers[header_name] = f"{prefix} {token}".strip()
        return headers

    async def retrieve(self, request: PluginRequest) -> PluginResult:
        url = request.config.get("url")
        if not url:
            return PluginResult(self.key, PluginStatus.PERMANENT_FAILURE, request.access_key, message="URL não configurada")
        method = str(request.config.get("method", "POST")).upper()
        payload_key = request.config.get("access_key_field", "chave")
        url = url.replace("{access_key}", request.access_key or "")
        try:
            async with httpx.AsyncClient(timeout=float(request.config.get("timeout", 30))) as client:
                kwargs = {"headers": self._headers(request.config, request.secrets)}
                if method in {"POST", "PUT", "PATCH"}:
                    kwargs["json"] = {
                        payload_key: request.access_key,
                        "environment": request.environment,
                        "operation": request.operation,
                        **request.parameters,
                        **request.config.get("payload", {}),
                    }
                response = await client.request(method, url, **kwargs)
            if response.status_code == 404:
                return PluginResult(self.key, PluginStatus.NOT_FOUND, request.access_key)
            if response.status_code == 429:
                return PluginResult(self.key, PluginStatus.RATE_LIMITED, request.access_key, retry_after_seconds=60)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "xml" in content_type or response.content.lstrip().startswith(b"<"):
                return PluginResult(self.key, PluginStatus.FOUND, request.access_key, xml=response.content)
            data = response.json()
            path = str(request.config.get("xml_json_path", "xml_base64")).split(".")
            value = data
            for part in path:
                value = value[part]
            encoding = request.config.get("xml_encoding", "base64")
            xml = base64.b64decode(value) if encoding == "base64" else str(value).encode()
            return PluginResult(self.key, PluginStatus.FOUND, request.access_key, xml=xml, metadata={"http_status": response.status_code})
        except httpx.TimeoutException:
            return PluginResult(self.key, PluginStatus.TEMPORARY_FAILURE, request.access_key, message="Timeout")
        except Exception as exc:
            return PluginResult(self.key, PluginStatus.TEMPORARY_FAILURE, request.access_key, message=str(exc))


class ConsultaDanfePlugin(GenericHttpXmlPlugin):
    key = "consultadanfe"
    name = "ConsultaDanfe API"


class NFeDistributionPlugin(FiscalPlugin):
    key = "nfe-distribution"
    name = "Distribuição DF-e NF-e"
    version = "2.0.0"
    capabilities = Capabilities(True, True, False, True, True, True, True, False, frozenset({"nfe", "nfce"}))

    async def healthcheck(self, config: dict, secrets: dict) -> tuple[bool, str]:
        certificate_id = config.get("certificate_id")
        if not certificate_id:
            return False, "Selecione um certificado A1"
        environment = config.get("environment", "production")
        endpoint = self._endpoint(config, environment)
        return True, f"Configuração pronta para {environment}: {endpoint}"

    def _endpoint(self, config: dict, environment: str) -> str:
        override = config.get(f"{environment}_url") or config.get("url")
        return str(override or NFE_DISTRIBUTION_ENDPOINTS.get(environment, NFE_DISTRIBUTION_ENDPOINTS["production"]))

    async def _actor(self, request: PluginRequest) -> tuple[LegalEntity, str]:
        if request.legal_entity_id is None:
            raise ValueError("Selecione o CNPJ para consulta no Ambiente Nacional")
        async with SessionLocal() as db:
            entity = await db.scalar(
                select(LegalEntity).where(
                    LegalEntity.id == request.legal_entity_id,
                    LegalEntity.tenant_id == request.tenant_id,
                )
            )
        if entity is None:
            raise ValueError("CNPJ não encontrado no tenant")
        configured_cuf = str(request.config.get("cuf_autor") or "").strip()
        if configured_cuf:
            return entity, configured_cuf.zfill(2)
        lookup = (entity.metadata_json or {}).get("company_lookup") or {}
        uf = str(((lookup.get("address") or {}).get("state") or "")).upper()
        cuf = UF_TO_CUF.get(uf)
        if not cuf:
            raise ValueError("Informe a UF autorizadora na configuração do conector")
        return entity, cuf

    def _payload(self, *, entity: LegalEntity, cuf: str, request: PluginRequest) -> bytes:
        tp_amb = "1" if request.environment == "production" else "2"
        operation = request.operation
        if operation == "retrieve_by_key":
            operation = "consChNFe"
        if operation == "consChNFe":
            if not request.access_key or len(request.access_key) != 44:
                raise ValueError("consChNFe exige chave NF-e com 44 dígitos")
            query = f"<consChNFe><chNFe>{request.access_key}</chNFe></consChNFe>"
        elif operation == "consNSU":
            nsu = str(request.parameters.get("nsu") or "").zfill(15)
            if len(nsu) != 15 or not nsu.isdigit():
                raise ValueError("consNSU exige NSU com até 15 dígitos")
            query = f"<consNSU><NSU>{nsu}</NSU></consNSU>"
        elif operation == "distNSU":
            ult_nsu = str(request.parameters.get("ult_nsu") or "000000000000000").zfill(15)
            if len(ult_nsu) != 15 or not ult_nsu.isdigit():
                raise ValueError("distNSU exige ultNSU com 15 dígitos")
            query = f"<distNSU><ultNSU>{ult_nsu}</ultNSU></distNSU>"
        else:
            raise ValueError(f"Operação DF-e não suportada: {operation}")
        actor_tag = "CPF" if len(entity.document) == 11 else "CNPJ"
        inner = (
            '<distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">'
            f"<tpAmb>{tp_amb}</tpAmb><cUFAutor>{cuf}</cUFAutor>"
            f"<{actor_tag}>{entity.document}</{actor_tag}>{query}</distDFeInt>"
        )
        envelope = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
            '<soap12:Body>'
            '<nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">'
            f"<nfeDadosMsg>{inner}</nfeDadosMsg>"
            '</nfeDistDFeInteresse>'
            '</soap12:Body></soap12:Envelope>'
        )
        return envelope.encode("utf-8")

    def _parse_response(self, content: bytes, access_key: str | None) -> PluginResult:
        root = etree.fromstring(content, parser=XML_PARSER)
        ret_nodes = root.xpath("//*[local-name()='retDistDFeInt']")
        if not ret_nodes:
            message = "Resposta SOAP sem retDistDFeInt"
            faults = root.xpath("//*[local-name()='Text']/text() | //*[local-name()='faultstring']/text()")
            if faults:
                message = str(faults[0])
            return PluginResult(self.key, PluginStatus.TEMPORARY_FAILURE, access_key, message=message)
        ret = ret_nodes[0]
        text = lambda name: next((str(value) for value in ret.xpath(f"./*[local-name()='{name}']/text()")), None)
        cstat = text("cStat")
        motivo = text("xMotivo")
        ult_nsu = text("ultNSU")
        max_nsu = text("maxNSU")
        documents: list[PluginDocument] = []
        for node in ret.xpath(".//*[local-name()='docZip']"):
            encoded = (node.text or "").strip()
            if not encoded:
                continue
            try:
                xml = gzip.decompress(base64.b64decode(encoded))
            except Exception:
                continue
            documents.append(
                PluginDocument(
                    xml=xml,
                    schema=node.attrib.get("schema"),
                    nsu=node.attrib.get("NSU"),
                    metadata={"schema": node.attrib.get("schema"), "nsu": node.attrib.get("NSU")},
                )
            )
        metadata = {
            "cstat": cstat,
            "message": motivo,
            "ult_nsu": ult_nsu,
            "max_nsu": max_nsu,
            "documents_returned": len(documents),
        }
        if documents:
            return PluginResult(self.key, PluginStatus.FOUND, access_key, documents=documents, metadata=metadata, message=motivo)
        if cstat == "137":
            return PluginResult(self.key, PluginStatus.NOT_FOUND, access_key, metadata=metadata, message=motivo)
        if cstat == "656":
            return PluginResult(self.key, PluginStatus.RATE_LIMITED, access_key, metadata=metadata, retry_after_seconds=3600, message=motivo)
        if cstat in {"138", "140"}:
            return PluginResult(self.key, PluginStatus.NOT_FOUND, access_key, metadata=metadata, message=motivo)
        return PluginResult(self.key, PluginStatus.TEMPORARY_FAILURE, access_key, metadata=metadata, message=motivo or f"cStat {cstat}")

    async def retrieve(self, request: PluginRequest) -> PluginResult:
        try:
            entity, cuf = await self._actor(request)
            certificate_id = UUID(str(request.config.get("certificate_id")))
            endpoint = self._endpoint(request.config, request.environment)
            payload = self._payload(entity=entity, cuf=cuf, request=request)
            async with temporary_mtls_material(
                tenant_id=request.tenant_id,
                certificate_id=certificate_id,
                legal_entity_id=request.legal_entity_id,
            ) as (cert_path, key_path):
                ssl_context = ssl.create_default_context()
                ssl_context.load_cert_chain(cert_path, key_path)
                timeout = float(request.config.get("timeout", 45))
                headers = {
                    "Content-Type": f'application/soap+xml; charset=utf-8; action="{SOAP_ACTION}"',
                    "SOAPAction": SOAP_ACTION,
                    "User-Agent": "HubFiscal/0.4",
                }
                async with httpx.AsyncClient(verify=ssl_context, timeout=timeout) as client:
                    response = await client.post(endpoint, content=payload, headers=headers)
                response.raise_for_status()
                result = self._parse_response(response.content, request.access_key)
                result.metadata.update({"environment": request.environment, "endpoint": endpoint, "operation": request.operation})
                return result
        except (ValueError, CertificateMaterialError) as exc:
            return PluginResult(self.key, PluginStatus.PERMANENT_FAILURE, request.access_key, message=str(exc))
        except httpx.TimeoutException:
            return PluginResult(self.key, PluginStatus.TEMPORARY_FAILURE, request.access_key, message="Timeout no Ambiente Nacional")
        except httpx.HTTPStatusError as exc:
            return PluginResult(self.key, PluginStatus.TEMPORARY_FAILURE, request.access_key, message=f"Ambiente Nacional HTTP {exc.response.status_code}")
        except Exception as exc:
            return PluginResult(self.key, PluginStatus.TEMPORARY_FAILURE, request.access_key, message=str(exc))


class NfseNationalPlugin(GenericHttpXmlPlugin):
    key = "nfse-national"
    name = "NFS-e Padrão Nacional"
    capabilities = Capabilities(True, True, False, True, True, True, True, False, frozenset({"nfse"}))


class WebIssPlugin(GenericHttpXmlPlugin):
    key = "webiss"
    name = "WebISS / NFS-e Municipal"
    capabilities = Capabilities(True, True, False, True, True, True, False, False, frozenset({"nfse"}))


class MailboxPlugin(GenericHttpXmlPlugin):
    key = "fiscal-mailbox"
    name = "Caixa de e-mail fiscal"
    capabilities = Capabilities(True, True, False, True, False, True, False, False, frozenset({"nfe", "nfce", "cte", "mdfe", "nfse"}))


class PortalAssistedPlugin(FiscalPlugin):
    key = "portal-assisted"
    name = "Portal assistido"
    capabilities = Capabilities(False, True, True, False, True, False, True, True, frozenset({"nfe", "nfce", "cte", "mdfe", "nfse"}))

    async def retrieve(self, request: PluginRequest) -> PluginResult:
        return PluginResult(
            self.key,
            PluginStatus.HUMAN_ACTION_REQUIRED,
            request.access_key,
            metadata={
                "action": "open_assisted_session",
                "instructions": "Autentique com o certificado e conclua os desafios humanos no navegador visível.",
            },
            message="Intervenção humana necessária",
        )


BUILTIN_PLUGINS: dict[str, FiscalPlugin] = {
    plugin.key: plugin
    for plugin in [
        RepositoryPlugin(),
        SimulatedSourcePlugin(),
        GenericHttpXmlPlugin(),
        ConsultaDanfePlugin(),
        NFeDistributionPlugin(),
        NfseNationalPlugin(),
        WebIssPlugin(),
        MailboxPlugin(),
        PortalAssistedPlugin(),
    ]
}
