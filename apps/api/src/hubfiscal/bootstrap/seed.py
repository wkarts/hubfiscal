import asyncio

from sqlalchemy import select

from ..core.database import SessionLocal
from ..models import PluginDefinition
from ..plugins.registry import registry

SCHEMAS = {
    "repository": {},
    "simulated-source": {"type":"object","properties":{"enabled_for_demo":{"type":"boolean"}}},
    "generic-http-xml": {"type":"object","required":["url"],"properties":{"url":{"type":"string"},"method":{"type":"string"},"xml_json_path":{"type":"string"},"xml_encoding":{"type":"string"}}},
    "portal-assisted": {"type":"object","properties":{"portal_url":{"type":"string"}}},
    "consultadanfe": {"type":"object","required":["url"],"properties":{"url":{"type":"string"},"method":{"type":"string"},"xml_json_path":{"type":"string"}}},
    "nfe-distribution": {"type":"object","properties":{"url":{"type":"string"},"environment":{"type":"string"},"certificate_id":{"type":"string"}}},
    "nfse-national": {"type":"object","properties":{"url":{"type":"string"},"environment":{"type":"string"},"certificate_id":{"type":"string"}}},
    "webiss": {"type":"object","properties":{"url":{"type":"string"},"municipality_ibge_code":{"type":"string"},"layout_version":{"type":"string"}}},
    "fiscal-mailbox": {"type":"object","properties":{"url":{"type":"string"},"folder":{"type":"string"}}},
}

async def seed():
    async with SessionLocal() as db:
        for plugin in registry.all():
            existing = await db.scalar(select(PluginDefinition).where(PluginDefinition.key == plugin.key))
            payload = {
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
            if existing:
                existing.version = plugin.version; existing.name = plugin.name; existing.capabilities = payload; existing.config_schema = SCHEMAS.get(plugin.key,{})
            else:
                db.add(PluginDefinition(key=plugin.key, name=plugin.name, version=plugin.version, capabilities=payload, config_schema=SCHEMAS.get(plugin.key,{})))
        await db.commit()

if __name__ == "__main__": asyncio.run(seed())
