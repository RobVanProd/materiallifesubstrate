#!/usr/bin/env python3
"""Exact-arithmetic reference tests for the Material Life Substrate v0.

These tests do not validate a floating-point GPU solver. They validate the
accounting model and produce adversarial counterexamples that implementation
kernels must respect.
"""
from __future__ import annotations
from fractions import Fraction as F
from random import Random
from typing import Dict, Tuple
import hashlib
import json

SEED = 260828
rng = Random(SEED)


def qint(lo: int, hi: int) -> F:
    return F(rng.randint(lo, hi), rng.randint(1, 23))


def test_pair_transfer(n=100_000):
    for _ in range(n):
        a = rng.randint(0, 10000)
        b = rng.randint(0, 10000)
        q = rng.randint(0, a)
        a2, b2 = a - q, b + q
        assert a2 >= 0 and b2 >= 0
        assert a2 + b2 == a + b
    return n


def test_momentum_exchange(n=100_000):
    for _ in range(n):
        p1 = rng.randint(-10000, 10000)
        p2 = rng.randint(-10000, 10000)
        impulse = rng.randint(-1000, 1000)
        p1p, p2p = p1 + impulse, p2 - impulse
        assert p1p + p2p == p1 + p2
    return n


COMP: Dict[str, Tuple[int, int, int]] = {
    "A": (1, 0, 0),
    "B": (0, 1, 0),
    "C": (0, 0, 1),
    "AB": (1, 1, 0),
    "AC": (1, 0, 1),
    "BC": (0, 1, 1),
    "ABC": (1, 1, 1),
}
REACTIONS: Dict[str, Dict[str, int]] = {
    "A+B->AB": {"A": -1, "B": -1, "AB": 1},
    "A+C->AC": {"A": -1, "C": -1, "AC": 1},
    "B+C->BC": {"B": -1, "C": -1, "BC": 1},
    "AB+C->ABC": {"AB": -1, "C": -1, "ABC": 1},
    "AC+B->ABC": {"AC": -1, "B": -1, "ABC": 1},
    "BC+A->ABC": {"BC": -1, "A": -1, "ABC": 1},
}


def element_delta(stoich: Dict[str, int]) -> Tuple[int, int, int]:
    return tuple(
        sum(COMP[s][e] * nu for s, nu in stoich.items())
        for e in range(3)
    )


def inventory(state: Dict[str, F]) -> Tuple[F, F, F]:
    return tuple(
        sum((state.get(s, F(0)) * COMP[s][e] for s in COMP), F(0))
        for e in range(3)
    )


def test_stoichiometry(n=100_000):
    for name, rxn in REACTIONS.items():
        assert element_delta(rxn) == (0, 0, 0), (name, element_delta(rxn))

    names = list(REACTIONS)
    for _ in range(n):
        state = {s: F(rng.randint(0, 1000)) for s in COMP}
        name = rng.choice(names)
        rxn = REACTIONS[name]
        reactants = [s for s, nu in rxn.items() if nu < 0]
        max_extent = min(state[s] // (-rxn[s]) for s in reactants)
        extent = F(rng.randint(0, int(max_extent)))
        before = inventory(state)
        after = dict(state)
        for s, nu in rxn.items():
            after[s] += extent * nu
            assert after[s] >= 0
        assert inventory(after) == before
    return n, len(REACTIONS)


def test_energy_ledger(n=100_000):
    for _ in range(n):
        thermal = rng.randint(0, 10000)
        chemical = rng.randint(0, 10000)
        mechanical = rng.randint(0, 10000)
        reservoir = rng.randint(0, 10000)
        q = rng.randint(0, chemical)
        before = thermal + chemical + mechanical + reservoir
        thermal += q
        chemical -= q
        assert chemical >= 0
        assert thermal + chemical + mechanical + reservoir == before
        q2 = rng.randint(0, reservoir)
        thermal += q2
        reservoir -= q2
        assert reservoir >= 0
        assert thermal + chemical + mechanical + reservoir == before
    return n


def test_hierarchical_extensive_aggregation(n=25_000):
    for _ in range(n):
        fine = [
            {
                "mass": rng.randint(0, 1000),
                "energy": rng.randint(0, 1000),
                "A": rng.randint(0, 1000),
                "B": rng.randint(0, 1000),
            }
            for _ in range(rng.randint(1, 64))
        ]
        coarse = {k: sum(c[k] for c in fine) for k in fine[0]}
        for k in coarse:
            assert coarse[k] == sum(c[k] for c in fine)
    return n


def coarse_grain_false_affordance_counterexample():
    fine = ((F(1), F(0)), (F(0), F(1)))
    fine_reactable = any(a > 0 and b > 0 for a, b in fine)
    coarse = (sum((x[0] for x in fine), F(0)), sum((x[1] for x in fine), F(0)))
    coarse_reactable = coarse[0] > 0 and coarse[1] > 0
    assert not fine_reactable
    assert coarse_reactable
    assert sum(a for a, _ in fine) == coarse[0]
    assert sum(b for _, b in fine) == coarse[1]
    return {
        "fine_reactable": fine_reactable,
        "coarse_reactable": coarse_reactable,
        "A_conserved": True,
        "B_conserved": True,
        "meaning": "conservative aggregation can create a false local affordance",
    }


def Re(rho, U, L, mu):
    return rho * U * L / mu


def Fr2(U, g, L):
    return U * U / (g * L)


def Pe(U, L, D):
    return U * L / D


def Da(k, L, U):
    return k * L / U


def test_dynamic_similarity(n=10_000):
    for _ in range(n):
        alpha = qint(1, 20)
        beta = qint(1, 20)
        rho = qint(1, 20)
        U = qint(1, 20)
        L = qint(1, 20)
        mu = qint(1, 20)
        g = qint(1, 20)
        D = qint(1, 20)
        k = qint(1, 20)

        U2 = alpha / beta * U
        L2 = alpha * L
        mu2 = alpha * alpha / beta * mu
        g2 = alpha / (beta * beta) * g
        D2 = alpha * alpha / beta * D
        k2 = k / beta

        assert Re(rho, U2, L2, mu2) == Re(rho, U, L, mu)
        assert Fr2(U2, g2, L2) == Fr2(U, g, L)
        assert Pe(U2, L2, D2) == Pe(U, L, D)
        assert Da(k2, L2, U2) == Da(k, L, U)
    return n


def main():
    results = {
        "seed": SEED,
        "pair_transfer_cases": test_pair_transfer(),
        "momentum_exchange_cases": test_momentum_exchange(),
    }
    stoich_n, rxn_n = test_stoichiometry()
    results["stoichiometric_reactions_balanced"] = rxn_n
    results["stoichiometric_random_extent_cases"] = stoich_n
    results["energy_ledger_cases"] = test_energy_ledger()
    results["hierarchical_aggregation_cases"] = test_hierarchical_extensive_aggregation()
    results["coarse_grain_counterexample"] = coarse_grain_false_affordance_counterexample()
    results["dynamic_similarity_cases"] = test_dynamic_similarity()
    payload = json.dumps(results, sort_keys=True, indent=2)
    results["result_sha256_before_hash_field"] = hashlib.sha256(payload.encode()).hexdigest()
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
