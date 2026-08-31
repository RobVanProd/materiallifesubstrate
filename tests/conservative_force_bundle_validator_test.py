#!/usr/bin/env python3
"""Two-stage and semantic-mutation regression for force evidence.

Mutated raw bundles are resealed before validation.  Scientific mutations
must materialize to the registered bounded negative decision; structural and
provenance mutations must fail without publishing a partial destination.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Sequence


RAW_SCHEMA = "mls.conservative-force-consistency.raw-manifest.v1"
RAW_FILES = {
    "raw_summary.json", "raw_provenance.json", "configurations.csv",
    "reference_packets.csv", "relations.csv", "operators.csv", "h_matrix.csv",
    "current_packets.csv", "force_evaluations.csv", "relation_forces.csv",
    "packet_forces.csv", "reference_tangent.csv", "finite_tangent.csv",
    "metamorphic.csv", "compression.csv",
}
INVALID = "CONSERVATIVE FORCE BUNDLE INVALID"


def preimage(hashes: dict[str, str]) -> bytes:
    return b"".join(
        name.encode() + b"\0" + hashes[name].encode() + b"\n"
        for name in sorted(hashes)
    )


def reseal_raw(root: Path) -> None:
    hashes = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in sorted(RAW_FILES)
    }
    value = {
        "schema": RAW_SCHEMA,
        "file_sha256": hashes,
        "pre_hash_sha256": hashlib.sha256(preimage(hashes)).hexdigest(),
    }
    (root / "manifest.json").write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def mutate_csv(path: Path, change: Callable[[list[dict[str, str]]], None]) -> None:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        header = list(reader.fieldnames or ())
        rows = list(reader)
    change(rows)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments], check=False, capture_output=True,
        text=True, encoding="utf-8",
    )


def materialize(validator: Path, producer: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return run(
        str(validator), "materialize", "--producer", str(producer),
        "--output", str(output), "--allow-dirty",
    )


def validate(validator: Path, bundle: Path, compare: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [str(validator), "validate", "--bundle", str(bundle), "--allow-dirty"]
    if compare is not None:
        command.extend(("--compare", str(compare)))
    return run(*command)


def require_success(result: subprocess.CompletedProcess[str], marker: str) -> None:
    if result.returncode != 0 or marker not in result.stdout or "NO_PROMOTION" not in result.stdout:
        raise AssertionError(f"command failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")


def copy_mutate(
    source: Path, parent: Path, name: str, mutation: Callable[[Path], None]
) -> Path:
    target = parent / name
    shutil.copytree(source, target)
    mutation(target)
    reseal_raw(target)
    return target


def increment_raw_failures(root: Path, amount: int = 1) -> None:
    path = root / "raw_summary.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["raw_registered_failures"] += amount
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def expect_decision(
    validator: Path, raw: Path, output: Path, decision: str
) -> None:
    result = materialize(validator, raw, output)
    require_success(result, f"decision={decision}")
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    if summary["decision"] != decision or summary["no_promotion"] != "NO_PROMOTION":
        raise AssertionError(f"wrong bounded decision for {output.name}: {summary}")
    require_success(validate(validator, output), f"decision={decision}")


def expect_invalid(
    validator: Path, raw: Path, output: Path, label: str
) -> None:
    rejected = materialize(validator, raw, output)
    if rejected.returncode == 0 or INVALID not in rejected.stderr or output.exists():
        raise AssertionError(
            f"{label} did not fail closed\n"
            f"stdout:\n{rejected.stdout}\nstderr:\n{rejected.stderr}"
        )
    if list(output.parent.glob(f".{output.name}.materialize-*")):
        raise AssertionError(f"{label} left an owned staging directory")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--producer", required=True, type=Path)
    parser.add_argument("--producer-compare", type=Path)
    parser.add_argument("--validator", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    producer = args.producer.resolve()
    validator = args.validator.resolve()
    with tempfile.TemporaryDirectory(prefix="mls-force-validator-") as temporary:
        root = Path(temporary)
        final_a = root / "final-a"
        require_success(materialize(validator, producer, final_a), "CONSERVATIVE FORCE BUNDLE MATERIALIZED")
        require_success(validate(validator, final_a), "CONSERVATIVE FORCE BUNDLE VALID")

        if args.producer_compare is not None:
            final_b = root / "final-b"
            require_success(
                materialize(validator, args.producer_compare.resolve(), final_b),
                "CONSERVATIVE FORCE BUNDLE MATERIALIZED",
            )
            require_success(validate(validator, final_a, final_b), "byte comparison: PASS")

        def wrong_energy(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                row = next(row for row in rows if row["status"] == "valid_noncoincident" and row["probe"] != "reference")
                row["energy_j"] = float(float.fromhex(row["energy_j"]) * 1.5).hex()
            mutate_csv(bundle / "force_evaluations.csv", change)

        energy_raw = copy_mutate(producer, root, "raw-energy", wrong_energy)
        expect_decision(validator, energy_raw, root / "final-energy", "reject_force_implementation")

        def wrong_balance(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                row = next(row for row in rows if row["status"] == "valid_noncoincident")
                row["total_force_x_n"] = float.fromhex("0x1p+0").hex()
                row["pass"] = "false"
            mutate_csv(bundle / "force_evaluations.csv", change)
            increment_raw_failures(bundle)

        force_raw = copy_mutate(producer, root, "raw-force", wrong_balance)
        expect_decision(validator, force_raw, root / "final-force", "reject_force_conservation")

        def wrong_tangent(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                row = rows[0]
                row["force_jacobian_n_per_m"] = float(
                    float.fromhex(row["force_jacobian_n_per_m"]) + 1.0
                ).hex()
            mutate_csv(bundle / "finite_tangent.csv", change)

        tangent_raw = copy_mutate(producer, root, "raw-tangent", wrong_tangent)
        expect_decision(validator, tangent_raw, root / "final-tangent", "reject_finite_force_consistency")

        # The ordered degeneracy branch is independently unit-bound even when
        # the smoke geometry does not naturally exhibit registered collapse.
        sys.path.insert(0, str(validator.parent))
        import validate_conservative_force_bundle as implementation  # type: ignore
        from decimal import Decimal
        if implementation.registered_raw_convergence(
            [Decimal("0"), Decimal("1e100"), Decimal("1e100"), Decimal("1e100")],
            Decimal("1e-55"),
        ):
            raise AssertionError("validator accepted raw error re-emergence after floor")

        # The raw condition diagnostic is independently reproduced with the
        # same ordered-binary64 one-sided-Jacobi transition, rather than being
        # compared directly to the Decimal-100 scientific reference.
        diagonal = [[0.0 for _ in range(6)] for _ in range(6)]
        diagonal[0][0] = 1.0
        diagonal[1][1] = -0.25
        if implementation.binary64_condition_estimate(diagonal) != 4.0:
            raise AssertionError("binary64 signed-spectrum condition self-test")
        threshold = 512.0 * 6.0 * sys.float_info.epsilon
        ambiguous = [[0.0 for _ in range(6)] for _ in range(6)]
        ambiguous[0][0] = 1.0
        ambiguous[1][1] = threshold
        if implementation.binary64_condition_estimate(ambiguous) is not None:
            raise AssertionError("binary64 ambiguity-band condition self-test")
        below_band = [[0.0 for _ in range(6)] for _ in range(6)]
        below_band[0][0] = 1.0
        below_band[1][1] = threshold / 16.0
        if implementation.binary64_condition_estimate(below_band) != 1.0:
            raise AssertionError("binary64 null-tail condition self-test")
        above_band = [[0.0 for _ in range(6)] for _ in range(6)]
        above_band[0][0] = 1.0
        above_band[1][1] = 16.0 * threshold
        expected_above = 1.0 / (16.0 * threshold)
        if implementation.binary64_condition_estimate(above_band) != expected_above:
            raise AssertionError("binary64 resolved-tail condition self-test")
        if implementation.condition_reference_agreement(4.0, None):
            raise AssertionError("condition classifier disagreement was accepted")
        if not implementation.condition_reference_agreement(
            4.0, Decimal("4.000001")
        ):
            raise AssertionError("resolved condition distance became a hidden gate")

        # A mostly rigid vector can still lie in the K4-minus-edge rigidity
        # kernel.  The registered floppy control must be the unit mechanism
        # orthogonal to all six realized rigid modes, not merely contain some
        # non-rigid component.
        floppy_audit = implementation.Audit()
        implementation.validate_raw_metadata(
            producer, allow_dirty=True, audit=floppy_audit
        )
        floppy_configurations = implementation.parse_configurations(
            producer, floppy_audit
        )
        floppy_operators = implementation.parse_operators(
            producer, floppy_configurations, floppy_audit
        )
        floppy_payloads, _floppy_relations, _floppy_forces = (
            implementation.parse_evaluation_payloads(
                producer,
                floppy_configurations,
                floppy_operators,
                floppy_audit,
            )
        )
        floppy_payload = floppy_payloads[
            "exact.tetrahedron_k4_minus_edge.collective.one_third.reference.zero"
        ]
        packet_ids = floppy_payload.model.packet_ids
        rigid_basis = implementation.realized_rigid_basis(
            floppy_payload.model, floppy_audit, "floppy mutation fixture"
        )
        seed = [Decimal(0)] * (3 * len(packet_ids))
        seed[3 * packet_ids.index(3) + 2] = Decimal(1)
        mechanism = list(seed)
        for basis in rigid_basis:
            coefficient = implementation.dot(mechanism, basis)
            mechanism = [
                value - coefficient * basis_value
                for value, basis_value in zip(mechanism, basis, strict=True)
            ]
        mechanism_norm = implementation.norm(mechanism)
        mechanism = [value / mechanism_norm for value in mechanism]
        implementation.validate_floppy_direction(
            floppy_payload,
            implementation.unflatten(mechanism, packet_ids),
            floppy_audit,
        )
        # The preregistered floppy tangent has an exactly-zero linear target
        # and uses a componentwise infinity norm.  It must not silently drift
        # back to the producer's former per-packet Euclidean diagnostic.
        characteristic = max(
            float(value) for value in floppy_payload.model.reference_lengths
        )
        floppy_epsilon = (2.0 ** -8) * characteristic
        floppy_current = {}
        for packet_index, packet_id in enumerate(packet_ids):
            reference = floppy_payload.model.reference[packet_id]
            floppy_current[packet_id] = tuple(
                Decimal.from_float(
                    float(reference[axis])
                    + floppy_epsilon * float(mechanism[3 * packet_index + axis])
                )
                for axis in range(3)
            )
        parent_h_scale = max(
            abs(float(value))
            for row in floppy_payload.operator.parent_h
            for value in row
        )
        reproduced_floppy = implementation.binary64_floppy_tangent_error(
            floppy_payload.model,
            floppy_current,
            floppy_epsilon,
            parent_h_scale,
        )
        floppy_force = implementation.binary64_evaluate(
            floppy_payload.model, floppy_current
        ).forces
        expected_infinity = max(
            abs(component) / floppy_epsilon
            for packet_id in packet_ids
            for component in floppy_force[packet_id]
        ) / parent_h_scale
        former_euclidean = max(
            sum(component * component for component in floppy_force[packet_id])
            ** 0.5
            / floppy_epsilon
            for packet_id in packet_ids
        ) / parent_h_scale
        if reproduced_floppy != expected_infinity:
            raise AssertionError("floppy tangent is not the registered infinity norm")
        if reproduced_floppy == former_euclidean:
            raise AssertionError("floppy tangent regressed to per-packet Euclidean norm")
        high_precision_floppy = (
            implementation.high_precision_floppy_tangent_error(
                floppy_payload.model,
                floppy_current,
                floppy_payload.operator.parent_h,
                Decimal.from_float(floppy_epsilon),
            )
        )
        with implementation.localcontext() as context:
            context.prec = implementation.DIGITS
            high_precision_actual = [
                value / Decimal.from_float(floppy_epsilon)
                for value in implementation.force_vector(
                    floppy_payload.model, floppy_current
                )
            ]
            high_precision_scale = max(
                implementation.max_abs(
                    value
                    for row in floppy_payload.operator.parent_h
                    for value in row
                ),
                implementation.TINY64,
            )
            exact_zero_target_error = (
                implementation.max_abs(high_precision_actual)
                / high_precision_scale
            )
        if high_precision_floppy != exact_zero_target_error:
            raise AssertionError(
                "Decimal floppy tangent did not use the registered exact zero target"
            )
        rigid_weight = Decimal(15).sqrt() / Decimal(4)
        mostly_rigid = [
            Decimal("0.25") * mechanism_value + rigid_weight * rigid_value
            for mechanism_value, rigid_value in zip(
                mechanism, rigid_basis[0], strict=True
            )
        ]
        try:
            implementation.validate_floppy_direction(
                floppy_payload,
                implementation.unflatten(mostly_rigid, packet_ids),
                implementation.Audit(),
            )
        except implementation.ValidationError:
            pass
        else:
            raise AssertionError("mostly-rigid kernel mode passed floppy gate")

        finding = implementation.ScientificFindings()
        finding.degeneracy(False)
        if finding.decision() != "retain_force_but_block_dynamics_on_degeneracy":
            raise AssertionError("degeneracy decision order regression")
        finding.inconclusive(False, "synthetic_raw_nonconvergence")
        if finding.decision() != "stop_inconclusive_or_implementation_failure":
            raise AssertionError("inconclusive decision precedence regression")

        # Exercise an authenticated producer bundle through the independent
        # inconclusive outcome.  The injected predicate represents a detected
        # raw-convergence ambiguity; no producer row or provenance is made
        # malformed, and the ordinary positive path above remains unpatched.
        inconclusive_output = root / "final-inconclusive"
        original_convergence = implementation.registered_raw_convergence
        implementation.registered_raw_convergence = lambda _errors, _floor: False
        try:
            _checks, _pre_hash, inconclusive_decision = implementation.materialize(
                producer, inconclusive_output, allow_dirty=True
            )
            if inconclusive_decision != "stop_inconclusive_or_implementation_failure":
                raise AssertionError("valid raw nonconvergence did not seal inconclusive")
            inconclusive_summary = json.loads(
                (inconclusive_output / "summary.json").read_text(encoding="utf-8")
            )
            if (
                inconclusive_summary["inconclusive_failure_events"] <= 0
                or not inconclusive_summary["inconclusive_reasons"]
                or inconclusive_summary["all_registered_noncoincident_cases_passed"]
            ):
                raise AssertionError("inconclusive summary was not explicit")
        finally:
            implementation.registered_raw_convergence = original_convergence

        # A structurally authentic raw binary64 condition can disagree with
        # the independent Decimal classifier.  That is registered degeneracy
        # evidence, not malformed-bundle rejection.  Patch only the independent
        # classifier to exercise the ordered decision through materialization.
        classification_output = root / "final-condition-classification"
        original_condition = implementation.independent_condition_estimate
        implementation.independent_condition_estimate = (
            lambda _matrix, _dimension: None
        )
        try:
            _checks, _pre_hash, classification_decision = (
                implementation.materialize(
                    producer, classification_output, allow_dirty=True
                )
            )
            if classification_decision != (
                "retain_force_but_block_dynamics_on_degeneracy"
            ):
                raise AssertionError(
                    "classifier disagreement did not seal as degeneracy"
                )
            classification_summary = json.loads(
                (classification_output / "summary.json").read_text(
                    encoding="utf-8"
                )
            )
            if (
                classification_summary["degeneracy_failure_events"] <= 0
                or classification_summary[
                    "all_registered_noncoincident_cases_passed"
                ]
            ):
                raise AssertionError(
                    "classifier disagreement was not explicit in summary"
                )
        finally:
            implementation.independent_condition_estimate = original_condition

        def corrupt_order(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                rows[0]["observed_order"] = float(
                    float.fromhex(rows[0]["observed_order"]) + 1.0
                ).hex()
            mutate_csv(bundle / "reference_tangent.csv", change)

        invalid_raw = copy_mutate(producer, root, "raw-invalid", corrupt_order)
        expect_invalid(
            validator, invalid_raw, root / "must-not-publish", "observed-order mutation"
        )

        structural_mutations: tuple[
            tuple[str, Callable[[Path], None]], ...
        ] = (
            (
                "omitted-evaluation",
                lambda bundle: mutate_csv(
                    bundle / "force_evaluations.csv", lambda rows: rows.pop(0)
                ),
            ),
            (
                "base-coordinate",
                lambda bundle: mutate_csv(
                    bundle / "current_packets.csv",
                    lambda rows: rows[0].__setitem__(
                        "x_m", float(float.fromhex(rows[0]["x_m"]) + 0.125).hex()
                    ),
                ),
            ),
            (
                "velocity-substitution",
                lambda bundle: mutate_csv(
                    bundle / "current_packets.csv",
                    lambda rows: next(
                        row for row in rows if ".direction." in row["evaluation_id"]
                    ).__setitem__("vx_m_per_s", "0x0.0p+0"),
                ),
            ),
            (
                "metamorphic-h-digest",
                lambda bundle: mutate_csv(
                    bundle / "metamorphic.csv",
                    lambda rows: rows[0].__setitem__("transformed_h_sha256", "0" * 64),
                ),
            ),
            (
                "ratio-tolerance",
                lambda bundle: mutate_csv(
                    bundle / "metamorphic.csv",
                    lambda rows: rows[0].__setitem__(
                        "scaling_ratio_tolerance",
                        float(2.0 * float.fromhex(rows[0]["scaling_ratio_tolerance"])).hex(),
                    ),
                ),
            ),
            (
                "shifted-torque-scale",
                lambda bundle: mutate_csv(
                    bundle / "force_evaluations.csv",
                    lambda rows: next(
                        row for row in rows if row["status"] == "valid_noncoincident"
                    ).__setitem__("balance_scale_torque_nm", "0x1.0000000000000p+0"),
                ),
            ),
            (
                "combined-power-scale",
                lambda bundle: mutate_csv(
                    bundle / "force_evaluations.csv",
                    lambda rows: next(
                        row for row in rows if row["status"] == "valid_noncoincident"
                    ).__setitem__("balance_scale_power_w", "0x1.0000000000000p+0"),
                ),
            ),
            (
                "binary64-condition-value",
                lambda bundle: mutate_csv(
                    bundle / "compression.csv",
                    lambda rows: next(
                        row for row in rows
                        if row["condition_estimate"] != "unresolved"
                    ).__setitem__(
                        "condition_estimate",
                        float(
                            2.0 * float.fromhex(next(
                                row for row in rows
                                if row["condition_estimate"] != "unresolved"
                            )["condition_estimate"])
                        ).hex(),
                    ),
                ),
            ),
            (
                "binary64-condition-classification",
                lambda bundle: mutate_csv(
                    bundle / "compression.csv",
                    lambda rows: next(
                        row for row in rows
                        if row["condition_estimate"] != "unresolved"
                    ).__setitem__("condition_estimate", "unresolved"),
                ),
            ),
            (
                "compression-other-packet",
                lambda bundle: mutate_csv(
                    bundle / "current_packets.csv",
                    lambda rows: next(
                        row for row in rows
                        if ".compression.1" in row["evaluation_id"]
                        and row["packet_index"] == "2"
                    ).__setitem__(
                        "z_m",
                        float(float.fromhex(next(
                            row for row in rows
                            if ".compression.1" in row["evaluation_id"]
                            and row["packet_index"] == "2"
                        )["z_m"]) + 0.25).hex(),
                    ),
                ),
            ),
        )
        for label, mutation in structural_mutations:
            raw = copy_mutate(producer, root, f"raw-{label}", mutation)
            expect_invalid(validator, raw, root / f"invalid-{label}", label)

    print("conservative force two-stage validator regression: PASS")
    print("NO_PROMOTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
