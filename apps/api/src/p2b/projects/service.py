"""Projects, requirements and enquiries (DOMAIN_ARCHITECTURE 3.3; STATE_MODEL 5; API sections 3, 4;
REQUIREMENT_QUESTIONS_V1 section L). Slice 1 moves a project only from DRAFT to SUBMITTED; review
and acceptance belong to slice 2."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.catalog.interface import (
    active_city,
    active_question_set,
    question_set,
    review_flags,
    validate_answers,
)
from p2b.core.errors import NotFound, StateConflict, ValidationFailed, VersionConflict
from p2b.core.geocoding import Geocoder, GeocoderUnavailable
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import (
    ActorType,
    ComingSoonWork,
    EnquiryKind,
    MembershipRole,
    PackageAvailability,
    ProjectStatus,
    ProjectType,
)
from p2b.identity.interface import Actor
from p2b.projects.estimates import record_estimate
from p2b.projects.models import (
    Enquiry,
    GeocodeCache,
    Project,
    ProjectMembership,
    ProjectRequirement,
    ProjectStatusHistory,
)

P = ProjectStatus
# STATE_MODEL section 5, the part slices 1 and 2 implement. Operations decline with the existing
# CANCELLED state (ruling 2.1); nothing leaves CANCELLED, because no reactivation flow is defined.
PROJECT = TransitionTable[ProjectStatus](
    "project",
    [
        Transition(None, P.DRAFT, "create"),
        Transition(P.DRAFT, P.SUBMITTED, "submit"),
        Transition(P.SUBMITTED, P.ACCEPTED, "accept"),
        Transition(P.SUBMITTED, P.NEEDS_INFO, "ask"),
        Transition(P.NEEDS_INFO, P.SUBMITTED, "resubmit"),
        Transition(P.SUBMITTED, P.CANCELLED, "cancel"),
        Transition(P.NEEDS_INFO, P.CANCELLED, "cancel"),
    ],
)
# The family may change the requirement while drafting and when operations ask for more (2.7).
EDITABLE = frozenset({P.DRAFT.value, P.NEEDS_INFO.value})
# Statuses in which the workspace exists (created on ACCEPTED, STATE_MODEL 5).
WITH_WORKSPACE = frozenset(
    status.value for status in (P.ACCEPTED, P.PLANNING, P.PLAN_ISSUED, P.SOURCING, P.CONTRACTED,
                      P.BUILDING, P.HANDOVER_PENDING, P.COMPLETED, P.ARCHIVED, P.ON_HOLD)
)  # fmt: skip

FLOORS_FROM_ANSWER = {"G": 1, "G_PLUS_1": 2, "G_PLUS_2": 3, "G_PLUS_3": 4}

# Whether the Plan2Build package can be offered (PD-21). The review runs in the background and
# never blocks the free dashboard; ACCEPTED means only that the project passed the initial
# eligibility review. Statuses after ACCEPTED belong to later slices and stay eligible.
PACKAGE_AVAILABILITY = {
    P.DRAFT: PackageAvailability.NOT_SUBMITTED,
    P.SUBMITTED: PackageAvailability.UNDER_REVIEW,
    P.NEEDS_INFO: PackageAvailability.UNDER_REVIEW,
    P.CANCELLED: PackageAvailability.NOT_ELIGIBLE,
    **{status: PackageAvailability.ELIGIBLE for status in (
        P.ACCEPTED, P.PLANNING, P.PLAN_ISSUED, P.SOURCING, P.CONTRACTED, P.BUILDING,
        P.HANDOVER_PENDING, P.COMPLETED, P.ARCHIVED, P.ON_HOLD)},
}  # fmt: skip


def package_availability(project: Project) -> PackageAvailability:
    return PACKAGE_AVAILABILITY[ProjectStatus(project.status)]


class ProjectCreated(EventPayload):
    project_id: uuid.UUID
    owner_user_id: uuid.UUID


class RequirementSubmitted(EventPayload):
    project_id: uuid.UUID
    question_set_version: int
    review_flags: list[str]


class ReviewDecided(EventPayload):
    """`project.accepted`, `project.needs_info`, `project.cancelled`. `message` is the text the
    family sees (the request or the reason); it is never an internal note."""

    project_id: uuid.UUID
    owner_user_id: uuid.UUID
    message: str | None


class EnquiryCreated(EventPayload):
    enquiry_id: uuid.UUID
    kind: EnquiryKind


@dataclass(frozen=True)
class Membership:
    project_id: uuid.UUID
    role: MembershipRole
    project_status: ProjectStatus


async def member_role(
    session: AsyncSession, *, user_id: uuid.UUID, project_id: uuid.UUID
) -> Membership | None:
    """The authorisation primitive other modules call (DOMAIN_ARCHITECTURE 3.3,
    `assert_membership`): the caller's active role on the project, or None."""
    row = (
        await session.execute(
            select(ProjectMembership.role, Project.status)
            .join(Project, Project.id == ProjectMembership.project_id)
            .where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.user_id == user_id,
                ProjectMembership.revoked_at.is_(None),
            )
        )
    ).first()
    if row is None:
        return None
    return Membership(project_id, MembershipRole(row[0]), ProjectStatus(row[1]))


@dataclass(frozen=True)
class DesignBasis:
    """What the designs module may read about a project: the member's role, the status and the
    requirement answers as submitted (the caller sanitises them before any provider sees them)."""

    project_id: uuid.UUID
    role: MembershipRole
    status: ProjectStatus
    question_set_version: int
    requirement_version: int
    answers: dict[str, Any]


async def design_basis(
    session: AsyncSession, *, user_id: uuid.UUID, project_id: uuid.UUID
) -> DesignBasis | None:
    """None when the user is not a member of the project (callers answer 404)."""
    membership = await member_role(session, user_id=user_id, project_id=project_id)
    if membership is None:
        return None
    requirement = await _requirement(session, project_id)
    return DesignBasis(
        project_id=project_id,
        role=membership.role,
        status=membership.project_status,
        question_set_version=requirement.question_set_version,
        requirement_version=requirement.version,
        answers=dict(requirement.answers),
    )


@dataclass(frozen=True)
class BillingFacts:
    """What billing may read about a project (Slice 3.3): ownership, whether the package can be
    offered, and the allow-listed characteristics a pricing rule may use. Nothing personal."""

    project_id: uuid.UUID
    code: str
    owner_user_id: uuid.UUID
    status: ProjectStatus
    availability: PackageAvailability
    characteristics: dict[str, Any]


@dataclass(frozen=True)
class ConnectionFacts:
    """What the engagements module may read about a project (Slice 3.4): ownership and status,
    the requirement's services answer, the brief a professional sees before acceptance (no
    identity, locality only), and the plot pin, which is revealed only after acceptance (N-08)."""

    project_id: uuid.UUID
    code: str
    owner_user_id: uuid.UUID
    status: ProjectStatus
    availability: PackageAvailability
    question_set_version: int
    services: list[str]
    has_contractor: bool | None
    locality: str | None
    point: tuple[float, float] | None  # latitude, longitude
    brief: dict[str, Any]


async def connection_facts(session: AsyncSession, project_id: uuid.UUID) -> ConnectionFacts | None:
    project = await session.get(Project, project_id)
    if project is None:
        return None
    requirement = await _requirement(session, project_id)
    answers = requirement.answers
    point = (
        await session.execute(
            select(
                func.ST_Y(func.ST_GeomFromWKB(func.ST_AsBinary(Project.plot_geom))),
                func.ST_X(func.ST_GeomFromWKB(func.ST_AsBinary(Project.plot_geom))),
            ).where(Project.id == project_id, Project.plot_geom.is_not(None))
        )
    ).one_or_none()
    services = [str(v) for v in answers.get("services_needed") or []]
    return ConnectionFacts(
        project_id=project.id,
        code=project.code,
        owner_user_id=project.owner_user_id,
        status=ProjectStatus(project.status),
        availability=package_availability(project),
        question_set_version=requirement.question_set_version,
        services=services,
        has_contractor=answers.get("has_contractor"),
        locality=project.locality,
        point=(float(point[0]), float(point[1])) if point else None,
        brief={
            "locality": project.locality,
            "plot_area_sqft": str(project.plot_area_sqft) if project.plot_area_sqft else None,
            "built_up_area_sqft": project.built_up_area_sqft,
            "floors": project.floors,
            "basement": project.has_basement,
            "budget_band": project.budget_band,
            "start_window": project.start_window,
            "services": services,
        },
    )


@dataclass(frozen=True)
class BuildPlanFacts:
    """What the buildplan module may read about a project (Slice 3.5): identity, ownership,
    status and the requirement version a Build Plan version is prepared from."""

    project_id: uuid.UUID
    code: str
    locality: str | None
    owner_user_id: uuid.UUID
    status: ProjectStatus
    availability: PackageAvailability
    requirement_version: int
    floors: int | None
    has_basement: bool | None
    built_up_area_sqft: int | None


async def build_plan_facts(session: AsyncSession, project_id: uuid.UUID) -> BuildPlanFacts | None:
    project = await session.get(Project, project_id)
    if project is None:
        return None
    requirement = await _requirement(session, project_id)
    return BuildPlanFacts(
        project_id=project.id,
        code=project.code,
        locality=project.locality,
        owner_user_id=project.owner_user_id,
        status=ProjectStatus(project.status),
        availability=package_availability(project),
        requirement_version=requirement.version,
        floors=project.floors,
        has_basement=project.has_basement,
        built_up_area_sqft=project.built_up_area_sqft,
    )


async def billing_facts(session: AsyncSession, project_id: uuid.UUID) -> BillingFacts | None:
    project = await session.get(Project, project_id)
    if project is None:
        return None
    requirement = await _requirement(session, project_id)
    return BillingFacts(
        project_id=project.id,
        code=project.code,
        owner_user_id=project.owner_user_id,
        status=ProjectStatus(project.status),
        availability=package_availability(project),
        characteristics={
            "built_up_area_sqft": project.built_up_area_sqft,
            "floors": project.floors,
            "basement": project.has_basement,
            "quality_tier": project.quality_tier,
            "property_type": requirement.answers.get("property_type"),
        },
    )


async def project_point(
    session: AsyncSession, *, user_id: uuid.UUID, project_id: uuid.UUID
) -> tuple[float, float] | None:
    """The submitted plot location (latitude, longitude) of a project the user belongs to, for
    project-aware professional filters; None when not a member or not yet submitted."""
    if await member_role(session, user_id=user_id, project_id=project_id) is None:
        return None
    row = (
        await session.execute(
            select(
                func.ST_Y(func.ST_GeomFromWKB(func.ST_AsBinary(Project.plot_geom))),
                func.ST_X(func.ST_GeomFromWKB(func.ST_AsBinary(Project.plot_geom))),
            ).where(Project.id == project_id, Project.plot_geom.is_not(None))
        )
    ).first()
    return (float(row[0]), float(row[1])) if row else None


async def question_set_version_of(session: AsyncSession, project_id: uuid.UUID) -> int:
    """The question set the project's requirement is answered against."""
    version = await session.scalar(
        select(ProjectRequirement.question_set_version).where(
            ProjectRequirement.project_id == project_id
        )
    )
    if version is None:
        raise NotFound
    return int(version)


async def _member_project(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, *, for_update: bool = False
) -> tuple[Project, str]:
    """The project and the actor's role. 404 when the actor is not a member: a family never learns
    that another family's project exists (SECURITY 4.2, BR-013)."""
    query = (
        select(Project, ProjectMembership.role)
        .join(ProjectMembership, ProjectMembership.project_id == Project.id)
        .where(
            Project.id == project_id,
            ProjectMembership.user_id == actor.user_id,
            ProjectMembership.revoked_at.is_(None),
        )
    )
    if for_update:
        query = query.with_for_update(of=Project)
    row = (await session.execute(query)).first()
    if row is None:
        raise NotFound
    return row[0], row[1]


async def _requirement(session: AsyncSession, project_id: uuid.UUID) -> ProjectRequirement:
    return (
        await session.scalars(
            select(ProjectRequirement).where(ProjectRequirement.project_id == project_id)
        )
    ).one()


async def _record_status(
    session: AsyncSession,
    project: Project,
    old: ProjectStatus | None,
    actor: Actor,
    *,
    role: str = MembershipRole.OWNER.value,
    reason: str | None = None,
) -> None:
    """One history row and one audit row per transition (STATE_MODEL 1 rule 3)."""
    session.add(
        ProjectStatusHistory(
            id=new_id(), project_id=project.id, from_status=old.value if old else None,
            to_status=project.status, actor_user_id=actor.user_id, reason=reason,
        )
    )  # fmt: skip
    await record(
        session,
        action="project.status_changed",
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        actor_role=role,
        session_id=actor.session_id,
        old_value={"status": old.value} if old else None,
        new_value={"status": project.status},
        reason=reason,
    )


async def create_project(
    session: AsyncSession, actor: Actor, *, city_name: str, project_type: ProjectType
) -> Project:
    city = await active_city(session, city_name)
    if city is None:
        raise ValidationFailed(
            details={"fields": {"city": ["Plan2Build is not in this city yet."]}}
        )
    number = (await session.execute(text("SELECT nextval('project_code_seq')"))).scalar_one()
    status = PROJECT.target(None, "create")
    project = Project(
        id=new_id(),
        code=f"P2B-{city.code}-{number:05d}",
        owner_user_id=actor.user_id,
        status=status.value,
        project_type=project_type.value,
        city_code=city.code,
    )
    session.add(project)
    await session.flush()
    questions = await active_question_set(session)
    session.add(
        ProjectRequirement(
            id=new_id(), project_id=project.id, question_set_version=questions.version
        )
    )
    session.add(
        ProjectMembership(
            id=new_id(), project_id=project.id, user_id=actor.user_id,
            role=MembershipRole.OWNER.value, granted_by=actor.user_id,
        )
    )  # fmt: skip
    await session.flush()
    await _record_status(session, project, None, actor)
    await publish(
        session,
        event_type="project.created",
        aggregate_type="project",
        aggregate_id=project.id,
        payload=ProjectCreated(project_id=project.id, owner_user_id=actor.user_id),
        dedupe_suffix="created",
    )
    return project


async def list_projects(session: AsyncSession, actor: Actor) -> list[Project]:
    return list(
        await session.scalars(
            select(Project)
            .join(ProjectMembership, ProjectMembership.project_id == Project.id)
            .where(
                ProjectMembership.user_id == actor.user_id, ProjectMembership.revoked_at.is_(None)
            )
            .order_by(Project.created_at.desc(), Project.id.desc())
            .limit(100)
        )
    )


async def get_project(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID
) -> tuple[Project, ProjectRequirement]:
    project, _ = await _member_project(session, actor, project_id)
    return project, await _requirement(session, project.id)


async def save_requirement(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    *,
    answers: dict[str, Any],
    version: int,
) -> ProjectRequirement:
    """Save the answers (any number of times while DRAFT, and again after operations ask for more
    information, ruling 2.7). Each given answer must be well formed; completeness is checked only
    at submission."""
    project, role = await _member_project(session, actor, project_id, for_update=True)
    if role != MembershipRole.OWNER.value:
        raise NotFound
    if project.status not in EDITABLE:
        raise StateConflict(details={"current_state": project.status})
    requirement = await _requirement(session, project.id)
    if requirement.version != version:
        raise VersionConflict(details={"current_version": requirement.version})
    definition = await question_set(session, requirement.question_set_version)
    cleaned, errors = validate_answers(definition, answers, complete=False)
    if errors:
        raise ValidationFailed(details={"fields": errors})
    requirement.answers = cleaned
    requirement.version += 1
    await session.flush()
    return requirement


def _plot_area(answers: dict[str, Any]) -> Decimal:
    if answers["plot_is_rectangular"]:
        return Decimal(str(answers["plot_width_ft"])) * Decimal(str(answers["plot_depth_ft"]))
    return Decimal(str(answers["plot_area_sqft"]))


async def submit_requirement(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    *,
    version: int,
    allow_demo_rates: bool,
) -> tuple[Project, ProjectRequirement]:
    """DRAFT -> SUBMITTED, or NEEDS_INFO -> SUBMITTED after a request for information (2.7).
    Every submission goes to Plan2Build's review, which runs in the background (PD-21); review
    flags travel with it (REQUIREMENT_QUESTIONS_V1 L.4). Budget never rejects anyone. The
    indicative estimate is stored with the submission."""
    project, role = await _member_project(session, actor, project_id, for_update=True)
    if role != MembershipRole.OWNER.value:
        raise NotFound
    current = ProjectStatus(project.status)
    target = PROJECT.target(current, "resubmit" if current == P.NEEDS_INFO else "submit")
    requirement = await _requirement(session, project.id)
    if requirement.version != version:
        raise VersionConflict(details={"current_version": requirement.version})
    definition = await question_set(session, requirement.question_set_version)
    answers, errors = validate_answers(definition, requirement.answers, complete=True)
    if errors:
        raise ValidationFailed(details={"fields": errors})

    flags = review_flags(definition, answers)
    now = (await session.execute(select(func.now()))).scalar_one()
    requirement.answers = answers
    requirement.review_flags = flags
    requirement.submitted_at = now
    requirement.version += 1

    location = answers["location"]
    built_up = answers["built_up_area_sqft"]
    project.locality = answers["locality"]
    project.plot_geom = WKTElement(f"POINT({location['lng']} {location['lat']})", srid=4326)
    project.plot_area_sqft = _plot_area(answers)
    project.built_up_area_sqft = None if built_up == "NOT_SURE" else int(built_up)
    project.floors = FLOORS_FROM_ANSWER[answers["floors"]]
    project.has_basement = answers["basement"]
    project.quality_tier = answers["quality_tier"]
    project.budget_band = answers["budget_band"]
    project.start_window = answers["start_timeline"]
    project.submitted_at = now
    project.status = target.value
    project.version += 1
    await session.flush()
    await _record_status(session, project, current, actor)
    await record_estimate(
        session, project, requirement_version=requirement.version, allow_demo=allow_demo_rates
    )
    await publish(
        session,
        event_type="requirement.submitted",
        aggregate_type="project",
        aggregate_id=project.id,
        payload=RequirementSubmitted(
            project_id=project.id, question_set_version=definition.version, review_flags=flags
        ),
        # One event per submission: a resubmission is a new review (2.7).
        dedupe_suffix=f"submitted:{requirement.version}",
    )
    return project, requirement


async def create_enquiry(
    session: AsyncSession,
    *,
    kind: EnquiryKind,
    email: str,
    work_type: ComingSoonWork | None,
    ip_hash: str,
) -> uuid.UUID:
    """The two capture paths. Recorded for operations; no Phase-2 workflow (R-1, R-2)."""
    if (kind == EnquiryKind.COMING_SOON_HELP) != (work_type is not None):
        raise ValidationFailed(
            details={"fields": {"work_type": ["Choose the type of work for this request."]}}
        )
    enquiry_id = new_id()
    session.add(
        Enquiry(
            id=enquiry_id, kind=kind.value, work_type=work_type.value if work_type else None,
            email=email.strip().lower(), ip_hash=ip_hash,
        )
    )  # fmt: skip
    await session.flush()
    await publish(
        session,
        event_type="enquiry.created",
        aggregate_type="enquiry",
        aggregate_id=enquiry_id,
        payload=EnquiryCreated(enquiry_id=enquiry_id, kind=kind),
        dedupe_suffix="created",
    )
    return enquiry_id


def _cache_key(lat: float, lng: float) -> str:
    # Four decimals is about 11 m: close enough for a neighbourhood name, coarse enough to reuse.
    return f"rev:{lat:.4f},{lng:.4f}"


async def suggest_locality(
    session: AsyncSession, geocoder: Geocoder, *, lat: float, lng: float
) -> str | None:
    """A locality name for the pin, from the cache or the geocoder. None when unknown or the
    provider is down: the family then types it (R-3 lets the family correct the value)."""
    key = _cache_key(lat, lng)
    cached = await session.get(GeocodeCache, key)
    if cached is not None:
        return cached.locality
    try:
        place = await geocoder.reverse(lat, lng)
    except GeocoderUnavailable:
        return None
    if geocoder.name != "none":  # only real answers are cached
        await session.execute(
            insert(GeocodeCache)
            .values(
                query_normalised=key, provider=geocoder.name, locality=place.locality,
                city=place.city, result=place.raw,
            )
            .on_conflict_do_nothing()
        )  # fmt: skip
    return place.locality


@dataclass(frozen=True)
class ReviewSnapshot:
    """A project as operations reviews it (API 18: read-only composite). Review flags are
    included here and nowhere on the homeowner side."""

    project_id: uuid.UUID
    code: str
    status: ProjectStatus
    city_code: str
    locality: str | None
    owner_user_id: uuid.UUID
    created_at: datetime
    submitted_at: datetime | None
    question_set_version: int
    answers: dict[str, Any]
    review_flags: list[str]


async def review_snapshots(
    session: AsyncSession, project_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ReviewSnapshot]:
    """For staff routes only: the caller must already hold an operations role. No membership
    check, because operations read every project (API 18)."""
    if not project_ids:
        return {}
    rows = await session.execute(
        select(Project, ProjectRequirement)
        .join(ProjectRequirement, ProjectRequirement.project_id == Project.id)
        .where(Project.id.in_(project_ids))
    )
    return {
        project.id: ReviewSnapshot(
            project_id=project.id,
            code=project.code,
            status=ProjectStatus(project.status),
            city_code=project.city_code,
            locality=project.locality,
            owner_user_id=project.owner_user_id,
            created_at=project.created_at,
            submitted_at=project.submitted_at,
            question_set_version=requirement.question_set_version,
            answers=requirement.answers,
            review_flags=list(requirement.review_flags),
        )
        for project, requirement in rows.all()
    }


async def submitted_project_ids(session: AsyncSession) -> list[uuid.UUID]:
    """Projects waiting for review, oldest submission first (queue backfill and checks)."""
    return list(
        await session.scalars(
            select(Project.id)
            .where(Project.status == ProjectStatus.SUBMITTED.value)
            .order_by(Project.submitted_at, Project.id)
        )
    )


@dataclass(frozen=True)
class EnquirySummary:
    kind: EnquiryKind
    work_type: ComingSoonWork | None
    email: str


async def enquiry_summary(session: AsyncSession, enquiry_id: uuid.UUID) -> EnquirySummary | None:
    """For notifications to operations only (internal mailbox)."""
    enquiry = await session.get(Enquiry, enquiry_id)
    if enquiry is None:
        return None
    return EnquirySummary(
        kind=EnquiryKind(enquiry.kind),
        work_type=ComingSoonWork(enquiry.work_type) if enquiry.work_type else None,
        email=enquiry.email,
    )
