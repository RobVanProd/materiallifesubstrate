# Validation, implementation, and proof boundary

## Status language

Use these words literally:

- **specified:** a requirement is written;
- **implemented:** source exists and was reviewed, but may not have run;
- **executed:** a command produced a captured result for an identified build;
- **passed:** captured evidence satisfies predeclared criteria;
- **kernel-verified:** Lean's kernel accepted the pinned project with no
  `sorry`/`admit` or substituted axioms beyond those declared;
- **replicated:** an independent implementation or environment reproduced it.

“Formalized,” “tested,” and “verified” are not interchangeable.

## Current repository status

At bootstrap, the architecture and contracts are specified. On 2026-08-28 the
`formal/` tree, pinned to Lean/Mathlib `v4.33.0-rc1`, completed `lake build`
successfully (`963 jobs`) and a Lean-source scan found no `sorry` or `admit`
tokens. This promotes only the formal statements actually encoded there; it does
not establish C++ conformance, numerical accuracy, or physical validity.

The committed exact-arithmetic reference was executed on 2026-08-28 with
`python reference/exact_arithmetic_v0.py`. A second execution through
`python tools/exact_validation.py --mode full --provenance-only --verify
reference/validation_results_v0.json` byte-compared its generated result with the
committed reference. Both completed successfully with seed `260828` and reported
the expected pre-hash
`92405699657c404e4dcd324a16ca0d3cd0e7a82ff395ccfb277c47c10766a2da`.
This promotes only the historical exact-arithmetic rows represented by that
fixture; it does not promote C++, numerical, Lean, or empirical coverage.

No document in this repository, by itself, is evidence that the C++ reference
model, numerical solvers, chemistry, gauntlet, life, ecology, or evolutionary
hypotheses have passed. Implementation status must be derived from versioned
build artifacts and machine-readable result manifests, never README prose.

## Four independent evidence columns

| Property or claim | Lean/formal | Exact executable | Numerical/solver | Empirical/evolution |
|---|---|---|---|---|
| Pair-transfer total | Pinned kernel build passed | Executed v0: 100,000 | Packet/grid convergence required | Not applicable |
| Transfer non-negativity under bounded extent | Pinned kernel build passed | Executed within v0 transfer cases | Positivity/rejection statistics required | Not applicable |
| Equal/opposite momentum exchange | Pinned kernel build passed | Executed v0: 100,000 | Gates 2 and 5 required | Not applicable |
| Stoichiometric element conservation | Pinned kernel build passed | Executed v0: 6 definitions and 100,000 extents | Coupled kinetics/transport convergence required | Not applicable |
| Chemical/thermal energy transaction | Pinned kernel build passed | Executed within 100,000 v0 ledger cases | Coupled energy residual convergence required | Exploit quarantine for evolved cycles |
| World/reservoir energy accounting | Pinned kernel build passed | Executed within 100,000 v0 ledger cases | Boundary benchmark required | Long-run closure at Gates 12–15 |
| Extensive aggregation | Pinned kernel build passed | Executed v0: 25,000 | Split/merge/sleep/page replay required | Affordance preservation remains empirical |
| Re/Fr²/Pe/Da scale algebra | Pinned kernel build passed | Executed v0: 10,000 rational transforms | Regime benchmarks required | Morphology/ecology equivalence not implied |
| Coarse false-affordance example | Pinned kernel build passed | Executed v0: counterexample reproduced | Candidate LOD must face intervention replay | Unknown-future affordances remain open |
| Mechanics, transport, fracture, isotropy | Out of scope except selected identities | Unit/reference arithmetic only | Gates 2, 3, 5, 6 | Gate 9 for discovered functions |
| Raw-matter composability | Cannot prove from accounting | Fixtures may support measurement | Gate 7 physical response | Gate 8 blind rediscovery |
| Life, ecology, learning, culture | Cannot establish | Cannot establish | Necessary substrate evidence only | Gates 10–15 and H2–H6 |

The rule is strict: **a green formal cell cannot promote a red or empty numerical
or empirical cell.** The converse also holds: an appealing empirical run cannot
repair a failed accounting theorem or solver benchmark.

## Evidence bundle contract

Every executed validation bundle should contain:

```text
claim/gate identifier and acceptance criterion version
source commit and dirty-worktree state
compiler, dependencies, target architecture, and build configuration
scenario/configuration and unit-system hashes
initial checkpoint and intervention hashes
seed and deterministic random-stream identity
command line and start/end timestamps
raw observations and ledgers
pass/fail evaluator version and output
artifact SHA-256 values
human-readable summary generated from the same raw results
```

Failed and interrupted runs remain visible. A summary hash is not a substitute
for the underlying cases and executable provenance.

Use the mandatory fields and command/result tables in the
[publication/review evidence template](review-evidence-template.md). The current
C++ state/update formulas, approximation boundary, known failure modes, and test
mappings are recorded in
[implemented-subsystem-contracts.md](implemented-subsystem-contracts.md).

## Reproduced exact-arithmetic provenance

The exact-arithmetic suite using seed `260828` executed with the following counts:
100,000 conservative pair transfers; 100,000
equal/opposite momentum exchanges; 100,000 reaction extents across 6 balanced
reaction definitions; 100,000 energy conversions; 25,000 aggregation cases;
10,000 rational dynamic-similarity transforms; and one reproduced coarse-
graining counterexample. It reports the pre-hash SHA-256
`92405699657c404e4dcd324a16ca0d3cd0e7a82ff395ccfb277c47c10766a2da`.

The committed [`reference/validation_results_v0.json`](../reference/validation_results_v0.json)
is the reproduced fixture. It is valid evidence for those exact arithmetic
identities, subject to the present source and environment provenance. It is not a
full Gate 1 evidence bundle and is not evidence for a simulator.

## Formal verification boundary

The Lean candidates intentionally prove small, inspectable statements:

- conservation of paired algebraic transfers;
- positivity given a legal bounded transfer;
- equal/opposite momentum exchange;
- element conservation from `A nu = 0`;
- paired energy conversions and world/reservoir exchange;
- conservation under exact partition aggregation;
- the finite coarse-graining counterexample;
- the four declared scale-ratio identities; and
- an initial abstract interventional agreement relation, including that identity
  compression satisfies it.

Even a successful kernel build proves these theorems only under their definitions
and assumptions. It does not prove that C++ implements them, floating-point
reductions are stable, constitutive equations describe useful matter, chemistry
is expressive, or evolution is open-ended. Traceability from code transactions to
formal terms is future work.

## Promotion checklist

Before changing a cell or gate to green:

1. link the immutable raw evidence and evaluator;
2. verify hashes and source/build identity;
3. confirm the acceptance criterion predates result inspection;
4. check failures, exclusions, and residual distributions, not just an aggregate;
5. reproduce the command from a clean checkout; and
6. update only the column actually supported.
