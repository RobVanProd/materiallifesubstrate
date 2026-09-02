# Explicit Fractional Phase-State Lab preregistration

## 1. Immutable parent and experimental boundary

The only accepted parent is:

```text
source commit: 6dfaf29821ded7e1349358c671b52e73f345c26a
evidence tag: phase-space-time-corefinement-lab-evidence-v1
tag object: b4df81ae41b9b341ae49f564e784976f8b731084
decision: reject_order_matched_space_time_corefinement
force domain: r/l0 >= 2^-24
```

The accepted public archive has SHA-256
`cf3427082fc66426c4074e615decbc5353ba0bc216a1b480f0c688e18f8f3c8d`
and size `4,481,719` bytes. Before candidate interpretation, a detached
checkout of the evidence tag must reproduce the sealed parent raw twins,
oracle decision, 33 semantic mutations, quiet-case second-order windows,
internal-velocity plateau, improving primitive drift scale, vanishing central
relation kicks, exact momentum and angular momentum, registered exact
reversibility, frame result, and energy classification. A mismatch is
`stop_inconclusive_or_wrong_parent`.

This lab asks only whether explicit exact fractional packet phase state removes
the generic kick/drift lattice obstruction. It is not an integrator bakeoff.
It does not install dynamics in `World`, add contact or fracture, reinterpret
numerical energy, or promote any candidate. Every disposition remains
**NO PROMOTION TO AUTHORITATIVE WORLD DYNAMICS**.

## 2. Exact reciprocal lattice obstruction

For raw integer relation and momentum vectors `R,P in Z^3`, define positive
component gcds `g_r,g_p` and primitive vectors

```text
u_r = R/g_r,    u_p = P/g_p.
```

Exact-central integer kicks are integer multiples of `u_r`; exact-orbital-L
integer drifts are integer multiples of `u_p`. With physical state

```text
r = Lq R,    p = Pq P,
```

their minimum nonzero magnitudes satisfy

```text
J_min  = (Pq/Lq) * ||r||/g_r,
dx_min = (Lq/Pq) * ||p||/g_p.
```

The primary exact theorem is stated without square roots:

```text
J_min^2 * dx_min^2
  = ||r||^2 * ||p||^2 / (g_r^2 * g_p^2).
```

For primitive `R` and `P`, the right side is independent of `Lq` and `Pq`.
Lean must prove the rational algebra, including non-unit gcds, and connect the
minimum-vector facts to the prior primitive-multiple theorems. If the identity
or its architectural interpretation is false, candidate dynamics stops until
the interpretation is corrected. Lean does not prove floating-point behavior,
bounded-state viability, or integration order.

## 3. Frozen inherited mechanics

The experiment preserves unchanged:

- Candidate-C relation topology and orientation;
- the local collective energy and accepted symmetric `H_force`;
- cancellation-resistant binary64 Path-B relation geometry;
- the accepted `r/l0 >= 2^-24` state and complete-chord domain contract;
- conservative radial force scalar `g = H e`;
- KDK stage order and atomic rejection;
- nearest-even binary64 evaluation semantics; and
- the parent physical models, initial states, horizons, and timestep hierarchy.

There is no relation-keyed pending impulse, fixed fractional denominator,
subgrid snapping, denominator truncation, adaptive precision, force cap,
coordinate clamp, contact, hidden energy store, automatic substepping, altered
`H_force`, altered reference geometry, or persistent binary floating state.

## 4. Canonical authoritative fractional phase state

At every packet and Cartesian component, the authoritative state is

```text
x = Lq * (X + xi),    p = Pq * (P + pi),
X,P in signed-64,     xi,pi in Q.
```

The candidate uses the accepted fixed `R=128` level-zero unit profile at every
timestep level:

```text
Lq = 1 / 128,000,000,000 m
Mq = 1 / 524,288 kg
Tq = 1 / 1,000,000,000 s
Pq = 1 / 67,108,864 kg m s^-1
Eq = 1 / 8,589,934,592 J
Fq = 1,953,125 / 131,072 N.
```

Every rational is reduced with positive denominator; zero is uniquely `0/1`.
Deterministic integer carry keeps each residual in the exact half-open interval
`[-1/2,1/2)`, using `carry=floor(value+1/2)`. Equivalent fractions therefore
cannot produce distinct states or hashes. A carry outside signed-64 range
fails closed before commit.

Residuals are physical phase state, not error logs. They are checkpointed,
hashed, permuted with packet IDs, used by every state observer, and included in
exact momentum, exact orbital angular momentum, kinetic energy, force
geometry, kick, drift, covariance, replay, and rejection comparisons.

## 5. Force and drift bridges

For each relation, subtract complete exact rational positions first. Only the
resulting relative vector is rounded componentwise to binary64 for the accepted
Path-B evaluator; absolute packet positions are never independently rounded
before subtraction.

The accepted evaluator supplies binary64 relation length and conjugate scalar
bit patterns. Reconstruct both finite values as their exact rationals and form

```text
alpha = (signed timestep) * g_binary64_exact / r_binary64_exact.
```

The authoritative relation impulse is `alpha` times the complete exact
rational relation vector. Equal and opposite endpoint updates are therefore
exactly central in the full fractional geometry. Zero length and all accepted
domain failures reject atomically.

Drift is exact rational arithmetic:

```text
x_next = x + (p/m) * signed timestep,
```

followed only by canonical coarse/residual carry. It has no positional
projection and no directional rounding.

## 6. Registered trajectories and convergence

Reuse the parent one-second physical horizon and five timestep levels:

```text
h[k] = (1/16) / 2^k seconds,    k in {0,1,2,3,4}
steps[k] = 16 * 2^k.
```

Run KDK and retain the preregistered symplectic-Euler first-order diagnostic
control without selecting between integrators. The decisive scenarios remain:

1. K4 breathing/deformation;
2. K4 with nonzero internal velocity; and
3. octahedron deformation.

The exact same smooth 110-decimal-digit independent ODE oracle and physical
initial conditions are used. Every KDK scenario must exhibit three consecutive
halvings with `1.6 <= observed order <= 2.4` before any declared floor. The
internal-velocity case is decisive; quiet cases may not regress. The first-order
control must remain materially distinguishable.

Failure to recover the internal-velocity window is
`reject_fractional_phase_state_as_quantization_cure`.

## 7. Exact accounting, replay, domain, and covariance

At every kick, drift, and complete step, evaluate exact rational

```text
P_total = sum_i p_i,
L_total = sum_i x_i cross p_i.
```

Both must equal their initial values literally. Running the registered KDK
trajectory with `+h` and then `-h` must recover every coarse integer and reduced
residual numerator/denominator exactly. Domain rejection must leave the entire
prior state, time, energy observations, and event stream unchanged.

Checkpoint/resume must preserve canonical numerators and denominators
byte-for-byte and reproduce the complete event suffix. Packet permutation,
translation, proper signed-axis lattice rotation, and the common exactly
representable velocity boost reuse the parent semantics. Boosted relative
trajectory error must converge at the same order as the unboosted case.

Any accounting, reversibility, checkpoint, or atomicity failure is
`reject_fractional_phase_state_accounting`.

## 8. Energy diagnostics

Mechanical energy is diagnostic only:

```text
E_mech = exact rational SI kinetic energy + accepted relational U(x).
```

Repeat the short convergence traces and sixteen-second internal-velocity runs.
Maximum excursion, final error, and least-squares secular slope must contract
with timestep toward the independent smooth/KDK behavior. Energy discrepancy
never becomes heat, stored energy, or hidden state.

## 9. Preregistered exact-state complexity budget

At the initial state and after every complete registered step, export for every
packet, phase kind, and component:

- reduced residual numerator and positive denominator;
- numerator bit length (`0` has bit length `0`);
- denominator bit length;
- physical time and timestep level; and
- canonical state/checkpoint byte count.

Report maxima, medians, linear bit-growth slopes versus physical time, and
level-to-level growth. Before any candidate trajectory data, the finite
evidence-budget ceiling is frozen as:

```text
maximum numerator or denominator bit length: 262,144 bits
median numerator or denominator bit length: 131,072 bits
canonical encoded checkpoint size:          8,388,608 bytes
```

These limits are deliberately generous relative to the accepted signed-64
coarse state. The exact step that first crosses a ceiling is completed and
recorded without truncation, then that trajectory stops with
`complexity_budget_exceeded`. No rational is rounded, snapped, or discarded.

If convergence and covariance are restored but any registered short or long
trajectory crosses this ceiling, the disposition is
`fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved`.

## 10. Independent validation and mutation inventory

The independent validator consumes canonical integer/rational strings and
binary64 bit patterns. It independently checks reduction, interval carry,
state hashes, exact `P` and `L`, centrality, drift, unit identities, endpoint
errors, observed order, energy statistics, and complexity classification. The
smooth ODE oracle is separately formulated and refined twice; a binary64 KDK
trajectory is never the truth target.

Mutation tests must reject at least: wrong parent SHA/tag/object/archive;
changed topology, reference coordinates, `H_force`, Path-B geometry, or force
domain; direct absolute-position rounding; noncentral fractional kicks;
Cartesian drift rounding; a fixed denominator; unreduced or noncanonical
fractions; hidden remainder state; omitted residuals in `P`, `L`, energy,
hashing, permutation, or checkpointing; denominator truncation; false
reversibility, convergence, boost, energy, or complexity claims; changed
complexity ceilings; and promotion relabeling.

## 11. Decision order

Apply the first matching disposition:

1. parent mismatch -> `stop_inconclusive_or_wrong_parent`;
2. false obstruction theorem -> stop and correct the architecture diagnosis;
3. exact accounting/reversibility/atomicity failure ->
   `reject_fractional_phase_state_accounting`;
4. missing internal-velocity second-order window ->
   `reject_fractional_phase_state_as_quantization_cure`;
5. recovered dynamics with exceeded state-complexity budget ->
   `fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved`;
6. recovered convergence, covariance, energy contraction, and controlled state
   growth -> `retain_explicit_fractional_phase_state_for_research`.

Every outcome is `NO_PROMOTION`. Failed attempts remain preserved. Evidence is
materialized twice, independently validated, sealed, published, freshly
downloaded, reverified, and then the branch stops.
