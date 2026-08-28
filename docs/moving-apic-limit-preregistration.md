# Moving APIC limit lab preregistration

**Frozen before final data:** 2026-08-28 on branch
`moving-apic-limit-lab`, descended from the sealed Affine Advection Lab.

**Status:** bounded causal diagnosis. This is not a new solver bakeoff and
cannot promote E, E_oracleB, PIC, APIC, or any mechanics component.

Deterministic seed: `260828`. The lattice itself is nonrandom; the seed is
retained for traceability and for the unchanged historical control.

## Question

The sealed Affine Advection Lab refined `h` and `dt` while retaining the same
nine physical particles. Its particle density per grid cell therefore fell as
the grid was refined. This lab asks two narrower questions:

1. Does Path E converge when `h`, `dt`, and particle spacing are co-refined on
   a fixed physical domain at fixed particles/cell and fixed
   `U_ref dt / h`?
2. If it does not, does replacing only the transported post-G2P affine state
   with the analytic convected affine state remove the defect?

The exact continuum, units, paths, errors, and energy separation are frozen in
[`moving-apic-limit-contract.md`](moving-apic-limit-contract.md).

## Control 0 -- unchanged fixed-particle replay

The previous coupled test is retained unchanged and is explicitly **not**
continuum-limit evidence:

- general-affine field;
- phase `(0.49,0.01,0.83)`;
- orientation `p210_sppm`;
- unequal-mass asymmetric nine-particle layout at `1:17`;
- Paths C, D, and E; and
- `(h,dt) = (1,0.1), (0.5,0.05), (0.25,0.025), (0.125,0.0125)`.

This is exactly `3 paths * 4 levels = 12` raw rows. Its gate is the sealed
fingerprint: C and E each fail the same seven metrics--affine gradient,
intercept, dispersion, trajectory position, material velocity, center orbital
angular momentum, and center physical kinetic energy--while D passes all
eleven metrics. Exact mass/time and transfer-invariant gates must remain green.
Any mismatch blocks a causal verdict. These rows may never be pooled into the
new continuum regression.

The control is pinned, not regenerated or qualitatively substituted:

- accepted source SHA: `bb4b8bafd4a830b08c1e7e751090e850dbea1d7a`;
- immutable release tag: `affine-advection-lab-evidence-v1`;
- `final-a/coupled_refinement.csv` SHA-256:
  `67cb234a0ebaf6dac2251412eb845f18c78806b2d92857608f537439d8de2ad1`;
- exact 12-row schema-header SHA-256, including its LF terminator:
  `174cc146ca76cd9859975e14540d01999d1b74fe8f717eb935b446346bed6330`.

The new evidence may copy those bytes and independently revalidate them, but
it may not recompute them and call the result the sealed control.
The source gate also requires no diff from the accepted SHA in
`include/mls/affine_advection_lab.hpp`, `src/affine_advection_lab.cpp`, and
`apps/affine_advection_diagnostic.cpp`; Path E must remain the accepted
implementation, not a rewritten equivalent.

## Experiment 1 -- fixed-domain co-refinement

The initial domain, density, analytic field, horizon, mass quantum, and
particle-placement rule are identical at every level. The two grid origins
are `phase * h` for phases `(0,0,0)` and `(0.49,0.01,0.83)`.

| Level | `h` (m) | `dt` (s) | Time quanta | Steps | Nominal cells/axis | Nominal cells | `dx_p` (m) | Particles/axis | Particles | Particles/cell | Mass/particle (kg) | Mass quanta/particle |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | `1/2` | `1/40` | 4 | 4 | 4 | 64 | `1/4` | 8 | 512 | 8 | `1/64` | 64 |
| 1 | `1/4` | `1/80` | 2 | 8 | 8 | 512 | `1/8` | 16 | 4,096 | 8 | `1/512` | 8 |
| 2 | `1/8` | `1/160` | 1 | 16 | 16 | 4,096 | `1/16` | 32 | 32,768 | 8 | `1/4096` | 1 |

Each row has exactly `32768` mass quanta or `8 kg`. “Nominal cells” means the
fixed initial cube divided by `h`; the sparse grid remains unbounded and its
allocated-node count is reported separately rather than forced to this value.

The executed matrix is:

- field/orientation: general affine under `p210_sppm` only;
- phases: the two listed above;
- paths: E and E_oracleB; and
- levels: 0, 1, and 2.

It contains exactly `2 paths * 2 phases * 3 levels = 12` raw rows.

## Experiment 2 -- particles/cell increase

This smaller sweep holds the domain, continuum, `h=1/4 m`, `dt=1/80 s`, eight
steps, hard phase `(0.49,0.01,0.83)`, and `p210_sppm` fixed. Only particle
sampling density changes dyadically.

| Sampling level | Particles/cell | Particles/axis/cell | `dx_p` (m) | Total particles | Mass/particle (kg) | Mass quanta/particle | Total mass quanta |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1 | 1 | `1/4` | 512 | `1/64` | 64 | 32,768 |
| 1 | 8 | 2 | `1/8` | 4,096 | `1/512` | 8 | 32,768 |
| 2 | 64 | 4 | `1/16` | 32,768 | `1/4096` | 1 | 32,768 |

Paths E and E_oracleB produce exactly `2 paths * 3 levels = 6` raw rows.
This sweep diagnoses particle-density sensitivity; it is not a substitute for
the simultaneous `h,dt,dx_p` limit.

## Numerical one-step causal controls

Before any horizon/convergence verdict, every fixed-domain co-refinement
configuration emits one control row from its first physical step. This is
exactly `2 paths * 2 phases * 3 levels = 12` rows. E_oracleB retains the paper
pre-override state in this row; its intervention is evaluated separately.

For every particle, the row measures the maximum symmetric Frobenius-relative
error in:

1. complete-stencil moment stationarity, `D_next = D_old`;
2. the paper result `B_next = A_initial D_old`;
3. the paper effective gradient `B_next D_next^-1 = A_initial`;
4. the observed stale-gradient discrepancy against
   `dt A_initial^2 (I + dt A_initial)^-1`; and
5. for E_oracleB only, the post-override effective gradient against
   `A_exact(t_next)`.

Each applicable error must be finite and at most `5e-11`. A missing or failed
control blocks both causal and viability verdicts; a passing horizon unit test
cannot replace it. These are numerical diagnostics of the formal identity,
not evidence that the transfer is physically valid.

## Frozen convergence rule

The unchanged fixed-particle control retains its previously frozen four-level
rule: either all four values are below the hard tolerance, or each refined
value is at most `0.70` of its predecessor and the finest is at most `0.125`
of the coarsest.

Both new experiments use a three-level rule. For errors `(e0,e1,e2)`, a metric
passes only if either:

1. all three values are at or below its hard tolerance; or
2. `e1 <= 0.70 e0`, `e2 <= 0.70 e1`, and `e2 <= 0.25 e0`.

If `e2 > 5e-14` and exceeds either predecessor, the ratio branch fails. The
independent all-below branch may still pass. Missing, non-finite, negative, or
inapplicable data in a required metric fail. No post-result tolerance changes
are permitted.

Every raw row must first pass the exact and hard row gates in the contract.
Convergence cannot rescue failed conservation or malformed configuration.

## Exact completeness counts

| Evidence table | Required rows | Construction |
|---|---:|---|
| Fixed-particle raw control | 12 | 3 paths * 4 levels |
| Fixed-domain co-refinement raw | 12 | 2 paths * 2 phases * 3 levels |
| Particles/cell raw | 6 | 2 paths * 3 levels |
| **All primary raw rows** | **30** | exact sum above |
| Phase-pair rows | 6 | 2 paths * 3 co-refinement levels |
| One-step causal-control rows | 12 | 2 paths * 2 phases * 3 levels |
| **All raw and derived/control rows** | **48** | 30 primary + 6 phase-pair + 12 causal-control |
| Fixed-control convergence rows | 33 | 3 path families * 11 metrics |
| Co-refinement convergence rows | 44 | 2 paths * 2 phases * 11 metrics |
| Particles/cell convergence rows | 22 | 2 path families * 11 metrics |
| Phase-sensitivity convergence rows | 6 | 2 paths * 3 paired metrics |
| **All convergence rows** | **105** | exact sum above |
| Exact/hard gate-family rows | 153 | 9 scope/path/phase families * 17 named gates |
| Sealed-control prerequisite rows | 4 | source SHA + tag + CSV hash + schema hash |

Smoke or development output is provisional and cannot satisfy these counts.
Every final evidence summary must state expected and actual counts for every
row above and refuse a verdict when any count differs.

## Mandatory failure tables

The evidence bundle must report every convergence group, not only totals. Each
of the 105 rows contains:

- scope, path, phase where applicable, metric, and ordered level IDs;
- all raw errors and the registered hard tolerance;
- `all_below`, each `0.70` contraction comparison, the endpoint comparison,
  resolved-finest-increase flag, ratio-branch result, final pass, and a failure
  reason code.

The summary must additionally group failure counts by
`scope -> path -> phase -> metric`, including zero-failure groups. It must
show the worst value and its exact configuration for every metric. Exact and
hard row-gate failures are tabulated separately by scope/path/phase/gate;
phase is explicitly inapplicable for the sealed and particles/cell families.
They are never mixed with approximation failures.

The exact/hard table has exactly nine families: sealed C/D/E; co-refinement
E and E_oracleB at each of two phases; and particles/cell E and E_oracleB.
Every family emits all 17 named contract gates, including explicit
`applicable=false, evaluated=0, failures=0` rows. Thus it contains exactly
`9 * 17 = 153` rows. Applicable rows also contain the expected/evaluated
configuration count, failure count, worst value, tolerance, and exact worst
configuration. The four pinned-control prerequisites are a separate four-row
table and may not be hidden in the 153-row count.

For E_oracleB, every raw row retains pre-override transfer residuals,
post-override representation totals, the analytic `B=A_exact D` constraint
error, and the override magnitude. No affine/augmented energy diagnostic is a
physical-energy pass condition.

## Frozen causal decision logic

Define `core_pass(path)` to mean:

- every fixed-domain co-refinement and phase-derived exact/hard row gate for
  that path passes, including all applicable one-step causal controls;
- all 22 co-refinement metric groups for that path pass (two phases times
  eleven metrics);
- all three phase-sensitivity groups for that path pass.

Define `density_pass(path)` to mean that every exact/hard row gate and all
eleven particles/cell groups for that path pass. This is a quadrature-density
diagnostic; it is not part of the APIC viability predicate.

Define `viable_E` as `core_pass(E)`. Proper fixed-domain co-refinement at both
phases, the phase-sensitivity metrics, and every exact/hard gate therefore
decide whether E remains a viable research candidate under this bounded
experiment. A particles/cell failure must be reported and informs causal
attribution, but cannot by itself veto `viable_E` when proper co-refinement
passes. “Viable research candidate” is not promotion or approval for
constitutive mechanics.

The old-control fingerprint, four byte/source prerequisites, and all external
build/formal/replication gates are prerequisites for every verdict.
The source-SHA prerequisite includes the required zero-diff check for the
three accepted Path E source files; it is not a fifth hidden prerequisite.

| E core | E density | E_oracleB core | E_oracleB density | Result |
|---|---|---|---|---|
| pass | pass | pass | either | E remains viable for research under proper co-refinement. Report metric-level E/oracle differences; do not infer that every prior failure was solely a particles/cell artifact. No promotion. |
| pass | fail | pass | either | E remains viable under proper co-refinement; quadrature-density behavior is unresolved and both density tables must be reported, but density does not veto viability. No promotion. |
| fail | fail | pass | pass | Reject standard JST moving APIC as the MLS mechanics foundation for this requirement. Affine `B_p` transport is supported for the registered E-fail/oracle-pass metric intersection in both scopes. |
| fail | fail | pass | fail | Reject standard JST moving APIC for this requirement. Core affine-state support coexists with remaining density projection/quadrature; report both metric partitions. |
| fail | pass | pass | either | Reject standard JST moving APIC for this requirement. The proper co-refinement and density sequences disagree, so report mixed quadrature/co-refinement sensitivity rather than a singular attribution. |
| fail | either | fail | either | Reject standard JST moving APIC for this requirement. Because the oracle intervention also fails, classify the remaining defect as projection/quadrature under this experiment and stop for head-agent review. |
| pass | either | fail | either | E remains a viable research candidate from its proper co-refinement result, but E_oracleB is invalid/inconsistent for causal attribution. No promotion. |

An exact/hard row-gate, completeness, build, formal, replay, or replication
failure supersedes the table with `no viability or causal verdict`. A split by
phase is a core failure, never averaged away. The verifier must publish the
exact metric partitions: E-fail/oracle-pass (affine-state intervention
support), E-fail/oracle-fail (remaining projection/quadrature), and
E-pass/oracle-fail (intervention-induced failure). It must also publish both
paths' complete particles/cell failure tables even when `viable_E` is true.

No outcome promotes either path. The maximum allowed conclusion is causal
support within this finite three-level experiment.

## Independent verification and stop rule

The independent verifier must reconstruct lattice coordinates, exact particle
counts and masses, `U_ref dt/h`, analytic `A(t),b(t)`, expected Cartesian axes,
all convergence flags, grouped failure tables, and the decision string without
calling the C++ diagnostic implementation. Two full runs must be byte
identical. The bundle must also retain source SHA/branch/cleanliness, compiler
versions, seed, commands, C++/Python/Lean results, CI replication, and all
failed rows.

The three-level ceiling is frozen for feasibility. A fourth dyadic level would
contain `64^3 = 262144` particles and require 32 steps. Across two phases and
two paths it alone adds `33554432` particle steps, or `905969664` quadratic
27-node stencil samples, before map/reduction overhead. It is not silently
dropped after results; it is excluded here before the final run.

For scale, the selected three-level co-refinement contains `2236416` particle
steps or `60383232` stencil samples across both paths and phases. The selected
particles/cell sweep adds `598016` particle steps or `16146432` stencil
samples. Map allocation, canonical sorting, diagnostics, and deterministic
reruns add overhead, but this remains materially smaller than adding level 3.

After the bundle is complete, stop for head-agent review. Do not add stress,
forces, gravity, elasticity, contact, fracture, diffusion, reaction kinetics,
chemistry, organisms, rendering, GPU work, or another transfer family.
