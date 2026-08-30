#!/usr/bin/env python3
"""Emit source and tool versions for a relational evidence command receipt."""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys


def run(command: list[str], cwd: pathlib.Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"version command failed ({completed.returncode}): {' '.join(command)}\n"
            + completed.stdout
        )
    return completed.stdout.rstrip("\r\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--cxx", required=True)
    parser.add_argument("--lake", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve(strict=True)
    source_sha = run(["git", "rev-parse", "HEAD"], repo)
    source_branch = run(["git", "branch", "--show-current"], repo)
    source_status = run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], repo
    )
    formal = repo / "formal"
    if not formal.is_dir():
        raise RuntimeError("formal project directory is missing")
    lake_path = pathlib.Path(args.lake)
    lean_name = "lean.exe" if lake_path.name.lower().endswith(".exe") else "lean"
    lean_path = lake_path.with_name(lean_name)
    records = (
        ("cxx", [args.cxx, "--version"], repo),
        ("cmake", ["cmake", "--version"], repo),
        ("python", [sys.executable, "--version"], repo),
        ("lean", [str(lean_path), "--version"], formal),
        ("lake", [args.lake, "--version"], formal),
    )
    print(f"source_sha={source_sha}")
    print(f"source_branch={source_branch}")
    print("source_status_begin")
    if source_status:
        print(source_status)
    print("source_status_end")
    for name, command, command_cwd in records:
        print(f"{name}_command={command[0]}")
        print(f"{name}_cwd={command_cwd}")
        print(f"{name}_version_begin")
        print(run(command, command_cwd))
        print(f"{name}_version_end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
