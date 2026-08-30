#!/usr/bin/env python3
"""Determinism and semantic-mutation regression for the constitutive oracle."""

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
    "CONSTITUTIVE EXPRESSIVITY ORACLE INVALID",
    "CONSTITUTIVE EXPRESSIVITY ORACLE MISMATCH",
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
    target.write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result = invoke(oracle, target)
    if result.returncode == 0:
        raise AssertionError(f"oracle accepted mutation {label}")
    diagnostic = f"{result.stdout}\n{result.stderr}"
    if not any(marker in diagnostic for marker in ACCEPTED_FAILURE_MARKERS):
        raise AssertionError(f"mutation {label} lacked stable rejection marker\n{diagnostic}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--oracle",
        type=Path,
        default=root / "reference" / "constitutive_expressivity_oracle.py",
    )
    parser.add_argument(
        "--canonical",
        type=Path,
        default=root / "tests" / "constitutive_expressivity_oracle.canonical.json",
    )
    args = parser.parse_args()

    first = invoke(args.oracle, args.canonical)
    second = invoke(args.oracle, args.canonical)
    if first.returncode != 0 or second.returncode != 0:
        raise AssertionError(
            "positive oracle verification failed\n"
            f"first:\n{first.stdout}\n{first.stderr}\n"
            f"second:\n{second.stdout}\n{second.stderr}"
        )
    if first.stdout != second.stdout:
        raise AssertionError("oracle output was not deterministic")
    baseline = json.loads(args.canonical.read_text(encoding="utf-8"))
    if json.loads(first.stdout) != baseline:
        raise AssertionError("verified output differs from canonical JSON")

    mutations: tuple[tuple[str, Callable[[dict], None], bool], ...] = (
        (
            "stale-primary-moment",
            lambda value: value["seven_direction_cubature"].__setitem__(
                "second_and_fourth_moments_exact", False
            ),
            False,
        ),
        (
            "rehashed-primary-fourth-moment",
            lambda value: value["seven_direction_cubature"][
                "fourth_moment_nonzero_entries"
            ].__setitem__("0000", "13/1"),
            True,
        ),
        (
            "rehashed-pair-cauchy-ratio",
            lambda value: value["pair_separable_cauchy_control"].__setitem__(
                "K_over_G", "2/1"
            ),
            True,
        ),
        (
            "rehashed-pair-tangent",
            lambda value: value["pair_separable_cauchy_control"][
                "kelvin_tangent_derived_from_extensions"
            ][0].__setitem__(0, "11/1"),
            True,
        ),
        (
            "rehashed-collective-map",
            lambda value: value["local_collective_bulk_shear_controls"].__setitem__(
                "coefficient_map", "A=K, B=G"
            ),
            True,
        ),
        (
            "rehashed-collective-cross-coupling",
            lambda value: value["local_collective_bulk_shear_controls"]["targets"][
                2
            ].__setitem__("volumetric_deviatoric_cross_coupling", "1/1000"),
            True,
        ),
        (
            "rehashed-collective-kelvin-energy",
            lambda value: value["local_collective_bulk_shear_controls"]["targets"][
                3
            ]["kelvin_basis_energies"].__setitem__(5, "2/1"),
            True,
        ),
        (
            "rehashed-secondary-moment",
            lambda value: value["independent_face_diagonal_bulk_control"].__setitem__(
                "total_weight_and_moment_m", "16/1"
            ),
            True,
        ),
        (
            "rehashed-secondary-map",
            lambda value: value["independent_face_diagonal_bulk_control"][
                "collective_identities"
            ].__setitem__("coefficient_map", "A=3K/20, B=G/4"),
            True,
        ),
        (
            "rehashed-secondary-cauchy",
            lambda value: value["independent_face_diagonal_bulk_control"][
                "pair_cauchy_control"
            ].__setitem__("poisson_ratio_3d", "1/3"),
            True,
        ),
        (
            "rehashed-objectivity",
            lambda value: value["finite_length_objectivity_and_dimension"].__setitem__(
                "translation_proper_rotation_invariant_exact", False
            ),
            True,
        ),
        (
            "rehashed-dimension-law",
            lambda value: value["finite_length_objectivity_and_dimension"][
                "scale_controls"
            ]["2/1"].__setitem__("energy_ratio", "2/1"),
            True,
        ),
        (
            "rehashed-id-invariance",
            lambda value: value["finite_length_objectivity_and_dimension"].__setitem__(
                "packet_id_bijections_invariant_exact", False
            ),
            True,
        ),
        (
            "rehashed-graph-kernel",
            lambda value: value["selected_exact_graph_H_kernel_controls"]["graphs"][
                0
            ].__setitem__("rank_R", 5),
            True,
        ),
        (
            "rehashed-locality",
            lambda value: value["selected_exact_graph_H_kernel_controls"]["graphs"][
                2
            ]["collective_targets"][0].__setitem__("H_nonlocal_entries", 1),
            True,
        ),
        (
            "rehashed-floppy-control",
            lambda value: value["selected_exact_graph_H_kernel_controls"].__setitem__(
                "intentionally_floppy_graph_remains_floppy", False
            ),
            True,
        ),
        (
            "rehashed-regularization",
            lambda value: value.__setitem__("numerical_regularization_used", True),
            True,
        ),
        (
            "rehashed-force",
            lambda value: value.__setitem__("force_or_time_integration_present", True),
            True,
        ),
        (
            "rehashed-promotion",
            lambda value: value.__setitem__("candidate_promotion_permitted", True),
            True,
        ),
        ("rehashed-seed", lambda value: value.__setitem__("seed", 260829), True),
        ("rehashed-schema", lambda value: value.__setitem__("schema", "wrong"), True),
        ("rehashed-extra", lambda value: value.__setitem__("unexpected", 1), True),
        ("missing-hash", lambda value: value.pop("result_sha256_before_hash_field"), False),
    )
    with tempfile.TemporaryDirectory(prefix="mls-constitutive-oracle-") as temporary:
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
        "constitutive expressivity exact-oracle regression: PASS "
        f"(2 deterministic positives, {len(mutations) + 1} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
