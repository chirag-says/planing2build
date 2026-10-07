"""Editing a plan (Checkpoint 3): a batch of typed operations applied to the head document,
then the same checks a generated plan gets. Pure and deterministic: the same document and batch
give the same result, byte for byte.

Nothing here repairs or adjusts an edit. The batch applies as given (or is rejected whole), the
soft quality terms are re-measured, and the independent validator judges the result. The caller
stores it only if the validator passes (IC 18.7)."""

from collections.abc import Sequence
from dataclasses import dataclass

from p2b.core.vocabulary import ConstraintStrength, PlanOpRejection, PlanSource
from p2b.houseplans.engine.canonical import sha256_of
from p2b.houseplans.engine.generate import soft_constraints
from p2b.houseplans.engine.intent import ArchitecturalIntent
from p2b.houseplans.engine.model import HousePlan
from p2b.houseplans.engine.objective import score_plan
from p2b.houseplans.engine.ops import (
    REVERTS,
    STRUCTURAL,
    OperationRejected,
    PlanOp,
    RevertToRevision,
    apply,
)
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.engine.validate import ValidationReport, validate

MAX_BATCH = 50


class BatchRejected(Exception):
    """Operation `index` of the batch could not apply; nothing in the batch applied."""

    def __init__(self, index: int, rejected: OperationRejected):
        super().__init__(f"operation {index}: {rejected}")
        self.index, self.rejected = index, rejected


@dataclass(frozen=True)
class EditResult:
    plan: HousePlan  # revision_no + 1, source EDITED, soft terms re-measured, body hash stamped
    report: ValidationReport
    inverse: tuple[PlanOp, ...]  # applied in this order, it restores the original body exactly


def apply_batch(
    plan: HousePlan, ops: Sequence[PlanOp], ruleset: RulesetContent | None = None
) -> tuple[HousePlan, tuple[PlanOp, ...]]:
    """The plan with every operation applied in order, and the batch that undoes it: the
    inverses in reverse order, or, when the batch holds a structural edit, REVERT_TO_REVISION of
    the revision it started from (Checkpoint 3.1). A revert must be alone in its batch and is
    applied by the plan service, so one here is rejected."""
    start = plan.meta.revision_no
    inverses: list[PlanOp] = []
    for index, op in enumerate(ops):
        try:
            if isinstance(op, REVERTS):
                raise OperationRejected(
                    op.op, "a revert must be alone in its batch", PlanOpRejection.REVERT_NOT_ALONE
                )
            plan, inverse = apply(plan, op, ruleset)
        except OperationRejected as rejected:
            raise BatchRejected(index, rejected) from None
        inverses.append(inverse)
    if any(isinstance(op, STRUCTURAL) for op in ops):
        return plan, (RevertToRevision(revision=start),)
    return plan, tuple(reversed(inverses))


def apply_edit(
    plan: HousePlan, ops: Sequence[PlanOp], ruleset: RulesetContent
) -> tuple[HousePlan, tuple[PlanOp, ...]]:
    """Everything `edit` does except validation: the batch applied, soft terms re-measured,
    revision_no + 1, source EDITED and the body hash stamped. Replaying a logged batch with it
    reproduces the logged revision exactly (the log stores only validated batches)."""
    if not ops or len(ops) > MAX_BATCH:
        raise ValueError(f"a batch has 1 to {MAX_BATCH} operations")
    edited, inverse = apply_batch(plan, ops, ruleset)
    constraints = list(edited.constraints)
    if any(c.strength == ConstraintStrength.SOFT for c in constraints):
        # the stored soft terms measured the old geometry: measure them again
        hard = [c for c in constraints if c.strength == ConstraintStrength.HARD]
        quality = score_plan(edited, ruleset)
        constraints = hard + (soft_constraints(quality, len(hard) + 1) if quality else [])
    meta = edited.meta.model_copy(
        update={"revision_no": plan.meta.revision_no + 1, "source": PlanSource.EDITED}
    )
    edited = edited.model_copy(update={"constraints": constraints, "meta": meta})
    stamped = edited.meta.model_copy(update={"body_sha256": sha256_of(edited.body())})
    return edited.model_copy(update={"meta": stamped}), inverse


def edit(
    plan: HousePlan,
    ops: Sequence[PlanOp],
    ruleset: RulesetContent,
    *,
    intent: ArchitecturalIntent | None,
    ruleset_version: int | None,
    ruleset_sha256: str | None,
) -> EditResult:
    edited, inverse = apply_edit(plan, ops, ruleset)
    report = validate(
        edited,
        ruleset,
        intent=intent,
        ruleset_version=ruleset_version,
        ruleset_sha256=ruleset_sha256,
    )
    return EditResult(edited, report, inverse)
