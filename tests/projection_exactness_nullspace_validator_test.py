#!/usr/bin/env python3
"""Positive and re-manifested mutation tests for the nullspace validator."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Callable, Sequence


MANIFEST_SCHEMA = "mls.projection-exactness-nullspace.manifest.v1"
CSV_FILES = (
    "systems.csv", "particles.csv", "nodes.csv", "stencils.csv", "matrix.csv",
    "rhs.csv", "witness.csv", "solve_diagnostics.csv", "high_precision.csv",
    "high_precision_pivots.csv", "nullspace_modes.csv", "nullspace_status.csv",
    "nullspace_metrics.csv",
)
FILES = (*CSV_FILES, "summary.json")
RAW_FILES = ("particles.csv", "nodes.csv", "stencils.csv", "matrix.csv", "rhs.csv")
INVALID = "PROJECTION EXACTNESS NULLSPACE BUNDLE INVALID"


def manifest_payload(hashes: dict[str, str]) -> bytes:
    lines = ["{", '  "algorithm": "SHA-256",', '  "files": {']
    names = sorted(hashes)
    for index, name in enumerate(names):
        comma = "," if index + 1 < len(names) else ""
        lines.append(f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}")
    lines.extend(("  },", f'  "schema": {json.dumps(MANIFEST_SCHEMA)}', "}"))
    return "\n".join(lines).encode()


def refresh_manifest(bundle: Path) -> None:
    hashes = {name: hashlib.sha256((bundle / name).read_bytes()).hexdigest() for name in FILES}
    value = {
        "algorithm": "SHA-256", "files": hashes, "schema": MANIFEST_SCHEMA,
        "pre_hash_sha256": hashlib.sha256(manifest_payload(hashes)).hexdigest(),
    }
    (bundle / "manifest.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def refresh_summary_counts(bundle: Path) -> None:
    value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
    value["row_counts"] = {
        name: len(read_rows(bundle / name)[1]) for name in CSV_FILES
    }
    (bundle / "summary.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_validator(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "projection_exactness_nullspace_validator_under_test", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import validator {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or ()), list(reader)


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def mutate_row(bundle: Path, name: str, change: Callable[[dict[str, str]], None]) -> None:
    fields, rows = read_rows(bundle / name)
    if not rows:
        raise AssertionError(f"empty mutation table {name}")
    change(rows[0])
    write_rows(bundle / name, fields, rows)


def refresh_assembly_digest(bundle: Path, system_id: str) -> None:
    digest = hashlib.sha256()
    digest.update(b"MLS-PROJECTION-EXACTNESS-ASSEMBLY-v1\n")
    for name in RAW_FILES:
        fields, rows = read_rows(bundle / name)
        for row in rows:
            if row["system_id"] != system_id:
                continue
            digest.update(name.encode("ascii"))
            for field in fields:
                digest.update(b"\0")
                digest.update(row[field].encode())
            digest.update(b"\n")
    fields, rows = read_rows(bundle / "systems.csv")
    for row in rows:
        if row["system_id"] == system_id:
            row["assembly_payload_sha256"] = digest.hexdigest()
    write_rows(bundle / "systems.csv", fields, rows)


def run_validator(validator: Path, bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(validator), "--bundle", str(bundle), "--oracle-fixture"],
        check=False, capture_output=True, text=True, encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--oracle", type=Path, default=root / "reference/projection_exactness_nullspace_oracle.py")
    parser.add_argument("--validator", type=Path, default=root / "reference/validate_projection_exactness_nullspace_bundle.py")
    args = parser.parse_args(argv)
    mutations = 0
    positives = 0
    with tempfile.TemporaryDirectory(prefix="mls-nullspace-validator-") as temporary:
        base = Path(temporary) / "base"
        subprocess.run([sys.executable, str(args.oracle), "--write-fixture", str(base)], check=True, capture_output=True, text=True)
        positive = run_validator(args.validator, base)
        if positive.returncode != 0:
            raise AssertionError(f"positive fixture rejected\n{positive.stdout}\n{positive.stderr}")
        positives += 1

        def reject(name: str, mutation: Callable[[Path], None], *, refresh: bool = True) -> None:
            nonlocal mutations
            target = Path(temporary) / name
            shutil.copytree(base, target)
            mutation(target)
            if refresh:
                refresh_manifest(target)
            result = run_validator(args.validator, target)
            if result.returncode == 0 or INVALID not in result.stderr:
                raise AssertionError(f"mutation {name} accepted\n{result.stdout}\n{result.stderr}")
            mutations += 1

        def matrix_semantic(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "matrix.csv")
            rows[0]["value_kg"] = (float.fromhex(rows[0]["value_kg"]) * 1.25).hex()
            sid = rows[0]["system_id"]
            write_rows(bundle / "matrix.csv", fields, rows)
            refresh_assembly_digest(bundle, sid)

        reject("matrix-semantic", matrix_semantic)

        def rhs_semantic(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "rhs.csv")
            rows[0]["value_kg_m_per_s"] = (
                float.fromhex(rows[0]["value_kg_m_per_s"]) + 0.25).hex()
            sid = rows[0]["system_id"]
            write_rows(bundle / "rhs.csv", fields, rows)
            refresh_assembly_digest(bundle, sid)

        reject("rhs-semantic", rhs_semantic)
        reject("witness-pass", lambda b: mutate_row(b, "witness.csv", lambda r: r.__setitem__("pass", "false")))
        reject("solve-forward", lambda b: mutate_row(b, "solve_diagnostics.csv", lambda r: r.__setitem__("normalized_forward_error", "1e+0")))
        reject(
            "noncanonical-decimal",
            lambda b: mutate_row(
                b, "high_precision.csv",
                lambda r: r.__setitem__("pivot_threshold_relative", "1e80")),
        )
        reject("hp-promotion", lambda b: mutate_row(b, "high_precision.csv", lambda r: r.__setitem__("promotion_eligible", "true")))
        reject("null-mode", lambda b: mutate_row(b, "nullspace_modes.csv", lambda r: r.__setitem__("z_value_m_per_s", "0x1.8p+0")))
        reject("null-visible", lambda b: mutate_row(b, "nullspace_metrics.csv", lambda r: r.__setitem__("gradient_visible", "false")))

        def missing_null_mode(bundle: Path) -> None:
            mode_fields, mode_rows = read_rows(bundle / "nullspace_modes.csv")
            metric_fields, metric_rows = read_rows(bundle / "nullspace_metrics.csv")
            removed = max(int(row["mode_index"]) for row in metric_rows)
            write_rows(
                bundle / "nullspace_modes.csv", mode_fields,
                [row for row in mode_rows if int(row["mode_index"]) != removed],
            )
            write_rows(
                bundle / "nullspace_metrics.csv", metric_fields,
                [row for row in metric_rows if int(row["mode_index"]) != removed],
            )
            refresh_summary_counts(bundle)

        reject("missing-null-mode", missing_null_mode)

        def forged_rank_and_cardinality(bundle: Path) -> None:
            mode_fields, mode_rows = read_rows(bundle / "nullspace_modes.csv")
            metric_fields, metric_rows = read_rows(bundle / "nullspace_metrics.csv")
            removed = max(int(row["mode_index"]) for row in metric_rows)
            write_rows(
                bundle / "nullspace_modes.csv", mode_fields,
                [row for row in mode_rows if int(row["mode_index"]) != removed],
            )
            retained_metrics = [
                row for row in metric_rows if int(row["mode_index"]) != removed
            ]
            for row in retained_metrics:
                row["rank"] = str(int(row["rank"]) + 1)
            write_rows(bundle / "nullspace_metrics.csv", metric_fields, retained_metrics)
            status_fields, status_rows = read_rows(bundle / "nullspace_status.csv")
            status_rows[0]["threshold_rank"] = str(
                int(status_rows[0]["threshold_rank"]) + 1)
            status_rows[0]["nullity"] = str(int(status_rows[0]["nullity"]) - 1)
            status_rows[0]["constructed_mode_count"] = str(
                int(status_rows[0]["constructed_mode_count"]) - 1)
            write_rows(bundle / "nullspace_status.csv", status_fields, status_rows)
            refresh_summary_counts(bundle)

        reject("forged-null-rank-cardinality", forged_rank_and_cardinality)

        def zero_alpha_coherent_shift(bundle: Path) -> None:
            mode_fields, mode_rows = read_rows(bundle / "nullspace_modes.csv")
            for row in mode_rows:
                if row["mode_index"] == "0":
                    row["shifted_value_m_per_s"] = row["representative_value_m_per_s"]
            write_rows(bundle / "nullspace_modes.csv", mode_fields, mode_rows)
            metric_fields, metric_rows = read_rows(bundle / "nullspace_metrics.csv")
            metric = next(row for row in metric_rows if row["mode_index"] == "0")
            metric["alpha_dimensionless"] = "0x0.0p+0"
            metric["shifted_residual_normalized"] = metric["base_residual_normalized"]
            metric["residual_change_l2_kg_m_per_s"] = "0e+0"
            metric["residual_change_normalized"] = "0e+0"
            metric["reconstruction_delta_normalized"] = "0e+0"
            write_rows(bundle / "nullspace_metrics.csv", metric_fields, metric_rows)

        reject("zero-null-alpha", zero_alpha_coherent_shift)
        reject(
            "null-residual-change",
            lambda b: mutate_row(
                b, "nullspace_metrics.csv",
                lambda r: r.__setitem__("residual_change_normalized", "1e+0")),
        )

        def node_grid_index(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "nodes.csv")
            rows[0]["grid_i"] = str(int(rows[0]["grid_i"]) + 1)
            sid = rows[0]["system_id"]
            write_rows(bundle / "nodes.csv", fields, rows)
            refresh_assembly_digest(bundle, sid)

        reject("node-grid-coordinate", node_grid_index)

        def analytic_gradient(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "stencils.csv")
            pair: tuple[int, int] | None = None
            for left in range(len(rows)):
                for right in range(left + 1, len(rows)):
                    if (rows[left]["system_id"] == rows[right]["system_id"]
                            and rows[left]["particle_index"] == rows[right]["particle_index"]
                            and rows[left]["grad_x_per_m"] != rows[right]["grad_x_per_m"]):
                        pair = (left, right)
                        break
                if pair is not None:
                    break
            if pair is None:
                raise AssertionError("no distinct same-particle gradients")
            left, right = pair
            rows[left]["grad_x_per_m"], rows[right]["grad_x_per_m"] = (
                rows[right]["grad_x_per_m"], rows[left]["grad_x_per_m"])
            sid = rows[left]["system_id"]
            write_rows(bundle / "stencils.csv", fields, rows)
            refresh_assembly_digest(bundle, sid)

        reject("analytic-gradient", analytic_gradient)

        def unavailable_node_value(bundle: Path, prefix: str) -> None:
            fields, rows = read_rows(bundle / "nodes.csv")
            row = next(item for item in rows if item[f"{prefix}_available"] == "false")
            row[f"{prefix}_vhat_x_m_per_s"] = "0x0.0p+0" if prefix == "pcg" else "0e+0"
            sid = row["system_id"]
            write_rows(bundle / "nodes.csv", fields, rows)
            refresh_assembly_digest(bundle, sid)

        reject("unavailable-pcg-node-value", lambda b: unavailable_node_value(b, "pcg"))
        reject("unavailable-hp-node-value", lambda b: unavailable_node_value(b, "hp"))

        def failed_pcg_metric(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "solve_diagnostics.csv")
            row = next(item for item in rows if item["status"] != "solved")
            row["backward_residual_l2_kg_m_per_s"] = "0x0.0p+0"
            write_rows(bundle / "solve_diagnostics.csv", fields, rows)

        reject("failed-pcg-solution-metric", failed_pcg_metric)

        def solved_accuracy_classification(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "solve_diagnostics.csv")
            row = next(item for item in rows if item["status"] == "solved")
            row["accuracy_classification"] = (
                "backward_and_forward_pass"
                if row["accuracy_classification"] == "backward_pass_forward_fail"
                else "backward_pass_forward_fail"
            )
            write_rows(bundle / "solve_diagnostics.csv", fields, rows)

        reject("pcg-accuracy-classification", solved_accuracy_classification)
        reject(
            "legacy-pcg-threshold",
            lambda b: mutate_row(
                b, "solve_diagnostics.csv",
                lambda r: r.__setitem__(
                    "legacy_normalized_residual_threshold", float(1e-11).hex())),
        )

        def legacy_residual_pair(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "solve_diagnostics.csv")
            row = next(item for item in rows if item["legacy_residual_applicable"] == "true")
            row["legacy_residual_applicable"] = "false"
            write_rows(bundle / "solve_diagnostics.csv", fields, rows)

        reject("legacy-pcg-residual-pair", legacy_residual_pair)

        def repeated_vector_sg(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "witness.csv")
            sid = rows[0]["system_id"]
            row = next(item for item in rows if item["system_id"] == sid and item["component"] == "1")
            row["sg_minus_v_l2_m_per_s_sqrt_kg"] = format(
                Decimal(row["sg_minus_v_l2_m_per_s_sqrt_kg"]) * 2, "e")
            row["sgv_denominator_m_per_s_sqrt_kg"] = format(
                Decimal(row["sgv_denominator_m_per_s_sqrt_kg"]) * 2, "e")
            write_rows(bundle / "witness.csv", fields, rows)

        reject("vector-sg-repeat", repeated_vector_sg)

        def noncanonical_hex(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "particles.csv")
            value = float.fromhex(rows[0]["mass_kg"])
            rows[0]["mass_kg"] = "0x1p+0" if value == 1.0 else "0x1p-1"
            sid = rows[0]["system_id"]
            write_rows(bundle / "particles.csv", fields, rows)
            refresh_assembly_digest(bundle, sid)

        reject("noncanonical-binary64", noncanonical_hex)

        reject(
            "hp-condition-provenance",
            lambda b: mutate_row(
                b, "high_precision.csv",
                lambda r: r.__setitem__(
                    "condition_kind", "high_precision_pivot_ratio_estimate")),
        )

        def pivot_trace(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "high_precision_pivots.csv")
            rows[0]["original_row_index"] = str(
                (int(rows[0]["original_row_index"]) + 1) % 27)
            write_rows(bundle / "high_precision_pivots.csv", fields, rows)

        reject("hp-pivot-trace", pivot_trace)
        reject(
            "hp-component-metadata",
            lambda b: mutate_row(
                b, "high_precision.csv",
                lambda r: r.__setitem__("decimal_digits", "41")),
        )
        reject(
            "null-status-count",
            lambda b: mutate_row(
                b, "nullspace_status.csv",
                lambda r: r.__setitem__(
                    "constructed_mode_count", str(int(r["constructed_mode_count"]) - 1))),
        )
        reject(
            "null-status-basis-complete",
            lambda b: mutate_row(
                b, "nullspace_status.csv",
                lambda r: r.__setitem__("basis_complete", "false")),
        )

        def summary_decision(bundle: Path) -> None:
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            value["decision"] = "stop_inconclusive_rank_or_solver_diagnosis"
            (bundle / "summary.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        reject("summary-decision", summary_decision)

        def oracle_summary_result(bundle: Path) -> None:
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            value["oracle"]["nullspace_nullity"] = 18
            (bundle / "summary.json").write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        reject("oracle-summary-result", oracle_summary_result)

        def extra_summary_key(bundle: Path) -> None:
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            value["ignored_provenance"] = "forged"
            (bundle / "summary.json").write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        reject("extra-summary-key", extra_summary_key)

        def nonstandard_json(bundle: Path) -> None:
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            value["seed"] = float("nan")
            (bundle / "summary.json").write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        reject("nonstandard-json-constant", nonstandard_json)

        def duplicate_json_key(bundle: Path) -> None:
            path = bundle / "summary.json"
            original = path.read_text(encoding="utf-8")
            path.write_text(
                '{\n  "schema": "duplicate",' + original[1:], encoding="utf-8")

        reject("duplicate-json-key", duplicate_json_key)

        reject(
            "json-boolean-type",
            lambda b: (
                (lambda value: (b / "summary.json").write_text(
                    json.dumps({**value, "promotion": 0}, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8"))(
                        json.loads((b / "summary.json").read_text(encoding="utf-8")))
            ),
        )

        reject("unexpected-directory", lambda b: (b / "unexpected").mkdir())
        reject("checkpoint-hash", lambda b: mutate_row(b, "systems.csv", lambda r: r.__setitem__("input_checkpoint_sha256_after", "0" * 64)))

        def corrupt_manifest(bundle: Path) -> None:
            value = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            value["pre_hash_sha256"] = "0" * 64
            (bundle / "manifest.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        reject("manifest-corrupt", corrupt_manifest, refresh=False)

    validator_module = load_validator(args.validator)

    def direct_reject(name: str, operation: Callable[[], None]) -> None:
        nonlocal mutations
        try:
            operation()
        except validator_module.InvalidBundle:
            mutations += 1
            return
        raise AssertionError(f"direct mutation {name} accepted")

    def registered_rows(smoke: bool = False) -> list[dict[str, str]]:
        expected = validator_module.registered_expectations()
        if smoke:
            by_id = {str(row["system_id"]): row for row in expected}
            expected = [by_id[system_id] for system_id in validator_module.SMOKE_SYSTEM_IDS]
        return [{
            "system_id": str(row["system_id"]),
            "case_class": str(row["case_class"]),
            "field": str(row["field"]),
            "phase": str(row["phase"]),
            "orientation": str(row["orientation"]),
            "level": str(row["level"]),
            "time_quanta": str(row["time_quanta"]),
            "full_solve_applicable": "true",
            "high_precision_applicable": "true" if row["hp"] else "false",
            "nullspace_applicable": "true" if row["null"] else "false",
            "assembly_exported": "true" if row["exported"] else "false",
        } for row in expected]

    full_rows = registered_rows()
    validator_module.validate_registered_matrix(full_rows, False)
    positives += 1
    smoke_rows = registered_rows(smoke=True)
    validator_module.validate_registered_matrix(smoke_rows, False, True)
    positives += 1

    def reject_registered(name: str, mutate: Callable[[list[dict[str, str]]], None], *, smoke: bool = False) -> None:
        rows = copy.deepcopy(smoke_rows if smoke else full_rows)
        mutate(rows)
        direct_reject(
            name,
            lambda: validator_module.validate_registered_matrix(
                rows, False, smoke),
        )

    def swap_flag(rows: list[dict[str, str]], field: str) -> None:
        selected = next(row for row in rows if row[field] == "true")
        unselected = next(row for row in rows if row[field] == "false")
        selected[field], unselected[field] = "false", "true"

    reject_registered("registered-null10", lambda rows: swap_flag(rows, "nullspace_applicable"))
    reject_registered("registered-hp4", lambda rows: swap_flag(rows, "high_precision_applicable"))
    reject_registered("registered-main-field", lambda rows: rows[0].__setitem__("field", "general_affine"))
    reject_registered("registered-main-time", lambda rows: rows[0].__setitem__("time_quanta", "4"))
    reject_registered(
        "registered-micro-level",
        lambda rows: next(row for row in rows if row["case_class"] == "full_rank_micro").__setitem__("level", "1"),
    )
    reject_registered(
        "registered-singular-phase",
        lambda rows: next(row for row in rows if row["case_class"] == "singular_ppc1").__setitem__("phase", "p000"),
    )
    reject_registered("registered-order", lambda rows: rows.reverse())
    reject_registered("registered-smoke-selection", lambda rows: rows.reverse(), smoke=True)

    full_summary: dict[str, object] = {
        "analytic_witness_all_pass": True,
        "authoritative_input_sha256": validator_module.expected_authoritative_input_sha256(),
        "branch": "projection-exactness-nullspace-lab",
        "compiler_id": "test-compiler",
        "compiler_version": "1.0",
        "configured_source_branch": "projection-exactness-nullspace-lab",
        "decision": "stop_center_state_gradient_nullspace_blocker",
        "diagnostic_pseudoinverse_promotion_eligible": False,
        "high_precision_all_pass": True,
        "hp_subset_paired_recovery_component_count": 3,
        "hp_subset_pcg_nonrecovery_component_count": 3,
        "mode": "full",
        "parent_sha": validator_module.SOURCE_PARENT_SHA,
        "pcg_solved_gate_miss_component_count": 48,
        "pcg_status_component_counts": {"solved": 225, "ill_conditioned": 3},
        "prior_failure_geometry_paired_recovery_component_count": 0,
        "prior_failure_geometry_pcg_nonrecovery_component_count": 0,
        "producer": "cpp_projection_exactness_nullspace_lab",
        "promotion": False,
        "provisional": False,
        "registered_system_ids": [],
        "row_counts": {},
        "schema": validator_module.SUMMARY_SCHEMA,
        "seed": validator_module.SEED,
        "singular_center_invariant": True,
        "singular_gradient_visible": True,
        "source_dirty": False,
        "source_sha": "1" * 40,
        "supported_findings": [],
        "sweep_complete": True,
        "tolerances": dict(validator_module.EXPECTED_TOLERANCES),
        "tool_language": "C++20",
    }
    validator_module.validate_summary_provenance(full_summary, False)
    positives += 1

    smoke_summary = copy.deepcopy(full_summary)
    smoke_summary.update({
        "configured_source_branch": "mechanical-observability-lab",
        "decision": "smoke_provisional_no_scientific_decision",
        "mode": "smoke",
        "provisional": True,
        "source_dirty": True,
        "sweep_complete": False,
    })
    validator_module.validate_summary_provenance(
        smoke_summary, False, smoke_provisional=True)
    positives += 1

    def reject_summary(name: str, mutate: Callable[[dict[str, object]], None]) -> None:
        summary = copy.deepcopy(full_summary)
        mutate(summary)
        direct_reject(
            name,
            lambda: validator_module.validate_summary_provenance(summary, False),
        )

    reject_summary("summary-source-dirty", lambda summary: summary.__setitem__("source_dirty", True))
    reject_summary("summary-configured-branch", lambda summary: summary.__setitem__("configured_source_branch", "other"))
    reject_summary("summary-provisional", lambda summary: summary.__setitem__("provisional", True))
    reject_summary("summary-sweep", lambda summary: summary.__setitem__("sweep_complete", False))
    reject_summary("summary-compiler", lambda summary: summary.__setitem__("compiler_id", "unknown"))
    reject_summary("summary-language", lambda summary: summary.__setitem__("tool_language", "C++17"))
    reject_summary("summary-parent", lambda summary: summary.__setitem__("parent_sha", "0" * 40))
    reject_summary("summary-seed", lambda summary: summary.__setitem__("seed", 1))
    reject_summary("summary-mode", lambda summary: summary.__setitem__("mode", "smoke"))
    reject_summary("summary-producer", lambda summary: summary.__setitem__("producer", "other"))

    def corrupt_authoritative(summary: dict[str, object]) -> None:
        authoritative = summary["authoritative_input_sha256"]
        assert isinstance(authoritative, dict)
        authoritative["contract"] = "0" * 64

    reject_summary("summary-authoritative", corrupt_authoritative)

    def corrupt_tolerance(summary: dict[str, object]) -> None:
        tolerances = summary["tolerances"]
        assert isinstance(tolerances, dict)
        tolerances["high_precision_normalized_forward"] = "1e-9"

    reject_summary("summary-tolerance", corrupt_tolerance)
    reject_summary("summary-extra-key", lambda summary: summary.__setitem__("ignored", True))
    reject_summary(
        "summary-count-type",
        lambda summary: summary.__setitem__("pcg_solved_gate_miss_component_count", False),
    )

    smoke_summary = copy.deepcopy(full_summary)
    smoke_summary.update({
        "mode": "smoke", "provisional": True, "sweep_complete": False,
        "source_dirty": True,
    })
    validator_module.validate_summary_provenance(smoke_summary, False, True)
    positives += 1

    metric_system_id = "main_translation_t0_l0_p000_p012_sppp"
    metric_expected = next(
        row for row in validator_module.registered_expectations()
        if row["system_id"] == metric_system_id
    )
    metric_system = {
        "system_id": metric_system_id,
        "max_stencil_size": "27",
        "max_particle_contributions_per_node": "64",
        "max_matrix_row_nnz": "125",
        "h_m": float(metric_expected["h"]).hex(),
    }
    bounds = validator_module.expected_metric_only_witness_bounds(metric_system)

    def make_witness(component: int) -> dict[str, str]:
        return {
            "system_id": metric_system_id, "component": str(component),
            "mg_minus_q_l2_kg_m_per_s": "0e+0",
            "mgq_denominator_kg_m_per_s": "1e+0",
            "normalized_mg_minus_q": "0e+0",
            "mgq_roundoff_bound": format(bounds["mgq"], "e"), "mgq_pass": "true",
            "sg_minus_v_l2_m_per_s_sqrt_kg": "0e+0",
            "sgv_denominator_m_per_s_sqrt_kg": "1e+0",
            "normalized_sg_minus_v": "0e+0",
            "sgv_roundoff_bound": format(bounds["sgv"], "e"), "sgv_pass": "true",
            "partition_max_residual": "0e+0",
            "partition_roundoff_bound": format(bounds["partition"], "e"),
            "partition_pass": "true", "linear_reproduction_max_residual_m": "0e+0",
            "linear_reproduction_roundoff_bound_m": format(bounds["linear"], "e"),
            "linear_reproduction_pass": "true",
            "gradient_partition_max_residual_per_m": "0e+0",
            "gradient_partition_roundoff_bound_per_m": format(bounds["gradient"], "e"),
            "gradient_partition_pass": "true", "pass": "true",
        }

    def make_solve(component: int) -> dict[str, str]:
        return {
            "system_id": metric_system_id, "component": str(component),
            "status": "solved", "accuracy_classification": "backward_and_forward_pass",
            "solver": "pcg_control", "iterations": "1",
            "legacy_residual_applicable": "true",
            "legacy_normalized_residual": "0x0.0p+0",
            "legacy_normalized_residual_threshold": float(5e-12).hex(),
            "legacy_termination_reason": "unregularized PCG solved",
            "backward_residual_l2_kg_m_per_s": "0e+0",
            "backward_denominator_kg_m_per_s": "1e+0",
            "normalized_backward_residual": "0e+0",
            "grid_forward_lumped_numerator_m_per_s_sqrt_kg": "0e+0",
            "grid_forward_lumped_denominator_m_per_s_sqrt_kg": "1e+0",
            "normalized_forward_error": "0e+0",
            "reconstruction_mass_numerator_m_per_s_sqrt_kg": "0e+0",
            "reconstruction_mass_denominator_m_per_s_sqrt_kg": "1e+0",
            "normalized_reconstruction_error": "0e+0",
            "raw_condition_value": "NA", "raw_condition_kind": "unavailable",
            "preconditioned_condition_value": "NA",
            "preconditioned_condition_kind": "unavailable",
            "condition_times_normalized_residual": "NA",
        }

    metric_witness = {
        (metric_system_id, str(component)): make_witness(component)
        for component in range(3)
    }
    metric_solve = {
        (metric_system_id, str(component)): make_solve(component)
        for component in range(3)
    }
    if not validator_module.validate_metric_only_system(
        metric_system, metric_witness, metric_solve):
        raise AssertionError("valid metric-only rows did not pass")
    positives += 1

    def reject_metric(
        name: str,
        mutate: Callable[[dict[tuple[str, str], dict[str, str]], dict[tuple[str, str], dict[str, str]]], None],
    ) -> None:
        witness = copy.deepcopy(metric_witness)
        solve = copy.deepcopy(metric_solve)
        mutate(witness, solve)
        direct_reject(
            name,
            lambda: validator_module.validate_metric_only_system(
                metric_system, witness, solve),
        )

    reject_metric(
        "metric-only-witness-quotient",
        lambda witness, _solve: witness[(metric_system_id, "0")].__setitem__(
            "normalized_mg_minus_q", "1e+0"),
    )
    reject_metric(
        "metric-only-vector-sg",
        lambda witness, _solve: witness[(metric_system_id, "1")].__setitem__(
            "sgv_denominator_m_per_s_sqrt_kg", "2e+0"),
    )
    reject_metric(
        "metric-only-solve-quotient",
        lambda _witness, solve: solve[(metric_system_id, "0")].__setitem__(
            "normalized_forward_error", "1e+0"),
    )
    reject_metric(
        "metric-only-accuracy",
        lambda _witness, solve: solve[(metric_system_id, "0")].__setitem__(
            "accuracy_classification", "backward_pass_forward_fail"),
    )
    reject_metric(
        "metric-only-condition-pair",
        lambda _witness, solve: solve[(metric_system_id, "0")].__setitem__(
            "raw_condition_kind", "dense_numerical_estimate"),
    )

    failed_metric_solve = copy.deepcopy(metric_solve)
    for row in failed_metric_solve.values():
        row.update({
            "status": "ill_conditioned", "accuracy_classification": "not_available",
            "iterations": "7", "backward_residual_l2_kg_m_per_s": "NA",
            "legacy_residual_applicable": "false",
            "legacy_normalized_residual": "NA",
            "legacy_termination_reason": "ill-conditioned rank diagnostic",
            "backward_denominator_kg_m_per_s": "NA", "normalized_backward_residual": "NA",
            "grid_forward_lumped_numerator_m_per_s_sqrt_kg": "NA",
            "grid_forward_lumped_denominator_m_per_s_sqrt_kg": "NA",
            "normalized_forward_error": "NA",
            "reconstruction_mass_numerator_m_per_s_sqrt_kg": "NA",
            "reconstruction_mass_denominator_m_per_s_sqrt_kg": "NA",
            "normalized_reconstruction_error": "NA",
            "raw_condition_value": "0x1.0000000000000p+1",
            "raw_condition_kind": "dense_numerical_estimate",
            "preconditioned_condition_value": "0x1.8000000000000p+1",
            "preconditioned_condition_kind": "dense_numerical_estimate",
            "condition_times_normalized_residual": "NA",
        })
    if not validator_module.validate_metric_only_system(
        metric_system, metric_witness, failed_metric_solve):
        raise AssertionError("valid unavailable metric-only rows did not pass")
    positives += 1

    print(
        "Projection exactness/nullspace validator regression: PASS "
        f"({positives} positives, {mutations} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
