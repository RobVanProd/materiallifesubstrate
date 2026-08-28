# Time + Transfer Lab preregistration

**Sealed before the final sweep:** 2026-08-28  
**Parent checkpoint:** `6649ebb7545b97197c80d3e752efc34c6646721a`  
**Branch:** `time-transfer-lab`

This document fixes the measurements, parameter sweep, tolerances, and
promotion rule before the final Time + Transfer bakeoff is run. Later evidence
must preserve this text and report every result, including failures. A change
to this protocol requires a new commit and invalidates any earlier result as a
selection result; such output may be retained only as exploratory evidence.

### Pre-sweep audit amendment

An adversarial review of the harness was completed before any full sweep. Only
a deliberately incomplete smoke run had been executed. That review found
ambiguities in the original roundoff rule and mismatches between several
implemented gates and this document. This revision reseals the protocol before
selection data exists. The smoke output remains nonselection evidence and may
not be used to choose a candidate.

The amended rules below make five points explicit:

1. candidate angular momentum means center orbital angular momentum for PIC
   and center-plus-affine angular momentum for APIC; center-only APIC orbital
   momentum remains a required diagnostic but is not itself an APIC
   conservation claim;
2. candidate energy means center kinetic energy for PIC and the documented
   center-plus-affine diagnostic for APIC; APIC center-only kinetic energy is
   reported but is not a promotion gate;
3. APIC's affine matrix reproduction and cumulative linear/angular totals are
   hard-gated where claimed;
4. the frozen Cartesian-product row counts are part of eligibility; and
5. the numerical harness can issue only a provisional numerical result. The
   overall recommendation requires an independent bundle check of source
   provenance, deterministic rerun, checkpoint/replay, C++, Lean, and CI.

The lab compares transfer operators. It does not implement or validate the
Moving Least Squares Material Point Method, continuum mechanics, or a physical
constitutive law.

## Scope and representations

The authoritative MLS-0 world continues to use exact signed 64-bit fixed-point
quanta for conserved ledgers. Physical time is represented separately from
`Tick`: `Time` is a count of configured time quanta, and the configuration
declares the rational number of SI seconds per time quantum. No transfer
residual may be written to stored, thermal, structural, chemical, or boundary
energy.

The experimental transfer state uses deterministic binary64 arithmetic and a
documented Cartesian grid spacing. It is deliberately outside the
authoritative world transition API. Particle order and grid reduction order
are canonical. Checkpoints preserve all authoritative fixed-point state
exactly; transient transfer workspaces are reconstructed.

The candidates are:

1. **PIC** — particle-to-grid mass-weighted velocity followed by weighted
   grid-to-particle velocity.
2. **APIC** — PIC plus one affine velocity matrix per particle, using the
   candidate's explicitly documented kernel moment matrix.
3. **FLIP diagnostic** — grid velocity increments applied to particle
   velocities. With no physical grid update in this lab, the zero-increment
   case is reported as an identity diagnostic and is ineligible for promotion.

All PIC/APIC tests use the same tensor-product quadratic B-spline weights and
27-node support. Candidate neighbor enumeration may use grid cells, but the
weights—not voxel adjacency—define transfer support.

## Fields and invariants

The prescribed velocity fields are:

- constant translation, `v(x) = b`;
- rigid rotation, `v(x) = omega cross (x - c)`;
- general affine motion, `v(x) = A (x - c) + b`, with a matrix containing
  symmetric and antisymmetric parts.

For every particle-to-grid and grid-to-particle pass, record:

- total particle and grid mass;
- particle and grid linear momentum;
- particle orbital angular momentum and grid orbital angular momentum about
  the same declared origin;
- particle and grid kinetic energy;
- particle velocity reconstruction error against the prescribed field;
- the standalone numerical-energy residual, never a physical ledger entry.

For APIC, the transfer-energy diagnostic includes the affine subcell term
defined by its local second-moment matrix. Translational-only particle energy
is also reported, but it cannot be used to claim energy conservation.

For each repeated-transfer row, also compare initial and terminal linear
momentum and the candidate's declared angular total. APIC affine-matrix
reconstruction is a separate metric from particle velocity reconstruction; a
correct velocity field with a corrupted affine matrix does not pass APIC.

## Error normalization

For scalar extensive quantities, use

`relative(a,b) = abs(a-b) / max(1, abs(a), abs(b))`.

For vectors and matrices, use the Euclidean/Frobenius norm in the numerator
and the largest corresponding norm in the denominator. Reconstruction uses
mass-weighted RMS velocity error divided by
`max(1, mass-weighted RMS reference speed)`.

The energy residual is signed:

`R_E = E_after - E_before`.

Its reported normalized magnitude uses the scalar rule above. Exact
fixed-point accounting failures and floating approximation residuals are
separate result fields.

## Frozen sweep

The final deterministic sweep uses seed `260828` and the Cartesian product
below unless a combination is mathematically redundant. Any omitted
combination must be named in the evidence bundle.

| Dimension | Values |
|---|---|
| candidate | PIC, APIC; FLIP identity diagnostic separately |
| velocity field | translation, rigid rotation, general affine |
| fractional grid phase | `(0.00,0.00,0.00)`, `(0.13,0.37,0.71)`, `(0.49,0.01,0.83)`, `(0.91,0.59,0.23)` |
| signed axis orientation | all 24 proper signed permutations (`det = +1`) |
| particle layout | regular 2x2x2, unequal-mass asymmetric, seeded jittered 27-particle cloud |
| grid spacing `h` | 1, 1/2, 1/4 in one declared length unit |
| mass ratio | 1:1 and 1:17 (the asymmetric layout also carries its specified spectrum) |
| transfer cycles | 1, 4, 16, 64 |
| physical step | `dt`, `dt/2`, `dt/4`, where base `dt` is four configured time quanta (4, 2, and 1 exact quanta) |

Grid spacing refinement holds the same physical particle configuration and
velocity field fixed. Timestep experiments advect the same affine field for a
fixed physical horizon using 1, 2, and 4 exact time increments. A pure transfer
cycle with no modeled grid evolution is timestep-independent by construction;
those rows are retained as a diagnostic and are not counted as evidence of
temporal convergence.

## Predeclared hard tolerances

These are binary64 reference tolerances, measured with deterministic summation
order:

| Claim | Maximum normalized error |
|---|---:|
| P2G mass | `2e-13` |
| P2G linear momentum, when claimed by candidate | `2e-12` |
| P2G orbital angular momentum, when claimed by candidate | `2e-11` |
| constant-field one-cycle reconstruction | `2e-12` |
| APIC affine/rigid one-cycle reconstruction | `5e-11` |
| claimed invariant after 64 cycles | `2e-9` |
| checkpoint exact roundtrip/replay | bit-exact authoritative state and identical state hash |

A result within tolerance is only numerical evidence for this finite transfer
experiment. It is not evidence of physical validity.

PIC is not expected to reproduce general affine fields or conserve their
orbital angular momentum after grid-to-particle reconstruction; those failures
must be measured, not hidden. FLIP without a grid update has no transfer
reconstruction claim and is not eligible for selection.

## Convergence rule

For reconstruction and absolute numerical-energy residual, a candidate passes
the refinement gate for a field/layout/orientation/phase family only if either:

1. all three resolutions are below the relevant hard tolerance; or
2. `e(h/4) <= 0.70 * e(h/2)` and `e(h/2) <= 0.70 * e(h)`, with
   `e(h/4) <= 0.25 * e(h)`.

Values below `5e-14` are treated as the binary64 roundoff floor for the ratio
test, but their unrounded values remain in the output. NaN, infinity, or a
missing row is an automatic failure. For a metric with a hard tolerance, three
values below that tolerance pass even if their sub-tolerance ordering changes.
For a metric without a hard tolerance, three values at or below the roundoff
floor pass. Otherwise, a finest-grid value above the roundoff floor and above
both coarser values blocks the ratio branch. This prevents meaningless ordering
of sub-roundoff values from creating a false failure while still rejecting a
resolved finest-level increase.

Timestep convergence uses the same rule on fixed-horizon position, velocity,
candidate-energy residual, and exact physical-time errors. The center-only
APIC energy series is diagnostic. The pure-remap rows remain explicitly
timestep-independent and are not temporal-convergence evidence.

The full run must contain exactly these data rows (CSV headers excluded):

| Table | Required rows |
|---|---:|
| `transfer_sweep.csv` | 124,416 (62,208 per candidate) |
| `h_convergence.csv` | 186,624 after adding the APIC affine-matrix metric |
| `ballistic_regrid_sweep.csv` | 31,104 |
| `time_convergence.csv` | 51,840 |
| `flip_identity_diagnostic.csv` | 5,184 |

The h-convergence total comprises four metrics for every PIC group, four
shared metrics for every APIC group, and a fifth affine-matrix metric for every
APIC group. Expected group and row counts are independently recomputed rather
than inferred from whichever map keys happened to be produced.

## Promotion and recommendation rule

A candidate is eligible for recommendation only if it:

1. passes mass, cumulative linear momentum, and its explicitly declared
   angular-total contracts under the complete sweep;
2. passes its declared translation and, for APIC, affine-matrix reproduction
   claims at every tested cycle count;
3. has no exact-accounting, checkpoint, deterministic-rerun, or continued
   replay failure;
4. passes the refinement rule for particle/grid reconstruction and candidate
   energy residual, and the timestep rule for fixed-horizon position, velocity,
   candidate energy, and exact clock;
5. has no grid-phase or proper-axis-orientation family exceeding the hard
   tolerances above for a claimed invariant.
6. produces every frozen row/group and comes from a clean source tree whose
   runtime HEAD equals the embedded configure-time SHA; and
7. has green local C++/Python/Lean gates and green independent CI replication
   at that exact source SHA.

Among eligible candidates, compare in this fixed order: worst affine
reconstruction error, worst angular-momentum error, worst normalized energy
residual, then worst 64-cycle drift. Here worst affine reconstruction is the
maximum of general-affine particle-velocity error and APIC affine-matrix error;
worst angular error spans P2G, round-trip, and cumulative candidate totals;
worst energy spans P2G, round-trip, and cumulative candidate-energy residuals;
and 64-cycle drift is the maximum claimed reconstruction or cumulative
invariant error on those rows. Implementation simplicity is only a final
tie-break. If no candidate is eligible, the result is **no promotion**. The
literature does not override this gate, and APIC is not a predetermined winner.

The C++ harness reports only numerical eligibility and a provisional numerical
ordering. It must always mark its own output as insufficient for overall
selection. An independent verifier reads the completed files back from disk,
checks their cryptographic hashes and dimensions, checks runtime Git
provenance, and combines the external checkpoint/build/Lean/CI gates. Only that
sealed bundle may state the overall recommendation.

## Evidence requirements

The sealed bundle must contain raw machine-readable rows and summarized worst
cases, exact commands, source SHA, compiler/tool versions, local versus CI
provenance, checkpoint/replay hashes, Lean theorem and `#print axioms` output,
all candidate failures, and the recommendation produced by the rule above.
It must explicitly state that the experiment excludes forces, stress, contact,
and every other constitutive-mechanics operation.

The harness's streaming FNV-1a values are diagnostics only. The independent
verifier must close and reread every file and record SHA-256 digests. Bytewise
determinism is required for repeated runs of the same executable/toolchain;
cross-toolchain floating tables are compared by the registered tolerances and
need not have identical hashes because C++ `long double` width and math-library
evaluation may differ.
