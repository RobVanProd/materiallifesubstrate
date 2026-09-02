# Authoritative Drift State Bridge Lab preregistration

## 1. Immutable parent and experiment boundary

The only accepted parent is:

```text
source commit: d8fca8b0bf59a92382048bfb1389126552ac92f3
evidence tag: authoritative-mechanics-state-bridge-lab-evidence-v1
tag object: 0a920fbb080525123d29dbea0a81b3bee3b9eec6
decision: retain_direct_quantized_mechanics_bridge_for_research
selected coherent representation: R=16
accepted force domain: r/l0 >= 2^-24
```

The accepted archive has SHA-256
`95cc1adc7f61b7d2db5009e3bfcdd185227a96d8e4513c91526886efc611660f`.
Any identity mismatch is `stop_inconclusive_or_wrong_parent`.  This laboratory
prescribes force-free drift at fixed momentum.  It does not evaluate a force,
apply an impulse, advance `World`, or authorize time integration.  Every result
remains **NO PROMOTION TO DYNAMICS**.

## 2. Frozen mechanics representation

The inherited exact unit family is unchanged:

```text
Lq(R)=Lq/R, Mq(R)=Mq/R, Tq(R)=Tq,
Pq(R)=Pq/R^2, Eq(R)=Eq/R^3, Fq(R)=Fq/R^2,

Lq=1/1,000,000,000 m, Mq=1/4,096 kg, Tq=1/1,000,000,000 s.
```

The accepted stateless central impulse bridge, integer kinetic-energy
convention, cancellation-resistant relation geometry, and force safe domain are
immutable inputs.  Drift changes position only.  Momentum, mass, kinetic energy,
all energy channels, and every impulse-bridge input remain unchanged.

Evaluate `R in {1,2,4,8,16}` first.  `R=16` is the first selectable value because
coarser profiles have already failed the combined mechanics bridge.  Only if the
drift gate fails at `R=16`, append `R in {32,64,128}` in that order.  Every appended
profile must rerun the inherited impulse and kinetic-floor gates before it can be
selected.

## 3. Mandatory parent fingerprint

Before evaluating a repair, call the inherited `World` ballistic transition on
two registered controls at `dt=1 Tq`:

- mass `10`, momentum `(10,0,0)`: exact displacement `(1,0,0)` must pass;
- mass `10`, momentum `(1,0,0)`: the nonintegral displacement must throw
  `std::domain_error`, preserve the physical-state hash, and preserve time/tick.

Both begin with zero `PositionRemainder3`.  Existing nonzero remainder state is
also ineligible.  Failure to reproduce this pass/fail fingerprint stops the lab.

## 4. Fixed force-free inventory

Base-profile authoritative packets use these exact raw momenta and masses; the
same SI states scale as momentum times `R^2` and mass times `R`:

| case | momentum | mass | purpose |
|---|---:|---:|---|
| zero | `(0,0,0)` | 37 | stationary identity |
| axis | `(5,0,0)` | 37 | axis-aligned fraction |
| mixed primitive | `(-3,5,-7)` | 41 | mixed signs, primitive direction |
| non-coprime | `(14,-21,28)` | 43 | `g=7`, primitive `(2,-3,4)` |
| magnitude | `(33,22,-11)` | 47 | `g=11`, primitive `(3,2,-1)` |
| equal velocity A | `(2,-3,1)` | 5 | mass-independence pair |
| equal velocity B | `(6,-9,3)` | 15 | same exact SI velocity as A |

Initial positions are small distinct integer vectors and are held fixed when a
displacement is evaluated.  Physical horizons are exactly `32`, `96`, and `160`
`Tq`, and subdivision counts are exactly `N in {1,2,4,8,16,32}`.  Every horizon
is divisible by every registered `N`; changing `Tick` is never used as timestep
refinement.

The axis, mixed, non-coprime, and magnitude cases form the center-of-mass group.
The equal-velocity pair is checked separately.  Packet enumeration, packet IDs,
and group order are permuted in regression rows without changing the result.

## 5. Candidate paths

**A — Cartesian nearest rounding (negative control).**  For each substep and
axis, independently nearest-even round

```text
p_axis_raw * dt_raw / m_raw.
```

It is permanently ineligible.  At least one registered mixed-direction row must
have a resolved nonzero exact `Delta L = displacement x momentum`; otherwise the
negative control has not been exercised.

**B — primitive-momentum directional quantization.**  For nonzero momentum,
write `p=g*u`, with positive component gcd `g` and primitive signed integer
direction `u`.  Nearest-even round only

```text
q = round_even(g * dt_raw / m_raw)
```

and apply `q*u`.  Zero momentum maps to zero displacement.  No component is
rounded independently.  Exact integer arithmetic must establish
`(q*u) x (g*u)=0` for every row.

**C — explicit position remainder.**  This path is not evaluated unless every
registered stateless refinement fails.  If opened, it must state whether the
remainder is numerical-error memory or subquantum physical position.  Because it
can affect later position and force, it is causal authoritative numerical state:
it needs an exact unit, canonical packet-owned checkpoint encoding, physical and
replay hashing, restart identity, permutation invariance, and a separately proved
balance law.  The existing untagged `PositionRemainder3` is not activated by this
preregistration.

The independent exact-rational oracle is permanently ineligible.

## 6. Error, spread, and selection gates

All errors are reported in metres and in the base physical length quantum `Lq`,
never only in candidate raw counts.  For each row export the exact rational SI
target, applied raw displacement, component and Euclidean-vector errors, raw and
SI orbital-angular-momentum delta, overflow margin, and unchanged momentum/mass/
kinetic-energy witnesses.

For a primitive direction `u`, subdivision `N`, and refinement `R`, the
registered nearest-rounding envelope is

```text
component error <= |u_axis| * N/(2R) Lq
vector error    <= ||u||_2 * N/(2R) Lq.
```

The corresponding full-versus-subdivision spread envelope uses `(N+1)/(2R)`.
These preregistered envelopes decrease exactly as `1/R`; observed errors must
remain inside them.  A selectable profile must additionally satisfy across the
entire inventory:

```text
maximum component error       <= 1 Lq
maximum vector error          <= 3/2 Lq
maximum component spread      <= 1 Lq
maximum vector spread         <= 3/2 Lq
maximum COM component error   <= 1 Lq
maximum COM vector error      <= 3/2 Lq.
```

The smallest coherent profile satisfying these bounds and all exact gates is
selected.  Ties at one-half are nearest-even.  Every rounding decision is
rederived from exact signed integer numerator/positive denominator input.

## 7. Exact conservation and translational gates

Every selectable row requires:

- momentum, mass, and integer kinetic energy literally unchanged;
- no heat, stored, structural, or other energy residual;
- exact raw `Delta L=0` per packet and for every packet group;
- equal applied displacement for the registered equal-SI-velocity pair whenever
  its target exceeds one selected `Lq(R)`;
- deterministic packet-ID relabeling, packet permutation, replay, and restart;
  and
- positive checked signed-64-bit headroom for accepted rows.

Near-overflow controls use an axis momentum whose `p*dt` product is the largest
registered safe product and its adjacent overflowing value.  The first must be
accepted without wrap and the second rejected before mutation.

## 8. Force-domain chord regression

Related-packet controls export integer initial/final relative vectors and an
integer rest length.  The oracle minimizes exactly

```text
r(s)=r0+s(r1-r0), 0<=s<=1
```

by clamping the exact rational stationary point.  A chord is admissible only if
its minimum squared ratio is at least `2^-48`, equivalent to
`min |r(s)|/l0 >= 2^-24`.  Registered safe, endpoint-below-boundary, and
interior-zero-crossing controls must be distinguished.  Crossing rows are
reported as domain events; displacement is never clipped and endpoints are never
moved.

## 9. Formal, independent, and mutation gates

Lean proves only exact statements: force-free drift leaves momentum unchanged;
an exact scalar displacement along momentum preserves orbital angular momentum;
primitive-direction integer quantization has that property; and coherent raw
refinement satisfies `(R^2 p) dt/(R m) = R(p dt/m)`.  It makes no floating-point
or empirical error claim.

The independent oracle consumes integer CSV fields, independently implements
signed rational nearest-even rounding, recomputes every target/error/cross
product/COM result, and checks exact chord minima.  Mutations must reject at
least: restored Cartesian rounding masquerading as B, wrong gcd/sign, half-away
rounding, changed mass or momentum, changed unit scale, hidden momentum or energy
mutation, omitted torque, false equal-velocity equivalence, overflow wrapping,
safe-domain clipping, and a crossing relabeled as admissible.

## 10. Decision order

1. Wrong parent fingerprint: `stop_inconclusive_or_wrong_parent`.
2. Cartesian rounding torque witness: `reject_cartesian_drift_quantization`.
3. B passes the combined bridge at `R=16`:
   `retain_stateless_directional_drift_bridge_for_research`.
4. The first passing value is finer than 16 and its inherited impulse/kinetic
   gates also pass:
   `retain_refined_stateless_mechanics_representation_for_research`.
5. Only fully explicit C passes: `retain_explicit_position_remainder_for_research`.
6. Otherwise: `reconsider_authoritative_fixed_point_kinematics`.

Every outcome remains **NO PROMOTION TO DYNAMICS**.
