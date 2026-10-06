"""From service objects to API responses, shared by the professional, public and operations
routes. Public builders read only public fields (D-01): never contact details, the base point,
documents, references, checks' notes or reviewer identity (security section of K0)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from p2b.catalog.interface import (
    ListingRequirements,
    active_listing_requirements,
    service_category_rows,
)
from p2b.core.storage import Storage
from p2b.core.vocabulary import (
    CheckKind,
    CheckOutcome,
    ListingState,
    PortfolioReviewState,
    ProfessionalDocumentKind,
)
from p2b.documents.interface import FileSummary, public_image_urls
from p2b.professionals.models import ProfessionalCategory, ProfessionalProfile
from p2b.professionals.schemas import (
    CategoryOut,
    CheckOut,
    DirectoryCardOut,
    DirectoryPageOut,
    DocumentOut,
    FileOut,
    HistoryOut,
    OwnCategoryOut,
    OwnDashboardOut,
    OwnProfileOut,
    PointIn,
    PortfolioImageOut,
    PortfolioOut,
    PublicCategoryOut,
    PublicProfileOut,
    ReferenceOut,
    RequirementOut,
    ReviewDetailOut,
    ReviewItemOut,
)
from p2b.professionals.service import (
    NAME_LOCKING,
    DirectoryPage,
    Evidence,
    PublicProfile,
    ReviewDetail,
    _categories,
    _point,
    evidence_for,
    missing_evidence,
    missing_profile_fields,
    provided,
)


async def category_names(session: AsyncSession) -> dict[str, str]:
    return {row.code: row.name for row in await service_category_rows(session)}


def _file(summary: FileSummary | None) -> FileOut | None:
    if summary is None:
        return None
    return FileOut(
        file_id=summary.file_id,
        file_name=summary.file_name,
        content_type=summary.content_type,
        size_bytes=summary.size_bytes,
        state=summary.state,
    )


def profile_out(
    profile: ProfessionalProfile, point: tuple[float, float] | None, *, names_locked: bool
) -> OwnProfileOut:
    return OwnProfileOut(
        profile_id=profile.id,
        display_name=profile.display_name,
        firm_name=profile.firm_name,
        bio=profile.bio,
        years_experience=profile.years_experience,
        team_size=profile.team_size,
        base_locality=profile.base_locality,
        base_point=PointIn(lat=point[0], lng=point[1]) if point else None,
        service_radius_km=profile.service_radius_km,
        missing=missing_profile_fields(profile),
        names_locked=names_locked,
    )


def requirement_outs(
    requirements: ListingRequirements, counts: dict[CheckKind, int]
) -> list[RequirementOut]:
    return [
        RequirementOut(
            id=r.id,
            label=r.label,
            accepts=r.accepts,
            level=r.level,
            count=r.count,
            provided=sum(counts[k] for k in r.accepts if k != CheckKind.SITE_VISIT),
        )
        for r in requirements.requirements.requirements
    ]


def evidence_outs(
    evidence: Evidence,
) -> tuple[list[DocumentOut], list[ReferenceOut], list[PortfolioOut]]:
    documents = [
        DocumentOut(
            document_id=d.id,
            kind=ProfessionalDocumentKind(d.kind),
            category_code=d.category_code,
            details=dict(d.details),
            file=_file(evidence.files.get(d.file_id)),
        )
        for d in evidence.documents
    ]
    references = [
        ReferenceOut(
            reference_id=r.id,
            category_code=r.category_code,
            name=r.name,
            phone=r.phone,
            project_note=r.project_note,
        )
        for r in evidence.references
    ]
    portfolio = [
        PortfolioOut(
            item_id=p.id,
            caption=p.caption,
            review_state=PortfolioReviewState(p.review_state),
            file=_file(evidence.files.get(p.file_id)),
        )
        for p in evidence.portfolio
    ]
    return documents, references, portfolio


async def own_dashboard(session: AsyncSession, profile: ProfessionalProfile) -> OwnDashboardOut:
    categories = await _categories(session, profile.id)
    evidence = await evidence_for(session, profile)
    names = await category_names(session)
    outs = []
    for category in categories:
        requirements = await active_listing_requirements(session, category.category_code)
        counts = provided(evidence, category.category_code)
        outs.append(
            OwnCategoryOut(
                code=category.category_code,
                name=names.get(category.category_code, category.category_code),
                subtypes=list(category.subtypes),
                listing_state=ListingState(category.listing_state),
                hidden=category.hidden,
                public=category.listing_state == ListingState.LISTED and not category.hidden,
                message=category.message,
                submitted_at=category.submitted_at,
                listed_at=category.listed_at,
                review_due_at=category.review_due_at,
                reapply_after=category.reapply_after,
                requirements=requirement_outs(requirements, counts) if requirements else [],
                missing_requirements=missing_evidence(requirements, counts) if requirements else [],
            )
        )
    documents, references, portfolio = evidence_outs(evidence)
    rows = await service_category_rows(session)
    return OwnDashboardOut(
        profile=profile_out(
            profile,
            await _point(session, profile),
            names_locked=any(c.listing_state in NAME_LOCKING for c in categories),
        ),
        categories=outs,
        documents=documents,
        references=references,
        portfolio=portfolio,
        available_categories=[
            CategoryOut(code=r.code, name=r.name, parent_code=r.parent_code) for r in rows
        ],
    )


def review_detail_out(
    detail: ReviewDetail,
    *,
    names: dict[str, str],
    emails: dict[uuid.UUID, str],
    email: str | None,
    queue_item: ReviewItemOut | None,
) -> ReviewDetailOut:
    """For operations routes only: everything, including private evidence and notes."""
    documents, references, portfolio = evidence_outs(detail.evidence)
    counts = provided(detail.evidence, detail.category.category_code)
    case = detail.case
    return ReviewDetailOut(
        category_id=detail.category.id,
        category_code=detail.category.category_code,
        category_name=names.get(detail.category.category_code, detail.category.category_code),
        subtypes=list(detail.category.subtypes),
        listing_state=ListingState(detail.category.listing_state),
        hidden=detail.category.hidden,
        review_due_at=detail.category.review_due_at,
        profile=profile_out(detail.profile, detail.base_point, names_locked=True),
        email=email,
        requirements=requirement_outs(detail.requirements, counts),
        unmet=detail.unmet,
        case_open=bool(case and case.decided_at is None),
        case_decision=case.decision if case else None,
        checks=[
            CheckOut(
                kind=CheckKind(c.kind),
                subject=c.subject,
                outcome=CheckOutcome(c.outcome),
                detail=dict(c.detail),
                internal_note=c.internal_note,
                recorded_by_email=emails.get(c.recorded_by),
                recorded_at=c.recorded_at,
            )
            for c in detail.checks
        ],
        documents=documents,
        references=references,
        portfolio=portfolio,
        history=[
            HistoryOut(
                event=h.event,
                from_state=ListingState(h.from_state) if h.from_state else None,
                to_state=ListingState(h.to_state),
                actor_email=emails.get(h.actor_user_id) if h.actor_user_id else None,
                actor_role=h.actor_role,
                reason=h.reason,
                at=h.at,
            )
            for h in detail.history
        ],
        queue_item=queue_item,
    )


def _public_categories(
    categories: list[ProfessionalCategory],
    names: dict[str, str],
    verified: dict[uuid.UUID, list[str]] | None = None,
    registrations: dict[uuid.UUID, list[dict[str, str]]] | None = None,
) -> list[PublicCategoryOut]:
    return [
        PublicCategoryOut(
            code=c.category_code,
            name=names.get(c.category_code, c.category_code),
            subtypes=list(c.subtypes),
            verified=[CheckKind(k) for k in (verified or {}).get(c.id, [])],
            registrations=(registrations or {}).get(c.id, []),
        )
        for c in categories
    ]


def _card(
    profile: ProfessionalProfile, categories: list[PublicCategoryOut], cover: str | None
) -> DirectoryCardOut:
    return DirectoryCardOut(
        profile_id=profile.id,
        display_name=profile.display_name,
        firm_name=profile.firm_name,
        base_locality=profile.base_locality,
        service_radius_km=profile.service_radius_km,
        years_experience=profile.years_experience,
        team_size=profile.team_size,
        categories=categories,
        cover_image_url=cover,
    )


async def directory_out(
    session: AsyncSession, storage: Storage, page: DirectoryPage, covers: dict[uuid.UUID, uuid.UUID]
) -> DirectoryPageOut:
    names = await category_names(session)
    urls = await public_image_urls(session, storage, list(covers.values()))
    return DirectoryPageOut(
        items=[
            _card(
                p,
                _public_categories(page.categories.get(p.id, []), names),
                urls.get(covers[p.id]) if p.id in covers else None,
            )
            for p in page.profiles
        ],
        next_cursor=page.next_cursor,
    )


async def public_profile_out(
    session: AsyncSession, storage: Storage, public: PublicProfile
) -> PublicProfileOut:
    names = await category_names(session)
    urls = await public_image_urls(session, storage, [p.file_id for p in public.portfolio])
    categories = _public_categories(public.categories, names, public.verified, public.registrations)
    card = _card(
        public.profile,
        categories,
        urls.get(public.portfolio[0].file_id) if public.portfolio else None,
    )
    return PublicProfileOut(
        **card.model_dump(),
        bio=public.profile.bio,
        portfolio=[
            PortfolioImageOut(caption=p.caption, image_url=urls.get(p.file_id))
            for p in public.portfolio
        ],
    )
