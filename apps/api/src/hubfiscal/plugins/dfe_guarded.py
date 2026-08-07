from __future__ import annotations

from ..services.dfe_rate_limit import consume_point_lookup
from .builtin import NFeDistributionPlugin
from .sdk import PluginRequest, PluginResult, PluginStatus


class GuardedNFeDistributionPlugin(NFeDistributionPlugin):
    """Distribuição DF-e com proteção distribuída para consultas pontuais."""

    async def retrieve(self, request: PluginRequest) -> PluginResult:
        operation = "consChNFe" if request.operation == "retrieve_by_key" else request.operation
        if operation in {"consChNFe", "consNSU"} and request.legal_entity_id is not None:
            allowed, remaining, retry_after = await consume_point_lookup(
                tenant_id=request.tenant_id,
                legal_entity_id=request.legal_entity_id,
                environment=request.environment,
            )
            if not allowed:
                return PluginResult(
                    self.key,
                    PluginStatus.RATE_LIMITED,
                    request.access_key,
                    retry_after_seconds=retry_after,
                    metadata={
                        "operation": operation,
                        "environment": request.environment,
                        "point_lookup_remaining": 0,
                    },
                    message=f"Limite de consultas pontuais atingido. Tente novamente em {retry_after} segundo(s) ou use distNSU.",
                )
            result = await super().retrieve(request)
            result.metadata["point_lookup_remaining"] = remaining
            return result
        return await super().retrieve(request)
