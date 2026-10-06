"""Listing requirements as data (D-02). A requirement names the check kinds that satisfy it, how
many passed checks it needs, and whether it is REQUIRED or WHERE_APPLICABLE. A WHERE_APPLICABLE
requirement is met by enough passed checks or by operations marking one of its kinds not
applicable, so nothing is skipped silently."""

from pydantic import BaseModel, Field, model_validator

from p2b.core.vocabulary import CheckKind, CheckOutcome, RequirementLevel


class Requirement(BaseModel):
    id: str = Field(pattern=r"^[a-z_]{2,40}$")
    label: str = Field(min_length=2, max_length=120)
    accepts: list[CheckKind] = Field(min_length=1)
    level: RequirementLevel
    count: int = Field(default=1, ge=1, le=5)


class RequirementSet(BaseModel):
    requirements: list[Requirement] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> "RequirementSet":
        ids = [r.id for r in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("requirement ids must be unique")
        return self


def unmet(
    requirements: RequirementSet, outcomes: list[tuple[CheckKind, CheckOutcome]]
) -> list[str]:
    """Ids of the requirements the recorded check outcomes do not satisfy."""
    missing = []
    for requirement in requirements.requirements:
        kinds = set(requirement.accepts)
        passed = sum(
            1 for kind, outcome in outcomes if kind in kinds and outcome == CheckOutcome.PASSED
        )
        not_applicable = any(
            kind in kinds and outcome == CheckOutcome.NOT_APPLICABLE for kind, outcome in outcomes
        )
        if passed >= requirement.count:
            continue
        if requirement.level == RequirementLevel.WHERE_APPLICABLE and not_applicable:
            continue
        missing.append(requirement.id)
    return missing
