from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decrypt_secret
from ..models import JobStatus, PluginInstallation, RetrievalJob, RoutingPolicy
from ..plugins.registry import registry
from ..plugins.sdk import PluginRequest, PluginStatus
from .documents import persist_parsed_document
from .xml import parse_xml


async def _resolve_installations(db: AsyncSession, job: RetrievalJob) -> list[PluginInstallation]:
    policy = await db.scalar(
        select(RoutingPolicy).where(
            RoutingPolicy.tenant_id == job.tenant_id,
            RoutingPolicy.document_type == job.document_type,
            RoutingPolicy.operation == "retrieve_by_key",
            RoutingPolicy.enabled.is_(True),
        ).order_by(RoutingPolicy.legal_entity_id.desc().nullslast())
    )
    stmt = select(PluginInstallation).where(
        PluginInstallation.tenant_id == job.tenant_id,
        PluginInstallation.enabled.is_(True),
    )
    installations = list((await db.scalars(stmt)).all())
    by_id = {str(item.id): item for item in installations}
    by_key: dict[str, list[PluginInstallation]] = {}
    for item in installations:
        by_key.setdefault(item.plugin_key, []).append(item)
    if policy and policy.steps:
        ordered = []
        for step in sorted(policy.steps, key=lambda item: item.get("priority", 100)):
            installation = by_id.get(str(step.get("installation_id")))
            if installation is None and step.get("plugin_key"):
                candidates = by_key.get(step["plugin_key"], [])
                installation = candidates[0] if candidates else None
            if installation:
                ordered.append(installation)
        if ordered:
            return ordered
    return sorted(installations, key=lambda item: item.priority)


async def execute_retrieval_job(db: AsyncSession, job_id: UUID) -> RetrievalJob:
    job = await db.get(RetrievalJob, job_id, with_for_update=True)
    if job is None:
        raise LookupError("Job não encontrado")
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    job.progress = 5
    await db.commit()

    installations = await _resolve_installations(db, job)
    attempts: list[dict] = []
    human_action = None
    for index, installation in enumerate(installations, start=1):
        plugin = registry.get(installation.plugin_key)
        secrets = {}
        if installation.encrypted_secrets:
            secrets = json.loads(decrypt_secret(installation.encrypted_secrets).decode())
        request = PluginRequest(
            tenant_id=job.tenant_id,
            legal_entity_id=job.legal_entity_id,
            document_type=job.document_type,
            access_key=job.access_key,
            config=installation.config,
            secrets=secrets,
        )
        result = await plugin.retrieve(request)
        attempts.append({
            "plugin": plugin.key,
            "installation": installation.name,
            "status": result.status,
            "message": result.message,
            "metadata": result.metadata,
            "at": datetime.now(UTC).isoformat(),
        })
        job.progress = min(90, 10 + int(index / max(len(installations), 1) * 75))
        job.attempts = attempts
        await db.commit()

        if result.status == PluginStatus.FOUND and result.xml:
            parsed = parse_xml(result.xml)
            document = await persist_parsed_document(
                db,
                tenant_id=job.tenant_id,
                legal_entity_id=job.legal_entity_id,
                parsed=parsed,
                source_key=plugin.key,
                source_metadata=result.metadata,
            )
            job.result_document_id = document.id
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.finished_at = datetime.now(UTC)
            await db.commit()
            return job
        if result.status == PluginStatus.HUMAN_ACTION_REQUIRED:
            human_action = {"plugin": plugin.key, **result.metadata}

    job.human_action = human_action
    job.status = JobStatus.HUMAN_ACTION_REQUIRED if human_action else JobStatus.NOT_FOUND
    job.progress = 100
    job.finished_at = datetime.now(UTC)
    await db.commit()
    return job
