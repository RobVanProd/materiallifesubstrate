# MLS Lean accounting proofs

This directory contains small formal models of accounting identities and one
coarse-graining counterexample. They are not a formalization of the full
simulator.

## Verification status

**PINNED BUILD PASSED:** On 2026-08-28, Lean `v4.33.0-rc1` and Lake `5.0.0`
compiled the project successfully (`963 jobs`). A source scan found no `sorry` or
`admit` tokens. This establishes only that the pinned Lean kernel accepted the
encoded statements; it does not verify the C++ implementation or physics.

The project pins both Lean and Mathlib to `v4.33.0-rc1`. Release candidates may be
less reproducible over time than archived stable releases; retain the generated
Lake manifest and dependency hashes in any evidence bundle.

## Reproduce the build

From this directory, with `elan` available:

```powershell
lake update
lake build
rg -n "\b(sorry|admit)\b" --glob "*.lean" .
```

Archive the complete command output, source commit, dirty status, `lean --version`,
`lake --version`, `lake-manifest.json`, and hashes. The grep is a review aid; the
Lean kernel build is authoritative for theorem acceptance.

## Coverage

- `Conservation.lean`: local transfers, positivity, momentum, energy, reservoir
  accounting, and partition aggregation.
- `Chemistry.lean`: general finite stoichiometric element conservation.
- `Scaling.lean`: Reynolds, Froude-squared, Peclet, and first-order Damkohler
  scaling identities over rational quantities.
- `CoarseGraining.lean`: exact separated-reactant false-affordance example.
- `SimulationSafety.lean`: an initial exact interventional agreement definition
  and identity-compression sanity theorem.

These theorems do not prove that production C++ matches the model, that floating-
point solvers converge, or that MLS supports material affordances or life. See
[`../docs/validation-status.md`](../docs/validation-status.md).
