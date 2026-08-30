# Relational Observability Confirmation contract

## Scope

This laboratory measures whether explicit central-distance relations contain
enough kinematic information to distinguish generic three-dimensional
non-rigid motion from the six infinitesimal rigid motions. It selects no
constitutive response and performs no physical time evolution.

## State variables and units

Authoritative laboratory input is limited to:

| Variable | Unit | Meaning |
|---|---|---|
| stable packet ID | none | label only; tested by full bijections |
| packet position | metre | physical center position |
| packet mass | exact integer quanta | checkpoint provenance; unused by `R` |
| packet velocity | metre/second | transient operator test input |
| relation endpoints | packet IDs | explicit generic physical topology |
| relation reference length | metre | finite-objectivity/checkpoint evidence |

The sparse lookup grid is transient and may only enumerate candidate pairs.
It supplies no velocity gradient, strain, deformation, stress, force, or
hidden mechanics state.

## Update/operator law

There is no state update. For each noncoincident relation `(i,j)`, the
read-only central observable is

```
d|x_j-x_i|/dt = ((x_j-x_i)/|x_j-x_i|) . (v_j-v_i).
```

Stacking these rows forms the rigidity operator `R`. Global translations and
infinitesimal rotations lie in `ker(R)`. A registered ordinary 3-D graph is
mechanically observable only when its complete kernel equals the realized
rigid-motion subspace.

## Accounting and objectivity

This lab creates no matter, momentum, angular momentum, or physical energy and
does not close any physical ledger with a numerical residual. It checks exact
checkpoint preservation and read-only diagnostics. A finite proper rigid
motion preserves every bond length. A positive uniform scale multiplies every
length by that scale while leaving unit-direction `R` unchanged up to the
corresponding orthogonal input/row permutations.

## Numerical approximation

Packet positions and raw rows use binary64. Rank is diagnosed independently
by complete Householder CPQR and a direct rectangular one-sided-Jacobi SVD.
The Python verifier uses exact dyadic/modular rank and selected 90-digit direct
SVD calculations. Thresholds, ambiguity bands, perturbations, deformations,
and selection rules are frozen in the preregistration.

## Known failure modes

- underconnected or intentionally flexible graphs have genuine floppy modes;
- coincident endpoints make a unit direction undefined and fail closed;
- near-degenerate geometry can make a mathematically rigid graph numerically
  unsafe even before exact rank is lost;
- arbitrary IDs or relation ordering can leak into results if semantic
  canonicalization is wrong;
- normal equations can square conditioning and manufacture a false null tail;
- row deletion, normalization, regularization, or stabilization can hide an
  observability failure;
- an explicit relation topology is physical input and may be too restrictive
  for later material classes even if this lab passes.

Classical bond-based peridynamics is only a representation reference here.
Central relations are not claimed to span arbitrary isotropic constitutive
behavior, and known Cauchy/Poisson restrictions remain outside this kinematic
test.

## Tests and stop boundary

Tests cover raw row norms, complete spectra/null residuals, exact small ranks,
all inherited generic/flexible configurations, translations, rotations,
scales, packet/relation permutations, full ID bijections, fixed-topology
geometry perturbations, nonsingular homogeneous deformations, the complete
nested deletion path, lookup/brute-force agreement, checkpoints, twin
determinism, GCC/Clang/MSVC, Python, and Lean trust gates.

No outcome authorizes force, stiffness, elasticity, pressure, damage,
fracture, contact, gravity, chemistry, organisms, rendering, or GPU work.

