"""Checkpoint 2, 2.1 and 2.2 acceptance on the benchmark corpora (tests/fixtures/houseplans/
benchmark_cp2.json, benchmark_cp2_1_quality.json and benchmark_cp2_2_quality.json, labels fixed
before their first runs).
Latency is not asserted here: CI machines vary, and the VPS gate is measured with
`scripts/benchmark_houseplans.py` on the VPS itself (CP2-U5)."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "scripts"))

from benchmark_houseplans import benchmark, quality_summary, summarise  # noqa: E402


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    args = argparse.Namespace(
        fixtures=str(API_ROOT / "tests" / "fixtures" / "houseplans"),
        cases="",
        repeats=1,
        svg_dir="",
        plans_dir="",
        no_baseline=False,
        quiet=True,
        label="test",
        corpus="all",
        concurrency="",
    )
    result = benchmark(args)
    result["summary"] = summarise(result)
    result["summary"]["quality"] = quality_summary(result["rows"])
    return result


def test_all_eleven_original_feasible_cases_are_valid(report: dict[str, Any]) -> None:
    """Checkpoint 2 met 10 of 11; Checkpoint 2.1 must not lose any and solves the 25x40 case."""
    acceptance = report["summary"]["acceptance"]
    assert acceptance["original_expected_feasible"] == 11
    assert acceptance["original_valid"] == 11


def test_every_cp1_valid_case_stays_valid_and_nothing_invalid_is_produced(
    report: dict[str, Any],
) -> None:
    acceptance = report["summary"]["acceptance"]
    assert acceptance["cp1_valid_cases_still_valid"]
    assert acceptance["invalid_attempts"] == 0
    assert acceptance["expected_infeasible_but_valid"] == []
    assert {r["outcome"] for r in report["rows"]} <= {"VALID", "INFEASIBLE"}


def test_proven_is_claimed_only_where_the_label_expects_infeasible(
    report: dict[str, Any],
) -> None:
    for row in report["rows"]:
        if row["classification"] == "PROVEN":
            assert row["expect"] == "INFEASIBLE", row["case"]
        if row["outcome"] == "INFEASIBLE":
            assert row["classification"] in ("PROVEN", "NO_SUPPORTED_LAYOUT"), row["case"]


def test_quality_is_at_most_half_of_checkpoint_1_and_no_case_scores_worse(
    report: dict[str, Any],
) -> None:
    for corpus in ("shared_original", "shared_all"):
        figures = report["summary"]["acceptance"][corpus]
        assert figures["quality_ratio"] <= 0.5, corpus
        assert figures["cases_scoring_worse"] == [], corpus


def test_rooms_over_aspect_limit_are_at_most_half_of_checkpoint_1(report: dict[str, Any]) -> None:
    """Missed in Checkpoint 2 (0.657 and 0.529); met in Checkpoint 2.1 by the new topologies, with
    the Checkpoint 2 definition of the aspect term unchanged."""
    for corpus in ("shared_original", "shared_all"):
        assert report["summary"]["acceptance"][corpus]["aspect_ratio"] <= 0.5, corpus


def test_layouts_come_from_several_topology_families(report: dict[str, Any]) -> None:
    quality = report["summary"]["quality"]
    winners: set[str] = set()
    for group in quality.values():
        winners |= set(group["families_won"])
    assert len(winners) >= 5, winners
    assert quality["quality"]["mean_families_feasible"] >= 2


def test_generation_and_candidate_ranking_are_deterministic(report: dict[str, Any]) -> None:
    assert all(r["deterministic"] for r in report["rows"])


def test_the_live_cp1_baseline_equals_the_recorded_one(report: dict[str, Any]) -> None:
    recorded = json.loads(
        (API_ROOT / "tests" / "fixtures" / "houseplans" / "benchmark_baseline_cp1.json").read_text(
            "utf-8"
        )
    )["cases"]
    assert {r["case"]: r["cp1"] for r in report["rows"]} == recorded
