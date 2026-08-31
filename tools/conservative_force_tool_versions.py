#!/usr/bin/env python3
"""Emit fail-closed source, arithmetic-contract, and toolchain identity."""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import platform
import re
import shutil
import subprocess
import sys


SOURCE_RE = re.compile(r"[0-9a-f]{40}")
SEED = 260828
BINARY64_CONTRACT = \
    "iec559_size8_digits53_explicit_order_fp_contract_off_v1"


def run(command: list[str], cwd: pathlib.Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"version command failed ({completed.returncode}): "
            f"{' '.join(command)}\n{completed.stdout}"
        )
    return completed.stdout.rstrip("\r\n")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def executable(value: str) -> pathlib.Path:
    found = shutil.which(value)
    if found is None:
        candidate = pathlib.Path(value)
        if not candidate.is_file():
            raise RuntimeError(f"required executable is missing: {value}")
        found = str(candidate)
    result = pathlib.Path(found).resolve(strict=True)
    if not result.is_file():
        raise RuntimeError(f"required executable is not a file: {result}")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--cxx", required=True)
    parser.add_argument("--lake", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if SOURCE_RE.fullmatch(args.source_sha) is None:
        raise RuntimeError("--source-sha must be one lowercase 40-hex commit")
    if not args.branch or any(character.isspace() for character in args.branch):
        raise RuntimeError("--branch must be one nonempty branch name")

    repo = args.repo.resolve(strict=True)
    formal = (repo / "formal").resolve(strict=True)
    source_sha = run(["git", "rev-parse", "HEAD"], repo)
    source_branch = run(["git", "branch", "--show-current"], repo)
    source_status = run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], repo
    )
    if source_sha != args.source_sha:
        raise RuntimeError("live repository HEAD differs from --source-sha")
    if source_branch != args.branch:
        raise RuntimeError("live repository branch differs from --branch")
    if source_status:
        raise RuntimeError("live repository is dirty; tool identity is not sealable")

    lake_path = executable(args.lake)
    executable_suffix = ".exe" if lake_path.suffix.lower() == ".exe" else ""
    lean_path = lake_path.with_name("lean" + executable_suffix)
    elan_path = lake_path.with_name("elan" + executable_suffix)
    cxx_path = executable(args.cxx)
    toolchain = formal / "lean-toolchain"
    manifest = formal / "lake-manifest.json"
    mathlib = formal / ".lake" / "packages" / "mathlib"
    if not lean_path.is_file() or not elan_path.is_file():
        raise RuntimeError("Lean/Elan executable is missing beside Lake")
    if not toolchain.is_file() or not manifest.is_file() or not mathlib.is_dir():
        raise RuntimeError("pinned Lean/Mathlib identity is incomplete")
    toolchain_text = toolchain.read_text(encoding="utf-8").strip()
    if not toolchain_text or "\n" in toolchain_text or "\r" in toolchain_text:
        raise RuntimeError("lean-toolchain must contain one nonempty line")
    mathlib_commit = run(["git", "rev-parse", "HEAD"], mathlib)
    if SOURCE_RE.fullmatch(mathlib_commit) is None:
        raise RuntimeError("Mathlib checkout identity is not a commit SHA")

    print(f"source_sha={source_sha}")
    print(f"source_branch={source_branch}")
    print("source_status_begin")
    print("source_status_end")
    print(f"seed={SEED}")
    print(f"binary64_contract={BINARY64_CONTRACT}")
    print(f"platform={platform.platform()}")
    print(f"python_implementation={platform.python_implementation()}")
    print(f"lean_toolchain={toolchain_text}")
    print(f"lean_toolchain_sha256={sha256(toolchain)}")
    print(f"lake_manifest_sha256={sha256(manifest)}")
    print(f"mathlib_commit={mathlib_commit}")

    records = (
        ("git", [str(executable("git")), "--version"], repo),
        ("cmake", [str(executable("cmake")), "--version"], repo),
        ("ctest", [str(executable("ctest")), "--version"], repo),
        ("ninja", [str(executable("ninja")), "--version"], repo),
        ("cxx", [str(cxx_path), "--version"], repo),
        ("python", [str(pathlib.Path(sys.executable).resolve()), "--version"], repo),
        ("elan", [str(elan_path), "--version"], formal),
        ("lean", [str(lean_path), "--version"], formal),
        ("lake", [str(lake_path), "--version"], formal),
    )
    for name, command, cwd in records:
        print(f"{name}_command={command[0]}")
        print(f"{name}_cwd={cwd}")
        print(f"{name}_version_begin")
        output = run(command, cwd)
        if not output:
            raise RuntimeError(f"{name} version output is empty")
        print(output)
        print(f"{name}_version_end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
