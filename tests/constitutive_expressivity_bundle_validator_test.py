#!/usr/bin/env python3
"""Positive/twin and semantic-mutation regression for the bundle validator."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Callable


MARKER = "CONSTITUTIVE EXPRESSIVITY BUNDLE INVALID"


def run(
    validator: pathlib.Path,
    bundle: pathlib.Path,
    expect_success: bool,
    compare: pathlib.Path | None = None,
    required_rejection: str | None = None,
) -> None:
    command = [
        sys.executable,
        str(validator),
        "--bundle",
        str(bundle),
        "--allow-dirty",
    ]
    if compare is not None:
        command.extend(("--compare", str(compare)))
    completed = subprocess.run(
        command, text=True, capture_output=True, check=False, timeout=180
    )
    if (completed.returncode == 0) != expect_success:
        raise RuntimeError(
            f"unexpected validator outcome {completed.returncode}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    if not expect_success and MARKER not in completed.stderr:
        raise RuntimeError(
            f"validator rejection lacked stable marker:\n{completed.stdout}\n{completed.stderr}"
        )
    if (
        not expect_success
        and required_rejection is not None
        and required_rejection not in completed.stderr
    ):
        raise RuntimeError(
            "validator rejection did not prove required ordering: "
            f"{required_rejection!r}\n{completed.stdout}\n{completed.stderr}"
        )


def read_csv(path: pathlib.Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or ()), list(reader)


def write_csv(path: pathlib.Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def mutate_csv(path: pathlib.Path, mutation: Callable[[list[dict[str, str]]], None]) -> None:
    fields, rows = read_csv(path)
    if not rows:
        raise RuntimeError(f"cannot mutate empty {path.name}")
    mutation(rows)
    write_csv(path, fields, rows)


def reseal(root: pathlib.Path) -> None:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    names = sorted(manifest["file_sha256"])
    hashes = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in names
    }
    manifest["file_sha256"] = hashes
    preimage = b"".join(
        name.encode("utf-8") + b"\0" + hashes[name].encode("ascii") + b"\n"
        for name in names
    )
    manifest["pre_hash_sha256"] = hashlib.sha256(preimage).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def mutate_json(path: pathlib.Path, mutation: Callable[[dict], None]) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    mutation(value)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validator", type=pathlib.Path, required=True)
    parser.add_argument("--bundle", type=pathlib.Path, required=True)
    parser.add_argument("--compare", type=pathlib.Path)
    args = parser.parse_args()

    run(args.validator, args.bundle, True)
    run(args.validator, args.bundle, True)
    if args.compare is not None:
        run(args.validator, args.bundle, True, args.compare)

    mutation_names = (
        "energy", "residual", "basis", "locality", "target", "id_label",
        "kernel", "source", "oracle", "selected_subset", "packet",
        "relation", "checkpoint", "spectrum", "role", "decision",
        "promotion", "inventory",
    )
    with tempfile.TemporaryDirectory(prefix="mls-constitutive-validator-") as temporary:
        root = pathlib.Path(temporary)
        targets: dict[str, pathlib.Path] = {}
        for name in (*mutation_names, "twin", "twin_order"):
            target = root / name
            shutil.copytree(args.bundle, target)
            targets[name] = target

        mutate_csv(
            targets["energy"] / "strain_energy.csv",
            lambda rows: rows[0].__setitem__("actual_energy", "0x1.0000000000000p+20"),
        )
        mutate_csv(
            targets["residual"] / "graph_energy.csv",
            lambda rows: rows[0].__setitem__(
                "rigid_energy_residual", "0x1.0000000000000p-4"
            ),
        )
        mutate_csv(
            targets["basis"] / "basis_vectors.csv",
            lambda rows: rows[0].__setitem__("x", "0x1.0000000000000p+4"),
        )
        mutate_csv(
            targets["locality"] / "graph_energy.csv",
            lambda rows: rows[0].__setitem__("nonlocal_off_diagonal_count", "1"),
        )
        mutate_csv(
            targets["target"] / "bulk_expressivity.csv",
            lambda rows: rows[1].__setitem__("target_k_over_g", "0x1.0000000000000p+5"),
        )
        mutate_csv(
            targets["id_label"] / "metamorphic.csv",
            lambda rows: next(row for row in rows if row["probe"] == "id_reverse").__setitem__(
                "probe", "id_physics"
            ),
        )
        mutate_csv(
            targets["kernel"] / "graph_energy.csv",
            lambda rows: rows[0].__setitem__("lr_rank", str(int(rows[0]["lr_rank"]) - 1)),
        )
        mutate_json(
            targets["source"] / "provenance.json",
            lambda value: value["inherited_blobs"].__setitem__(
                "src/mechanical_observability_lab.cpp", "0" * 40
            ),
        )
        mutate_json(
            targets["oracle"] / "provenance.json",
            lambda value: value.__setitem__("exact_oracle_pre_hash", "0" * 64),
        )
        mutate_json(
            targets["selected_subset"] / "provenance.json",
            lambda value: value["selected_subset_sha256"].__setitem__(
                "packets.csv", "0" * 64
            ),
        )
        mutate_csv(
            targets["packet"] / "packets.csv",
            lambda rows: rows[0].__setitem__("x_m", "0x1.0000000000000p+4"),
        )
        mutate_csv(
            targets["relation"] / "relations.csv",
            lambda rows: rows[0].__setitem__("reference_length_m", "0x1.0000000000000p+4"),
        )
        checkpoint = next((targets["checkpoint"] / "checkpoints").glob("*.bin"))
        payload = bytearray(checkpoint.read_bytes())
        payload[-1] ^= 1
        checkpoint.write_bytes(payload)
        mutate_csv(
            targets["spectrum"] / "spectra.csv",
            lambda rows: rows[0].__setitem__("singular_value", "0x1.0000000000000p+20"),
        )
        mutate_csv(
            targets["role"] / "configurations.csv",
            lambda rows: rows[0].__setitem__("role", "semantic_solid"),
        )
        mutate_json(
            targets["decision"] / "summary.json",
            lambda value: value.__setitem__("decision", "representation_expressive_but_local_constitutive_law_unresolved"),
        )
        mutate_json(
            targets["promotion"] / "summary.json",
            lambda value: value.__setitem__("no_promotion", False),
        )
        (targets["inventory"] / "unexpected.txt").write_text("x\n", encoding="utf-8")

        for name in mutation_names:
            if name != "inventory":
                reseal(targets[name])
            try:
                run(args.validator, targets[name], False)
            except RuntimeError as error:
                raise RuntimeError(f"mutation {name}: {error}") from error

        # This altered compiler receipt remains individually valid, so only a
        # byte-for-byte twin comparison is allowed to reject it.
        mutate_json(
            targets["twin"] / "provenance.json",
            lambda value: value.__setitem__("compiler_version", value["compiler_version"] + ".twin"),
        )
        reseal(targets["twin"])
        run(args.validator, targets["twin"], True)
        run(
            args.validator,
            args.bundle,
            False,
            targets["twin"],
            required_rejection="twin bundles are not byte-for-byte identical",
        )

        # Prove twin bytes are checked before either expensive semantic path:
        # this primary copy is itself invalid, but the required rejection must
        # still be the earlier closed-tree mismatch.
        mutate_json(
            targets["twin_order"] / "summary.json",
            lambda value: value.__setitem__("decision", "invalid_before_twin_check"),
        )
        run(
            args.validator,
            targets["twin_order"],
            False,
            targets["twin"],
            required_rejection="twin bundles are not byte-for-byte identical",
        )

    print(
        "constitutive expressivity bundle validator regression: PASS "
        f"(2 deterministic positives, {len(mutation_names)} semantic mutations, "
        "1 twin mutation, fail-fast twin ordering)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
