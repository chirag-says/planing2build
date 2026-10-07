"""The concept floor plan engine (PD-28, ADR-025). Pure: no database, no I/O, no language model.
Imports only the standard library, Pydantic and `p2b.core.vocabulary` (import-linter contract).

    normalise   requirement answers + provisional design inputs → ArchitecturalIntent
    generate    intent + ruleset → VALID HousePlan, INFEASIBLE (PROVEN or NO_SUPPORTED_LAYOUT),
                or INVALID (a defect, MVP path only)
    validate    any HousePlan (or raw JSON) → ValidationReport
    repair      deterministic repair through typed operations
    score_plan  HousePlan → QualityScore, the one definition of layout quality
    plan_geometry  HousePlan → PlanGeometry, the only geometry a renderer consumes

Solvers: ZonedLocalSearchSolver (production, Checkpoint 2) and DeterministicMVPLayoutSolver
(Checkpoint 1, the fallback and reference)."""

from p2b.houseplans.engine.canonical import sha256_of
from p2b.houseplans.engine.derive import PlanGeometry, plan_geometry
from p2b.houseplans.engine.feasibility import FeasibilityReport
from p2b.houseplans.engine.fit import fixture_fit
from p2b.houseplans.engine.generate import Attempt, GenerationResult, generate
from p2b.houseplans.engine.intent import (
    ArchitecturalIntent,
    DesignInputs,
    InputConflict,
    NeedsInput,
    Normalised,
    Unsupported,
    normalise,
)
from p2b.houseplans.engine.model import HousePlan
from p2b.houseplans.engine.objective import QualityScore, score_plan
from p2b.houseplans.engine.ops import PlanOp, apply
from p2b.houseplans.engine.repair import repair
from p2b.houseplans.engine.ruleset import RulesetContent, missing_citations
from p2b.houseplans.engine.solver import LayoutSolver
from p2b.houseplans.engine.solver.mvp import DeterministicMVPLayoutSolver
from p2b.houseplans.engine.solver.zoned_ls import ZonedLocalSearchSolver
from p2b.houseplans.engine.validate import ENGINE_VERSION, ValidationReport, validate

__all__ = [
    "ENGINE_VERSION",
    "ArchitecturalIntent",
    "Attempt",
    "DesignInputs",
    "DeterministicMVPLayoutSolver",
    "FeasibilityReport",
    "GenerationResult",
    "HousePlan",
    "InputConflict",
    "LayoutSolver",
    "NeedsInput",
    "Normalised",
    "PlanGeometry",
    "PlanOp",
    "QualityScore",
    "RulesetContent",
    "Unsupported",
    "ValidationReport",
    "ZonedLocalSearchSolver",
    "apply",
    "fixture_fit",
    "generate",
    "missing_citations",
    "normalise",
    "plan_geometry",
    "repair",
    "score_plan",
    "sha256_of",
    "validate",
]
