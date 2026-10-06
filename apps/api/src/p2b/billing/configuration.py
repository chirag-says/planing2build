"""Commercial configuration (SLICE3_3_READINESS B, C, F): offerings and their versions, pricing
rules, instalment plans and tax configuration. ADMIN creates a version as a DRAFT and publishes
it in a separate step (MFA at the route); publishing retires the previous ACTIVE version. A
published version never changes (trigger). Production refuses versions marked TEST, so
development values cannot reach a real buyer.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing.models import (
    InstalmentPlanVersion,
    Offering,
    OfferingVersion,
    PricingRuleVersion,
    TaxConfigurationVersion,
)
from p2b.billing.money import split
from p2b.billing.pricing import PricingRule, parse_rule
from p2b.billing.tax import TaxConfig, missing_fields, parse_lines
from p2b.core.config import Settings
from p2b.core.errors import BillingNotConfigured, NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import ActorType, ConfigStatus, OfferingKind, PaymentMode

ACTIVE = ConfigStatus.ACTIVE.value
PUBLISHED = (ConfigStatus.ACTIVE.value, ConfigStatus.RETIRED.value)
OFFERING_CODES = {OfferingKind.PACKAGE: "P2B_PACKAGE", OfferingKind.AI_CREDIT: "AI_CREDIT_SINGLE"}

Versioned = PricingRuleVersion | InstalmentPlanVersion | TaxConfigurationVersion | OfferingVersion


class InstalmentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    share_bp: int = Field(ge=1, le=10000, description="Share of the order in basis points")
    due: Literal["ON_ORDER", "DAYS_AFTER_ACTIVATION"]
    days: int | None = Field(default=None, ge=1, le=3650)


class InstalmentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instalments: list[InstalmentSpec] = Field(min_length=2, max_length=12)

    @model_validator(mode="after")
    def _shape(self) -> "InstalmentPlan":
        """The one initial shape (L-03): the first due on ordering, the rest a number of days
        after activation, in order; shares add up to the whole."""
        first, *rest = self.instalments
        if first.due != "ON_ORDER" or first.days is not None:
            raise ValueError("the first instalment is due when the order is created")
        days = [i.days for i in rest]
        if any(i.due != "DAYS_AFTER_ACTIVATION" for i in rest) or None in days:
            raise ValueError("later instalments are due a number of days after activation")
        if days != sorted(set(days)):  # type: ignore[type-var]
            raise ValueError("later instalments must fall due in order")
        if sum(i.share_bp for i in self.instalments) != 10000:
            raise ValueError("instalment shares must add up to 10000 basis points")
        return self


def parse_plan(raw: list[dict[str, Any]]) -> InstalmentPlan:
    try:
        return InstalmentPlan.model_validate({"instalments": raw})
    except ValidationError as exc:
        raise ValidationFailed(
            message="The instalment plan is not valid.",
            details={"fields": {"instalments": [e["msg"] for e in exc.errors()][:10]}},
        ) from None


def tax_config_of(row: TaxConfigurationVersion) -> TaxConfig:
    return TaxConfig(
        row.legal_name,
        row.address,
        row.gstin,
        row.state_code,
        row.invoice_series,
        row.prices_include_tax,
        parse_lines(row.lines),
    )


def _refuse_test_in_production(settings: Settings, *rows: Versioned | None) -> None:
    if settings.env == "production" and any(r is not None and r.is_test for r in rows):
        raise BillingNotConfigured(
            message="Test values are never used in production.", details={"missing": ["live"]}
        )


async def _next_version(session: AsyncSession, model: type[Versioned], **scope: Any) -> int:
    query = select(func.max(model.version))
    for name, value in scope.items():
        query = query.where(getattr(model, name) == value)
    return int((await session.scalar(query)) or 0) + 1


async def _audit_created(
    session: AsyncSession,
    row: Versioned,
    kind: str,
    actor_user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    await record(
        session,
        action=f"billing.{kind}_created",
        entity_type=kind,
        entity_id=row.id,
        actor_type=ActorType.USER,
        actor_user_id=actor_user_id,
        actor_role="ADMIN",
        session_id=session_id,
        new_value={"version": row.version, "is_test": row.is_test},
    )


async def create_pricing_rule(
    session: AsyncSession,
    *,
    offering_code: str,
    rule: dict[str, Any],
    is_test: bool,
    note: str,
    actor_user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> PricingRuleVersion:
    if await session.get(Offering, offering_code) is None:
        raise ValidationFailed(details={"fields": {"offering_code": ["Unknown offering."]}})
    parsed = parse_rule(rule)
    row = PricingRuleVersion(
        id=new_id(),
        offering_code=offering_code,
        version=await _next_version(session, PricingRuleVersion, offering_code=offering_code),
        status=ConfigStatus.DRAFT.value,
        rule=parsed.model_dump(mode="json", by_alias=True),
        currency="INR",
        is_test=is_test,
        note=note.strip(),
        created_by=actor_user_id,
    )
    session.add(row)
    await session.flush()
    await _audit_created(session, row, "pricing_rule_version", actor_user_id, session_id)
    return row


async def create_instalment_plan(
    session: AsyncSession,
    *,
    instalments: list[dict[str, Any]],
    is_test: bool,
    note: str,
    actor_user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> InstalmentPlanVersion:
    plan = parse_plan(instalments)
    row = InstalmentPlanVersion(
        id=new_id(),
        version=await _next_version(session, InstalmentPlanVersion),
        status=ConfigStatus.DRAFT.value,
        instalments=[i.model_dump(mode="json") for i in plan.instalments],
        is_test=is_test,
        note=note.strip(),
        created_by=actor_user_id,
    )
    session.add(row)
    await session.flush()
    await _audit_created(session, row, "instalment_plan_version", actor_user_id, session_id)
    return row


async def create_tax_configuration(
    session: AsyncSession,
    *,
    legal_name: str,
    address: str,
    gstin: str,
    state_code: str,
    invoice_series: str,
    prices_include_tax: bool,
    lines: dict[str, Any],
    is_test: bool,
    note: str,
    actor_user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> TaxConfigurationVersion:
    parsed = parse_lines(lines)
    row = TaxConfigurationVersion(
        id=new_id(),
        version=await _next_version(session, TaxConfigurationVersion),
        status=ConfigStatus.DRAFT.value,
        legal_name=legal_name.strip(),
        address=address.strip(),
        gstin=gstin.strip().upper(),
        state_code=state_code.strip(),
        invoice_series=invoice_series.strip().upper(),
        prices_include_tax=prices_include_tax,
        lines=parsed.model_dump(mode="json", exclude_none=True),
        is_test=is_test,
        note=note.strip(),
        created_by=actor_user_id,
    )
    session.add(row)
    await session.flush()
    await _audit_created(session, row, "tax_configuration_version", actor_user_id, session_id)
    return row


async def create_offering_version(
    session: AsyncSession,
    *,
    offering_code: str,
    pricing_rule_version_id: uuid.UUID,
    payment_modes: list[PaymentMode],
    instalment_plan_version_id: uuid.UUID | None,
    terms_version: str,
    is_test: bool,
    note: str,
    actor_user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> OfferingVersion:
    offering = await session.get(Offering, offering_code)
    if offering is None:
        raise ValidationFailed(details={"fields": {"offering_code": ["Unknown offering."]}})
    rule = await session.get(PricingRuleVersion, pricing_rule_version_id)
    if rule is None or rule.offering_code != offering_code:
        raise ValidationFailed(
            details={"fields": {"pricing_rule_version_id": ["Not this offering's rule."]}}
        )
    modes = sorted({m.value for m in payment_modes})
    if not modes:
        raise ValidationFailed(details={"fields": {"payment_modes": ["Choose at least one."]}})
    if offering.kind == OfferingKind.AI_CREDIT.value and modes != [PaymentMode.FULL.value]:
        raise ValidationFailed(
            details={"fields": {"payment_modes": ["AI credits are paid in full."]}}
        )
    wants_plan = PaymentMode.INSTALMENTS.value in modes
    if wants_plan != (instalment_plan_version_id is not None):
        raise ValidationFailed(
            details={
                "fields": {
                    "instalment_plan_version_id": ["Instalments need a plan, and only they do."]
                }
            }
        )
    if (
        instalment_plan_version_id
        and await session.get(InstalmentPlanVersion, instalment_plan_version_id) is None
    ):
        raise ValidationFailed(
            details={"fields": {"instalment_plan_version_id": ["Unknown plan."]}}
        )
    if not terms_version.strip():
        raise ValidationFailed(details={"fields": {"terms_version": ["Name the terms version."]}})
    row = OfferingVersion(
        id=new_id(),
        offering_code=offering_code,
        version=await _next_version(session, OfferingVersion, offering_code=offering_code),
        status=ConfigStatus.DRAFT.value,
        pricing_rule_version_id=pricing_rule_version_id,
        payment_modes=modes,
        instalment_plan_version_id=instalment_plan_version_id,
        terms_version=terms_version.strip(),
        is_test=is_test,
        note=note.strip(),
        created_by=actor_user_id,
    )
    session.add(row)
    await session.flush()
    await _audit_created(session, row, "offering_version", actor_user_id, session_id)
    return row


ConfigKind = Literal["pricing-rules", "instalment-plans", "tax-configurations", "offerings"]
MODELS: dict[str, type[Versioned]] = {
    "pricing-rules": PricingRuleVersion,
    "instalment-plans": InstalmentPlanVersion,
    "tax-configurations": TaxConfigurationVersion,
    "offerings": OfferingVersion,
}


async def publish(
    session: AsyncSession,
    settings: Settings,
    kind: ConfigKind,
    version_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> Versioned:
    model = MODELS[kind]
    row = cast(Versioned | None, await session.get(model, version_id, with_for_update=True))
    if row is None:
        raise NotFound
    if row.status != ConfigStatus.DRAFT.value:
        raise StateConflict(details={"current_state": row.status})
    _refuse_test_in_production(settings, row)
    scope: list[Any] = []
    if isinstance(row, TaxConfigurationVersion):
        missing = missing_fields(tax_config_of(row))
        if missing:
            raise ValidationFailed(
                message="The tax configuration is incomplete.", details={"missing": missing}
            )
    if isinstance(row, OfferingVersion):
        rule = await session.get_one(PricingRuleVersion, row.pricing_rule_version_id)
        plan = (
            await session.get(InstalmentPlanVersion, row.instalment_plan_version_id)
            if row.instalment_plan_version_id
            else None
        )
        if rule.status not in PUBLISHED or (plan is not None and plan.status not in PUBLISHED):
            raise StateConflict(details={"publish": "publish the pricing rule and plan first"})
        _refuse_test_in_production(settings, rule, plan)
        scope.append(OfferingVersion.offering_code == row.offering_code)
    if isinstance(row, PricingRuleVersion):
        scope.append(PricingRuleVersion.offering_code == row.offering_code)
    await session.execute(
        update(model)
        .where(model.status == ACTIVE, *scope)
        .values(status=ConfigStatus.RETIRED.value)
    )
    row.status = ACTIVE
    row.published_by = actor_user_id
    row.published_at = (await session.execute(select(func.now()))).scalar_one()
    await session.flush()
    await record(
        session,
        action=f"billing.{model.__tablename__}_published",
        entity_type=model.__tablename__,
        entity_id=row.id,
        actor_type=ActorType.USER,
        actor_user_id=actor_user_id,
        actor_role="ADMIN",
        session_id=session_id,
        new_value={"version": row.version, "is_test": row.is_test},
    )
    return row


async def versions(session: AsyncSession, kind: ConfigKind) -> list[Versioned]:
    model = MODELS[kind]
    return list(await session.scalars(select(model).order_by(model.created_at.desc()).limit(100)))


@dataclass(frozen=True)
class ActiveOffer:
    """Everything an order is priced and taxed with, all published and in force."""

    offering: Offering
    version: OfferingVersion
    rule_version: PricingRuleVersion
    rule: PricingRule
    plan_version: InstalmentPlanVersion | None
    plan: InstalmentPlan | None
    tax_version: TaxConfigurationVersion
    tax: TaxConfig

    @property
    def is_test(self) -> bool:
        rows: list[Versioned | None] = [
            self.version,
            self.rule_version,
            self.plan_version,
            self.tax_version,
        ]
        return any(r is not None and r.is_test for r in rows)


async def active_offer(
    session: AsyncSession, settings: Settings, kind: OfferingKind
) -> ActiveOffer:
    """The offer in force for a kind, or BillingNotConfigured naming what is missing."""
    code = OFFERING_CODES[kind]
    offering = await session.get(Offering, code)
    version = (
        await session.scalars(
            select(OfferingVersion).where(
                OfferingVersion.offering_code == code, OfferingVersion.status == ACTIVE
            )
        )
    ).one_or_none()
    tax_version = (
        await session.scalars(
            select(TaxConfigurationVersion).where(TaxConfigurationVersion.status == ACTIVE)
        )
    ).one_or_none()
    missing = [
        name for name, value in (("offering", version), ("tax", tax_version)) if value is None
    ]
    if offering is None or version is None or tax_version is None:
        raise BillingNotConfigured(details={"missing": missing or ["offering"]})
    rule_version = await session.get_one(PricingRuleVersion, version.pricing_rule_version_id)
    plan_version = (
        await session.get_one(InstalmentPlanVersion, version.instalment_plan_version_id)
        if version.instalment_plan_version_id
        else None
    )
    tax = tax_config_of(tax_version)
    if missing_fields(tax) or getattr(tax.lines, kind.value) is None:
        raise BillingNotConfigured(details={"missing": ["tax"]})
    _refuse_test_in_production(settings, version, rule_version, plan_version, tax_version)
    return ActiveOffer(
        offering,
        version,
        rule_version,
        parse_rule(rule_version.rule),
        plan_version,
        parse_plan(plan_version.instalments) if plan_version else None,
        tax_version,
        tax,
    )


async def offer_published(session: AsyncSession, settings: Settings, kind: OfferingKind) -> bool:
    """Whether a complete offer of this kind is in force (and allowed in this environment)."""
    try:
        await active_offer(session, settings, kind)
    except BillingNotConfigured:
        return False
    return True


def instalment_amounts(plan: InstalmentPlan | None, total: Decimal) -> list[Decimal]:
    if plan is None:
        return [total]
    return split(total, [i.share_bp for i in plan.instalments])
