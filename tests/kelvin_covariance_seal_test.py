#!/usr/bin/env python3
"""Mutation tests for the Kelvin outer-manifest hash boundary."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile


def load_tool():
    path = pathlib.Path(__file__).resolve().parents[1] / "tools" / \
        "seal_kelvin_covariance_evidence.py"
    spec = importlib.util.spec_from_file_location("kelvin_sealer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load sealer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    tool = load_tool()
    provenance = {
        "repository_url": "https://example.invalid/repo",
        "branch": "kelvin-covariance-audit",
        "source_sha": "1" * 40,
        "ci_run_id": "7",
        "tag": "kelvin-covariance-audit-evidence-v1",
        "decision": "SUPPORTED_DIAGNOSTIC_COORDINATE_DEFECT",
        "promotion_permitted": False,
    }
    with tempfile.TemporaryDirectory(prefix="mls-kelvin-seal-") as temporary:
        root = pathlib.Path(temporary)
        (root / "payload").mkdir()
        (root / "payload" / "a.txt").write_text("alpha\n", encoding="utf-8")
        (root / "payload" / "b.bin").write_bytes(b"\x00\x01\x02")
        tool.write_manifest(root, provenance)
        tool.verify_manifest_only(root)

        original = (root / "payload" / "a.txt").read_bytes()
        (root / "payload" / "a.txt").write_bytes(original + b"x")
        try:
            tool.verify_manifest_only(root)
            raise RuntimeError("content mutation was accepted")
        except tool.SealError:
            pass
        (root / "payload" / "a.txt").write_bytes(original)
        tool.write_manifest(root, provenance)

        (root / "payload" / "extra").write_text("x", encoding="utf-8")
        try:
            tool.verify_manifest_only(root)
            raise RuntimeError("inventory mutation was accepted")
        except tool.SealError:
            pass
        (root / "payload" / "extra").unlink()
        tool.write_manifest(root, provenance)

        manifest_path = root / "outer-seal.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["pre_hash_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        try:
            tool.verify_manifest_only(root)
            raise RuntimeError("pre-hash mutation was accepted")
        except tool.SealError:
            pass

    print("kelvin covariance outer-seal mutation regression: PASS (3 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
