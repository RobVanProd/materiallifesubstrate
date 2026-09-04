#!/usr/bin/env python3
"""Require two generated evidence directories to be byte-for-byte equal."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


class ComparisonError(RuntimeError):
    """Raised when a directory is unsafe or differs from its peer."""


def regular_files(root: Path) -> dict[str, Path]:
    if not root.is_dir() or root.is_symlink():
        raise ComparisonError(f"not a non-symlink directory: {root}")
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ComparisonError(f"symlink is forbidden: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ComparisonError(f"non-regular entry is forbidden: {path}")
        relative = path.relative_to(root).as_posix()
        result[relative] = path
    if not result:
        raise ComparisonError(f"evidence directory is empty: {root}")
    return result


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    arguments = parser.parse_args()

    first = regular_files(arguments.first)
    second = regular_files(arguments.second)
    if first.keys() != second.keys():
        missing = sorted(first.keys() - second.keys())
        extra = sorted(second.keys() - first.keys())
        raise ComparisonError(
            f"file sets differ; missing={missing!r}; extra={extra!r}")
    for relative in sorted(first):
        first_digest = digest(first[relative])
        second_digest = digest(second[relative])
        if first_digest != second_digest:
            raise ComparisonError(
                f"content differs for {relative}: "
                f"{first_digest} != {second_digest}")

    print(f"Evidence directory byte comparison: PASS ({len(first)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
