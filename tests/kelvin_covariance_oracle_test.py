#!/usr/bin/env python3
"""Determinism and semantic-mutation regression for the Kelvin oracle."""

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
    "KELVIN COVARIANCE ORACLE INVALID",
    "KELVIN COVARIANCE ORACLE MISMATCH",
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
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--oracle",
        type=Path,
        default=root / "reference" / "kelvin_covariance_oracle.py",
    )
    parser.add_argument(
        "--canonical",
        type=Path,
        default=root / "tests" / "kelvin_covariance_oracle.canonical.json",
    )
    args = parser.parse_args()

    first = invoke(args.oracle, args.canonical)
    second = invoke(args.oracle, args.canonical)
    if first.returncode != 0 or second.returncode != 0:
        raise AssertionError(
            "positive oracle verification failed\n"
            f"first:\n{first.stdout}\n{first.stderr}\nsecond:\n{second.stdout}\n{second.stderr}"
        )
    if first.stdout != second.stdout:
        raise AssertionError("oracle output was not deterministic")
    baseline = json.loads(args.canonical.read_text(encoding="utf-8"))
    if json.loads(first.stdout) != baseline:
        raise AssertionError("verified output differs from canonical JSON")

    mutations: tuple[tuple[str, Callable[[dict], None], bool], ...] = (
        (
            "stale-raw-identity",
            lambda value: value["raw_covariance"].__setitem__("operator_identity_exact", False),
            False,
        ),
        (
            "rehashed-raw-spectrum",
            lambda value: value["raw_covariance"].__setitem__(
                "singular_values_scale_as_inverse_length", False
            ),
            True,
        ),
        (
            "rehashed-counterexample",
            lambda value: value["scalar_row_normalization_counterexample"].__setitem__(
                "counterexample_confirmed", False
            ),
            True,
        ),
        (
            "rehashed-counterexample-difference",
            lambda value: value["scalar_row_normalization_counterexample"].__setitem__(
                "exact_nonzero_difference",
                {"rational": "0/1", "sqrt2_coefficient": "0/1"},
            ),
            True,
        ),
        (
            "rehashed-block-normalization",
            lambda value: value["rotationally_invariant_block_scalar_diagnostic"].__setitem__(
                "normalized_gram_similarity_exact", False
            ),
            True,
        ),
        (
            "rehashed-promotion",
            lambda value: value.__setitem__("candidate_promotion_permitted", True),
            True,
        ),
        ("rehashed-seed", lambda value: value.__setitem__("seed", 260829), True),
        ("rehashed-schema", lambda value: value.__setitem__("schema", "wrong"), True),
        ("rehashed-extra-field", lambda value: value.__setitem__("unexpected", 1), True),
        ("missing-hash", lambda value: value.pop("result_sha256_before_hash_field"), False),
    )
    with tempfile.TemporaryDirectory(prefix="mls-kelvin-oracle-") as temporary:
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
        "kelvin covariance exact-oracle regression: PASS "
        f"(2 deterministic positives, {len(mutations) + 1} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
