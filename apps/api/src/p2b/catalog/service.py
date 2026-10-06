"""Rate card selection and estimates (S05 F2; API_ARCHITECTURE section 3)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.catalog.estimator import Estimate, EstimateInputs, RatesV1, compute_estimate
from p2b.catalog.listing import RequirementSet
from p2b.catalog.models import (
    City,
    ListingRequirementVersion,
    RateCard,
    RequirementQuestionSet,
    ServiceCategory,
    ServiceValueCategory,
    SpecGroup,
    SpecLineMaster,
    SpecLineMasterVersion,
    StageMaster,
    StageMasterVersion,
)
from p2b.catalog.questions import QuestionSetDefinition
from p2b.core.errors import ValidationFailed
from p2b.core.vocabulary import ConfigStatus, EngineerSignoff

SUPPORTED_SCHEMA_VERSIONS = {1}


async def active_rate_card(
    session: AsyncSession, *, city: str, allow_demo: bool
) -> RateCard | None:
    """The newest card for the city already in force. Demo cards are skipped when not allowed
    (production), so prototype values can never reach a real homeowner there."""
    query = (
        select(RateCard)
        .where(
            func.lower(RateCard.city) == city.strip().lower(),
            RateCard.valid_from <= func.now(),
        )
        .order_by(RateCard.version.desc())
        .limit(1)
    )
    if not allow_demo:
        query = query.where(RateCard.is_demo.is_(False))
    return (await session.scalars(query)).one_or_none()


async def active_question_set(session: AsyncSession) -> QuestionSetDefinition:
    row = (
        await session.scalars(
            select(RequirementQuestionSet).where(
                RequirementQuestionSet.status == ConfigStatus.ACTIVE.value
            )
        )
    ).one()
    return QuestionSetDefinition.model_validate(row.definition)


async def question_set(session: AsyncSession, version: int) -> QuestionSetDefinition:
    row = await session.get_one(RequirementQuestionSet, version)
    return QuestionSetDefinition.model_validate(row.definition)


async def active_stage_names(session: AsyncSession) -> dict[int, str]:
    """Stage names by number from the active stage configuration (S04 section 4)."""
    rows = await session.execute(
        select(StageMaster.number, StageMaster.name)
        .join(StageMasterVersion, StageMasterVersion.version == StageMaster.version)
        .where(StageMasterVersion.status == ConfigStatus.ACTIVE.value)
    )
    return {number: name for number, name in rows.all()}


async def city_name(session: AsyncSession, code: str) -> str | None:
    return (await session.scalars(select(City.name).where(City.code == code))).one_or_none()


@dataclass(frozen=True)
class RateCardRef:
    id: uuid.UUID
    city: str
    version: int
    is_demo: bool
    label: str


async def estimate_for_city(
    session: AsyncSession, *, city: str, inputs: EstimateInputs, allow_demo: bool
) -> tuple[RateCardRef, Estimate] | None:
    """The estimate from the card in force for the city, or None when there is none (production
    until a real card is published, D-16). The public estimator turns None into a 422."""
    card = await active_rate_card(session, city=city, allow_demo=allow_demo)
    if card is None:
        return None
    if card.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise RuntimeError(f"rate card schema {card.schema_version} has no engine")
    ref = RateCardRef(card.id, card.city, card.version, card.is_demo, card.label)
    return ref, compute_estimate(inputs, RatesV1.model_validate(card.rates))


async def estimate(
    session: AsyncSession, *, city: str, inputs: EstimateInputs, allow_demo: bool
) -> tuple[RateCardRef, Estimate]:
    found = await estimate_for_city(session, city=city, inputs=inputs, allow_demo=allow_demo)
    if found is None:
        raise ValidationFailed(
            details={"fields": {"city": ["No estimate is available for this city."]}}
        )
    return found


async def active_city(session: AsyncSession, name: str) -> City | None:
    return (
        await session.scalars(
            select(City).where(func.lower(City.name) == name.strip().lower(), City.is_active)
        )
    ).one_or_none()


@dataclass(frozen=True)
class StageMasterRow:
    id: uuid.UUID
    number: int
    code: str
    name: str
    sequence: int
    is_audit_gate: bool
    is_payment_milestone: bool
    repeats_per_floor: bool
    default_duration_days: int | None


async def active_stage_masters(session: AsyncSession) -> list[StageMasterRow]:
    """The 16 stages of the active stage configuration, in sequence (S04 section 4)."""
    rows = await session.scalars(
        select(StageMaster)
        .join(StageMasterVersion, StageMasterVersion.version == StageMaster.version)
        .where(StageMasterVersion.status == ConfigStatus.ACTIVE.value)
        .order_by(StageMaster.sequence)
    )
    return [
        StageMasterRow(
            id=row.id,
            number=row.number,
            code=row.code,
            name=row.name,
            sequence=row.sequence,
            is_audit_gate=row.is_audit_gate,
            is_payment_milestone=row.is_payment_milestone,
            repeats_per_floor=row.repeats_per_floor,
            default_duration_days=row.default_duration_days,
        )
        for row in rows
    ]


async def stage_master_names(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Names of specific stage configuration rows, whatever their version's status."""
    if not ids:
        return {}
    rows = await session.execute(
        select(StageMaster.id, StageMaster.name).where(StageMaster.id.in_(ids))
    )
    return {row_id: name for row_id, name in rows.all()}


@dataclass(frozen=True)
class GroupRow:
    code: str
    name: str
    issued: str
    sequence: int


async def spec_groups(session: AsyncSession) -> list[GroupRow]:
    rows = await session.scalars(select(SpecGroup).order_by(SpecGroup.sequence))
    return [GroupRow(row.code, row.name, row.issued, row.sequence) for row in rows]


@dataclass(frozen=True)
class SpecMasterRow:
    code: str
    group: str
    sequence: int
    item: str
    consuming_stages: list[int]
    decide_by_weeks: int
    verified_at: str | None
    brand_category: str | None
    is_structural: bool
    is_long_lead: bool
    version_id: uuid.UUID
    performance_specification: str
    engineer_signoff: EngineerSignoff


async def active_spec_masters(session: AsyncSession) -> list[SpecMasterRow]:
    """Every line with its active issued criteria, in catalogue order (S04 tables 5 to 7)."""
    rows = await session.execute(
        select(SpecLineMaster, SpecLineMasterVersion)
        .join(SpecLineMasterVersion, SpecLineMasterVersion.code == SpecLineMaster.code)
        .where(SpecLineMasterVersion.status == ConfigStatus.ACTIVE.value)
        .order_by(SpecLineMaster.sequence)
    )
    return [
        SpecMasterRow(
            code=master.code,
            group=master.spec_group,
            sequence=master.sequence,
            item=master.item,
            consuming_stages=list(master.consuming_stages),
            decide_by_weeks=master.decide_by_weeks,
            verified_at=master.verified_at,
            brand_category=master.brand_category,
            is_structural=master.is_structural,
            is_long_lead=master.is_long_lead,
            version_id=version.id,
            performance_specification=version.performance_specification,
            engineer_signoff=EngineerSignoff(version.engineer_signoff),
        )
        for master, version in rows.all()
    ]


@dataclass(frozen=True)
class CategoryRow:
    code: str
    parent_code: str | None
    name: str
    sequence: int


async def service_category_rows(session: AsyncSession) -> list[CategoryRow]:
    """Active categories and subtypes, in display order."""
    rows = await session.scalars(
        select(ServiceCategory)
        .where(ServiceCategory.active)
        .order_by(ServiceCategory.sequence, ServiceCategory.code)
    )
    return [CategoryRow(r.code, r.parent_code, r.name, r.sequence) for r in rows]


@dataclass(frozen=True)
class ListingRequirements:
    id: uuid.UUID
    category_code: str
    version: int
    requirements: RequirementSet
    validity_months: int
    reapply_months: int


def _requirements(row: ListingRequirementVersion) -> ListingRequirements:
    return ListingRequirements(
        id=row.id,
        category_code=row.category_code,
        version=row.version,
        requirements=RequirementSet.model_validate({"requirements": row.requirements}),
        validity_months=row.validity_months,
        reapply_months=row.reapply_months,
    )


async def active_listing_requirements(
    session: AsyncSession, category_code: str
) -> ListingRequirements | None:
    row = (
        await session.scalars(
            select(ListingRequirementVersion).where(
                ListingRequirementVersion.category_code == category_code,
                ListingRequirementVersion.status == ConfigStatus.ACTIVE.value,
            )
        )
    ).one_or_none()
    return _requirements(row) if row else None


async def listing_requirements(session: AsyncSession, version_id: uuid.UUID) -> ListingRequirements:
    """A specific version (the one a category was reviewed against)."""
    return _requirements(await session.get_one(ListingRequirementVersion, version_id))


async def categories_for_services(
    session: AsyncSession, question_set_version: int, values: list[str]
) -> list[str]:
    """The professional categories a requirement's services answer names (N-01), distinct."""
    if not values:
        return []
    rows = await session.scalars(
        select(ServiceValueCategory.category_code)
        .where(
            ServiceValueCategory.question_set_version == question_set_version,
            ServiceValueCategory.service_value.in_(values),
        )
        .distinct()
    )
    return sorted(rows)
