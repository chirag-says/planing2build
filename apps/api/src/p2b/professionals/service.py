"""Professionals (Slice 3.2; SLICE3_2_READINESS K0).

A professional registers (or operations create the account, D-04), fills a profile, adds
categories (D-06), supplies evidence (documents, references, portfolio) and submits a category
for review. Operations record checks against the category's versioned requirements (D-02) and
approve, request changes or reject; only approval lists a category. Operations or admins may
suspend and reinstate (D-10); the professional may hide and show a listed category (D-11).
The public directory shows LISTED, not hidden categories only, in a neutral daily shuffle (D-08).
"""

import base64
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from geoalchemy2 import WKTElement
from sqlalchemy import Integer, Select, String, and_, cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.catalog.interface import (
    ListingRequirements,
    active_listing_requirements,
    listing_requirements,
    service_category_rows,
    unmet,
)
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import (
    ActorType,
    CheckKind,
    CheckOutcome,
    FilePurpose,
    FileState,
    ListingState,
    PortfolioReviewState,
    ProfessionalDocumentKind,
    RequirementLevel,
    VerificationDecision,
)
from p2b.documents.interface import FileSummary, file_purpose, personal_files
from p2b.identity.interface import Actor
from p2b.professionals.models import (
    ListingHistory,
    PortfolioItem,
    ProfessionalCategory,
    ProfessionalDocument,
    ProfessionalProfile,
    ProfessionalReference,
    VerificationCase,
    VerificationCheck,
)

L = ListingState
LISTING = TransitionTable[ListingState](
    "professional_listing",
    [
        Transition(None, L.DRAFT, "create"),
        Transition(L.DRAFT, L.PENDING_REVIEW, "submit"),
        Transition(L.CHANGES_REQUESTED, L.PENDING_REVIEW, "submit"),
        Transition(L.REJECTED, L.PENDING_REVIEW, "submit"),  # reapply, after the waiting time
        Transition(L.LISTED, L.PENDING_REVIEW, "reverify"),  # D-02 periodic re-verification
        Transition(L.PENDING_REVIEW, L.CHANGES_REQUESTED, "request_changes"),
        Transition(L.PENDING_REVIEW, L.LISTED, "approve"),
        Transition(L.PENDING_REVIEW, L.REJECTED, "reject"),
        Transition(L.LISTED, L.SUSPENDED, "suspend"),
        Transition(L.SUSPENDED, L.LISTED, "reinstate"),
    ],
)
# Evidence is frozen while operations review it.
LOCKING = frozenset({L.PENDING_REVIEW.value})
# Name and firm are what the public sees and what operations verified: fixed once submitted.
NAME_LOCKING = frozenset({L.PENDING_REVIEW.value, L.LISTED.value, L.SUSPENDED.value})
EDITABLE_SUBTYPES = frozenset({L.DRAFT.value, L.CHANGES_REQUESTED.value, L.REJECTED.value})
DOCUMENT_CHECK = {
    ProfessionalDocumentKind.IDENTITY: CheckKind.IDENTITY,
    ProfessionalDocumentKind.BUSINESS: CheckKind.BUSINESS,
    ProfessionalDocumentKind.REGISTRATION: CheckKind.REGISTRATION,
}
PROFILE_REQUIRED = (
    "display_name",
    "base_locality",
    "base_geom",
    "service_radius_km",
    "years_experience",
    "bio",
)
Role = Literal["PROFESSIONAL", "OPS", "ADMIN"]


class CategorySubmitted(EventPayload):
    professional_category_id: uuid.UUID
    profile_id: uuid.UUID


class ListingChanged(EventPayload):
    professional_category_id: uuid.UUID
    profile_id: uuid.UUID
    listing_state: ListingState
    hidden: bool


# --- shared helpers ---------------------------------------------------------------------------


async def _now(session: AsyncSession) -> datetime:
    return (await session.execute(select(func.now()))).scalar_one()


def _months(start: datetime, months: int) -> datetime:
    """Calendar months forward, clamped to the month's last day."""
    year, month = divmod(start.month - 1 + months, 12)
    year, month = start.year + year, month + 1
    day = start.day
    while True:
        try:
            return start.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1


async def _history(
    session: AsyncSession,
    category: ProfessionalCategory,
    *,
    event: str,
    from_state: str | None,
    actor_user_id: uuid.UUID | None,
    role: Role,
    reason: str | None = None,
    session_id: uuid.UUID | None = None,
) -> None:
    session.add(
        ListingHistory(
            id=new_id(),
            professional_category_id=category.id,
            event=event,
            from_state=from_state,
            to_state=category.listing_state,
            actor_user_id=actor_user_id,
            actor_role=role,
            reason=reason,
        )
    )
    await session.flush()
    await record(
        session,
        action=f"professional_listing.{event}",
        entity_type="professional_category",
        entity_id=category.id,
        actor_type=ActorType.USER,
        actor_user_id=actor_user_id,
        actor_role=role,
        session_id=session_id,
        old_value={"listing_state": from_state},
        new_value={"listing_state": category.listing_state, "hidden": category.hidden},
        reason=reason,
    )
    await publish(
        session,
        event_type="professional.listing_changed",
        aggregate_type="professional_category",
        aggregate_id=category.id,
        payload=ListingChanged(
            professional_category_id=category.id,
            profile_id=category.profile_id,
            listing_state=ListingState(category.listing_state),
            hidden=category.hidden,
        ),
        dedupe_suffix=f"{event}:{category.version}",
    )


async def _move(
    session: AsyncSession,
    category: ProfessionalCategory,
    trigger: str,
    *,
    actor_user_id: uuid.UUID | None,
    role: Role,
    reason: str | None = None,
    session_id: uuid.UUID | None = None,
) -> None:
    current = ListingState(category.listing_state)
    category.listing_state = LISTING.target(current, trigger).value
    category.version += 1
    await session.flush()
    await _history(
        session,
        category,
        event=trigger,
        from_state=current.value,
        actor_user_id=actor_user_id,
        role=role,
        reason=reason,
        session_id=session_id,
    )


def _text(value: str | None, field_name: str, *, required: bool = True, limit: int = 2000) -> str:
    cleaned = (value or "").strip()
    if required and not cleaned:
        raise ValidationFailed(details={"fields": {field_name: ["Write a short message."]}})
    if len(cleaned) > limit:
        raise ValidationFailed(details={"fields": {field_name: ["The text is too long."]}})
    return cleaned


# --- the professional's own side --------------------------------------------------------------


async def _ensure_profile(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    created_by: uuid.UUID | None,
    display_name: str | None = None,
) -> uuid.UUID | None:
    """Create the account's empty profile unless it exists. Concurrent first requests (a page
    and its layout, two tabs) race here, so the insert yields to the unique key instead of
    failing. Returns the new profile's id, or None when it already existed."""
    created: uuid.UUID | None = await session.scalar(
        pg_insert(ProfessionalProfile)
        .values(id=new_id(), user_id=user_id, created_by=created_by, display_name=display_name)
        .on_conflict_do_nothing(index_elements=[ProfessionalProfile.user_id])
        .returning(ProfessionalProfile.id)
    )
    return created


async def own_profile(
    session: AsyncSession, actor: Actor, *, lock: bool = False
) -> ProfessionalProfile:
    """The actor's profile, created empty on first use (self-registration, D-04)."""
    query = select(ProfessionalProfile).where(ProfessionalProfile.user_id == actor.user_id)
    profile = (await session.scalars(query.with_for_update() if lock else query)).one_or_none()
    if profile is not None:
        return profile
    created = await _ensure_profile(session, user_id=actor.user_id, created_by=None)
    if created is not None:
        await record(
            session,
            action="professional_profile.created",
            entity_type="professional_profile",
            entity_id=created,
            actor_type=ActorType.USER,
            actor_user_id=actor.user_id,
            actor_role="PROFESSIONAL",
            session_id=actor.session_id,
        )
    return (await session.scalars(query.with_for_update() if lock else query)).one()


async def _categories(session: AsyncSession, profile_id: uuid.UUID) -> list[ProfessionalCategory]:
    return list(
        await session.scalars(
            select(ProfessionalCategory)
            .where(ProfessionalCategory.profile_id == profile_id)
            .order_by(ProfessionalCategory.created_at)
        )
    )


@dataclass
class ProfileUpdate:
    display_name: str | None = None
    firm_name: str | None = None
    bio: str | None = None
    years_experience: int | None = None
    team_size: int | None = None
    base_locality: str | None = None
    base_point: tuple[float, float] | None = None  # latitude, longitude
    service_radius_km: int | None = None
    fields_set: frozenset[str] = field(default_factory=frozenset)


async def update_profile(
    session: AsyncSession, actor: Actor, change: ProfileUpdate
) -> ProfessionalProfile:
    profile = await own_profile(session, actor, lock=True)
    states = {c.listing_state for c in await _categories(session, profile.id)}
    locked = bool(states & NAME_LOCKING)
    for name in change.fields_set:
        value = getattr(change, name)
        if name in ("display_name", "firm_name"):
            value = (value or "").strip() or None
            if locked and value != getattr(profile, name):
                raise StateConflict(
                    message="Your name and firm are fixed once a category is submitted.",
                    details={"field": name},
                )
        if name == "base_locality":
            value = (value or "").strip() or None
        if name == "bio":
            value = (value or "").strip() or None
        if name == "base_point":
            profile.base_geom = (
                WKTElement(f"POINT({value[1]} {value[0]})", srid=4326) if value else None
            )
            continue
        setattr(profile, name, value)
    profile.version += 1
    await session.flush()
    await session.refresh(profile)
    await record(
        session,
        action="professional_profile.updated",
        entity_type="professional_profile",
        entity_id=profile.id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        actor_role="PROFESSIONAL",
        session_id=actor.session_id,
        new_value={"fields": sorted(change.fields_set)},
    )
    return profile


def missing_profile_fields(profile: ProfessionalProfile) -> list[str]:
    return [name for name in PROFILE_REQUIRED if getattr(profile, name) in (None, "")]


async def _category_codes(session: AsyncSession) -> tuple[set[str], dict[str, str]]:
    """Top-level category codes, and each subtype's parent."""
    rows = await service_category_rows(session)
    return (
        {r.code for r in rows if r.parent_code is None},
        {r.code: r.parent_code for r in rows if r.parent_code},
    )


def _check_subtypes(code: str, subtypes: list[str], parents: dict[str, str]) -> list[str]:
    cleaned = sorted(set(subtypes))
    if any(parents.get(subtype) != code for subtype in cleaned):
        raise ValidationFailed(
            details={"fields": {"subtypes": ["Choose subtypes of this category."]}}
        )
    return cleaned


async def add_category(
    session: AsyncSession, actor: Actor, code: str, subtypes: list[str]
) -> ProfessionalCategory:
    profile = await own_profile(session, actor, lock=True)
    tops, parents = await _category_codes(session)
    if code not in tops:
        raise ValidationFailed(details={"fields": {"category": ["Choose a category."]}})
    existing = (
        await session.scalars(
            select(ProfessionalCategory).where(
                ProfessionalCategory.profile_id == profile.id,
                ProfessionalCategory.category_code == code,
            )
        )
    ).one_or_none()
    if existing is not None:
        return existing
    category = ProfessionalCategory(
        id=new_id(),
        profile_id=profile.id,
        category_code=code,
        subtypes=_check_subtypes(code, subtypes, parents),
        listing_state=LISTING.target(None, "create").value,
    )
    session.add(category)
    await session.flush()
    await session.refresh(category)
    await _history(
        session,
        category,
        event="create",
        from_state=None,
        actor_user_id=actor.user_id,
        role="PROFESSIONAL",
        session_id=actor.session_id,
    )
    return category


async def own_category(
    session: AsyncSession, actor: Actor, code: str, *, lock: bool = True
) -> tuple[ProfessionalProfile, ProfessionalCategory]:
    profile = await own_profile(session, actor)
    query = select(ProfessionalCategory).where(
        ProfessionalCategory.profile_id == profile.id, ProfessionalCategory.category_code == code
    )
    category = (await session.scalars(query.with_for_update() if lock else query)).one_or_none()
    if category is None:
        raise NotFound
    return profile, category


async def set_subtypes(
    session: AsyncSession, actor: Actor, code: str, subtypes: list[str]
) -> ProfessionalCategory:
    _, category = await own_category(session, actor, code)
    if category.listing_state not in EDITABLE_SUBTYPES:
        raise StateConflict(details={"current_state": category.listing_state})
    _, parents = await _category_codes(session)
    category.subtypes = _check_subtypes(code, subtypes, parents)
    category.version += 1
    await session.flush()
    return category


async def _evidence_locked(session: AsyncSession, profile_id: uuid.UUID) -> bool:
    return any(c.listing_state in LOCKING for c in await _categories(session, profile_id))


async def _own_file(
    session: AsyncSession, actor: Actor, file_id: uuid.UUID, purpose: FilePurpose
) -> None:
    owner = await file_purpose(session, file_id)
    if owner is None or owner != (actor.user_id, purpose.value):
        raise ValidationFailed(details={"fields": {"file_id": ["Upload the file first."]}})


async def add_document(
    session: AsyncSession,
    actor: Actor,
    *,
    kind: ProfessionalDocumentKind,
    file_id: uuid.UUID,
    category_code: str | None,
    details: dict[str, str],
) -> ProfessionalDocument:
    profile = await own_profile(session, actor, lock=True)
    if await _evidence_locked(session, profile.id):
        raise StateConflict(message="Documents are fixed while Plan2Build reviews them.")
    await _own_file(session, actor, file_id, FilePurpose.VERIFICATION_EVIDENCE)
    if category_code is not None and category_code not in (await _category_codes(session))[0]:
        raise ValidationFailed(details={"fields": {"category": ["Choose a category."]}})
    document = ProfessionalDocument(
        id=new_id(),
        profile_id=profile.id,
        category_code=category_code,
        kind=kind.value,
        file_id=file_id,
        details={k: v.strip()[:120] for k, v in details.items() if v.strip()},
    )
    session.add(document)
    await session.flush()
    await session.refresh(document)
    return document


async def add_reference(
    session: AsyncSession, actor: Actor, *, category_code: str, name: str, phone: str, note: str
) -> ProfessionalReference:
    profile = await own_profile(session, actor, lock=True)
    if await _evidence_locked(session, profile.id):
        raise StateConflict(message="References are fixed while Plan2Build reviews them.")
    if category_code not in (await _category_codes(session))[0]:
        raise ValidationFailed(details={"fields": {"category": ["Choose a category."]}})
    reference = ProfessionalReference(
        id=new_id(),
        profile_id=profile.id,
        category_code=category_code,
        name=_text(name, "name", limit=120),
        phone=_text(phone, "phone", limit=20),
        project_note=_text(note, "project_note", limit=300),
    )
    session.add(reference)
    await session.flush()
    await session.refresh(reference)
    return reference


async def add_portfolio_item(
    session: AsyncSession, actor: Actor, *, file_id: uuid.UUID, caption: str
) -> PortfolioItem:
    profile = await own_profile(session, actor, lock=True)
    if await _evidence_locked(session, profile.id):
        raise StateConflict(message="Your portfolio is fixed while Plan2Build reviews it.")
    await _own_file(session, actor, file_id, FilePurpose.PORTFOLIO)
    item = PortfolioItem(
        id=new_id(),
        profile_id=profile.id,
        file_id=file_id,
        caption=_text(caption, "caption", limit=200),
    )
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return item


async def remove_evidence(
    session: AsyncSession,
    actor: Actor,
    kind: Literal["document", "reference", "portfolio"],
    item_id: uuid.UUID,
) -> None:
    profile = await own_profile(session, actor, lock=True)
    if await _evidence_locked(session, profile.id):
        raise StateConflict(message="Evidence is fixed while Plan2Build reviews it.")
    model: type[ProfessionalDocument] | type[ProfessionalReference] | type[PortfolioItem]
    if kind == "document":
        model = ProfessionalDocument
    elif kind == "reference":
        model = ProfessionalReference
    else:
        model = PortfolioItem
    removed = await session.execute(
        update(model)
        .where(model.id == item_id, model.profile_id == profile.id, model.removed_at.is_(None))
        .values(removed_at=func.now())
        .returning(model.id)
    )
    if removed.first() is None:
        raise NotFound


@dataclass(frozen=True)
class Evidence:
    documents: list[ProfessionalDocument]
    references: list[ProfessionalReference]
    portfolio: list[PortfolioItem]
    files: dict[uuid.UUID, FileSummary]


async def evidence_for(session: AsyncSession, profile: ProfessionalProfile) -> Evidence:
    documents = list(
        await session.scalars(
            select(ProfessionalDocument)
            .where(
                ProfessionalDocument.profile_id == profile.id,
                ProfessionalDocument.removed_at.is_(None),
            )
            .order_by(ProfessionalDocument.created_at)
        )
    )
    references = list(
        await session.scalars(
            select(ProfessionalReference)
            .where(
                ProfessionalReference.profile_id == profile.id,
                ProfessionalReference.removed_at.is_(None),
            )
            .order_by(ProfessionalReference.created_at)
        )
    )
    portfolio = list(
        await session.scalars(
            select(PortfolioItem)
            .where(PortfolioItem.profile_id == profile.id, PortfolioItem.removed_at.is_(None))
            .order_by(PortfolioItem.created_at)
        )
    )
    files = await personal_files(
        session, profile.user_id, [d.file_id for d in documents] + [p.file_id for p in portfolio]
    )
    return Evidence(documents, references, portfolio, files)


def provided(evidence: Evidence, category_code: str) -> dict[CheckKind, int]:
    """What the professional has supplied for a category, by check kind (available files only).
    SITE_VISIT is never supplied: operations visit."""
    available = {fid for fid, f in evidence.files.items() if f.state == FileState.AVAILABLE}
    counts: dict[CheckKind, int] = dict.fromkeys(CheckKind, 0)
    for document in evidence.documents:
        if document.category_code in (None, category_code) and document.file_id in available:
            counts[DOCUMENT_CHECK[ProfessionalDocumentKind(document.kind)]] += 1
    counts[CheckKind.REFERENCE] = sum(
        1 for r in evidence.references if r.category_code == category_code
    )
    counts[CheckKind.PORTFOLIO] = sum(1 for p in evidence.portfolio if p.file_id in available)
    return counts


def missing_evidence(requirements: ListingRequirements, counts: dict[CheckKind, int]) -> list[str]:
    """REQUIRED requirements the professional has not supplied enough for (any accepted kind
    counts). Operations decide the WHERE_APPLICABLE ones and record site visits."""
    missing = []
    for requirement in requirements.requirements.requirements:
        if requirement.level != RequirementLevel.REQUIRED:
            continue
        supplied_kinds = [k for k in requirement.accepts if k != CheckKind.SITE_VISIT]
        if not supplied_kinds:
            continue
        if sum(counts[k] for k in supplied_kinds) < requirement.count:
            missing.append(requirement.id)
    return missing


async def submit_category(session: AsyncSession, actor: Actor, code: str) -> ProfessionalCategory:
    """Submit (or resubmit, or reapply) a category for review. Checks the profile and the
    evidence the professional must supply, freezes the requirement version and opens a case."""
    profile, category = await own_category(session, actor, code)
    state = ListingState(category.listing_state)
    if state == L.PENDING_REVIEW:
        return category  # already submitted: repeat-safe
    trigger = "reverify" if state == L.LISTED else "submit"
    now = await _now(session)
    if trigger == "reverify" and (category.review_due_at is None or category.review_due_at > now):
        raise StateConflict(
            message="Re-verification is not due yet.", details={"current_state": state.value}
        )
    if state == L.REJECTED and category.reapply_after and category.reapply_after > now:
        raise StateConflict(
            message="You can apply again later.",
            details={
                "current_state": state.value,
                "reapply_after": category.reapply_after.isoformat(),
            },
        )
    LISTING.target(state, trigger)  # 409 for SUSPENDED and anything else not allowed
    requirements = await active_listing_requirements(session, code)
    if requirements is None:
        raise RuntimeError(f"no active listing requirements for {code}")
    problems: dict[str, list[str]] = {}
    if missing := missing_profile_fields(profile):
        problems["profile"] = missing
    if missing := missing_evidence(
        requirements, provided(await evidence_for(session, profile), code)
    ):
        problems["requirements"] = missing
    if problems:
        raise ValidationFailed(message="Some details are still needed.", details=problems)
    category.requirement_version_id = requirements.id
    category.submitted_at = now
    category.message = None
    session.add(
        VerificationCase(
            id=new_id(),
            professional_category_id=category.id,
            requirement_version_id=requirements.id,
        )
    )
    await _move(
        session,
        category,
        trigger,
        actor_user_id=actor.user_id,
        role="PROFESSIONAL",
        session_id=actor.session_id,
    )
    await publish(
        session,
        event_type="professional.category_submitted",
        aggregate_type="professional_category",
        aggregate_id=category.id,
        payload=CategorySubmitted(professional_category_id=category.id, profile_id=profile.id),
        dedupe_suffix=f"submitted:{category.version}",
    )
    return category


async def set_hidden(
    session: AsyncSession, actor: Actor, code: str, *, hidden: bool
) -> ProfessionalCategory:
    """D-11: hide or show a listed category. Showing again needs the re-verification to be not
    yet due; a due category goes through re-verification instead."""
    _, category = await own_category(session, actor, code)
    if category.listing_state != L.LISTED.value:
        raise StateConflict(details={"current_state": category.listing_state})
    if category.hidden == hidden:
        return category
    if not hidden and category.review_due_at and category.review_due_at <= await _now(session):
        raise StateConflict(
            message=(
                "Your listing is due for re-verification. Submit it for review to show it again."
            ),
            details={"current_state": category.listing_state, "reverification": "due"},
        )
    category.hidden = hidden
    category.version += 1
    await session.flush()
    await _history(
        session,
        category,
        event="hide" if hidden else "show",
        from_state=category.listing_state,
        actor_user_id=actor.user_id,
        role="PROFESSIONAL",
        session_id=actor.session_id,
    )
    return category


# --- operations --------------------------------------------------------------------------------


async def create_profile_for(
    session: AsyncSession, *, user_id: uuid.UUID, created_by: uuid.UUID, display_name: str | None
) -> ProfessionalProfile:
    """The draft profile of an account operations created (D-04). Idempotent per account."""
    created = await _ensure_profile(
        session, user_id=user_id, created_by=created_by,
        display_name=(display_name or "").strip() or None,
    )  # fmt: skip
    if created is not None:
        await record(
            session,
            action="professional_profile.created",
            entity_type="professional_profile",
            entity_id=created,
            actor_type=ActorType.USER,
            actor_user_id=created_by,
            actor_role="OPS",
            reason="created by operations",
        )
    return (
        await session.scalars(
            select(ProfessionalProfile).where(ProfessionalProfile.user_id == user_id)
        )
    ).one()
    profile = ProfessionalProfile(
        id=new_id(),
        user_id=user_id,
        created_by=created_by,
        display_name=(display_name or "").strip() or None,
    )
    session.add(profile)
    await session.flush()
    await session.refresh(profile)
    await record(
        session,
        action="professional_profile.created",
        entity_type="professional_profile",
        entity_id=profile.id,
        actor_type=ActorType.USER,
        actor_user_id=created_by,
        actor_role="OPS",
        reason="created by operations",
    )
    return profile


@dataclass(frozen=True)
class ReviewDetail:
    profile: ProfessionalProfile
    category: ProfessionalCategory
    requirements: ListingRequirements
    case: VerificationCase | None
    checks: list[VerificationCheck]
    evidence: Evidence
    history: list[ListingHistory]
    unmet: list[str]
    base_point: tuple[float, float] | None


async def _point(session: AsyncSession, profile: ProfessionalProfile) -> tuple[float, float] | None:
    if profile.base_geom is None:
        return None
    row = (
        await session.execute(
            select(
                func.ST_Y(func.ST_GeomFromWKB(func.ST_AsBinary(ProfessionalProfile.base_geom))),
                func.ST_X(func.ST_GeomFromWKB(func.ST_AsBinary(ProfessionalProfile.base_geom))),
            ).where(ProfessionalProfile.id == profile.id)
        )
    ).one()
    return float(row[0]), float(row[1])


async def _latest_case(session: AsyncSession, category_id: uuid.UUID) -> VerificationCase | None:
    return (
        await session.scalars(
            select(VerificationCase)
            .where(VerificationCase.professional_category_id == category_id)
            .order_by(VerificationCase.opened_at.desc())
            .limit(1)
        )
    ).one_or_none()


def _effective(checks: list[VerificationCheck]) -> list[VerificationCheck]:
    """The latest result per (kind, subject): a correction replaces the earlier row."""
    latest: dict[tuple[str, str], VerificationCheck] = {}
    for check in sorted(checks, key=lambda c: c.recorded_at):
        latest[(check.kind, check.subject)] = check
    return list(latest.values())


async def review_detail(session: AsyncSession, category_id: uuid.UUID) -> ReviewDetail:
    """For operations routes only."""
    category = await session.get(ProfessionalCategory, category_id)
    if category is None:
        raise NotFound
    profile = await session.get_one(ProfessionalProfile, category.profile_id)
    requirements = (
        await listing_requirements(session, category.requirement_version_id)
        if category.requirement_version_id
        else await active_listing_requirements(session, category.category_code)
    )
    if requirements is None:
        raise RuntimeError(f"no listing requirements for {category.category_code}")
    case = await _latest_case(session, category.id)
    checks = (
        list(
            await session.scalars(
                select(VerificationCheck).where(VerificationCheck.case_id == case.id)
            )
        )
        if case
        else []
    )
    history = list(
        await session.scalars(
            select(ListingHistory)
            .where(ListingHistory.professional_category_id == category.id)
            .order_by(ListingHistory.at)
        )
    )
    effective = _effective(checks)
    return ReviewDetail(
        profile=profile,
        category=category,
        requirements=requirements,
        case=case,
        checks=sorted(checks, key=lambda c: c.recorded_at),
        evidence=await evidence_for(session, profile),
        history=history,
        unmet=unmet(
            requirements.requirements,
            [(CheckKind(c.kind), CheckOutcome(c.outcome)) for c in effective],
        ),
        base_point=await _point(session, profile),
    )


async def _open_case(session: AsyncSession, category: ProfessionalCategory) -> VerificationCase:
    case = (
        await session.scalars(
            select(VerificationCase)
            .where(
                VerificationCase.professional_category_id == category.id,
                VerificationCase.decided_at.is_(None),
            )
            .with_for_update()
        )
    ).one_or_none()
    if case is None or category.listing_state != L.PENDING_REVIEW.value:
        raise StateConflict(details={"current_state": category.listing_state, "case": "none open"})
    return case


async def record_check(
    session: AsyncSession,
    actor: Actor,
    category_id: uuid.UUID,
    *,
    kind: CheckKind,
    subject: str,
    outcome: CheckOutcome,
    detail: dict[str, str],
    note: str | None,
) -> VerificationCheck:
    category = await session.get(ProfessionalCategory, category_id, with_for_update=True)
    if category is None:
        raise NotFound
    case = await _open_case(session, category)
    requirements = await listing_requirements(session, case.requirement_version_id)
    accepted = {k for r in requirements.requirements.requirements for k in r.accepts}
    if kind not in accepted:
        raise ValidationFailed(
            details={"fields": {"kind": ["This category does not use this check."]}}
        )
    check = VerificationCheck(
        id=new_id(),
        case_id=case.id,
        kind=kind.value,
        subject=_text(subject, "subject", limit=80),
        outcome=outcome.value,
        detail={k: v.strip()[:300] for k, v in detail.items() if v.strip()},
        internal_note=_text(note, "note", required=False) or None,
        recorded_by=actor.user_id,
    )
    session.add(check)
    await session.flush()
    await record(
        session,
        action="verification_check.recorded",
        entity_type="professional_category",
        entity_id=category.id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        actor_role="OPS",
        session_id=actor.session_id,
        new_value={"kind": kind.value, "subject": check.subject, "outcome": outcome.value},
    )
    return check


async def decide(
    session: AsyncSession,
    actor: Actor,
    category_id: uuid.UUID,
    decision: VerificationDecision,
    *,
    message: str | None,
    note: str | None,
) -> ProfessionalCategory:
    """Approve (only when every requirement is met), request changes or reject (both with a
    message the professional sees). Closes the case; the caller resolves the queue item."""
    category = await session.get(ProfessionalCategory, category_id, with_for_update=True)
    if category is None:
        raise NotFound
    case = await _open_case(session, category)
    requirements = await listing_requirements(session, case.requirement_version_id)
    now = await _now(session)
    if decision == VerificationDecision.APPROVED:
        checks = _effective(
            list(
                await session.scalars(
                    select(VerificationCheck).where(VerificationCheck.case_id == case.id)
                )
            )
        )
        missing = unmet(
            requirements.requirements,
            [(CheckKind(c.kind), CheckOutcome(c.outcome)) for c in checks],
        )
        profile = await session.get_one(ProfessionalProfile, category.profile_id)
        if missing or missing_profile_fields(profile):
            raise StateConflict(
                message="Every requirement needs a recorded check before approval.",
                details={"unmet": missing, "profile": missing_profile_fields(profile)},
            )
        text_out = _text(message, "message", required=False) or None
        category.listed_at = now
        category.review_due_at = _months(now, requirements.validity_months)
        category.reapply_after = None
        trigger = "approve"
    else:
        text_out = _text(message, "message")
        trigger = (
            "request_changes" if decision == VerificationDecision.CHANGES_REQUESTED else "reject"
        )
        if decision == VerificationDecision.REJECTED:
            category.reapply_after = _months(now, requirements.reapply_months)
    category.message = text_out
    case.decision = decision.value
    case.decided_by = actor.user_id
    case.decided_at = now
    case.message_to_professional = text_out
    case.internal_note = _text(note, "note", required=False) or None
    await _move(
        session,
        category,
        trigger,
        actor_user_id=actor.user_id,
        role="OPS",
        reason=text_out,
        session_id=actor.session_id,
    )
    return category


async def suspend_or_reinstate(
    session: AsyncSession,
    actor: Actor,
    category_id: uuid.UUID,
    *,
    action: Literal["suspend", "reinstate"],
    reason: str,
    role: Literal["OPS", "ADMIN"],
) -> ProfessionalCategory:
    """D-10. Suspension keeps everything and only takes the listing out of public view."""
    category = await session.get(ProfessionalCategory, category_id, with_for_update=True)
    if category is None:
        raise NotFound
    target = L.SUSPENDED if action == "suspend" else L.LISTED
    if category.listing_state == target.value:
        return category  # repeat-safe
    await _move(
        session,
        category,
        action,
        actor_user_id=actor.user_id,
        role=role,
        reason=_text(reason, "reason"),
        session_id=actor.session_id,
    )
    return category


async def review_portfolio_item(
    session: AsyncSession, actor: Actor, item_id: uuid.UUID, *, approve: bool
) -> PortfolioItem:
    item = await session.get(PortfolioItem, item_id, with_for_update=True)
    if item is None or item.removed_at is not None:
        raise NotFound
    item.review_state = (
        PortfolioReviewState.APPROVED if approve else PortfolioReviewState.REJECTED
    ).value
    item.reviewed_by = actor.user_id
    item.reviewed_at = await _now(session)
    await session.flush()
    await record(
        session,
        action="portfolio_item.reviewed",
        entity_type="portfolio_item",
        entity_id=item.id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        actor_role="OPS",
        session_id=actor.session_id,
        new_value={"review_state": item.review_state},
    )
    return item


@dataclass(frozen=True)
class QueueRow:
    category_id: uuid.UUID
    profile_id: uuid.UUID
    display_name: str | None
    firm_name: str | None
    category_code: str
    listing_state: str
    submitted_at: datetime | None


async def queue_rows(
    session: AsyncSession, category_ids: list[uuid.UUID]
) -> dict[uuid.UUID, QueueRow]:
    if not category_ids:
        return {}
    rows = await session.execute(
        select(ProfessionalCategory, ProfessionalProfile)
        .join(ProfessionalProfile, ProfessionalProfile.id == ProfessionalCategory.profile_id)
        .where(ProfessionalCategory.id.in_(category_ids))
    )
    return {
        c.id: QueueRow(
            c.id,
            p.id,
            p.display_name,
            p.firm_name,
            c.category_code,
            c.listing_state,
            c.submitted_at,
        )
        for c, p in rows.all()
    }


async def categories_of_profile(
    session: AsyncSession, profile_id: uuid.UUID
) -> list[ProfessionalCategory]:
    return await _categories(session, profile_id)


# --- public directory --------------------------------------------------------------------------

PUBLIC = and_(
    ProfessionalCategory.listing_state == L.LISTED.value, ProfessionalCategory.hidden.is_(False)
)
PAGE_SIZE = 24


@dataclass(frozen=True)
class DirectoryFilters:
    category: str | None = None
    subtype: str | None = None
    q: str | None = None
    locality: str | None = None
    near: tuple[float, float] | None = None  # covers this point (latitude, longitude)


def _seed(cursor_seed: str | None, today: date) -> str:
    """D-08: a neutral daily shuffle. The seed is the day; a cursor keeps its day, so paging
    across midnight stays consistent."""
    return cursor_seed or today.isoformat()


def _shuffle_key(seed: str) -> Any:
    return func.md5(func.concat(cast(ProfessionalProfile.id, String), seed))


def _encode_cursor(seed: str, key: str, profile_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{seed}|{key}|{profile_id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, str, uuid.UUID]:
    try:
        seed, key, profile_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return seed, key, uuid.UUID(profile_id)
    except (ValueError, UnicodeDecodeError):
        raise ValidationFailed(details={"fields": {"cursor": ["Invalid cursor."]}}) from None


def _filtered(filters: DirectoryFilters) -> Select[Any]:
    listed = select(ProfessionalCategory.profile_id).where(PUBLIC)
    if filters.category:
        listed = listed.where(ProfessionalCategory.category_code == filters.category)
    if filters.subtype:
        listed = listed.where(ProfessionalCategory.subtypes.contains([filters.subtype]))
    query = select(ProfessionalProfile).where(ProfessionalProfile.id.in_(listed))
    if filters.q:
        pattern = f"%{filters.q.strip()}%"
        query = query.where(
            or_(
                ProfessionalProfile.display_name.ilike(pattern),
                ProfessionalProfile.firm_name.ilike(pattern),
            )
        )
    if filters.locality:
        query = query.where(
            ProfessionalProfile.base_locality.ilike(f"%{filters.locality.strip()}%")
        )
    if filters.near:
        lat, lng = filters.near
        point = func.ST_GeogFromText(f"SRID=4326;POINT({float(lng)} {float(lat)})")
        query = query.where(
            func.ST_DWithin(
                ProfessionalProfile.base_geom,
                point,
                # metres in integer: the column is smallint, which 1000 times would overflow
                cast(ProfessionalProfile.service_radius_km, Integer) * 1000,
            )
        )
    return query


@dataclass(frozen=True)
class DirectoryPage:
    profiles: list[ProfessionalProfile]
    categories: dict[uuid.UUID, list[ProfessionalCategory]]
    next_cursor: str | None


async def public_categories(
    session: AsyncSession, profile_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[ProfessionalCategory]]:
    if not profile_ids:
        return {}
    rows = await session.scalars(
        select(ProfessionalCategory)
        .where(ProfessionalCategory.profile_id.in_(profile_ids), PUBLIC)
        .order_by(ProfessionalCategory.category_code)
    )
    grouped: dict[uuid.UUID, list[ProfessionalCategory]] = {}
    for row in rows:
        grouped.setdefault(row.profile_id, []).append(row)
    return grouped


async def directory(
    session: AsyncSession, filters: DirectoryFilters, cursor: str | None, *, limit: int = PAGE_SIZE
) -> DirectoryPage:
    today = (await _now(session)).date()
    seed, after = (None, None)
    if cursor:
        seed, key, profile_id = _decode_cursor(cursor)
        after = (key, profile_id)
    seed = _seed(seed, today)
    key = _shuffle_key(seed)
    query = _filtered(filters).add_columns(key.label("shuffle"))
    if after:
        query = query.where(
            or_(key > after[0], and_(key == after[0], ProfessionalProfile.id > after[1]))
        )
    rows = (
        await session.execute(query.order_by(key, ProfessionalProfile.id).limit(limit + 1))
    ).all()
    page = rows[:limit]
    profiles = [row[0] for row in page]
    next_cursor = (
        _encode_cursor(seed, page[-1][1], page[-1][0].id) if len(rows) > limit and page else None
    )
    return DirectoryPage(
        profiles, await public_categories(session, [p.id for p in profiles]), next_cursor
    )


@dataclass(frozen=True)
class PublicProfile:
    profile: ProfessionalProfile
    categories: list[ProfessionalCategory]
    verified: dict[uuid.UUID, list[str]]  # category id -> check kinds passed at approval
    registrations: dict[uuid.UUID, list[dict[str, str]]]  # category id -> issuer and number
    portfolio: list[PortfolioItem]


async def public_profile(session: AsyncSession, profile_id: uuid.UUID) -> PublicProfile:
    profile = await session.get(ProfessionalProfile, profile_id)
    categories = (await public_categories(session, [profile_id])).get(profile_id, [])
    if profile is None or not categories:
        raise NotFound
    verified: dict[uuid.UUID, list[str]] = {}
    registrations: dict[uuid.UUID, list[dict[str, str]]] = {}
    documents = list(
        await session.scalars(
            select(ProfessionalDocument).where(
                ProfessionalDocument.profile_id == profile_id,
                ProfessionalDocument.kind == ProfessionalDocumentKind.REGISTRATION.value,
                ProfessionalDocument.removed_at.is_(None),
            )
        )
    )
    for category in categories:
        case = (
            await session.scalars(
                select(VerificationCase)
                .where(
                    VerificationCase.professional_category_id == category.id,
                    VerificationCase.decision == VerificationDecision.APPROVED.value,
                )
                .order_by(VerificationCase.decided_at.desc())
                .limit(1)
            )
        ).one_or_none()
        if case is None:
            continue
        passed = sorted(
            {
                c.kind
                for c in _effective(
                    list(
                        await session.scalars(
                            select(VerificationCheck).where(VerificationCheck.case_id == case.id)
                        )
                    )
                )
                if c.outcome == CheckOutcome.PASSED.value
            }
        )
        verified[category.id] = passed
        if CheckKind.REGISTRATION.value in passed:
            registrations[category.id] = [
                {k: v for k, v in d.details.items() if k in ("issuer", "number")}
                for d in documents
                if d.category_code in (None, category.category_code)
                and (d.details.get("issuer") or d.details.get("number"))
            ]
    portfolio = list(
        await session.scalars(
            select(PortfolioItem)
            .where(
                PortfolioItem.profile_id == profile_id,
                PortfolioItem.removed_at.is_(None),
                PortfolioItem.review_state == PortfolioReviewState.APPROVED.value,
            )
            .order_by(PortfolioItem.created_at)
        )
    )
    return PublicProfile(profile, categories, verified, registrations, portfolio)


async def cover_images(
    session: AsyncSession, profile_ids: list[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    """Each profile's first approved portfolio image, for directory cards."""
    if not profile_ids:
        return {}
    rows = await session.execute(
        select(PortfolioItem.profile_id, PortfolioItem.file_id)
        .where(
            PortfolioItem.profile_id.in_(profile_ids),
            PortfolioItem.removed_at.is_(None),
            PortfolioItem.review_state == PortfolioReviewState.APPROVED.value,
        )
        .order_by(PortfolioItem.profile_id, PortfolioItem.created_at)
        .ext(distinct_on(PortfolioItem.profile_id))
    )
    return {profile_id: file_id for profile_id, file_id in rows.all()}


async def categories_in_states(
    session: AsyncSession, states: list[ListingState], *, limit: int = 100
) -> list[QueueRow]:
    """Operations' list of categories by state (listed, suspended, rejected), newest first."""
    rows = await session.execute(
        select(ProfessionalCategory, ProfessionalProfile)
        .join(ProfessionalProfile, ProfessionalProfile.id == ProfessionalCategory.profile_id)
        .where(ProfessionalCategory.listing_state.in_([s.value for s in states]))
        .order_by(ProfessionalCategory.updated_at.desc())
        .limit(limit)
    )
    return [
        QueueRow(
            c.id,
            p.id,
            p.display_name,
            p.firm_name,
            c.category_code,
            c.listing_state,
            c.submitted_at,
        )
        for c, p in rows.all()
    ]


# --- connections (Slice 3.4) ---------------------------------------------------------------------


@dataclass(frozen=True)
class ConnectionCandidate:
    """A professional as the engagements module sees them for one category and one project."""

    profile_id: uuid.UUID
    user_id: uuid.UUID
    display_name: str | None
    firm_name: str | None
    listed: bool  # LISTED in the category (a hidden listing is still listed)
    hidden: bool  # hidden from the public directory by the professional
    covers: bool  # the service radius covers the plot (N-04)


async def connection_candidate(
    session: AsyncSession, profile_id: uuid.UUID, category_code: str, point: tuple[float, float]
) -> ConnectionCandidate | None:
    lat, lng = point
    plot = func.ST_GeogFromText(f"SRID=4326;POINT({float(lng)} {float(lat)})")
    row = (
        await session.execute(
            select(
                ProfessionalProfile,
                ProfessionalCategory.listing_state,
                ProfessionalCategory.hidden,
                func.coalesce(
                    func.ST_DWithin(
                        ProfessionalProfile.base_geom,
                        plot,
                        cast(ProfessionalProfile.service_radius_km, Integer) * 1000,
                    ),
                    False,
                ),
            )
            .outerjoin(
                ProfessionalCategory,
                and_(
                    ProfessionalCategory.profile_id == ProfessionalProfile.id,
                    ProfessionalCategory.category_code == category_code,
                ),
            )
            .where(ProfessionalProfile.id == profile_id)
        )
    ).one_or_none()
    if row is None:
        return None
    profile, state, hidden, covers = row
    return ConnectionCandidate(
        profile.id, profile.user_id, profile.display_name, profile.firm_name,
        listed=state == L.LISTED.value, hidden=hidden is not False, covers=bool(covers),
    )  # fmt: skip


async def profile_by_user(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    profile_id: uuid.UUID | None = await session.scalar(
        select(ProfessionalProfile.id).where(ProfessionalProfile.user_id == user_id)
    )
    return profile_id


async def profile_names(
    session: AsyncSession, profile_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[uuid.UUID, str | None, str | None]]:
    """Owner user, display name and firm per profile."""
    if not profile_ids:
        return {}
    rows = await session.execute(
        select(
            ProfessionalProfile.id,
            ProfessionalProfile.user_id,
            ProfessionalProfile.display_name,
            ProfessionalProfile.firm_name,
        ).where(ProfessionalProfile.id.in_(profile_ids))
    )
    return {r[0]: (r[1], r[2], r[3]) for r in rows.all()}


async def category_of_listing(
    session: AsyncSession, professional_category_id: uuid.UUID
) -> tuple[uuid.UUID, str] | None:
    """The profile and category code of a professional's category row."""
    row = (
        await session.execute(
            select(ProfessionalCategory.profile_id, ProfessionalCategory.category_code).where(
                ProfessionalCategory.id == professional_category_id
            )
        )
    ).one_or_none()
    return (row[0], row[1]) if row else None


@dataclass(frozen=True)
class Credential:
    """A listed professional's verified registration for one category (Slice 3.5, BP-04)."""

    profile_id: uuid.UUID
    display_name: str | None
    firm_name: str | None
    category_code: str
    listed: bool
    check_id: uuid.UUID
    case_id: uuid.UUID
    subject: str
    detail: dict[str, Any]
    recorded_at: datetime


async def registration_credential(
    session: AsyncSession, profile_id: uuid.UUID, category_code: str
) -> Credential | None:
    """The latest PASSED REGISTRATION check of the latest APPROVED case of the category, or
    None when the registration was never verified."""
    row = (
        await session.execute(
            select(ProfessionalProfile, ProfessionalCategory, VerificationCheck)
            .join(ProfessionalCategory, ProfessionalCategory.profile_id == ProfessionalProfile.id)
            .join(
                VerificationCase,
                VerificationCase.professional_category_id == ProfessionalCategory.id,
            )
            .join(VerificationCheck, VerificationCheck.case_id == VerificationCase.id)
            .where(
                ProfessionalProfile.id == profile_id,
                ProfessionalCategory.category_code == category_code,
                VerificationCase.decision == VerificationDecision.APPROVED.value,
                VerificationCheck.kind == CheckKind.REGISTRATION.value,
                VerificationCheck.outcome == CheckOutcome.PASSED.value,
            )
            .order_by(VerificationCase.decided_at.desc(), VerificationCheck.recorded_at.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return None
    profile, category, check = row
    return Credential(
        profile.id, profile.display_name, profile.firm_name, category_code,
        category.listing_state == L.LISTED.value, check.id, check.case_id, check.subject,
        dict(check.detail or {}), check.recorded_at,
    )  # fmt: skip
