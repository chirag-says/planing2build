# OR-Tools feasibility spike

Checkpoint 1, section N of `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_1.md`. A measurement, not an adoption: `ortools` is not in `apps/api/pyproject.toml` or `uv.lock`, and nothing in the application imports it.

```bash
docker build -t p2b-api:cp1-baseline apps/api
docker build -t p2b-api:cp1-ortools tools/spikes/ortools_feasibility
docker image inspect p2b-api:cp1-baseline p2b-api:cp1-ortools --format '{{.Size}}'
docker run --rm --cpus=1 --memory=2g p2b-api:cp1-ortools
```

`--cpus=1` stands in for one of the VPS's two cores (the worker solves one plan at a time). The real run on the staging VPS is still owed before CP-SAT is adopted. Results are recorded in `AI_DESIGN_ENGINE_CHECKPOINT_1_REPORT.md`.

The benchmark's room sizes are benchmark inputs, not architectural rules.
