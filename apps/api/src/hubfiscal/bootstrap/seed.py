import asyncio

from sqlalchemy import select

from ..core.database import SessionLocal
from ..models import PluginDefinition
from ..plugins.registry import registry

ENVIRONMENT_FIELD = {
    "key": "environment",
    "label": "Ambiente padrão",
    "type": "select",
    "default": "production",
    "options": [
        {"value": "production", "label": "Produção"},
        {"value": "homologation", "label": "Homologação"},
    ],
}
CERTIFICATE_FIELD = {
    "key": "certificate_id",
    "label": "Certificado A1",
    "type": "certificate",
    "required": True,
    "help": "Selecione um certificado ativo do cofre do CNPJ/tenant.",
}
UF_OPTIONS = [
    {"value": code, "label": label}
    for code, label in [
        ("11", "RO"), ("12", "AC"), ("13", "AM"), ("14", "RR"), ("15", "PA"), ("16", "AP"), ("17", "TO"),
        ("21", "MA"), ("22", "PI"), ("23", "CE"), ("24", "RN"), ("25", "PB"), ("26", "PE"), ("27", "AL"), ("28", "SE"), ("29", "BA"),
        ("31", "MG"), ("32", "ES"), ("33", "RJ"), ("35", "SP"), ("41", "PR"), ("42", "SC"), ("43", "RS"),
        ("50", "MS"), ("51", "MT"), ("52", "GO"), ("53", "DF"),
    ]
]

PLUGIN_UI = {
    "repository": {
        "category": "native",
        "maturity": "native",
        "description": "Consulta primeiro o cofre XML do próprio Hub Fiscal, sem custo externo.",
        "config_fields": [],
        "secret_fields": [],
        "operations": ["retrieve_by_key"],
    },
    "simulated-source": {
        "category": "development",
        "maturity": "demo",
        "description": "Fonte de demonstração para testes de roteamento. Não use em produção.",
        "config_fields": [
            {"key": "enabled_for_demo", "label": "Permitir respostas simuladas", "type": "boolean", "default": False},
        ],
        "secret_fields": [],
        "operations": ["retrieve_by_key"],
    },
    "nfe-distribution": {
        "category": "official",
        "maturity": "native",
        "description": "Conector nativo do Ambiente Nacional para NFeDistribuicaoDFe: chave, NSU e distribuição sequencial.",
        "docs_url": "https://www.nfe.fazenda.gov.br/portal/webServices.aspx",
        "config_fields": [
            ENVIRONMENT_FIELD,
            CERTIFICATE_FIELD,
            {
                "key": "cuf_autor",
                "label": "UF autorizadora do CNPJ",
                "type": "select",
                "options": UF_OPTIONS,
                "help": "Pode ser inferida do cadastro da empresa. Preencha quando a UF não estiver disponível no enriquecimento cadastral.",
            },
            {"key": "timeout", "label": "Timeout (segundos)", "type": "number", "default": 45, "min": 10, "max": 120},
            {"key": "production_url", "label": "Endpoint de produção (override)", "type": "url", "advanced": True},
            {"key": "homologation_url", "label": "Endpoint de homologação (override)", "type": "url", "advanced": True},
        ],
        "secret_fields": [],
        "operations": ["retrieve_by_key", "consChNFe", "consNSU", "distNSU"],
    },
    "generic-http-xml": {
        "category": "provider",
        "maturity": "configurable",
        "description": "Adapta APIs HTTP de terceiros que devolvam XML direto, texto ou XML em Base64.",
        "config_fields": [
            {"key": "url", "label": "URL da API", "type": "url", "required": True, "placeholder": "https://api.exemplo.com/documentos/{access_key}"},
            {"key": "healthcheck_url", "label": "URL de healthcheck", "type": "url", "advanced": True},
            {"key": "method", "label": "Método", "type": "select", "default": "POST", "options": [{"value": "GET", "label": "GET"}, {"value": "POST", "label": "POST"}]},
            {"key": "access_key_field", "label": "Campo da chave", "type": "text", "default": "chave"},
            {"key": "xml_json_path", "label": "Caminho do XML no JSON", "type": "text", "default": "xml_base64"},
            {"key": "xml_encoding", "label": "Codificação", "type": "select", "default": "base64", "options": [{"value": "base64", "label": "Base64"}, {"value": "text", "label": "Texto XML"}]},
            {"key": "timeout", "label": "Timeout (segundos)", "type": "number", "default": 30},
        ],
        "secret_fields": [
            {"key": "token", "label": "Token / API Key", "type": "password"},
        ],
        "operations": ["retrieve_by_key"],
    },
    "consultadanfe": {
        "category": "provider",
        "maturity": "configurable",
        "description": "Integração parametrizável com API de consulta de XML por chave.",
        "config_fields": [
            {"key": "url", "label": "Endpoint contratado", "type": "url", "required": True},
            {"key": "method", "label": "Método", "type": "select", "default": "POST", "options": [{"value": "GET", "label": "GET"}, {"value": "POST", "label": "POST"}]},
            {"key": "xml_json_path", "label": "Caminho do XML no retorno", "type": "text", "default": "xml_base64"},
        ],
        "secret_fields": [{"key": "token", "label": "Token da API", "type": "password", "required": True}],
        "operations": ["retrieve_by_key"],
    },
    "nfse-national": {
        "category": "official",
        "maturity": "configurable",
        "description": "Conector para provedores/serviços do padrão nacional de NFS-e. O endpoint depende do fluxo contratado/habilitado.",
        "config_fields": [
            ENVIRONMENT_FIELD,
            CERTIFICATE_FIELD,
            {"key": "url", "label": "Endpoint NFS-e Nacional", "type": "url", "required": True},
            {"key": "timeout", "label": "Timeout (segundos)", "type": "number", "default": 30},
        ],
        "secret_fields": [{"key": "token", "label": "Token, quando exigido", "type": "password"}],
        "operations": ["retrieve_by_key", "discovery"],
    },
    "webiss": {
        "category": "municipal",
        "maturity": "configurable",
        "description": "Conector municipal WebISS/NFS-e com parâmetros por município e versão de layout.",
        "config_fields": [
            {"key": "url", "label": "Endpoint WebISS", "type": "url", "required": True},
            {"key": "municipality_ibge_code", "label": "Código IBGE do município", "type": "text", "required": True},
            {"key": "layout_version", "label": "Versão/layout", "type": "text"},
        ],
        "secret_fields": [
            {"key": "token", "label": "Token / chave de integração", "type": "password"},
        ],
        "operations": ["retrieve_by_key", "discovery"],
    },
    "fiscal-mailbox": {
        "category": "automation",
        "maturity": "configurable",
        "description": "Fonte automatizada para caixas postais ou APIs que disponibilizem XMLs fiscais recebidos.",
        "config_fields": [
            {"key": "url", "label": "Endpoint da caixa fiscal", "type": "url", "required": True},
            {"key": "folder", "label": "Pasta/caixa", "type": "text", "default": "INBOX"},
        ],
        "secret_fields": [
            {"key": "token", "label": "Senha/Token", "type": "password"},
        ],
        "operations": ["discovery"],
    },
    "portal-assisted": {
        "category": "assisted",
        "maturity": "assisted",
        "description": "Fallback assistido para portais que exigem autenticação humana e CAPTCHA. O Hub Fiscal não automatiza o desafio humano.",
        "config_fields": [
            {"key": "portal_url", "label": "Portal", "type": "url", "required": True},
            CERTIFICATE_FIELD,
        ],
        "secret_fields": [],
        "operations": ["retrieve_by_key"],
    },
}


async def seed():
    async with SessionLocal() as db:
        for plugin in registry.all():
            existing = await db.scalar(select(PluginDefinition).where(PluginDefinition.key == plugin.key))
            capabilities = {
                "automatic": plugin.capabilities.automatic,
                "manual": plugin.capabilities.manual,
                "assisted": plugin.capabilities.assisted,
                "supports_batch": plugin.capabilities.supports_batch,
                "supports_key_lookup": plugin.capabilities.supports_key_lookup,
                "supports_discovery": plugin.capabilities.supports_discovery,
                "requires_certificate": plugin.capabilities.requires_certificate,
                "requires_human_action": plugin.capabilities.requires_human_action,
                "document_types": sorted(plugin.capabilities.document_types),
            }
            ui = PLUGIN_UI.get(plugin.key, {})
            if existing:
                existing.version = plugin.version
                existing.name = plugin.name
                existing.description = ui.get("description", "")
                existing.capabilities = capabilities
                existing.config_schema = ui
            else:
                db.add(
                    PluginDefinition(
                        key=plugin.key,
                        name=plugin.name,
                        version=plugin.version,
                        description=ui.get("description", ""),
                        capabilities=capabilities,
                        config_schema=ui,
                    )
                )
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
