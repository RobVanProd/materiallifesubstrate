#!/usr/bin/env python3
"""Run one evidence command and write a closed, machine-readable receipt."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import pathlib
import subprocess
import sys


SCHEMA = "mls-relational-observability-command-receipt-v1"
BRANCH = "relational-observability-confirmation"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=pathlib.Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--branch", default=BRANCH)
    parser.add_argument("--cwd", type=pathlib.Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    return args


def main() -> int:
    args = parse_args()
    receipt = args.receipt.resolve()
    if receipt.exists():
        raise SystemExit(f"receipt already exists: {receipt}")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    cwd = args.cwd.resolve(strict=True)
    started_at = utc_now()
    completed = subprocess.run(
        args.command,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    ended_at = utc_now()
    output = completed.stdout
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()
    try:
        decoded = output.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise SystemExit("evidence command output is not UTF-8") from error
    payload = {
        "schema": SCHEMA,
        "label": args.label,
        "source_sha": args.source_sha,
        "branch": args.branch,
        "cwd": str(cwd),
        "command": args.command,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "exit_code": completed.returncode,
        "output_bytes": len(output),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "output": decoded,
    }
    receipt.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
