#!/usr/bin/env python3
"""Audit the MLS Lean source boundary for placeholders and missing axiom reports."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


FORBIDDEN = re.compile(r"\b(?:sorry|admit|sorryAx)\b")
PROJECT_AXIOM = re.compile(r"^\s*axiom\s+", re.MULTILINE)
THEOREM = re.compile(r"^\s*theorem\s+([A-Za-z0-9_]+)", re.MULTILINE)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-root", type=Path, default=Path("formal"))
    return parser.parse_args()


def main() -> int:
    root = parse_arguments().formal_root.resolve()
    entry = root / "MLSFormal.lean"
    module_root = root / "MLSFormal"
    report_path = module_root / "AxiomReport.lean"
    sources = [entry, *sorted(module_root.rglob("*.lean"))]
    missing = [path for path in (entry, report_path) if not path.is_file()]
    if missing:
        for path in missing:
            print(f"missing required Lean source: {path}")
        return 1

    report = report_path.read_text(encoding="utf-8")
    findings: list[str] = []
    for path in sources:
        source = path.read_text(encoding="utf-8")
        for match in FORBIDDEN.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            findings.append(f"{path}:{line}: forbidden term {match.group(0)}")
        for match in PROJECT_AXIOM.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            findings.append(f"{path}:{line}: project-defined axiom declaration")
        if path != report_path:
            for theorem in THEOREM.findall(source):
                if f"#print axioms MLSFormal.{theorem}" not in report:
                    findings.append(
                        f"{path}: missing #print axioms entry for {theorem}"
                    )

    if findings:
        print("\n".join(findings))
        return 1
    print(
        "PASS: no sorry, admit, sorryAx, project-defined axiom declaration, "
        "or unreported theorem"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
