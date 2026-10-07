#!/usr/bin/env bash
# Checkpoint 2.1 VPS acceptance run (AI_DESIGN_ENGINE_CHECKPOINT_2_1_REPORT section 12).
#
# Run on the target VPS, from the repository checkout at the commit under test, with the
# Plan2Build stack idle:
#
#     bash apps/api/scripts/vps_benchmark.sh
#
# It records the environment, builds the production API image (the worker runs the same image),
# runs the documented benchmark command unchanged, and measures one cold start. Every number in
# the result comes from the benchmark script; nothing is typed by hand. Output: ./benchmark-vps-*/
set -euo pipefail

OUT="benchmark-vps-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
IMAGE="p2b-api:cp2-1"

{
  echo "date_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "provider_vendor: $(cat /sys/class/dmi/id/sys_vendor 2>/dev/null || echo unknown)"
  echo "provider_product: $(cat /sys/class/dmi/id/product_name 2>/dev/null || echo unknown)"
  echo "cpu_count: $(nproc)"
  echo "cpu_model: $(lscpu 2>/dev/null | sed -n 's/^Model name:[[:space:]]*//p' | head -1)"
  echo "memory:"; free -m
  echo "kernel: $(uname -srm)"
  echo "os: $(. /etc/os-release && echo "$PRETTY_NAME")"
  echo "docker:"; docker version --format 'client {{.Client.Version}} / server {{.Server.Version}}'
  echo "commit: $(git rev-parse HEAD)"
  echo "working_tree_clean: $(test -z "$(git status --porcelain)" && echo yes || echo NO)"
  echo "corpus_sha256:"
  sha256sum apps/api/tests/fixtures/houseplans/benchmark_cp2.json \
            apps/api/tests/fixtures/houseplans/benchmark_cp2_1_quality.json \
            apps/api/tests/fixtures/houseplans/ruleset_synthetic_test_only.json
  echo "load_before:"; uptime
} > "$OUT/environment.txt" 2>&1

docker build -t "$IMAGE" apps/api > "$OUT/build.log" 2>&1
docker run --rm "$IMAGE" python --version >> "$OUT/environment.txt" 2>&1

# The documented command (report section 12), unchanged except for the output directory.
docker run --rm --cpus 2 --user root \
  -v "$PWD/apps/api/scripts:/app/scripts:ro" \
  -v "$PWD/apps/api/tests/fixtures/houseplans:/app/fixtures:ro" \
  -v "$PWD/$OUT:/out" "$IMAGE" \
  python scripts/benchmark_houseplans.py --fixtures /app/fixtures --corpus all \
  --repeats 5 --fresh-process --concurrency 1,2,4 \
  --json /out/benchmark_vps.json --label vps > "$OUT/benchmark.log" 2>&1

# Cold start: a fresh container importing the engine and generating one plan.
start=$(date +%s%N)
docker run --rm \
  -v "$PWD/apps/api/scripts:/app/scripts:ro" \
  -v "$PWD/apps/api/tests/fixtures/houseplans:/app/fixtures:ro" "$IMAGE" \
  python scripts/benchmark_houseplans.py --fixtures /app/fixtures --corpus cp2 \
  --cases 2bhk_30x50_north_twowheeler_open --repeats 0 --no-baseline --quiet > /dev/null
end=$(date +%s%N)
echo "cold_start_container_one_plan_ms: $(( (end - start) / 1000000 ))" >> "$OUT/environment.txt"
echo "load_after:" >> "$OUT/environment.txt"; uptime >> "$OUT/environment.txt"

echo "Done: $OUT/environment.txt and $OUT/benchmark_vps.json"
