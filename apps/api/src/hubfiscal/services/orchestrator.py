from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decrypt_secret
from ..models import DfeCursor, JobStatus, PluginInstallation, RetrievalBatch, RetrievalJob, RoutingPolicy
from ..plugins.registry import registry
from ..plugins.sdk import PluginRequest, PluginResult, PluginStatus
from .documents import persist_parsed_document
from .xml import parse_xml

TERMINAL_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.PARTIAL,
    JobStatus.NOT_FOUND,
    JobStatus.FAILED,
    JobStatus.HUMAN_ACTION_REQUIRED,
}


async def _resolve_installations(db: AsyncSession, job: RetrievalJob) -> list[PluginInstallation]:
    if job.plugin_installation_id:
        selected = await db.scalar(
            select(PluginInstallation).where(
                PluginInstallation.id == job.plugin_installation_id,
                PluginInstallation.tenant_id == job.tenant_id,
                PluginInstallation.enabled.is_(True),
            )
        )
        return [selected] if selected else []

    operation = job.operation if job.operation not in {"consChNFe", "consNSU", "distNSU"} else job.operation
    policy = await db.scalar(
        select(RoutingPolicy).where(
            RoutingPolicy.tenant_id == job.tenant_id,
            RoutingPolicy.document_type == job.document_type,
            RoutingPolicy.operation == operation,
            RoutingPolicy.enabled.is_(True),
        ).order_by(RoutingPolicy.legal_entity_id.desc().nullslast())
    )
    stmt = select(PluginInstallation).where(
        PluginInstallation.tenant_id == job.tenant_id,
        PluginInstallation.enabled.is_(True),
    )
    installations = list((await db.scalars(stmt)).all())
    if job.legal_entity_id:
        installations = [item for item in installations if item.legal_entity_id in {None, job.legal_entity_id}]
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
            if installation and installation not in ordered:
                ordered.append(installation)
        if ordered:
            return ordered
    return sorted(installations, key=lambda item: item.priority)


async def _update_dfe_cursor(
    db: AsyncSession,
    job: RetrievalJob,
    installation: PluginInstallation,
    result: PluginResult,
) -> None:
    if installation.plugin_key != "nfe-distribution" or job.legal_entity_id is None:
        return
    if job.operation not in {"distNSU", "consNSU", "consChNFe"}:
        return
    cursor = await db.scalar(
        select(DfeCursor).where(
            DfeCursor.tenant_id == job.tenant_id,
            DfeCursor.legal_entity_id == job.legal_entity_id,
            DfeCursor.plugin_installation_id == installation.id,
            DfeCursor.environment == job.environment,
        )
    )
    if cursor is None:
        cursor = DfeCursor(
            tenant_id=job.tenant_id,
            legal_entity_id=job.legal_entity_id,
            plugin_installation_id=installation.id,
            environment=job.environment,
        )
        db.add(cursor)
    metadata = result.metadata or {}
    if metadata.get("ult_nsu"):
        cursor.last_nsu = str(metadata["ult_nsu"]).zfill(15)
    if metadata.get("max_nsu"):
        cursor.max_nsu = str(metadata["max_nsu"]).zfill(15)
    cursor.last_cstat = str(metadata.get("cstat")) if metadata.get("cstat") is not None else None
    cursor.last_message = result.message or metadata.get("message")
    cursor.last_checked_at = datetime.now(UTC)
    if cursor.last_cstat == "656" or (cursor.last_cstat == "137" and job.operation == "distNSU"):
        cursor.blocked_until = datetime.now(UTC) + timedelta(hours=1)
    elif result.status != PluginStatus.RATE_LIMITED:
        cursor.blocked_until = None


async def _persist_result_documents(
    db: AsyncSession,
    job: RetrievalJob,
    installation: PluginInstallation,
    result: PluginResult,
) -> list[UUID]:
    payloads = []
    if result.xml:
        payloads.append((result.xml, result.metadata))
    payloads.extend((item.xml, {**result.metadata, **item.metadata}) for item in result.documents)
    document_ids: list[UUID] = []
    ignored: list[str] = []
    for xml, metadata in payloads:
        try:
            parsed = parse_xml(xml)
        except Exception as exc:
            ignored.append(str(exc))
            continue
        document = await persist_parsed_document(
            db,
            tenant_id=job.tenant_id,
            legal_entity_id=job.legal_entity_id,
            parsed=parsed,
            source_key=installation.plugin_key,
            source_metadata=metadata,
        )
        if document.id not in document_ids:
            document_ids.append(document.id)
    if ignored:
        attempts = list(job.attempts or [])
        attempts.append({
            "plugin": installation.plugin_key,
            "installation": installation.name,
            "status": "partial_parse",
            "message": f"{len(ignored)} retorno(s) não puderam ser classificados como documento fiscal",
            "metadata": {"ignored": len(ignored)},
            "at": datetime.now(UTC).isoformat(),
        })
        job.attempts = attempts
    return document_ids


async def refresh_batch(db: AsyncSession, batch_id: UUID | None) -> None:
    if batch_id is None:
        return
    batch = await db.get(RetrievalBatch, batch_id)
    if batch is None:
        return
    jobs = list((await db.scalars(select(RetrievalJob).where(RetrievalJob.batch_id == batch_id))).all())
    terminal = [job for job in jobs if job.status in TERMINAL_STATUSES]
    batch.completed_count = len(terminal)
    batch.found_count = sum(1 for job in jobs if job.status in {JobStatus.COMPLETED, JobStatus.PARTIAL} and job.result_document_ids)
    batch.not_found_count = sum(1 for job in jobs if job.status == JobStatus.NOT_FOUND)
    batch.failed_count = sum(1 for job in jobs if job.status == JobStatus.FAILED)
    if not terminal:
        batch.status = JobStatus.QUEUED
    elif len(terminal) < batch.total_count:
        batch.status = JobStatus.RUNNING
    elif batch.failed_count:
        batch.status = JobStatus.PARTIAL
    else:
        batch.status = JobStatus.COMPLETED


async def mark_job_failed(db: AsyncSession, job_id: UUID, message: str) -> None:
    job = await db.get(RetrievalJob, job_id)
    if job is None:
        return
    job.status = JobStatus.FAILED
    job.error_message = message[:4000]
    job.progress = 100
    job.finished_at = datetime.now(UTC)
    await refresh_batch(db, job.batch_id)
    await db.commit()


async def execute_retrieval_job(db: AsyncSession, job_id: UUID) -> RetrievalJob:
    job = await db.get(RetrievalJob, job_id, with_for_update=True)
    if job is None:
        raise LookupError("Job não encontrado")
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    job.progress = 5
    await refresh_batch(db, job.batch_id)
    await db.commit()

    installations = await _resolve_installations(db, job)
    if not installations:
        job.status = JobStatus.FAILED
        job.error_message = "Nenhuma fonte/conector habilitado para esta operação"
        job.progress = 100
        job.finished_at = datetime.now(UTC)
        await refresh_batch(db, job.batch_id)
        await db.commit()
        return job

    attempts: list[dict] = []
    human_action = None
    saw_failure = False
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
            operation=job.operation,
            environment=job.environment,
            parameters=job.parameters or {},
            config=installation.config or {},
            secrets=secrets,
        )
        result = await plugin.retrieve(request)
        attempts.append({
            "plugin": plugin.key,
            "installation_id": str(installation.id),
            "installation": installation.name,
            "status": result.status,
            "message": result.message,
            "metadata": result.metadata,
            "at": datetime.now(UTC).isoformat(),
        })
        job.progress = min(90, 10 + int(index / max(len(installations), 1) * 75))
        job.attempts = attempts
        await _update_dfe_cursor(db, job, installation, result)
        await db.commit()

        if result.status == PluginStatus.FOUND and (result.xml or result.documents):
            document_ids = await _persist_result_documents(db, job, installation, result)
            job.result_document_ids = [str(item) for item in document_ids]
            job.result_document_id = document_ids[0] if document_ids else None
            job.status = JobStatus.COMPLETED if document_ids else JobStatus.PARTIAL
            job.progress = 100
            job.finished_at = datetime.now(UTC)
            if not document_ids:
                job.error_message = "A fonte retornou dados, mas nenhum documento fiscal pôde ser persistido"
            await refresh_batch(db, job.batch_id)
            await db.commit()
            return job
        if result.status == PluginStatus.HUMAN_ACTION_REQUIRED:
            human_action = {"plugin": plugin.key, **result.metadata}
        if result.status in {PluginStatus.TEMPORARY_FAILURE, PluginStatus.PERMANENT_FAILURE, PluginStatus.RATE_LIMITED, PluginStatus.NOT_AUTHORIZED}:
            saw_failure = True
            if result.status == PluginStatus.RATE_LIMITED:
                break

    job.human_action = human_action
    if human_action:
        job.status = JobStatus.HUMAN_ACTION_REQUIRED
    elif saw_failure:
        job.status = JobStatus.FAILED
        job.error_message = next((attempt.get("message") for attempt in reversed(attempts) if attempt.get("message")), "Falha nas fontes configuradas")
    else:
        job.status = JobStatus.NOT_FOUND
    job.progress = 100
    job.finished_at = datetime.now(UTC)
    await refresh_batch(db, job.batch_id)
    await db.commit()
    return job
