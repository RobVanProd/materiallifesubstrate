#!/usr/bin/env python3
"""Determinism and semantic-mutation regression for the force oracle."""

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


MARKERS = (
    "CONSERVATIVE FORCE ORACLE INVALID",
    "CONSERVATIVE FORCE ORACLE MISMATCH",
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
        timeout=180,
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
    completed = invoke(oracle, target)
    diagnostic = f"{completed.stdout}\n{completed.stderr}"
    if completed.returncode == 0:
        raise AssertionError(f"oracle accepted mutation {label}")
    if not any(marker in diagnostic for marker in MARKERS):
        raise AssertionError(f"mutation {label} lacked stable marker\n{diagnostic}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--oracle",
        type=Path,
        default=root / "reference" / "conservative_force_oracle.py",
    )
    parser.add_argument(
        "--canonical",
        type=Path,
        default=root / "tests" / "conservative_force_oracle.canonical.json",
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
        raise AssertionError("verified oracle differs from canonical JSON")
    sys.path.insert(0, str(args.oracle.resolve().parent))
    import conservative_force_oracle as oracle_implementation  # type: ignore
    from decimal import Decimal
    if oracle_implementation.registered_raw_convergence(
        [Decimal("1e-10"), Decimal("1e-9"), Decimal("1e-8"), Decimal("1e-60")],
        Decimal("1e-55"),
    ):
        raise AssertionError("late floor arrival hid earlier raw-error growth")
    if not oracle_implementation.registered_raw_convergence(
        [Decimal("1e-10"), Decimal("1e-20"), Decimal("1e-60"), Decimal("1e-58")],
        Decimal("1e-55"),
    ):
        raise AssertionError("registered floor arrival did not terminate ordering")
    if oracle_implementation.registered_raw_convergence(
        [Decimal("0"), Decimal("1e100"), Decimal("1e100"), Decimal("1e100")],
        Decimal("1e-55"),
    ):
        raise AssertionError("raw error re-emergence after floor was accepted")

    mutations: tuple[tuple[str, Callable[[dict], None], bool], ...] = (
        ("stale-hash", lambda value: value.__setitem__("seed", 260829), False),
        ("schema", lambda value: value.__setitem__("schema", "wrong"), True),
        (
            "analytic-sign",
            lambda value: value.__setitem__(
                "analytic_force", "f=+gradient(U)"
            ),
            True,
        ),
        (
            "raw-derivative",
            lambda value: value["collective_policy_controls"][0][
                "directional_derivatives"
            ][0]["raw"][0].__setitem__("centered_dU", "0"),
            True,
        ),
        (
            "extrapolated-derivative",
            lambda value: value["collective_policy_controls"][1][
                "directional_derivatives"
            ][2].__setitem__("extrapolated_dU", "0"),
            True,
        ),
        (
            "torque",
            lambda value: value["collective_policy_controls"][2].__setitem__(
                "maximum_total_torque_origin_nm", "1E-2"
            ),
            True,
        ),
        (
            "power",
            lambda value: value["collective_policy_controls"][0].__setitem__(
                "power_residual_w", "1"
            ),
            True,
        ),
        (
            "force-covariance",
            lambda value: value["collective_policy_controls"][0].__setitem__(
                "objective_force_residual_n", "1"
            ),
            True,
        ),
        (
            "scale-law",
            lambda value: value["collective_policy_controls"][0][
                "scale_controls"
            ][1].__setitem__("energy_ratio", "2"),
            True,
        ),
        (
            "geometric-term",
            lambda value: value["collective_policy_controls"][0].__setitem__(
                "geometric_hessian_norm_n_per_m", "0"
            ),
            True,
        ),
        (
            "tangent-symmetry",
            lambda value: value["collective_policy_controls"][2].__setitem__(
                "force_jacobian_symmetry_residual_n_per_m", "1"
            ),
            True,
        ),
        (
            "reference-limit",
            lambda value: value["collective_policy_controls"][1][
                "reference_tangent_limit"
            ][0].__setitem__("minimum_relative_error", "1"),
            True,
        ),
        (
            "collapse-floor",
            lambda value: value["coincident_relation_approach"]["rows"][8].__setitem__(
                "registered_domain_row", False
            ),
            True,
        ),
        (
            "coincidence",
            lambda value: value["coincident_relation_approach"].__setitem__(
                "exact_coincidence_failed_closed", False
            ),
            True,
        ),
        (
            "hidden-repulsion",
            lambda value: value["coincident_relation_approach"].__setitem__(
                "epsilon_normalization_or_hidden_repulsion_used", True
            ),
            True,
        ),
        (
            "integration",
            lambda value: value.__setitem__("time_integration_present", True),
            True,
        ),
        (
            "promotion",
            lambda value: value.__setitem__("candidate_promotion_permitted", True),
            True,
        ),
        ("extra-field", lambda value: value.__setitem__("unexpected", 1), True),
        (
            "missing-hash",
            lambda value: value.pop("result_sha256_before_hash_field"),
            False,
        ),
    )
    with tempfile.TemporaryDirectory(prefix="mls-force-oracle-") as temporary:
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
        completed = invoke(args.oracle, non_object)
        diagnostic = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode == 0 or not any(
            marker in diagnostic for marker in MARKERS
        ):
            raise AssertionError("non-object canonical was not rejected cleanly")

    print(
        "conservative force high-precision oracle regression: PASS "
        f"(2 deterministic positives, {len(mutations) + 1} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
