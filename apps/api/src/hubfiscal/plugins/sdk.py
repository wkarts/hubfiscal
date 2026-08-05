from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID


class PluginStatus(StrEnum):
    FOUND = "found"
    SUMMARY_ONLY = "summary_only"
    NOT_FOUND = "not_found"
    NOT_AUTHORIZED = "not_authorized"
    HUMAN_ACTION_REQUIRED = "human_action_required"
    RATE_LIMITED = "rate_limited"
    TEMPORARY_FAILURE = "temporary_failure"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass(frozen=True, slots=True)
class Capabilities:
    automatic: bool
    manual: bool
    assisted: bool
    supports_batch: bool
    supports_key_lookup: bool
    supports_discovery: bool
    requires_certificate: bool
    requires_human_action: bool
    document_types: frozenset[str]


@dataclass(slots=True)
class PluginRequest:
    tenant_id: UUID
    legal_entity_id: UUID | None
    document_type: str
    access_key: str | None
    config: dict[str, Any] = field(default_factory=dict)
    secrets: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PluginResult:
    plugin: str
    status: PluginStatus
    access_key: str | None = None
    xml: bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    retry_after_seconds: int | None = None
    message: str | None = None


class FiscalPlugin(ABC):
    key: str
    name: str
    version: str = "1.0.0"
    capabilities: Capabilities

    async def healthcheck(self, config: dict, secrets: dict) -> tuple[bool, str]:
        return True, "ok"

    @abstractmethod
    async def retrieve(self, request: PluginRequest) -> PluginResult:
        raise NotImplementedError
