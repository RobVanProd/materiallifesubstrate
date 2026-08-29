#!/usr/bin/env python3
"""Positive, deterministic, and semantic-mutation tests for the exact oracle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable


ACCEPTED_FAILURE_MARKERS = (
    "MECHANICAL OBSERVABILITY ORACLE INVALID",
    "MECHANICAL OBSERVABILITY ORACLE MISMATCH",
)


def render_without_hash(value: dict) -> str:
    payload = dict(value)
    payload.pop("result_sha256_before_hash_field", None)
    return json.dumps(payload, indent=2, sort_keys=True)


def refresh_hash(value: dict) -> None:
    value["result_sha256_before_hash_field"] = hashlib.sha256(
        render_without_hash(value).encode("utf-8")
    ).hexdigest()


def invoke(oracle: Path, canonical: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(oracle), "--verify", str(canonical)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def require_positive(oracle: Path, canonical: Path) -> str:
    first = invoke(oracle, canonical)
    if first.returncode != 0:
        raise AssertionError(f"positive oracle verification failed\n{first.stdout}\n{first.stderr}")
    second = invoke(oracle, canonical)
    if second.returncode != 0:
        raise AssertionError(f"repeat oracle verification failed\n{second.stdout}\n{second.stderr}")
    if first.stdout != second.stdout:
        raise AssertionError("oracle stdout was not deterministic across identical executions")
    return first.stdout


def require_rejection(
    oracle: Path,
    baseline: dict,
    directory: Path,
    label: str,
    mutation: Callable[[dict], None],
    *,
    rehash: bool,
) -> None:
    candidate = copy.deepcopy(baseline)
    mutation(candidate)
    if rehash:
        refresh_hash(candidate)
    target = directory / f"{label}.json"
    target.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = invoke(oracle, target)
    if result.returncode == 0:
        raise AssertionError(f"oracle accepted mutation {label}")
    diagnostic = f"{result.stdout}\n{result.stderr}"
    if not any(marker in diagnostic for marker in ACCEPTED_FAILURE_MARKERS):
        raise AssertionError(f"mutation {label} lacked a stable rejection marker\n{diagnostic}")


def main() -> int:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--oracle",
        type=Path,
        default=root / "reference" / "mechanical_observability_oracle.py",
    )
    parser.add_argument(
        "--canonical",
        type=Path,
        default=root / "tests" / "mechanical_observability_oracle.canonical.json",
    )
    args = parser.parse_args()

    stdout = require_positive(args.oracle, args.canonical)
    baseline = json.loads(args.canonical.read_text(encoding="utf-8"))
    if json.loads(stdout) != baseline:
        raise AssertionError("verified stdout did not reproduce the canonical JSON object")

    mutations: tuple[tuple[str, Callable[[dict], None], bool], ...] = (
        (
            "stale-rank",
            lambda value: value["registered_rank_claims"]["tetrahedron_k4"].__setitem__("rank", 5),
            False,
        ),
        (
            "rehashed-rank",
            lambda value: value["registered_rank_claims"]["tetrahedron_k4"].__setitem__("rank", 5),
            True,
        ),
        (
            "rehashed-topology",
            lambda value: value["rigidity_cases"][0]["edges"].pop(),
            True,
        ),
        (
            "rehashed-wls-rank",
            lambda value: value["corrected_wls_controls"].__setitem__("moment_rank", 2),
            True,
        ),
        (
            "rehashed-singular-accepted",
            lambda value: value["corrected_wls_controls"]["singular_control"].__setitem__(
                "inverse_rejected", False
            ),
            True,
        ),
        (
            "rehashed-volume-claim",
            lambda value: value["triple_volume_enrichment"].__setitem__(
                "expected_identity_confirmed", False
            ),
            True,
        ),
        (
            "rehashed-objectivity",
            lambda value: value["objectivity_controls"].__setitem__("all_exact", False),
            True,
        ),
        ("rehashed-seed", lambda value: value.__setitem__("seed", 260829), True),
        ("rehashed-schema", lambda value: value.__setitem__("schema", "wrong"), True),
        ("rehashed-promotion", lambda value: value.__setitem__("promotion_eligible", True), True),
        ("rehashed-extra-field", lambda value: value.__setitem__("unexpected", 1), True),
        ("missing-hash", lambda value: value.pop("result_sha256_before_hash_field"), False),
    )
    with tempfile.TemporaryDirectory(prefix="mls-mechanical-oracle-") as temporary:
        directory = Path(temporary)
        for label, mutation, rehash in mutations:
            require_rejection(
                args.oracle,
                baseline,
                directory,
                label,
                mutation,
                rehash=rehash,
            )

        non_object = directory / "non-object.json"
        non_object.write_text("[]\n", encoding="utf-8")
        result = invoke(args.oracle, non_object)
        diagnostic = f"{result.stdout}\n{result.stderr}"
        if result.returncode == 0 or not any(
            marker in diagnostic for marker in ACCEPTED_FAILURE_MARKERS
        ):
            raise AssertionError("non-object canonical was not rejected cleanly")

    print(
        "mechanical observability exact-oracle regression: PASS "
        f"(2 deterministic positives, {len(mutations) + 1} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
