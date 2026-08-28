# MLS Lean accounting proofs

This directory contains small formal models of accounting identities, an
executable traceability model for the implemented MLS transfer/reaction/boundary/
point-impulse transition shapes, and one coarse-graining counterexample. They are
not a formalization of the full simulator.

## Verification status

**HISTORICAL PINNED BUILD PASSED:** On 2026-08-28, Lean `v4.33.0-rc1` and
Lake `5.0.0` compiled the pre-hardening project at
`31c5733c618aead558dd7e4232a0976e2fc88bda` (`963 jobs`). A source scan found no
proof placeholders. That result does not cover later working-tree changes; each
hardening SHA requires its own captured build and axiom report. A kernel pass
establishes only the encoded statements, not the C++ implementation or physics.

The project pins both Lean and Mathlib to `v4.33.0-rc1`. Release candidates may be
less reproducible over time than archived stable releases; retain the generated
Lake manifest and dependency hashes in any evidence bundle.

## Reproduce the build

From this directory, with `elan` available:

```powershell
lake --wfail build
rg -n "\b(sorry|admit|sorryAx)\b|^\s*axiom\s+" --glob "*.lean" .
```

Do not run `lake update` as a reproduction step: it can rewrite the committed
manifest. Archive the complete command output, source commit, dirty status, `lean --version`,
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
- `TransitionModel.lean`: executable `PacketLite`/`WorldLite` transfers,
  reaction, boundary exchange, central pair impulse, the exact
  `Delta L = (r1-r2) x J` equation, transition-level conservation theorems, and
  emitted `#print axioms` reports for every exported claim in that module.
- `TransferLab.lean`: executable finite exact-rational PIC/APIC P2G and G2P
  maps, explicit partition-of-unity, first-moment, and affine dual-basis
  assumptions, and transition-definition-level mass, linear-momentum, affine
  reproduction, and APIC orbital-plus-affine angular-momentum theorems. It does
  not model a time integrator or continuum mechanics.
- `AffineAdvection.lean`: exact force-free affine advection with explicit
  two-sided inverse witnesses, the convected formulas
  `A' = A (I + dt A)⁻¹` and `b' = (I + dt A)⁻¹ b`, material-velocity
  preservation, an exact stale-gradient defect, and a homogeneous-coordinate
  proof that two analytic half steps equal one full step. The formal bridge
  constructs the full homogeneous inverse from the stated affine inverse and
  reduces the generator update back to the displayed `A'` and `b'` formulas;
  the resulting coefficient-level theorem proves that two half-step updates
  equal one full-step update. It introduces no inverse or conservation axioms
  and models no forces or constitutive laws.
- `MovingAPICLimit.lean`: an exact finite-stencil derivation of the
  Jiang--Schroeder--Teran moving-grid Eq. 38 update in the globally affine,
  force-free limit. It models old/new grid and particle positions explicitly,
  derives `B_next = A D_old`, and proves that a fixed second moment reconstructs
  the stale `C_next = A` rather than the analytically convected gradient, with
  an exact discrepancy formula. It assumes only the displayed finite-stencil
  moments and explicit inverse witnesses; it is not a mechanics model.
- `AxiomReport.lean`: committed `#print axioms` coverage for every theorem
  exported by all project modules; CI checks declarations against this list.

These theorems do not prove that production C++ matches the model, that floating-
point solvers converge, or that MLS supports material affordances or life. See
[`../docs/validation-status.md`](../docs/validation-status.md).
