from __future__ import annotations

from uuid import UUID

from redis.asyncio import Redis

from ..core.config import get_settings

POINT_LOOKUP_LIMIT = 20
WINDOW_SECONDS = 3600


async def consume_point_lookup(
    *,
    tenant_id: UUID,
    legal_entity_id: UUID,
    environment: str,
) -> tuple[bool, int, int]:
    """Reserva uma consulta consChNFe/consNSU em janela de uma hora.

    Retorna (allowed, remaining, retry_after_seconds). O controle usa Redis para
    funcionar de forma consistente entre múltiplos workers/containers.
    """
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    key = f"hubfiscal:dfe:point:{tenant_id}:{legal_entity_id}:{environment}"
    try:
        count = int(await client.incr(key))
        if count == 1:
            await client.expire(key, WINDOW_SECONDS)
        ttl = int(await client.ttl(key))
        if ttl < 1:
            ttl = WINDOW_SECONDS
        if count > POINT_LOOKUP_LIMIT:
            return False, 0, ttl
        return True, max(0, POINT_LOOKUP_LIMIT - count), ttl
    finally:
        await client.aclose()
