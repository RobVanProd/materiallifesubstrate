# Bounded Fractional Phase-State Lab preregistration

## 1. Immutable parent and experimental boundary

The only accepted parent is:

```text
source commit: 6f25d7428fde7420c1f4cbe1e3565c11a28e817c
evidence tag: explicit-fractional-phase-state-lab-evidence-v1
tag object: a0feca21f7676e0b6f1443c483bd62448d68c65b
decision: fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved
archive SHA-256: 77aad47e1842b4fe29760594ee247f609b5d1e88ae7e6b370d86c0bdbb6c71de
archive size: 31,142,852 bytes
force domain: r/l0 >= 2^-24
```

Before candidate interpretation, the immutable parent payload and both raw
twins must match their sealed hashes.  The independent verifier must reproduce
the parent decision, the three KDK second-order windows, the first-order
control, exact momentum, orbital angular momentum, relation centrality,
signed-time recovery, registered boost result, short energy contraction, and
the exact-rational complexity crossing near 400 long-run force steps.  A
mismatch is `stop_inconclusive_or_wrong_parent`.

This lab asks only whether fixed-storage, variable-exponent fractional packet
phase state retains the dynamics recovered by exact rationals.  It does not
alter topology, reference geometry, `H_force`, the collective energy, force
law, Path-B geometry, safe domain, KDK stage order, physical scenarios, units,
or material model.  It does not install mechanics in `World`, select an
integrator family, reinterpret numerical energy, or relax the accepted
conservation specification.  Every disposition is **NO PROMOTION TO
AUTHORITATIVE WORLD DYNAMICS**.

## 2. Registered candidate family and arithmetic backend

The complete registered precision inventory is frozen before trajectory data:

```text
B = 64, 96, 128, 192, 256 significand bits
```

No precision may be added or removed after candidate trajectory results are
known.  One trajectory uses one fixed `B` for its entire lifetime.  Adaptive
precision, per-step widening, floating expansions, rational residuals,
compensation ledgers, discarded-bit logs, and any other causal side state are
forbidden.

The candidate reference implementation is `gmpy2.mpfr` from
`gmpy2==2.3.1`, backed by **MPFR 4.2.2**.  Both versions are runtime assertions
and evidence fields.  Every causal primitive is rounded separately using
round-to-nearest, ties-to-even.  Fused operations are forbidden unless an
operation is explicitly registered as fused; this experiment registers none.

The normalized leading-bit exponent

```text
E = floor(log2(abs(value)))
```

is restricted to the inclusive range `[-16382, 16383]`.  In MPFR's
`0.5 <= mantissa < 1` exponent convention this is context `emin=-16381` and
`emax=16384`.  Subnormalization is disabled.  NaN, infinity, invalid,
division-by-zero, exponent-range, underflow, and overflow events reject the
whole step atomically.  Inexact is expected, recorded, and is not a failure.
The context flags are cleared and inspected around every registered primitive;
ambient Python or thread context may not determine arithmetic.

The initial integer-valued parent coordinates are converted directly at the
declared precision.  All are exactly representable at every registered `B`.
Negation and copying preserve a stored value exactly and are not extra rounding
operations.  Every addition, subtraction, multiplication, division, or
exact-rational-to-MPFR conversion named below is one independently rounded
operation.

## 3. Authoritative experimental state and canonical serialization

Positions and momenta are stored in the inherited raw unit coordinates:

```text
x_physical = Lq * x_raw
p_physical = Pq * p_raw
```

Each `x_raw` and `p_raw` component is one finite MPFR number at the trajectory's
fixed precision.  There is no signed-64 coarse part and no separately retained
fractional residual.  Packet ID, signed-64 raw mass, signed-64 raw time, and the
six bounded binary phase components are the complete causal state.

For a nonzero component the canonical mathematical representation is

```text
value = (-1)^sign * M * 2^(E - (B - 1)),
2^(B - 1) <= M < 2^B,
E in [-16382, 16383].
```

The wire record for one component is, in order:

```text
sign            unsigned 8-bit, 0 or 1
precision       unsigned 16-bit little-endian, exactly B
leading exponent signed 16-bit little-endian, exactly E
significand M   exactly B/8 unsigned big-endian bytes
```

Zero has exactly one encoding: sign `0`, exponent `0`, and an all-zero
significand; its precision remains `B`.  Negative zero, a non-normalized
nonzero significand, unused padding, stale MPFR limbs, mixed precision, and
out-of-range exponents are rejected.  Decoding and re-encoding must reproduce
the bytes exactly.

Canonical state order is ascending packet ID.  The state encoding starts with
the fixed magic `MLS-BOUNDED-BINARY-PHASE-v1\0`, then a fixed version/profile
record, signed-64 raw time, packet count, and packet records.  Each packet
contains unsigned-64 packet ID, signed-64 raw mass, then `x,y,z,px,py,pz` in
that order.  Profile and fixed-width integers use explicit little-endian
encoding; no host object dump or textual MPFR representation is authoritative.

The exact component size is `5 + B/8` bytes.  Therefore the six-component
phase payload and the complete packet record including ID and mass are:

| B | phase bytes/packet | complete bytes/packet |
|---:|---:|---:|
| 64 | 78 | 94 |
| 96 | 102 | 118 |
| 128 | 126 | 142 |
| 192 | 174 | 190 |
| 256 | 222 | 238 |

The encoder must report both these construction values and complete state
bytes.  For a fixed model and `B`, causal state size must be identical at the
initial state, step 1, step 400, every checkpoint, and the completed 16-second
run.  Transient MPFR scratch is not causal state.  Any cache, compensation,
history, replay metadata, or discarded-bit record that can influence later
physics is causal state and invalidates the candidate.

## 4. Frozen units and force semantics

All precisions and timestep levels use the accepted `R=128` profile:

```text
Lq = 1 / 128,000,000,000 m
Mq = 1 / 524,288 kg
Tq = 1 / 1,000,000,000 s
Pq = 1 / 67,108,864 kg m s^-1
Eq = 1 / 8,589,934,592 J
Fq = 1,953,125 / 131,072 N
```

The identities `Pq=Mq*Lq/Tq`, `Eq=Pq^2/Mq`, and `Fq*Tq=Pq` remain exact
verifier contracts.

At trajectory initialization, `Lq_B=RN_B(Lq)` is created once and frozen as
declared configuration for that precision.  It is regenerated from the exact
unit on checkpoint restore and is not adaptive phase history.  For every force
evaluation and every relation, in frozen relation-index order:

1. Compute each raw relative component as
   `r_raw[a] = RN_B(x_j[a] - x_i[a])`.
2. Convert the already-relative component, never either absolute position, by
   `r_si_B[a] = RN_B(r_raw[a] * Lq_B)`.
3. Correctly round `r_si_B[a]` to binary64 ties-to-even and feed the resulting
   bit pattern to the accepted cancellation-resistant Path-B evaluator.
4. Evaluate extension, direction, `H_force`, conjugates, and energy in the
   exact accepted binary64 operation order.  The reference relation geometry,
   topology, orientation, and `H_force` bit patterns remain immutable.
5. Reconstruct the finite returned binary64 relation length and conjugate as
   their exact dyadic values, then convert them exactly to `B` bits.  Because
   they have at most 53 significant bits this conversion is exact for every
   registered precision.

An absolute-position binary64 round trip is forbidden.  Force evaluation may
not read exact-rational positive-control state or verifier residuals.

For a signed kick interval `q` in raw time quanta, define once for that kick

```text
c_kick = RN_B(q * Tq * Lq / Pq)
```

by one correctly rounded conversion from the displayed exact rational.  For
each relation compute, in order,

```text
a       = RN_B(c_kick * g_binary64_exact)
alpha   = RN_B(a / r_binary64_exact)
J[a]    = RN_B(alpha * r_raw[a])
p_i[a]' = RN_B(p_i[a] + J[a])
p_j[a]' = RN_B(p_j[a] - J[a]).
```

The same stored `J[a]` is used at both endpoints.  It must not be described as
exactly central: component rounding can make `r_raw cross J` nonzero, and
endpoint accumulation can change total momentum.

For drift, compute once per packet

```text
c_drift = RN_B(q / mass_raw)
d[a]    = RN_B(c_drift * p[a])
x[a]'   = RN_B(x[a] + d[a]).
```

Momentum is copied unchanged.  There is no position projection or directional
rounding.  KDK remains first half-kick, full drift, second half-kick, with the
same frozen-state force semantics and an even raw timestep.  The diagnostic
control remains full kick then full drift.  Only a fully validated state is
committed.

## 5. Exact dyadic observer and independent arithmetic verifier

Every finite stored component is an exact dyadic.  The verifier reconstructs
it from `(sign,B,E,M)` as an exact integer times a power of two; MPFR objects,
decimal formatting, and the candidate's serialization helpers are not used by
the independent implementation.

The independent rounder accepts an exact integer or rational operation result,
determines its leading exponent with integer comparisons, divides to a
`B`-bit significand, and resolves the remainder by nearest/ties-to-even.  A
significand carry increments `E`.  It implements the frozen operation graph
with Python integer/Fraction arithmetic and must reproduce candidate state
hashes, endpoints, registered checkpoints, event suffixes, and exact residual
rows.  Its unbounded integers are verifier scratch, never causal state.

For a nonzero exact operation result `y` whose rounded result has leading
exponent `E`, the registered unit roundoff and half-ULP bound are

```text
u_B = 2^-B
half_ulp_B(y) = 2^(E-B).
```

For every audited primitive the independent verifier requires the stored
result to equal its own ties-to-even result exactly, not merely to lie within
the half-ULP bound.  It also exports the exact rounding error and verifies the
half-ULP inequality.  Exact zero must round to canonical positive zero;
nonzero underflow is a fail-closed event.

The causal MPFR operation counts, excluding the frozen binary64 Path-B work,
are preregistered from packet count `n` and relation count `m`:

```text
one kick:              17m + 1 rounded operations
one drift:              7n rounded operations
one KDK step:          34m + 7n + 2 rounded operations
one control step:      17m + 7n + 1 rounded operations
```

Per kick, the constant term is the one `c_kick` conversion and `17m` comprises
`3m` relative subtractions, `3m` relative-unit
multiplications, `2m` coefficient operations, `3m` impulse multiplications,
and `6m` endpoint accumulations.  Per drift, `7n` comprises `n` exact-rational
coefficient conversions, `3n` displacement multiplications, and `3n` position
accumulations.  Diagnostic reads do not modify state and are excluded.

The verifier derives conservative residual bounds by summing exact local
half-ULPs, rather than fitting a bound to final residuals.  If
`eps_i = p_i'-(p_i+J)` and `eps_j = p_j'-(p_j-J)`, a relation kick has

```text
Delta P = eps_i + eps_j
Delta L = (x_i-x_j) cross J + x_i cross eps_i + x_j cross eps_j.
```

Writing the component-rounded impulse as `J=alpha*r+eps_J` gives
`r cross J = r cross eps_J`.  For drift, with
`eps_d=(x'-x)-c_drift*p`,

```text
Delta L = eps_d cross p.
```

The exact dyadic observer evaluates the left sides literally.  The independent
bound replaces each error component on the right by the sum of the
corresponding registered half-ULPs and applies the triangle inequality.  Bounds
are accumulated in stage order and must contain every measured component.

Raw evidence may omit only values that the independent implementation derives
exactly from retained canonical data.  The compact registered form keeps every
accepted invocation and causal row; stores current raw total-momentum and
orbital-angular-momentum components; stores all five raw relation-residual
vectors plus the causal geometry/impulse hashes; and derives physical scaling,
norms, vector hashes, and initial-state deltas independently.  Sampled
bounded-versus-exact errors may be stored as a versioned SHA-256 commitment to
the row identity and three canonical exact fractions, accompanied by a fixed
bounded diagnostic display, provided the verifier reconstructs and checks the
fractions independently.  A display is never authoritative and never enters a
gate.  This is an evidence-encoding change only; row inventory, operation
order, arithmetic, budgets, and scientific gates are unchanged.

As a separate sanity envelope, every registered run must remain within
`abs(x_raw)<2^48`, `abs(p_raw)<2^40`, `abs(r_raw)<2^49`, and
`abs(J_raw)<2^40`.  These are evidence bounds, not clamps.  Crossing one fails
the experiment rather than changing state.  They imply the coarse
operation-count bounds, per Cartesian component and after `N` KDK steps,

```text
|Delta P| <= 4*m*N*u_B*2^40 * Pq
|Delta L| <= (16*m+4*n)*N*u_B*2^48*2^40 * Lq*Pq.
```

The local half-ULP sums are authoritative; these deliberately loose formulas
are an independently checked backstop and make the operation-count scaling
explicit before final data exist.

## 6. Positive control and registered trajectories

The exact-rational implementation remains an ineligible positive control.  It
is run once per registered trajectory and advanced in lockstep with all five
bounded candidates so its growing state is neither duplicated by precision nor
retained as hidden candidate state.  It must reproduce the sealed parent
fingerprint before bounded results are interpreted.

Reuse the exact one-second inventory and timestep hierarchy:

```text
h[k] = (1/16) / 2^k seconds, k in {0,1,2,3,4}
steps[k] = 16 * 2^k
scenarios = K4 breathing, K4 internal velocity, octahedron deformation
paths = KDK candidate, symplectic-Euler negative control
```

Reuse the independent 110-decimal-digit smooth ODE oracle and its two
refinements.  A binary64 or bounded-MPFR KDK path is never the smooth truth
target.  Also reuse the registered translation, common velocity boost, proper
signed-axis rotation, packet permutation, domain-crossing trajectory,
interior checkpoint, and 16-second internal-velocity run.

For exact-rational comparison through time, all five bounded precisions advance
beside one exact-rational KDK state.  Exact rational values may be discarded
after the exact-dyadic comparison row is emitted.  On a long trajectory the
exact control stops only at its sealed complexity ceiling; bounded candidates
continue to 16 seconds, and evidence labels the remaining interval as lacking
an exact-rational state comparator.

## 7. Representation and temporal convergence gates

At every common sample define physical componentwise envelopes

```text
R_x(B,s,k) = max |Lq * (x_B-x_Q)|
R_p(B,s,k) = max |Pq * (p_B-p_Q)|,
```

with maxima over time, packet, and component.  Endpoint values and a fixed
power-of-two sample schedule are also retained.  Separately define the
dimensionless state norm by scaling positions by `1 m` and momenta by
`1 kg m s^-1` before an Euclidean norm.  The exact-rational KDK versus smooth
ODE envelope at matching samples is `T(s,k)`.

For each scenario and timestep, bounded representation error must decrease
strictly with increasing `B` until it first falls below `T(s,k)`.  Before the
first registered physical-budget pass, adjacent nonzero envelopes must also
satisfy

```text
R(B_high) <= 4 * 2^(-(B_high-B_low)) * R(B_low).
```

Exact zero passes only if every higher precision is also zero.  Once an
envelope is below its physical budget, later precisions need only remain below
that budget.  A positive precision-insensitive plateau is structural failure.

A selectable precision must have `R_state <= 0.1*T(s,k)` at all five levels
and must stay inside the physical component budgets in Section 9.  Against the
smooth oracle, KDK must show at least three consecutive halvings with
`1.6 <= observed order <= 2.4` for all three scenarios.  The internal-velocity
case is decisive.  The first-order control must show at least two consecutive
orders in `[0.6,1.4]`, and its maximum observed order must remain at least
`0.5` below the KDK maximum.

## 8. Conservation, centrality, reversal, and frame measurements

At every kick, drift, and committed step reconstruct exact physical dyadics:

```text
P = Pq * sum_i p_i
L = Lq*Pq * sum_i x_i cross p_i
C_relation = Lq*Pq * (r cross Delta p).
```

Export signed components, infinity-norm envelopes, local rounding errors,
independent half-ULP bounds, and least-squares slopes.  Exact equality is
reported when it occurs but is not manufactured with history or compensation.

Run `N(+h)` followed from that exact stored endpoint by `N(-h)`.  Export the
exact dyadic recovered-minus-initial state.  Bit identity is reported but is
not required.  The recovery position and momentum envelopes must contract with
precision and satisfy the registered physical budgets at a selectable `B`.

For the common-velocity boost, compare relative packet positions and momenta
after removing the common translation.  Discrepancies must contract with `B`,
contract with timestep until the precision floor, and show no resolved secular
internal motion.  Translation, packet permutation, and proper signed-axis
rotation are tested independently.  Rotation is classified as bit-exact,
exact-dyadic, or precision-bounded; no arbitrary `SO(3)` claim is made.

For every nonzero residual envelope above its physical budget, adjacent
precisions must obey the same factor-four unit-roundoff scaling rule from
Section 7.  Every envelope must also remain within the independently summed
local half-ULP bound.  A precision-independent floor, a bound violation, or a
signed residual slope that remains above budget is structural, not merely
"small roundoff."

## 9. Frozen physical error budgets

The budgets are fixed exact fractions of the inherited physical quanta, not
values chosen from candidate results.  Let `q_budget=2^-20`.  The complete
budget table is:

| quantity | exact budget | decimal SI value |
|---|---:|---:|
| position / relative position | `Lq*q_budget = 1/134217728000000000 m` | `7.4505805969238286e-18 m` |
| momentum / total momentum | `Pq*q_budget = 1/70368744177664 kg m s^-1` | `1.4210854715202004e-14 kg m s^-1` |
| orbital angular momentum / centrality | `Lq*Pq*q_budget = 1/9007199254740992000000000 kg m^2 s^-1` | `1.1102230246251566e-25 kg m^2 s^-1` |
| representation-induced energy | `Eq*q_budget = 1/9007199254740992 J` | `1.1102230246251565e-16 J` |

These componentwise infinity-norm budgets apply to bounded-versus-exact state,
signed-time recovery, boost/translation/rotation/permutation discrepancy,
total `P`, total `L`, and relation centrality as dimensionally appropriate.
Meeting a budget does not waive the analytic half-ULP or convergence gates.

For the 16-second run, the representation-induced energy-slope budget is

```text
(Eq*2^-20) / 16 s = 1/144115188075855872 J s^-1.
```

The corresponding signed total-momentum and angular-momentum slope budgets are
their table values divided by 16 seconds.  A candidate's physical KDK energy
oscillation is not expected to vanish with `B`; the precision gate applies to
`E_B-E_Q` where the rational control exists, and otherwise to convergence
toward the 256-bit trace after the 256-bit prefix has itself passed the exact
control.  A selectable precision must keep its maximum and final
representation-induced energy error and its fitted slope below budget.

The smallest registered `B` satisfying every gate is the only selectable
candidate.  A lower precision is not retained merely because a higher one can
repair its output during verification.

## 10. Long-run bias and energy diagnostics

Run every precision for the complete 16-second internal-velocity trajectory at
all five registered timestep levels.  Record:

- exact-rational state error for the prefix where the exact control exists;
- maximum and final bounded-versus-control state error;
- maximum mechanical-energy excursion, final error, mean offset, and
  least-squares slope;
- the same statistics for `E_B-E_Q` on the exact prefix;
- exact-dyadic total-`P` and total-`L` maxima, endpoints, and signed component
  slopes; and
- boost-relative state maxima, endpoints, and slopes.

Mechanical energy is reconstructed as exact-dyadic SI kinetic energy plus the
accepted binary64 relational potential reconstructed from its bits.  It never
becomes thermal energy or stored state.

On the full interval lacking an exact-rational comparator, 256 bits may be a
convergence anchor only after its exact prefix is below one-sixteenth of every
applicable physical budget and the 192/256 difference obeys unit-roundoff
scaling.  Every lower candidate's full-run trace must then agree with the
256-bit trace within budget.  This is a bounded convergence check, not a claim
that 256 bits is exact.

A precision-independent linear residual, a representation-induced energy
slope above budget, a total-`P` or total-`L` slope above budget, or a
boost-dependent secular internal trajectory gives
`bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved`.

## 11. Exact domain predicate and atomicity

The safe domain remains exactly `r/l0 >= 2^-24`, equivalently
`|r|^2 >= 2^-48 |r0|^2`.  Stored endpoints are reconstructed as exact dyadics.
For a chord `A+tD`, `0<=t<=1`, compute exact dyadic dot products.  The minimum
is at `A` if `A dot D >= 0`, at `A+D` if `A dot D <= -D dot D`, and otherwise
the safety comparison is performed without division:

```text
((A dot A)*(D dot D) - (A dot D)^2)
  >= 2^-48 * (r0 dot r0) * (D dot D).
```

Components are aligned to a common power of two and compared with bounded
integer scratch whose maximum width is mechanically derived from `B` and the
frozen exponent range.  Scratch is transient.  Equality is safe.  If the exact
predicate cannot certify the complete chord, the whole step rejects: time,
phase state, hashes, energy observations, and event stream remain unchanged.
There is no clipping or automatic substepping.

## 12. Checkpoint, replay, determinism, and evidence

At one interior point per precision/timestep level, decode a canonical
checkpoint and resume.  The final state and complete subsequent event stream
must be byte-identical to uninterrupted execution.  Two independent complete
materializations must be byte-identical.  All iteration orders, CSV schemas,
binary64 bit encodings, exact dyadic encodings, booleans, line endings, and JSON
serialization are explicit and locale-independent.

The raw evidence must include at least:

- metadata, precision profiles, unit identities, immutable parent hashes, and
  positive-control receipts;
- frozen reference packets, relations, and `H_force` bit patterns;
- canonical initial, endpoint, recovery, and checkpoint states;
- per-sample bounded-versus-rational and bounded-versus-smooth errors;
- primitive operation counts and exact rounding-audit bounds;
- exact-dyadic momentum, angular-momentum, and relation-centrality residuals;
- short and long energy traces and fitted statistics;
- reversal, boost, translation, rotation, permutation, domain, replay, and
  fixed-state-size results; and
- source, dependency, compiler, Lean, twin, mutation, seal, release, and fresh
  public-download receipts.

The independent implementation consumes binary encodings and binary64 bit
patterns, not human decimal approximations.  Mutation tests must reject at
least: wrong parent identity; changed force inputs; wrong precision inventory;
wrong MPFR version or rounding mode; altered exponent range; subnormal or
negative-zero state; noncanonical significand; adaptive precision; hidden
residual/history; absolute-position binary64 conversion; changed operation
order; fused arithmetic; false operation count or half-ULP bound; omitted
state in any observer; false temporal order; false precision scaling; false
`P`, `L`, centrality, reversal, frame, energy, domain, size, or replay result;
changed physical budgets; and promotion relabeling.

GCC, Clang, MSVC, Python candidate/oracle, pinned Lean, semantic mutations,
outer-seal mutations, immutable-tag CI, twin evidence, and a fresh public
download must all pass.  Failed attempts remain preserved.

## 13. Formal scope

Lean does not formalize MPFR or claim a floating-point error bound.  It retains
the reciprocal integer-lattice obstruction and exact-rational positive-control
theorems.  For an ideal central pair impulse `J` and stored endpoint errors
`eps_i,eps_j`, formalize

```text
Delta P = eps_i + eps_j
Delta L = x_i cross eps_i + x_j cross eps_j
```

under explicit equal-and-opposite centrality assumptions, together with the
more general displayed identity containing `(x_i-x_j) cross J`.  Formalize the
drift identity `Delta L = eps_d cross p` under an ideal displacement parallel
to `p`.  These exact identities interpret measured residuals; numerical bounds
remain independent executable evidence.

## 14. Decision order

Apply the first matching disposition:

1. positive-control parent mismatch -> `stop_inconclusive_or_wrong_parent`;
2. highest registered precision fails internal-velocity second-order dynamics
   -> `reject_bounded_binary_fractional_phase_state`;
3. dynamics recovers but conservation, centrality, frame, reversal, or long-run
   residuals have a precision-independent, out-of-bound, or secular component
   -> `bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved`;
4. dynamics and all residuals converge with precision, but no registered `B`
   satisfies every frozen physical budget ->
   `bounded_phase_state_converges_but_required_precision_unresolved`;
5. the smallest fixed `B` passes temporal, representation, conservation,
   centrality, frame, long-run, domain, deterministic replay, state-size, and
   precision-scaled residual gates ->
   `retain_bounded_variable_exponent_phase_state_for_research`.

Every result remains **NO PROMOTION TO AUTHORITATIVE WORLD DYNAMICS**.  The lab
is complete only after it distinguishes unbounded phase information from
bounded, systematically discardable low bits, seals that causal result, and
stops.
