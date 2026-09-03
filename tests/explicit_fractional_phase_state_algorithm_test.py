#!/usr/bin/env python3
"""Focused executable contracts for the exact fractional candidate algorithm."""

from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "tools"))

import run_explicit_fractional_phase_state_lab as lab  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require(lab.gmpy2.version() == "2.3.1", "rational backend version differs")

    common = lab.Fraction(2**62)
    first = lab.Packet(1, 1, [common + lab.Fraction(1, 3), lab.Fraction(), lab.Fraction()],
                       [lab.Fraction(), lab.Fraction(), lab.Fraction()])
    second = lab.Packet(2, 1, [common + lab.Fraction(2, 3), lab.Fraction(), lab.Fraction()],
                        [lab.Fraction(), lab.Fraction(), lab.Fraction()])
    state = lab.State(0, [first, second])
    relation = lab.Relation(0, 1, 2, float(lab.Fraction(1, 3) * lab.LQ))
    exact_offset = lab.relation_offset(state, relation)
    require(exact_offset == [lab.Fraction(1, 3), lab.Fraction(), lab.Fraction()],
            "complete fractional relation offset differs")
    require(float(first.x[0] * lab.LQ) == float(second.x[0] * lab.LQ),
            "absolute-position negative control did not alias")
    require(float(exact_offset[0] * lab.LQ) != 0.0,
            "exact-relative candidate lost distinguishable offset")

    canonical = lab.State(7, [lab.Packet(
        9,
        3,
        [lab.Fraction(3, 2), lab.Fraction(-2, 4), lab.Fraction(5, 3)],
        [lab.Fraction(2, 6), lab.Fraction(-8, 9), lab.Fraction()],
    )])
    encoded = lab.encode_state(canonical)
    require(lab.encode_state(lab.decode_state(encoded)) == encoded,
            "canonical exact checkpoint did not round trip")

    kick_model = lab.Model(
        "pair",
        {1: [lab.Fraction(), lab.Fraction(), lab.Fraction()],
         2: [lab.Fraction(1, 3), lab.Fraction(), lab.Fraction()]},
        {1: 1, 2: 1},
        [relation],
        [[1.0]],
    )
    deformed = state.clone()
    deformed.packets[1].x[0] = common + lab.Fraction(1)
    deformed_offset = lab.relation_offset(deformed, relation)
    kicked = lab.kick(kick_model, deformed, 2, "algorithm", 0, 1, "kick", None)
    impulse = lab.vector_sub(kicked.packets[0].p, deformed.packets[0].p)
    require(impulse != [lab.Fraction()] * 3, "fractional kick test impulse vanished")
    require(lab.cross(impulse, deformed_offset) == [lab.Fraction()] * 3,
            "fractional kick is not exactly central")
    require(lab.vector_add(kicked.packets[0].p, kicked.packets[1].p) == [lab.Fraction()] * 3,
            "fractional kick changed total momentum")

    free = lab.State(0, [lab.Packet(
        1, 7, [lab.Fraction()] * 3,
        [lab.Fraction(1, 3), lab.Fraction(-2, 5), lab.Fraction(7, 11)],
    )])
    drifted = lab.drift(lab.Model("free", {}, {1: 7}, [], []), free, 13)
    require(drifted.packets[0].x == [
        lab.Fraction(13, 21), lab.Fraction(-26, 35), lab.Fraction(13, 11)
    ], "fractional drift projected or rounded the position")
    require(drifted.packets[0].p == free.packets[0].p,
            "fractional drift changed momentum")
    require(lab.exact_invariants(drifted) == lab.exact_invariants(free),
            "fractional drift changed exact invariants")

    crossing_relation = lab.Relation(0, 1, 2, float(lab.LQ))
    crossing_model = lab.Model(
        "crossing",
        {1: [lab.Fraction()] * 3, 2: [lab.Fraction(1), lab.Fraction(), lab.Fraction()]},
        {1: 1, 2: 1},
        [crossing_relation],
        [[0.0]],
    )
    crossing = lab.State(0, [
        lab.Packet(1, 1, [lab.Fraction()] * 3,
                   [lab.Fraction(1), lab.Fraction(), lab.Fraction()]),
        lab.Packet(2, 1, [lab.Fraction(1), lab.Fraction(), lab.Fraction()],
                   [lab.Fraction(-1), lab.Fraction(), lab.Fraction()]),
    ])
    before = lab.encode_state(crossing)
    status, returned = lab.one_step(
        crossing_model, crossing, 2, lab.KDK, "domain", 0, 1,
        None, None, lab.exact_invariants(crossing),
    )
    require(status == "chord_domain_failure", "crossing chord did not fail closed")
    require(lab.encode_state(returned) == before and lab.encode_state(crossing) == before,
            "domain rejection was not atomic")

    print("explicit fractional phase-state algorithm contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
