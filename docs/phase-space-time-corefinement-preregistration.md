# Phase-Space/Time Co-Refinement Lab preregistration

## 1. Immutable parent and experimental boundary

The only accepted parent is:

```text
source commit: 243d52938ef22f7bf37e4e37decbe209bec504cf
evidence tag: time-integration-foundation-lab-evidence-v1
tag object: 855e89d86fa0192f7cd24a9743e545f588335c44
decision: temporal_convergence_blocked_by_authoritative_quantization
selected coherent representation: R=128
force domain: r/l0 >= 2^-24
```

The accepted public archive has SHA-256
`d2c8f6e468a5f81c60ba4300276b6b301e1f4ab966eb4198bc4e3a02bff55dbb`
and size `7,742,347` bytes. Before any candidate result, a detached checkout
of the evidence tag must reproduce the fixed-`R=128` raw twins, oracle
decision, 20 oracle mutations, failed KDK trajectory tables, internal-velocity
plateau, exact momentum and angular momentum, exact registered reversibility,
Galilean discrepancy, and secular long-run energy classification. A mismatch
is `stop_inconclusive_or_wrong_parent`.

This lab asks only whether the accepted stateless primitive-directional phase
space recovers second-order dynamics when its physical lattice co-refines with
the timestep. It does not compare integrator families, introduce remainder
state, install any result in `World`, or authorize authoritative dynamics.
Every disposition remains **NO PROMOTION TO AUTHORITATIVE WORLD DYNAMICS**.

## 2. Integer drift obstruction

For nonzero integer momentum `p`, define

```text
g = gcd(|px|, |py|, |pz|),    u = p/g.
```

The first formal target is the exact lattice constraint

```text
d cross p = 0  ->  exists k in Z, d = k u,
```

under explicit primitive/Bezout assumptions, together with the corresponding
minimum nonzero squared-displacement statement. Its physical interpretation
is

```text
minimum nonzero exact-L drift = Lq * ||u||.
```

For `g=1`, `u=p_raw`, hence

```text
Lq * ||u|| = ||p_phys|| * Tq / Mq.
```

This is an architecture constraint, not a floating-point or integrator-order
claim. Lean will prove exact algebra only.

## 3. Frozen mechanics

The candidate preserves unchanged:

- cancellation-resistant binary64 relation geometry;
- the accepted `r/l0 >= 2^-24` domain and complete-chord rejection;
- explicit Candidate-C relation topology;
- the local collective energy and symmetric `H_force`;
- conservative central forces;
- stateless primitive-central impulse quantization;
- stateless primitive-momentum directional drift;
- nearest-even rounding; and
- atomic kick-drift-kick semantics.

There is no position or impulse remainder, subquantum coordinate, error
diffusion, hidden accumulator, force cap, coordinate clamp, energy reservoir,
automatic substep, widened authoritative integer, or adaptive unit profile.

## 4. Registered unit family

Level `k=0` is exactly the accepted `R=128` profile. For levels
`k in {0,1,2,3,4}`, define from the base SI units, never by fitting output:

```text
Mq[k] = Mq[0]
Tq[k] = Tq[0] / 2^(3k)
Lq[k] = Lq[0] / 2^(6k)
Pq[k] = Mq[k] Lq[k] / Tq[k] = Pq[0] / 2^(3k)
Eq[k] = Mq[k] Lq[k]^2 / Tq[k]^2 = Eq[0] / 2^(6k)
Fq[k] = Pq[k] / Tq[k] = Fq[0]
```

The exact base values are:

```text
Lq[0] = 1 / 128,000,000,000 m
Mq[0] = 1 / 524,288 kg
Tq[0] = 1 / 1,000,000,000 s
Pq[0] = 1 / 67,108,864 kg m s^-1
Eq[0] = 1 / 8,589,934,592 J
Fq[0] = 1,953,125 / 131,072 N
```

The raw ballistic factor remains exactly one:

```text
dx_raw = p_raw * dt_raw / m_raw.
```

The exact identities `Eq=Pq^2/Mq` and `Fq*Tq=Pq` must hold at every level.
The independent oracle reconstructs every unit as an exact rational.

## 5. Physical timestep hierarchy and fixed-width gate

Use the same one-second physical horizon and five timesteps as the parent:

```text
h[k] = (1/16) / 2^k seconds
steps[k] = 16 * 2^k.
```

Because `Tq` co-refines, the exact raw timestep is

```text
dt_raw[k] = 62,500,000 * 2^(2k),
```

which is even at every level. Each trajectory uses one frozen level profile;
representation changes within a trajectory are forbidden.

Raw position magnitude grows by `2^(6k)` and raw momentum magnitude by
`2^(3k)`. Every conversion and arithmetic operation must check signed-64-bit
range before committing. The five levels are attempted without silently using
wider authoritative state. If fixed-width range prevents the preregistered
convergence test before the required window is established, the disposition is
`corefinement_blocked_by_fixed_width_state`.

## 6. Bridge, invariant, reversibility, and domain gates

At every level independently verify:

- central impulse and primitive-directional drift contracts;
- exact total momentum and orbital angular momentum at every stage;
- the kinetic-floor numerical-residual contract;
- equal-velocity consistency;
- Path-B relation geometry and safe/crossing chord classification;
- overflow fail-closed without partial state;
- complete checkpoint replay and deterministic twin evidence; and
- exact registered signed-time recovery within that fixed representation.

Changing a representation between the forward and backward halves is
forbidden. Any invariant or reversibility failure is
`reject_corefined_quantized_composition`.

## 7. Dynamic inventory and independent oracle

Reuse the Time Integration Foundation physical models, initial conditions,
horizons, and independently implemented 110-decimal-digit smooth ODE oracle:

1. K4 breathing/deformation;
2. K4 with nonzero internal velocity;
3. octahedron deformation;
4. translated K4 internal-velocity case;
5. common exactly representable velocity boost;
6. proper cubic-lattice rotation; and
7. deliberately domain-crossing pair.

Every physical SI initial state is mapped independently into each exact unit
profile. `H_force`, reference coordinates in SI, topology, force law, and the
smooth oracle trajectory remain identical across levels.

## 8. Temporal and first-order-control gate

Compare the sealed fixed-`R=128` result against order-matched co-refinement.
For the co-refined KDK endpoint error, require three consecutive timestep
halvings with

```text
1.6 <= observed order <= 2.4
```

before any declared floor. The symplectic-Euler negative control must remain
materially distinguishable and exhibit first-order behavior. Merely moving a
plateau without recovering formal order is
`reject_order_matched_space_time_corefinement`.

The independent oracle consumes exported raw integers and exact rational unit
definitions, independently maps them to SI, and uses two refined
high-precision integrations. An ordinary binary64 KDK path is never the truth
target.

## 9. GCD and primitive diagnostics

At every accepted kick and drift export, for every packet:

```text
g(p), u=p/g, ||u||^2, Lq*||u||,
```

plus stage, level, timestep, scenario, packet ID, and raw momentum. The minimum
physical drift is recorded from the exact squared norm and exact rational
`Lq`, with a binary64 presentation value only as a diagnostic. The same values
are recorded under the common-velocity boost. This directly tests whether the
parent plateau and boost warning track momentum-gcd collapse.

## 10. Frame and energy gates

Translation and proper signed-axis-permutation trajectories must remain exact.
After removing the exact common COM motion, boosted relative position and
momentum errors must converge at the same asymptotic order as the unboosted
trajectory until their registered lattice floor. A persistent resolved frame
effect is `reject_corefined_phase_space_frame_covariance`.

Repeat the short energy envelopes and registered sixteen-second diagnostic.
Maximum excursion, final error, and least-squares secular slope must contract
toward the independent smooth/KDK behavior. A resolved refinement-independent
secular bias is `reject_corefined_long_run_energy_behavior`. No energy error is
stored as physical state.

## 11. Mutation boundary

Independent mutations must reject at least:

- wrong parent identity or parent negative disposition;
- altered `Lq`, `Mq`, or `Tq` exponent;
- inconsistent derived `Pq`, `Eq`, or `Fq`;
- hidden `R` increase or widened authoritative state;
- overflow relabeled as an accepted step;
- missing or false gcd/primitive diagnostics;
- false second-order classification;
- false boosted convergence;
- altered force law, topology, `H_force`, or reference geometry;
- hidden remainder state; and
- false invariant, reversibility, checkpoint, or atomic-domain result.

## 12. Decision order

Apply the first matching result:

1. parent mismatch: `stop_inconclusive_or_wrong_parent`;
2. inconsistent exact unit family:
   `stop_corefinement_unit_contract_inconsistent`;
3. signed-width block before the convergence window:
   `corefinement_blocked_by_fixed_width_state`;
4. invariant or reversibility failure:
   `reject_corefined_quantized_composition`;
5. missing three-halving second-order window:
   `reject_order_matched_space_time_corefinement`;
6. nonconvergent boosted relative dynamics:
   `reject_corefined_phase_space_frame_covariance`;
7. resolved nonconvergent secular energy bias:
   `reject_corefined_long_run_energy_behavior`;
8. otherwise:
   `retain_order_matched_space_time_corefinement_for_research`.

Even the successful disposition is **NO PROMOTION TO AUTHORITATIVE WORLD
DYNAMICS**. Seal the causal result and stop before any integrator-family
comparison or explicit fractional-state experiment.
