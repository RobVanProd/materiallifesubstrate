#!/usr/bin/env python3
"""Mutation tests for the Relational Observability outer-seal boundary."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile


def load_tool():
    path = pathlib.Path(__file__).resolve().parents[1] / \
        "tools" / "seal_relational_observability_evidence.py"
    spec = importlib.util.spec_from_file_location("relational_sealer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load sealer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_rejection(tool, root: pathlib.Path) -> None:
    try:
        tool.verify_manifest_only(root)
    except tool.SealError:
        return
    raise RuntimeError("outer seal accepted a mutation")


def main() -> int:
    tool = load_tool()
    provenance = {
        "repository_url": "https://example.invalid/repo",
        "branch": "relational-observability-confirmation",
        "source_sha": "1" * 40,
        "ci_run_id": "7",
        "tag": "relational-observability-confirmation-evidence-v1",
        "verdict": "retain_central_relational_representation_for_research",
        "promotion_permitted": False,
    }
    with tempfile.TemporaryDirectory(prefix="mls-relational-seal-") as temporary:
        root = pathlib.Path(temporary)
        (root / "payload").mkdir()
        payload = root / "payload" / "a.txt"
        payload.write_text("alpha\n", encoding="utf-8")
        (root / "payload" / "b.bin").write_bytes(b"\x00\x01\x02")
        tool.write_manifest(root, provenance)
        tool.verify_manifest_only(root)

        original = payload.read_bytes()
        payload.write_bytes(original + b"x")
        expect_rejection(tool, root)
        payload.write_bytes(original)
        tool.write_manifest(root, provenance)

        extra = root / "payload" / "extra"
        extra.write_text("x", encoding="utf-8")
        expect_rejection(tool, root)
        extra.unlink()
        tool.write_manifest(root, provenance)

        manifest_path = root / "outer-seal.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["pre_hash_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        expect_rejection(tool, root)

    print("relational observability outer-seal mutation regression: PASS (3 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

