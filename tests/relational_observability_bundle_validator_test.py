#!/usr/bin/env python3
"""Positive and semantic-mutation regression for the Candidate-C validator."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from typing import Callable


def exercise_direct_svd_regression(validator: pathlib.Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "relational_observability_validator_under_test", validator
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load validator for direct-SVD regression")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    delta = 2.0**-32
    if 1.0 + delta * delta != 1.0:
        raise RuntimeError("normal-equation collapse precondition not reproduced")
    matrix = [
        [Decimal(1), Decimal(1)],
        [Decimal(0), Decimal.from_float(delta)],
    ]
    values, _sweeps, converged = (
        module.independent_binary64_direct_singular_values(matrix, 2)
    )
    upper = 512.0 * 8.0 * 6.0 * sys.float_info.epsilon * values[0]
    if not converged or len(values) != 2 or not values[1] > upper:
        raise RuntimeError("direct SVD erased the Gram-collapse witness")
    zeros, _sweeps, converged = (
        module.independent_binary64_direct_singular_values([], 7)
    )
    if not converged or zeros != (0.0,) * 7:
        raise RuntimeError("direct SVD zero-row structural tail failed")


def run(
    validator: pathlib.Path, bundle: pathlib.Path, expect_success: bool
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--bundle",
            str(bundle),
            "--allow-dirty",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if (completed.returncode == 0) != expect_success:
        raise RuntimeError(
            f"unexpected validator outcome {completed.returncode}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )


def read_csv(path: pathlib.Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        return fields, list(reader)


def write_csv(
    path: pathlib.Path, fields: list[str], rows: list[dict[str, str]]
) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reseal(root: pathlib.Path) -> None:
    """Rehash a mutation so it reaches semantic checks, not just the manifest."""
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    names = set(manifest["file_sha256"])
    names.discard("summary.json")
    summary_path = root / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    hashes_without_summary = {name: sha256(root / name) for name in names}
    summary_preimage = "".join(
        f"{name}={hashes_without_summary[name]}\n"
        for name in sorted(hashes_without_summary)
    ) + f"verdict={summary['verdict']}\n"
    summary["pre_hash_sha256"] = hashlib.sha256(
        summary_preimage.encode("utf-8")
    ).hexdigest()
    summary_path.write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    hashes = {
        name: sha256(root / name)
        for name in manifest["file_sha256"]
    }
    manifest["file_sha256"] = dict(sorted(hashes.items()))
    manifest_preimage = "".join(
        f"{name}={hashes[name]}\n" for name in sorted(hashes)
    )
    manifest["pre_hash_sha256"] = hashlib.sha256(
        manifest_preimage.encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def mutate_csv(
    path: pathlib.Path, mutation: Callable[[list[dict[str, str]]], None]
) -> None:
    fields, rows = read_csv(path)
    if not rows:
        raise RuntimeError(f"cannot mutate empty table {path.name}")
    mutation(rows)
    write_csv(path, fields, rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validator", type=pathlib.Path, required=True)
    parser.add_argument("--bundle", type=pathlib.Path, required=True)
    args = parser.parse_args()
    exercise_direct_svd_regression(args.validator)
    run(args.validator, args.bundle, True)
    run(args.validator, args.bundle, True)
    with tempfile.TemporaryDirectory(prefix="mls-relational-validator-") as temporary:
        root = pathlib.Path(temporary)
        detached_smoke = root / "detached-smoke"
        shutil.copytree(args.bundle, detached_smoke)
        detached_summary_path = detached_smoke / "summary.json"
        detached_summary = json.loads(
            detached_summary_path.read_text(encoding="utf-8")
        )
        detached_manifest_path = detached_smoke / "manifest.json"
        detached_manifest = json.loads(
            detached_manifest_path.read_text(encoding="utf-8")
        )
        detached_summary["branch"] = "HEAD"
        detached_manifest["branch"] = "HEAD"
        detached_summary_path.write_text(
            json.dumps(detached_summary, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        detached_manifest_path.write_text(
            json.dumps(detached_manifest, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        reseal(detached_smoke)
        run(args.validator, detached_smoke, True)
        mutation_names = (
            "rank",
            "spectrum",
            "packet",
            "id_bijection",
            "topology",
            "verdict",
            "candidate_d",
            "inherited_blob",
            "flexible_control",
            "null_vector",
            "finite_length",
            "rank_reference",
            "topology_state",
            "id_metadata",
            "checkpoint",
            "inventory",
            "covariance",
            "contradictory_promotion",
        )
        targets: dict[str, pathlib.Path] = {}
        for name in mutation_names:
            target = root / name
            shutil.copytree(args.bundle, target)
            targets[name] = target

        mutate_csv(
            targets["rank"] / "observability.csv",
            lambda rows: rows[0].__setitem__(
                "qr_rank", str(int(rows[0]["qr_rank"]) + 1)
            ),
        )
        reseal(targets["rank"])

        def change_spectrum(rows: list[dict[str, str]]) -> None:
            for row in rows:
                if float.fromhex(row["singular_value"]) > 0.0:
                    row["singular_value"] = (
                        1.125 * float.fromhex(row["singular_value"])
                    ).hex()
                    return
            raise RuntimeError("no nonzero spectrum entry")

        mutate_csv(targets["spectrum"] / "spectra.csv", change_spectrum)
        reseal(targets["spectrum"])

        mutate_csv(
            targets["packet"] / "packets.csv",
            lambda rows: rows[0].__setitem__(
                "x_m", (float.fromhex(rows[0]["x_m"]) + 0.03125).hex()
            ),
        )
        reseal(targets["packet"])

        def change_bijection(rows: list[dict[str, str]]) -> None:
            row = rows[0]
            row["new_packet_id"] = row["old_packet_id"]

        mutate_csv(
            targets["id_bijection"] / "id_bijections.csv", change_bijection
        )
        reseal(targets["id_bijection"])

        mutate_csv(
            targets["topology"] / "topology_path.csv",
            lambda rows: rows[0].__setitem__(
                "rank", str(int(rows[0]["rank"]) + 1)
            ),
        )
        reseal(targets["topology"])

        summary_path = targets["verdict"] / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["verdict"] = (
            "retain_central_relational_representation_for_research"
            if summary["verdict"] != "retain_central_relational_representation_for_research"
            else "stop_inconclusive_or_implementation_failure"
        )
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        reseal(targets["verdict"])

        summary_path = targets["candidate_d"] / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["candidate_d_instantiated"] = True
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        reseal(targets["candidate_d"])

        summary_path = targets["inherited_blob"] / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        blob_name = sorted(summary["inherited_git_blobs"])[0]
        blob_hash = summary["inherited_git_blobs"][blob_name]
        summary["inherited_git_blobs"][blob_name] = (
            ("0" if blob_hash[0] != "0" else "1") + blob_hash[1:]
        )
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        reseal(targets["inherited_blob"])

        def change_flexible_control(rows: list[dict[str, str]]) -> None:
            for row in rows:
                if row["decision_scope"] == "intentionally_flexible":
                    row["classification"] = "rigid_only"
                    row["decision_gate_pass"] = "false"
                    return
            raise RuntimeError("no intentionally-flexible control row")

        mutate_csv(
            targets["flexible_control"] / "observability.csv",
            change_flexible_control,
        )
        summary_path = targets["flexible_control"] / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["gate_counts"]["pass"] -= 1
        summary["gate_counts"]["fail"] += 1
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        reseal(targets["flexible_control"])

        mutate_csv(
            targets["null_vector"] / "nullspace_vectors.csv",
            lambda rows: rows[0].__setitem__(
                "value", (float.fromhex(rows[0]["value"]) + 2.0**-20).hex()
            ),
        )
        reseal(targets["null_vector"])

        mutate_csv(
            targets["finite_length"] / "metamorphic.csv",
            lambda rows: rows[0].__setitem__("finite_length_residual", (0.25).hex()),
        )
        reseal(targets["finite_length"])

        mutate_csv(
            targets["rank_reference"] / "topology_path.csv",
            lambda rows: rows[0].__setitem__(
                "rank_certified",
                "false" if rows[0]["rank_certified"] == "true" else "true",
            ),
        )
        reseal(targets["rank_reference"])

        def change_topology_state(rows: list[dict[str, str]]) -> None:
            for row in rows:
                if row["configuration_id"].startswith("topology."):
                    row["mass_quanta"] = str(int(row["mass_quanta"]) + 1)
                    return
            raise RuntimeError("no topology packet row")

        mutate_csv(
            targets["topology_state"] / "packets.csv", change_topology_state
        )
        reseal(targets["topology_state"])

        def change_id_metadata(rows: list[dict[str, str]]) -> None:
            for row in rows:
                if row["probe_family"] == "id_bijection":
                    row["decision_scope"] = "non_generic_control"
                    return
            raise RuntimeError("no ID-bijection configuration row")

        mutate_csv(
            targets["id_metadata"] / "configurations.csv", change_id_metadata
        )
        reseal(targets["id_metadata"])

        checkpoint = next((targets["checkpoint"] / "checkpoints").glob("*.bin"))
        payload = bytearray(checkpoint.read_bytes())
        payload[-1] ^= 1
        checkpoint.write_bytes(payload)
        reseal(targets["checkpoint"])

        (targets["inventory"] / "unexpected.txt").write_text("x\n", encoding="utf-8")

        def change_covariance_claim(rows: list[dict[str, str]]) -> None:
            for row in rows:
                if row["control_kind"] == "packet_permutation":
                    # Keep the altered claim safely inside the registered
                    # pass tolerance.  Only independent reconstruction of the
                    # raw operator covariance should reject this mutation.
                    row["operator_covariance_residual"] = (
                        0.5 * float.fromhex(row["tolerance"])
                    ).hex()
                    return
            raise RuntimeError("no packet-permutation covariance control")

        mutate_csv(
            targets["covariance"] / "metamorphic.csv",
            change_covariance_claim,
        )
        reseal(targets["covariance"])

        contradictory_summary_path = (
            targets["contradictory_promotion"] / "summary.json"
        )
        contradictory_summary = json.loads(
            contradictory_summary_path.read_text(encoding="utf-8")
        )
        contradictory_summary["promotion_permitted"] = True
        contradictory_summary_path.write_text(
            json.dumps(contradictory_summary, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        reseal(targets["contradictory_promotion"])

        for name in mutation_names:
            try:
                run(args.validator, targets[name], False)
            except RuntimeError as error:
                raise RuntimeError(f"mutation {name}: {error}") from error
    print(
        "relational observability bundle validator regression: "
        "PASS (18 mutations; direct raw-matrix SVD regression)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
