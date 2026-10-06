# Checkpoint 2 layout research spike

Evidence for `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2.md`. Research code, not application code: nothing in `apps/` imports it, and OR-Tools is not an API dependency.

| File | What it is |
|---|---|
| `common.py` | Generalised spine zoning (parking side, spine position as a variable, one or two columns, optional rear band, column-assignment enumeration), one objective shared by every sizer, and an adapter that returns the engine's `Placed` |
| `local_search.py` | Deterministic coordinate-descent sizer, pure Python |
| `cpsat_sizer.py` | CP-SAT sizer for the same structure and objective (needs `ortools`) |
| `corpus.py` | 14 benchmark cases (11 expected feasible, 3 expected infeasible) |
| `run.py` | Runs a solver through the real engine (`generate` → plan builder → validator) and scores the final VALID plan from `PlanGeometry` |
| `Dockerfile.worker` | Separate solver-worker image, with or without OR-Tools |

```bash
cd tools/spikes/cp2_layout
../../../apps/api/.venv/Scripts/python run.py --solver mvp   # Checkpoint 1 baseline
../../../apps/api/.venv/Scripts/python run.py --solver ls    # zoned local search
SPIKE_ENUMERATE=0 ../../../apps/api/.venv/Scripts/python run.py --solver ls   # greedy column split only
```

The worker images are built from a minimal context (engine package, vocabulary, the synthetic ruleset and this folder), never the repository root. All preference numbers (aspect limits, weights, preferred-area factor) are synthetic benchmark values, not architectural rules (AD-05).
