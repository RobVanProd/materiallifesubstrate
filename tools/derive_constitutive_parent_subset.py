#!/usr/bin/env python3
"""Independently derive the Constitutive Expressivity parent subset hashes.

This script intentionally does not call the C++ producer. It selects and
canonicalizes the registered rows directly from the accepted Relational
Observability Confirmation fixture, then emits the producer-format input
tables and verifies their frozen SHA-256 commitments.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
from pathlib import Path


REGISTERED_IDS = {
    "exact.tetrahedron_k4",
    "exact.octahedron_graph",
    "base.sc3.r180.original",
    "base.bcc35.r180.original",
    "base.jitter27.r180.original",
    "base.free_face.r180.original",
    "base.sc3_deletion.delete25.original",
    "exact.tetrahedron_k4_minus_edge",
}

PARENT_SHA256 = {
    "configurations.csv": "cbae18e3b2c356e2898d1410f37fb90692d889f28438cfb5524753c87f1db2b7",
    "packets.csv": "dfd22994678333125b90f658d5b228c09f45e4564f52e02d6f38a3b2f3c924f7",
    "relations.csv": "14afdb0ac5822294a5d5437b3e622dffdc9f886dda395d0bfef5ae9b13c73093",
}

SELECTED_SHA256 = {
    "configurations.csv": "45d162381ec723dd9ce744f2cc23c4d21435a52b7c7e60a182073ee19a08d60e",
    "packets.csv": "843c9cb22c0b55e07c207135125a8334b0dd170a0f708aa1fb50f34d4c5d7363",
    "relations.csv": "0b2e21dcbf26454af316bec9323627aa1488ebc7aa1f14c006bfb41a231e0e6f",
}


def read_checked(path: Path) -> str:
    payload = path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    expected = PARENT_SHA256[path.name]
    if actual != expected:
        raise ValueError(f"accepted parent hash mismatch for {path.name}: {actual}")
    return payload.decode("utf-8")


def rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text, newline="")))


def encode(header: list[str], values: list[list[str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(values)
    return output.getvalue().encode("utf-8")


def derive(parent: Path) -> dict[str, bytes]:
    configuration_rows = rows(read_checked(parent / "configurations.csv"))
    packet_rows = rows(read_checked(parent / "packets.csv"))
    relation_rows = rows(read_checked(parent / "relations.csv"))

    selected_configs = {
        row["configuration_id"]: row
        for row in configuration_rows
        if row["configuration_id"] in REGISTERED_IDS
    }
    if set(selected_configs) != REGISTERED_IDS:
        raise ValueError("accepted parent is missing a registered configuration")

    packets_by_config: dict[str, list[dict[str, str]]] = {
        identifier: [] for identifier in REGISTERED_IDS
    }
    for row in packet_rows:
        if row["configuration_id"] in REGISTERED_IDS:
            packets_by_config[row["configuration_id"]].append(row)

    relations_by_config: dict[str, list[dict[str, str]]] = {
        identifier: [] for identifier in REGISTERED_IDS
    }
    for row in relation_rows:
        if (row["configuration_id"] in REGISTERED_IDS and
                row["selection_status"] == "retained"):
            relations_by_config[row["configuration_id"]].append(row)

    config_values: list[list[str]] = []
    packet_values: list[list[str]] = []
    relation_values: list[list[str]] = []
    for identifier in sorted(REGISTERED_IDS):
        packets = sorted(
            packets_by_config[identifier], key=lambda row: int(row["packet_id"]))
        relations = sorted(
            relations_by_config[identifier],
            key=lambda row: (int(row["first_id"]), int(row["second_id"])),
        )
        role = ("intentionally_floppy"
                if identifier == "exact.tetrahedron_k4_minus_edge"
                else "eligible_generic")
        config_values.append([
            identifier, identifier, role, str(len(packets)), str(len(relations))
        ])
        for index, row in enumerate(packets):
            packet_values.append([
                identifier, str(index), row["packet_id"], row["mass_quanta"],
                row["x_m"], row["y_m"], row["z_m"],
            ])
        for index, row in enumerate(relations):
            relation_values.append([
                identifier, str(index), row["first_id"], row["second_id"],
                row["reference_length_m"],
            ])

    return {
        "configurations.csv": encode(
            ["configuration_id", "parent_source_id", "role", "packet_count",
             "relation_count"], config_values),
        "packets.csv": encode(
            ["configuration_id", "packet_index", "packet_id", "mass_quanta",
             "x_m", "y_m", "z_m"], packet_values),
        "relations.csv": encode(
            ["configuration_id", "relation_index", "first_id", "second_id",
             "reference_length_m"], relation_values),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parent-bundle", "--fixture-bundle", dest="parent_bundle",
        required=True, type=Path,
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="verify the frozen commitments (always performed; receipt flag)",
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    payloads = derive(arguments.parent_bundle)
    for name, payload in payloads.items():
        digest = hashlib.sha256(payload).hexdigest()
        if digest != SELECTED_SHA256[name]:
            raise ValueError(f"selected subset hash mismatch for {name}: {digest}")
        print(f"{name} {digest}")
        if arguments.output is not None:
            arguments.output.mkdir(parents=True, exist_ok=True)
            (arguments.output / name).write_bytes(payload)
    print("constitutive parent subset: PASS")


if __name__ == "__main__":
    main()
