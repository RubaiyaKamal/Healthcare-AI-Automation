"""
Audit logging — called by every tool that touches patient data.

Writes "who did what, to which resource, when" into audit_log so the
system can demonstrate HIPAA-style access transparency. Every agent
tool must call one of these helpers before/after acting.
"""

import logging
from database import execute

log = logging.getLogger(__name__)


async def record(
    *,
    actor: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    summary: str | None = None,
    actor_type: str = "tool",
    ip_address: str | None = None,
) -> None:
    await execute(
        """
        INSERT INTO audit_log (actor, actor_type, action, resource_type, resource_id, summary, ip_address)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        actor,
        actor_type,
        action,
        resource_type,
        resource_id,
        summary,
        ip_address,
    )
    log.info("audit: actor=%s action=%s resource=%s/%s", actor, action, resource_type, resource_id)


async def record_patient_read(actor: str, patient_fhir_id: str, summary: str | None = None) -> None:
    await record(
        actor=actor,
        action="READ",
        resource_type="Patient",
        resource_id=patient_fhir_id,
        summary=summary,
    )


async def record_patient_create(actor: str, patient_fhir_id: str, summary: str | None = None) -> None:
    await record(
        actor=actor,
        action="CREATE",
        resource_type="Patient",
        resource_id=patient_fhir_id,
        summary=summary,
    )


async def record_eligibility_check(actor: str, patient_fhir_id: str, summary: str | None = None) -> None:
    await record(
        actor=actor,
        action="CHECK_ELIGIBILITY",
        resource_type="Patient",
        resource_id=patient_fhir_id,
        summary=summary,
    )