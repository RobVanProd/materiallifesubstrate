#!/usr/bin/env python3
"""Regression cases for the sealed Time + Transfer convergence rule."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference"))

from validate_transfer_bundle import convergence  # noqa: E402


def main() -> None:
    # This is the first shape that the full 6f30265 evidence exposed. The
    # finest value rises above the roundoff floor, but all three values remain
    # far inside the applicable hard reconstruction tolerance. The sealed
    # rule calls that a hard pass while still retaining the resolved-increase
    # diagnostic so the sub-tolerance non-monotonicity is not hidden.
    hard_pass = convergence(
        (1.522460489002253e-15, 2.4752116358277096e-14, 1.0830230618642341e-13),
        2.0e-9,
    )
    assert hard_pass.all_below_threshold
    assert hard_pass.finest_increase_failure
    assert not hard_pass.ratio_rule_pass
    assert hard_pass.passed

    # Without a hard tolerance, the same resolved increase is outside the
    # roundoff-floor branch and must block the ratio branch.
    resolved_increase = convergence(
        (1.522460489002253e-15, 2.4752116358277096e-14, 1.0830230618642341e-13),
        None,
    )
    assert not resolved_increase.all_below_threshold
    assert resolved_increase.finest_increase_failure
    assert not resolved_increase.passed

    sub_roundoff = convergence((1.0e-16, 2.0e-16, 3.0e-16), None)
    assert sub_roundoff.all_below_threshold
    assert not sub_roundoff.finest_increase_failure
    assert sub_roundoff.passed

    ratio_pass = convergence((1.0, 0.5, 0.2), None)
    assert not ratio_pass.all_below_threshold
    assert not ratio_pass.finest_increase_failure
    assert ratio_pass.ratio_rule_pass
    assert ratio_pass.passed

    print("Time + Transfer verifier convergence regression: PASS (4 cases)")


if __name__ == "__main__":
    main()
