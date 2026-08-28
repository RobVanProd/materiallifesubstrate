# Affine Advection Lab preregistration

**Frozen before the final sweep:** 2026-08-28 on branch
`affine-advection-lab`, descended from sealed Time + Transfer source
`f7873641733897708496d54b7fa8e4fa96a1b5f0`.

**Status:** causal diagnostic only. This is not a transfer-scheme bakeoff and
cannot promote PIC, APIC, or any other mechanics component. The sealed
`time-transfer-lab-evidence-v1` data and tag are immutable inputs.

## Question and preregistered hypothesis

The sealed APIC data have a distinctive time fingerprint: translation has no
time-family failures, while rigid rotation and general affine fields are near
roundoff after one remap and worsen after two and four remaps. This lab asks
whether a force-free particle step is retaining a stale or incomplete affine
Eulerian gradient.

Write the global field as

\[
v(x)=Ax+b.
\]

One force-free explicit particle-advection step is

\[
x'=(I+\Delta t A)x+\Delta t b.
\]

When \(I+\Delta t A\) is invertible, its exact Eulerian representation at the
new coordinates is

\[
A'=A(I+\Delta t A)^{-1},\qquad
b'=(I+\Delta t A)^{-1}b.
\]

It preserves each material particle velocity. Reusing the old field for the
second of two half steps creates the exact witnesses

\[
\delta x=h^2A(Ax+b),\qquad
\delta v=hA(Ax+b).
\]

The tested causal hypothesis is that this stale affine state, rather than the
one-remap representation error, causes the sealed nontranslation defect.

## Five fixed controls

| Path | Definition | Eligibility |
|---|---|---|
| A | Analytic ballistic evolution, no grid remap. | reference only |
| B | Existing static APIC P2G/G2P repeatedly applied with particle positions frozen and physical `dt=0`. | representation control only |
| C | The sealed existing static APIC `transfer_cycle`, followed by the existing ballistic position update in that order. | unchanged regression control; no promotion |
| D | Path C, but after advection replace the affine gradient with the analytic convected value above. | diagnostic control; permanently ineligible |
| E | A separate Jiang–Schroeder–Teran 2017 moving-state implementation using explicit `B_p`, computed `D_p`, old weights and old/new grid and particle positions. | literature/MLS evaluation only; no promotion in this lab |

Path E implements the published equations, not a wrapper that relabels Path C:
weights (18), mass and moment (24–25), P2G momentum (26), force-free grid
velocity/position (29–30), and G2P velocity, `B_p`, and position (37–39).
The full equations are documented in
[`affine-advection-lab-contract.md`](affine-advection-lab-contract.md).

## Mandatory pre-sweep sanity gate

Before any multiparticle final rows, Path E must pass the paper's original
isolated-particle, no-force result (JST 2017 Section 5.4, Eqs. 68–90):

\[
v_p^{n+1}=v_p^n,\qquad
x_p^{n+1}=x_p^n+\Delta t v_p^n,\qquad
B_p^{n+1}=B_p^n.
\]

The gate has 72 rows: three fields, two phases, three orientations, and four
timestep schedules. Any failed row blocks the multiparticle final run but is
preserved. This is the paper-derived meaning of stable/non-dissipative; no
separate affine-auxiliary energy invariant is invented.

## Frozen discriminating matrix

Seed: `260828`. Physical time uses a lab scale of exactly `1/80` second per
time quantum and remains separate from authoritative `Tick`. The fixed horizon
is eight quanta, or `0.1 s`.

| Axis | Frozen values |
|---|---|
| fields | translation; rigid rotation; general affine, using the sealed coefficients |
| fractional grid phases | `(0,0,0)`; `(0.49,0.01,0.83)` |
| proper signed orientations | `p012_sppp`; `p120_sppp`; `p210_sppm` |
| selected layout/mass pairs | regular 2x2x2 / 1:1; unequal-mass asymmetric / 1:17; seeded jittered 27 / 1:1 |
| core spacing | `h=0.5 m` |
| physical schedules for A/C/D/E | timestep quanta `8,4,2,1`, giving `1,2,4,8` steps over the same `0.1 s` horizon |
| frozen schedules for B | `1,2,4,8` remaps at unchanged positions; explicitly no physical timestep |

There are 54 core families and exactly `54 * 5 * 4 = 1,080` core raw
rows. The selected subset was checked read-only against the sealed results:
all 18 translation families pass the existing time gate and all 18 families
in each nontranslation field fail it. This check selected no outcomes from the
new lab.

One coupled sequence is also frozen: general affine field, phase
`(0.49,0.01,0.83)`, orientation `p210_sppm`, unequal-mass asymmetric layout at
1:17, and Paths C/D/E at

\[
(h,\Delta t)=
(1,0.1),(0.5,0.05),(0.25,0.025),(0.125,0.0125).
\]

This adds 12 rows. Total mandatory raw rows are therefore exactly **1,164**.
Smoke/development runs are nonfinal and must say so.

## Disjoint error categories

Every raw row carries applicability flags. An inapplicable measurement is
`NA`, never a fabricated zero.

### Static representation-transfer error

- immediate pre-advection particle velocity change;
- immediate effective affine-gradient change (`C` or `B D^-1`);
- occupied-grid reconstruction error;
- P2G and round-trip mass, linear momentum, center orbital angular momentum,
  and paper-augmented angular momentum as separate values.

### Affine-state/advection error

- effective gradient against analytic `A(t)`;
- recovered global intercept `b_p=v_p-C_p x_p` against analytic `b(t)`;
- cross-particle gradient and intercept dispersion; and
- for C, the observed stale velocity error against the exact witness above.

### Time/trajectory error

- mass-weighted position error against `x_0+T v_0`;
- material velocity error against `v_0`;
- linear momentum, center orbital angular momentum, and center physical
  particle kinetic-energy residuals; and
- exact mass quanta and exact elapsed time as separate exact fields.

Grid energy changes and APIC affine or center-plus-affine energy quantities are
standalone numerical diagnostics. They never close a physical ledger and do
not gate Path E unless a separately derived theorem establishes the claimed
invariant. This lab preregisters no such affine-energy invariant.

## Frozen tolerances

All floating comparisons use deterministic binary64 reductions and normalized
errors unless a unit is stated.

| Claim | Maximum error |
|---|---:|
| distributed grid mass | `2e-13` |
| linear momentum | `2e-12` |
| applicable static/paper angular total | `2e-11` |
| translation one-remap reconstruction | `2e-12` |
| affine/rigid one-remap reconstruction | `5e-11` |
| one-remap gradient/intercept/dispersion | `5e-11` |
| repeated/horizon identity, trajectory, gradient, intercept, dispersion | `2e-9` |
| roundoff floor for a no-hard-tolerance diagnostic | `5e-14` |
| exact mass/clock | exact equality |

Four-level convergence passes only if either every value is below its hard
tolerance, or each refinement is at most `0.70` of its predecessor and the
finest value is at most `0.125` of the coarsest. A diagnostic without a hard
tolerance may use the all-below branch only when every value is at or below
`5e-14`. Missing, `NaN`, or infinite data fail. A resolved finest-level
increase blocks the ratio branch unless the independent hard-tolerance branch
passes. The same rule applies to the coupled `h,dt` sequence.

## Frozen causal and Path E decisions

Path C reproduces the fingerprint only when all 18 translation families remain
below `2e-9`, and at least 17 of 18 families in each nontranslation field are
defect-positive: one-remap **trajectory position and material velocity** remain
below `2e-9`; the one-remap affine-gradient error matches the exact
`A-A' = dt A^2(I+dt A)^-1` stale-state witness within `5e-11`; a finer schedule
produces resolved material-velocity error above `2e-9`; the finest velocity
error is at least ten times both roundoff and its one-remap value; and its
four-level convergence gate fails. The affine-state error is expected to be
resolved at one remap—it is the proposed cause, not part of the sealed
near-roundoff trajectory fingerprint. Every exception is reported.

Path D removes the defect only when every selected family in all three fields
passes position, velocity, gradient, intercept, and dispersion at all four
levels through the all-below `2e-9` branch, and every resolved Path C finest
error is reduced by at least a factor of ten.

- C reproduces and D removes: stale/incomplete affine-state transport is
  **causally supported**.
- C fails to reproduce, or any D removal condition fails: the hypothesis is
  **rejected**.
- a build, formal, completeness, or replication gate failure: **no causal
  verdict**.

Independently, Path E passes its own lab gate only if all 72 isolated-particle
rows pass, exact mass/time and paper-derived momentum properties pass, static
representation gates pass, and every temporal and coupled family passes the
MLS convergence rule. Literature fidelity alone cannot pass the MLS gate. E
cannot be promoted here regardless of outcome.

## Evidence and stop rule

The sealed bundle requires two byte-identical full runs, an independent Python
verifier that reconstructs axes/counts/decisions and the analytic affine
witnesses without calling the C++ implementation, clean embedded Git
provenance, all historical tests, checkpoint/replay evidence, GCC/Clang/MSVC
CI, the exact Python oracles, and the pinned Lean build plus `#print axioms` for
every exported theorem. Lean source may contain no `sorry`, `admit`, `sorryAx`,
project-defined conservation axiom, or invertibility axiom.

After the diagnostic evidence is sealed, stop. Do not add stress, forces,
gravity, elasticity, contact, fracture, diffusion, reaction kinetics,
organisms, rendering, GPU work, or a new transfer family.
