"""Structural sign-off (PD-24, BP-04, BP-18, BP-20).

Every structural line of an IN_REVIEW version is signed by a qualified structural engineer, in
one of two ways: a verified listed engineer (verified registration, ACTIVE engagement on the
project) confirms with a one-time code; or operations upload an outside engineer's signed
document with the engineer's credential. Each sign-off records the engineer, the category, the
credential reference, the version and its content hash, the drawing set and its structural
drawing hashes, the line as signed, the statement (configurable, versioned), the evidence and the
time. The one-time code is a confirmation step, not a legally recognised electronic signature.

A sign-off is voided (never edited) when the version returns to draft, or when the signer or
operations revoke it before issue. After issue a revocation is recorded as an event; the version
can then no longer be accepted and is withdrawn or replaced (BP-20)."""

import uuid
from string import Template
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.buildplan.common import Who, conflict, db_now, history, require_package
from p2b.buildplan.models import (
    AcceptanceStatement,
    BuildPlanEvent,
    BuildPlanSpecValue,
    BuildPlanVersion,
    DrawingFile,
    DrawingSet,
    SignoffStatement,
    StructuralSignoff,
)
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import (
    BuildPlanState,
    ConfigStatus,
    DrawingClass,
    FilePurpose,
    FileState,
    SignerKind,
    SignoffMode,
    SignoffState,
)
from p2b.documents.interface import file_facts
from p2b.engagements.interface import active_engagements_of_profile
from p2b.professionals.interface import Credential, registration_credential

CATEGORY = "STRUCTURAL_ENGINEER"
REVOKED_AFTER_ISSUE = "REVOKED_AFTER_ISSUE"


# --- statements ------------------------------------------------------------------------------


# Both statements (structural sign-off, BP-04; homeowner acceptance, BP-05) are versioned
# configuration with the same lifecycle: DRAFT, then ACTIVE (one at a time), then RETIRED.
ACCEPTANCE_FIELDS = {"version_no": "1", "project_code": "P2B-TEST", "content_hash": "0" * 64}


async def active_statement[S: (SignoffStatement, AcceptanceStatement)](
    session: AsyncSession, model: type[S]
) -> S:
    statement = (
        await session.scalars(select(model).where(model.status == ConfigStatus.ACTIVE.value))
    ).one_or_none()
    if statement is None:
        raise conflict("NO_STATEMENT", "No statement of this kind is active.")
    return statement


async def statements[S: (SignoffStatement, AcceptanceStatement)](
    session: AsyncSession, model: type[S]
) -> list[S]:
    return list(await session.scalars(select(model).order_by(model.version)))


async def draft_statement[S: (SignoffStatement, AcceptanceStatement)](
    session: AsyncSession,
    who: Who,
    text: str,
    note: str,
    model: type[S],
) -> S:
    if model is AcceptanceStatement:
        try:
            Template(text).substitute(ACCEPTANCE_FIELDS)
        except (KeyError, ValueError):
            raise ValidationFailed(
                details={
                    "fields": {"text": ["Use only $version_no, $project_code, $content_hash."]}
                }
            ) from None
    latest = max((s.version for s in await statements(session, model)), default=0)
    statement = model(
        id=new_id(), version=latest + 1, text=text.strip(), status=ConfigStatus.DRAFT.value,
        note=note, created_by=who.user_id,
    )  # fmt: skip
    session.add(statement)
    await session.flush()
    return statement


async def activate_statement[S: (SignoffStatement, AcceptanceStatement)](
    session: AsyncSession,
    who: Who,
    statement_id: uuid.UUID,
    model: type[S],
) -> None:
    statement = await session.get(model, statement_id, with_for_update=True)
    if statement is None:
        raise NotFound
    if statement.status != ConfigStatus.DRAFT.value:
        raise StateConflict(details={"current_state": statement.status})
    current = (
        await session.scalars(
            select(model).where(model.status == ConfigStatus.ACTIVE.value).with_for_update()
        )
    ).one_or_none()
    if current is not None:
        current.status = ConfigStatus.RETIRED.value
        await session.flush()
    statement.status = ConfigStatus.ACTIVE.value
    statement.activated_by = who.user_id
    statement.activated_at = await db_now(session)
    await session.flush()


# --- what needs signing ----------------------------------------------------------------------


async def structural_values(
    session: AsyncSession, version_id: uuid.UUID
) -> dict[str, BuildPlanSpecValue]:
    rows = await session.scalars(
        select(BuildPlanSpecValue).where(
            BuildPlanSpecValue.version_id == version_id, BuildPlanSpecValue.is_structural
        )
    )
    return {row.line_code: row for row in rows}


async def signed(session: AsyncSession, version_id: uuid.UUID) -> list[StructuralSignoff]:
    return list(
        await session.scalars(
            select(StructuralSignoff)
            .where(
                StructuralSignoff.version_id == version_id,
                StructuralSignoff.state == SignoffState.SIGNED.value,
            )
            .order_by(StructuralSignoff.line_code)
        )
    )


async def all_of(session: AsyncSession, version_id: uuid.UUID) -> list[StructuralSignoff]:
    return list(
        await session.scalars(
            select(StructuralSignoff)
            .where(StructuralSignoff.version_id == version_id)
            .order_by(StructuralSignoff.line_code, StructuralSignoff.signed_at)
        )
    )


async def unsigned_lines(session: AsyncSession, version: BuildPlanVersion) -> list[str]:
    """Structural lines (applicable or not, BP-18) without a SIGNED sign-off on this exact
    content hash."""
    good = {
        s.line_code
        for s in await signed(session, version.id)
        if s.content_hash == version.content_hash
    }
    return sorted(set(await structural_values(session, version.id)) - good)


async def revoked_after_issue(session: AsyncSession, version_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(BuildPlanEvent.id).where(
            BuildPlanEvent.subject == "SIGNOFF",
            BuildPlanEvent.to_state == REVOKED_AFTER_ISSUE,
            BuildPlanEvent.reason.is_not(None),
            BuildPlanEvent.subject_id.in_(
                select(StructuralSignoff.id).where(StructuralSignoff.version_id == version_id)
            ),
        )
    )
    return found is not None


# --- signing ---------------------------------------------------------------------------------


async def _in_review(session: AsyncSession, version_id: uuid.UUID) -> BuildPlanVersion:
    version = await session.get(BuildPlanVersion, version_id, with_for_update=True)
    if version is None:
        raise NotFound
    if version.state != BuildPlanState.IN_REVIEW.value:
        raise StateConflict(details={"current_state": version.state})
    await require_package(session, version.project_id)
    return version


async def _drawings(
    session: AsyncSession, version: BuildPlanVersion
) -> tuple[uuid.UUID, list[str]]:
    assert version.drawing_set_id is not None  # noqa: S101 (IN_REVIEW versions have a set)
    files = await session.scalars(
        select(DrawingFile).where(
            DrawingFile.set_id == version.drawing_set_id,
            DrawingFile.drawing_class == DrawingClass.STRUCTURAL.value,
        )
    )
    return version.drawing_set_id, sorted(f.sha256 or "" for f in files)


async def _lines(
    session: AsyncSession, version: BuildPlanVersion, codes: list[str]
) -> list[BuildPlanSpecValue]:
    structural = await structural_values(session, version.id)
    wanted = list(dict.fromkeys(codes))
    if not wanted or set(wanted) - set(structural):
        raise ValidationFailed(details={"fields": {"line_codes": ["Choose structural lines."]}})
    already = {s.line_code for s in await signed(session, version.id)}
    if set(wanted) & already:
        raise conflict("ALREADY_SIGNED", "A chosen line is already signed.")
    return [structural[c] for c in wanted]


def _snapshot(value: BuildPlanSpecValue) -> dict[str, Any]:
    return {
        "criteria": value.criteria_text,
        "applicability": value.applicability,
        "value": value.value_text,
        "basis": value.basis,
        "not_applicable_reason": value.not_applicable_reason,
    }


async def engineer_for(
    session: AsyncSession, profile_id: uuid.UUID, project_id: uuid.UUID
) -> Credential:
    """A verified engineer: listed STRUCTURAL_ENGINEER with a verified registration and an
    ACTIVE engagement in that category on the project."""
    engaged = any(
        e.project_id == project_id and e.category_code == CATEGORY and e.party == "LISTED"
        for e in await active_engagements_of_profile(session, profile_id)
    )
    credential = await registration_credential(session, profile_id, CATEGORY)
    if not engaged or credential is None or not credential.listed:
        raise conflict("NOT_VERIFIED", "Only a verified structural engineer engaged here can sign.")
    return credential


async def sign_with_code(
    session: AsyncSession,
    who: Who,
    version_id: uuid.UUID,
    *,
    profile_id: uuid.UUID,
    codes: list[str],
    challenge_id: uuid.UUID,
) -> list[StructuralSignoff]:
    """The challenge was verified by the caller (purpose SIGN_STRUCTURAL, subject the version)."""
    version = await _in_review(session, version_id)
    credential = await engineer_for(session, profile_id, version.project_id)
    statement = await active_statement(session, SignoffStatement)
    set_id, hashes = await _drawings(session, version)
    rows = []
    for value in await _lines(session, version, codes):
        row = StructuralSignoff(
            id=new_id(), version_id=version.id, project_id=version.project_id,
            line_code=value.line_code, mode=SignoffMode.ONE_TIME_CODE.value,
            signer_kind=SignerKind.LISTED.value, profile_id=profile_id, category_code=CATEGORY,
            engineer_name=credential.display_name or credential.firm_name or "",
            engineer_firm=credential.firm_name,
            registration_number=str(credential.detail.get("number") or "") or None,
            registration_issuer=str(credential.detail.get("issuer") or "") or None,
            credential_reference={
                "verification_check_id": str(credential.check_id),
                "verification_case_id": str(credential.case_id),
                "subject": credential.subject,
                "recorded_at": credential.recorded_at.isoformat(),
            },
            statement_id=statement.id, statement_text=statement.text,
            content_hash=version.content_hash or "", drawing_set_id=set_id, drawing_hashes=hashes,
            line_snapshot=_snapshot(value), challenge_id=challenge_id, recorded_by=who.user_id,
            state=SignoffState.SIGNED.value,
        )  # fmt: skip
        session.add(row)
        rows.append(row)
    await session.flush()
    for row in rows:
        await history(
            session, project_id=version.project_id, subject="SIGNOFF", subject_id=row.id,
            old=None, new=SignoffState.SIGNED.value, who=who,
            detail={"line": row.line_code, "mode": row.mode, "content_hash": row.content_hash},
        )  # fmt: skip
    return rows


async def sign_with_document(
    session: AsyncSession,
    who: Who,
    version_id: uuid.UUID,
    *,
    codes: list[str],
    engineer_name: str,
    engineer_firm: str | None,
    registration_number: str,
    registration_issuer: str,
    credential_file_id: uuid.UUID,
    evidence_file_id: uuid.UUID,
    attestation: str,
) -> list[StructuralSignoff]:
    """Operations record an outside engineer's signed document (BP-04 mode 2)."""
    version = await _in_review(session, version_id)
    facts = await file_facts(session, [credential_file_id, evidence_file_id])
    for name, file_id in (("credential_file_id", credential_file_id),
                          ("evidence_file_id", evidence_file_id)):  # fmt: skip
        f = facts.get(file_id)
        if (
            f is None
            or f.project_id != version.project_id
            or f.purpose != FilePurpose.BUILD_PLAN_EVIDENCE
            or f.state != FileState.AVAILABLE
        ):
            raise ValidationFailed(details={"fields": {name: ["Upload the document first."]}})
    statement = await active_statement(session, SignoffStatement)
    set_id, hashes = await _drawings(session, version)
    rows = []
    for value in await _lines(session, version, codes):
        row = StructuralSignoff(
            id=new_id(), version_id=version.id, project_id=version.project_id,
            line_code=value.line_code, mode=SignoffMode.SIGNED_DOCUMENT.value,
            signer_kind=SignerKind.OUTSIDE.value, category_code=CATEGORY,
            engineer_name=engineer_name, engineer_firm=engineer_firm,
            registration_number=registration_number, registration_issuer=registration_issuer,
            credential_reference={
                "registration_number": registration_number,
                "registration_issuer": registration_issuer,
                "certificate_file_id": str(credential_file_id),
                "checked_by": str(who.user_id),
                "attestation": attestation,
            },
            credential_file_id=credential_file_id, statement_id=statement.id,
            statement_text=statement.text, content_hash=version.content_hash or "",
            drawing_set_id=set_id, drawing_hashes=hashes, line_snapshot=_snapshot(value),
            evidence_file_id=evidence_file_id, recorded_by=who.user_id,
            state=SignoffState.SIGNED.value,
        )  # fmt: skip
        session.add(row)
        rows.append(row)
    await session.flush()
    for row in rows:
        await history(
            session, project_id=version.project_id, subject="SIGNOFF", subject_id=row.id,
            old=None, new=SignoffState.SIGNED.value, who=who, reason=attestation,
            detail={"line": row.line_code, "mode": row.mode, "content_hash": row.content_hash},
        )  # fmt: skip
    return rows


async def _void(session: AsyncSession, who: Who, row: StructuralSignoff, reason: str) -> None:
    row.state = SignoffState.VOID.value
    row.voided_at = await db_now(session)
    row.voided_by = who.user_id
    row.void_reason = reason
    await session.flush()
    await history(
        session, project_id=row.project_id, subject="SIGNOFF", subject_id=row.id,
        old=SignoffState.SIGNED.value, new=SignoffState.VOID.value, who=who, reason=reason,
    )  # fmt: skip


async def void_all(session: AsyncSession, who: Who, version: BuildPlanVersion, reason: str) -> None:
    for row in await signed(session, version.id):
        await _void(session, who, row, reason)


async def revoke(
    session: AsyncSession,
    who: Who,
    signoff_id: uuid.UUID,
    reason: str,
    *,
    profile_id: uuid.UUID | None,
) -> None:
    """By the listed signer (profile_id) or operations (profile_id None). Before issue the
    sign-off is voided; after issue the revocation is an event that blocks acceptance (BP-20);
    the signed record itself never changes."""
    row = await session.get(StructuralSignoff, signoff_id, with_for_update=True)
    if row is None or (profile_id is not None and row.profile_id != profile_id):
        raise NotFound
    if row.state != SignoffState.SIGNED.value:
        raise StateConflict(details={"current_state": row.state})
    version = await session.get_one(BuildPlanVersion, row.version_id)
    if version.state == BuildPlanState.IN_REVIEW.value:
        await _void(session, who, row, reason)
        return
    if version.state in (BuildPlanState.ISSUED.value, BuildPlanState.ACCEPTED.value):
        await history(
            session, project_id=row.project_id, subject="SIGNOFF", subject_id=row.id,
            old=SignoffState.SIGNED.value, new=REVOKED_AFTER_ISSUE, who=who, reason=reason,
        )  # fmt: skip
        return
    raise StateConflict(details={"current_state": version.state})


async def drawing_set_of(session: AsyncSession, version: BuildPlanVersion) -> DrawingSet | None:
    return await session.get(DrawingSet, version.drawing_set_id) if version.drawing_set_id else None
