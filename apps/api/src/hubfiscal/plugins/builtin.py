from __future__ import annotations

import base64
from uuid import UUID

import httpx
from sqlalchemy import select

from ..core.database import SessionLocal
from ..models import FiscalDocument
from ..services.storage import storage
from .sdk import Capabilities, FiscalPlugin, PluginRequest, PluginResult, PluginStatus


class RepositoryPlugin(FiscalPlugin):
    key = "repository"
    name = "Repositório fiscal"
    capabilities = Capabilities(True, False, False, True, True, False, False, False, frozenset({"nfe","nfce","cte","mdfe","nfse"}))

    async def retrieve(self, request: PluginRequest) -> PluginResult:
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
    capabilities = Capabilities(True, True, False, True, True, True, False, False, frozenset({"nfe","nfse"}))

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
    capabilities = Capabilities(True, True, False, True, True, False, False, False, frozenset({"nfe","nfce","cte","mdfe","nfse"}))

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
                    kwargs["json"] = {payload_key: request.access_key, **request.config.get("payload", {})}
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


class NFeDistributionPlugin(GenericHttpXmlPlugin):
    key = "nfe-distribution"
    name = "Distribuição DF-e NF-e"
    capabilities = Capabilities(True, True, False, True, True, True, True, False, frozenset({"nfe", "nfce"}))


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
    capabilities = Capabilities(True, True, False, True, False, True, False, False, frozenset({"nfe","nfce","cte","mdfe","nfse"}))


class PortalAssistedPlugin(FiscalPlugin):
    key = "portal-assisted"
    name = "Portal assistido"
    capabilities = Capabilities(False, True, True, False, True, False, True, True, frozenset({"nfe","nfce","cte","mdfe","nfse"}))

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
    for plugin in [RepositoryPlugin(), SimulatedSourcePlugin(), GenericHttpXmlPlugin(), ConsultaDanfePlugin(), NFeDistributionPlugin(), NfseNationalPlugin(), WebIssPlugin(), MailboxPlugin(), PortalAssistedPlugin()]
}
