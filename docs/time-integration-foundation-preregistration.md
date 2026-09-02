# Time Integration Foundation Lab preregistration

## 1. Immutable parent and experimental boundary

The only accepted parent is:

```text
source commit: ffefb2ea9ee0f032946af4ed23acd12883f20cfe
evidence tag: authoritative-drift-state-bridge-lab-evidence-v1
tag object: 5a6237a9dcbe676aa4c89c10d5f9f94e935507e6
decision: retain_refined_stateless_mechanics_representation_for_research
selected coherent representation: R=128
force domain: r/l0 >= 2^-24
```

The accepted public archive has SHA-256
`8e17d8ea685e9b4717021bdae446533b1297788e2b9e63e4a0def991f7e040f8`
and size `6,496,485` bytes.  A mismatch in any parent identity or in the
accepted impulse, drift, Cartesian-torque-control, or chord fingerprints is
`stop_inconclusive_or_wrong_parent`.

This is the first bounded repeated-dynamics experiment.  It does not install
the result in `World`, select a production integrator, or authorize contact,
fracture, gravity, chemistry, life, rendering, GPU execution, or authoritative
dynamics.  Every disposition remains **NO PROMOTION TO AUTHORITATIVE WORLD
MECHANICS**.

## 2. Frozen mechanics and state

The lab uses, unchanged:

- cancellation-resistant binary64 relation geometry;
- the Candidate-C central-distance relation topology;
- the accepted local collective energy with symmetric `H_force`;
- central relation forces;
- the coherent `R=128` quanta;
- stateless primitive-central impulse quantization; and
- stateless primitive-momentum directional drift.

At `R=128` the exact quanta are:

```text
Lq = 1 / 128,000,000,000 m
Mq = 1 / 524,288 kg
Tq = 1 / 1,000,000,000 s
Pq = 1 / 67,108,864 kg m s^-1
Eq = 1 / 8,589,934,592 J
Fq = 1,953,125 / 131,072 N
```

The experimental phase state is only `(time_raw, packet id, position_raw,
momentum_raw, mass_raw)`.  There is no remainder, coordinate clamp, force cap,
energy reservoir, automatic substep, or persistent floating-point state.

## 3. Registered maps and atomic KDK semantics

Candidate B is signed-time kick-drift-kick Störmer/velocity Verlet.  For an
even nonzero raw timestep `h`, each half kick has the exact duration `h/2` time
quanta.  All relation forces in a kick are evaluated from one frozen position
state.  Each relation impulse is rounded once on the accepted primitive central
lattice and equal/opposite impulses are accumulated in canonical relation
order.  Drift applies the accepted primitive-momentum directional nearest-even
map once per packet.

Every relation is checked at the initial state.  Every complete straight
relative-position chord proposed by drift is checked against
`r/l0 >= 2^-24` before any update is committed.  A force, arithmetic, or chord
failure returns the unchanged prior phase state, unchanged time, and the first
canonical offending relation.  The second force evaluation and half kick occur
only after all chords pass; the complete state is committed only after every
stage succeeds.

Candidate A is the permanently ineligible first-order kick-drift symplectic
Euler control: one full kick at the initial position followed by one accepted
directional drift and the same atomic chord rule.  It exists only to falsify a
convergence test unable to distinguish first from second order.

## 4. Fixed models and trajectories

The K4 reference packets are `(0,0,0)`, `(1,0,0)`, `(0,1,0)`, and `(0,0,1)`
metres with the six complete-graph relations.  The octahedron uses the six
signed coordinate axes and its twelve non-antipodal edges.  Every packet has
exact mass `1 kg`.  Relation weights are one and the frozen collective policy
is

```text
A = 3*(K/G)/20 = 3/10, B = 1/4, K/G = 2.
```

Registered dynamics are:

1. K4 uniform `1001/1000` breathing displacement about its centroid, initially
   at rest;
2. the same K4 deformation with a zero-total-momentum internal velocity;
3. an octahedron deformation of at most `1/1000` in each registered component;
4. an exact translated copy of case 2;
5. a case-2 copy with common exactly representable velocity `1/128 m/s` along
   `(1,-1,1)`; and
6. a two-packet diagnostic whose proposed chord crosses exact coincidence.

All non-crossing initial states are separated from the force-domain boundary by
more than `2^20` times the threshold.  Signed-axis permutations with determinant
`+1` provide the exact cubic-lattice rotation controls; no arbitrary `SO(3)`
claim is made.

## 5. Characteristic frequency and timestep hierarchy

Before trajectory output, the accepted K4 reference tangent was assembled with
the registered one-kilogram masses.  Its six positive generalized eigenvalues
are, in `s^-2`, approximately

```text
0.503060201, 0.503060201, 0.54,
1.316939799, 1.316939799, 2.4.
```

Thus `omega_max = sqrt(2.4) = 1.549193338... s^-1`.  The registered largest
timestep is `1/16 s`, giving `omega_max*h = 0.0968246...`, more than a factor of
twenty below the linear Verlet limit `2`.  This choice is fixed before repeated
trajectory data.

The physical horizon is exactly one second and the five halving levels are:

```text
h seconds: 1/16, 1/32, 1/64, 1/128, 1/256
h raw Tq:  62500000, 31250000, 15625000, 7812500, 3906250
steps:     16, 32, 64, 128, 256
```

Every raw timestep is even.  The long-run energy diagnostic is fixed at sixteen
seconds with `h=1/64 s`.

## 6. Independent trajectory oracle and convergence gate

The independent Python oracle consumes exported integer state and IEEE-754 bit
patterns for all binary64 reference coordinates and `H_force` entries.  It
reconstructs those floats exactly, evaluates the accepted potential and force
independently at at least 100 decimal digits, and integrates the smooth ODE with
two refined high-precision RK4 calculations.  The two oracle endpoints must
agree to `2^-70` in the dimensionless state norm.

With `L*=1 m` and `P*=1 kg m/s`, endpoint error is

```text
sqrt(sum_i |dx_i|^2/(N L*^2) + sum_i |dp_i|^2/(N P*^2)).
```

A resolved pair has both errors above
`64*max(Lq/L*,Pq/P*)`.  Candidate B must show observed order in `[1.6,2.4]`
over three successive resolved halvings.  Candidate A must show order in
`[0.6,1.4]` over at least two resolved halvings and differ from B by at least
`0.5`.  After the fixed lattice floor is reached, three consecutive increases
greater than five percent are a systematic worsening and fail.  Absence of the
candidate-B window is
`temporal_convergence_blocked_by_authoritative_quantization`; `R` is never
increased in this lab.

## 7. Exact invariants, reversibility, and covariance

Literal raw total momentum and orbital angular momentum are recorded after
each kick, drift, and complete step.  Every accepted closed-system stage must
equal its initial values exactly.  Any change is
`reject_quantized_time_composition`.

For every registered non-crossing trajectory, run `N` steps with `+h` and then
`N` with `-h`.  Initial and recovered phase-state bytes must be identical.  No
tolerance is admissible.  Failure is
`reject_quantized_verlet_reversibility`.

Translated cases must have bit-identical relative authoritative trajectories.
Proper signed-axis permutations must be exactly covariant after semantic
inverse mapping.  For the common-velocity boost, compare COM-removed position
and relative momentum.  The discrepancy must decrease on every resolved
halving until it is at most `64 Lq` in position and `64 Pq` in momentum, after
which it may plateau below twice that envelope.  A resolved nonconvergent frame
effect is `reject_quantized_dynamics_frame_covariance`.

## 8. Energy, checkpoint, and domain gates

Mechanical energy is reported as exact rational kinetic energy reconstructed
from integer momentum and mass plus an independently evaluated accepted
potential.  The existing floored integer kinetic energy remains a separate
diagnostic.  No discrepancy enters any energy ledger.

For the one-second hierarchy, the maximum energy-excursion envelope must show
the same resolved second-order window as state error.  The sixteen-second run
records maximum excursion, mean offset, final error, and least-squares secular
slope.  A monotone same-sign increase in every quarter-window with a final
error exceeding the maximum bounded oscillatory excursion at the preceding
three quarters is classified as secular drift.

At the midpoint checkpoint, encode the complete experimental phase state and
subsequent event sequence.  Decode/resume must produce byte-identical final
state and events.  Twin runs and evidence trees must be byte-identical.

The crossing diagnostic must name its relation and return byte-identical prior
state, time, momentum, and energy diagnostics.  Non-atomic rejection is
`reject_time_domain_safety`.

## 9. Formal and mutation boundary

Lean proves only exact algebraic composition: central pair kicks preserve total
momentum and orbital angular momentum; momentum-direction drift preserves both;
their KDK composition preserves both; registered signed inverse laws imply KDK
reversibility; and an atomic rejection function returns its prior state.  It
does not call the finite-lattice map symplectic and proves no floating-point,
convergence, or error bound.

Independent mutations must reject at least: wrong parent/refinement, changed
`H` or reference coordinates, Cartesian impulse/drift substitution, noncentral
or unequal kick, omitted chord interior, partial state commit, odd timestep,
hidden remainder, altered nearest-even tie, false reversibility, false order,
boost-result relabeling, rotation remap error, checkpoint omission, and energy
discrepancy stored as physical energy.

## 10. Decision order

Apply the first matching result:

1. parent mismatch: `stop_inconclusive_or_wrong_parent`;
2. exact momentum or angular-momentum change:
   `reject_quantized_time_composition`;
3. non-bit-identical signed-time recovery:
   `reject_quantized_verlet_reversibility`;
4. no resolved second-order window:
   `temporal_convergence_blocked_by_authoritative_quantization`;
5. nonconvergent boosted internal dynamics:
   `reject_quantized_dynamics_frame_covariance`;
6. non-atomic domain rejection: `reject_time_domain_safety`;
7. otherwise:
   `retain_quantized_stormer_verlet_dynamics_candidate_for_research`.

The successful disposition would retain only a candidate for the later
integrator-family experiment.  It still means **NO PROMOTION TO AUTHORITATIVE
WORLD DYNAMICS**.
