# Physical interaction support contract

## Status and scope

This hardening contract replaces voxel-defined locality in MLS-0. The sparse
grid is a disposable spatial index: it may generate a superset of candidate
packet pairs, but cell membership or adjacency never authorizes heat transfer,
momentum transfer, chemistry, or any future physical interaction.

The conservation ledger also folds authoritative packet snapshots independently
of voxel cells. Cell diagnostic totals may be unavailable on fixed-width
overflow; such a diagnostic overflow cannot reject a representable world
transition merely because packets share a voxel.

## State variables and units

- Packet positions are exact signed 64-bit `Length` quanta in three axes.
- `WorldConfig::interaction_radius` is an explicit positive `Length` quantity.
- `voxel_edge` remains an independent positive storage/index length.

## Update and eligibility law

For point positions \(r_1,r_2\) and radius \(h\), a pair is eligible exactly
when

\[
  \lVert r_1-r_2\rVert^2 \le h^2.
\]

The boundary is inclusive. `World::transfer_heat` and the explicitly
actuated/dissipative central-impulse scaffold enforce this predicate before
their staged packet transition. A rejected operation leaves the world intact.

## Conservation law

Eligibility changes no state. An accepted transition must independently pass
the world matter, energy, linear-momentum, and angular-momentum ledger. Being
inside support is necessary for a pair operation; it is never evidence that a
particular physical law is valid.

## Numerical approximation

MLS-0 uses a spherical point-support cutoff in fixed-point position quanta. It
does not yet implement a smooth kernel, packet volume overlap, contact, or a
continuum discretization. Distance comparison is exact: a portable two-limb
unsigned product computes each square and checked two-limb additions compute
the sum. No signed square or compiler-specific 128-bit extension is used.

## Failure modes and explicit limitations

- A non-positive radius is invalid configuration.
- The hard cutoff is discontinuous at the radius and is not a validated kernel.
- Point distance ignores unresolved packet extent and shape.
- The grid has no candidate-neighbor API yet; this reference scan is not a
  throughput claim.
- Eligibility invariance does not establish isotropic forces, convergence, or
  physical validity.

## Adversarial tests

`tests/physical_support_tests.cpp` covers exact face-, edge-, and corner-like
offsets; all axis permutations/sign rotations of inside/outside offsets; an
ineligible pair inside one voxel; an eligible pair across a voxel face; 399
translated phases spanning positive and negative voxel boundaries; explicit
accepted face, two-axis edge, and three-axis corner crossings; a rejected distant
corner; a cell-diagnostic-overflow/world-total witness; extreme
signed coordinates; 32-bit limb boundaries; exact-radius inclusion; wide squared
sums; and zero-radius rejection. These are contract tests only, not mechanics
validation.
