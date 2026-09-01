# Authoritative Mechanics State Bridge Lab preregistration

## 1. Immutable parent and experiment boundary

The only accepted parent is:

```text
source commit: 2cc26e9a6e2aff8f40dec9787fe7e6e0e6b63f21
evidence tag: relation-geometry-resolution-lab-evidence-v1
tag object: ea423e350908b3446b754f7fb75457ca78313cde
decision: retain_relation_geometry_with_explicit_safe_domain_for_research
selected geometry: cancellation_resistant_binary64 (Path B)
safe domain: r/l0 >= 2^-24
```

The accepted archive has SHA-256
`653236250fb173e65662fe29a67a5c841bef0cdd3edb30ae00dccece4a82c9f7`.
The lab stops with `stop_inconclusive_or_wrong_parent` if any identity differs.
It installs no force in `World`, advances no position or clock, and remains
**NO PROMOTION TO DYNAMICS**.

## 2. Exact SI quantum contract

The base bridge profile is fixed before numerical output:

```text
Lq = 1 / 1,000,000,000 m
Mq = 1 / 4,096 kg
Tq = 1 / 1,000,000,000 s
Pq = Mq Lq / Tq       = 1 / 4,096 kg m s^-1
Eq = Mq Lq^2 / Tq^2   = 1 / 4,096 J
Fq = Mq Lq / Tq^2     = 1,953,125 / 8 N
```

All ratios are positive reduced rationals.  The existing
`PhysicalTimeScale{1,1000000000}` is exactly `Tq`.  The bridge accepts only
`MomentumMassToVelocityScale{1,1}` and kinetic-energy scale denominator `1`,
because those are the values satisfying both the ballistic raw equation and
the derived `Pq`/`Eq` definitions.  Merely positive non-default scale values
are legacy configurable scaffolds, not members of this mechanics profile.
Failure to reconcile any factor is
`stop_authoritative_unit_contract_inconsistent`.

The coherent resolution family uses
`R in {1,2,4,8,16}`:

```text
Lq(R)=Lq/R, Mq(R)=Mq/R, Tq(R)=Tq,
Pq(R)=Pq/R^2, Eq(R)=Eq/R^3, Fq(R)=Fq/R^2.
```

The same exact SI packet state therefore maps as position and mass raw values
times `R`, momentum raw values times `R^2`, and energy raw values times `R^3`.
The ballistic and integer kinetic-energy denominators remain one.  This is a
representation refinement, not a change in physics.

## 3. Frozen mechanics inventory

Use the accepted K4 central-distance relation graph on the rational tetrahedron
with packet IDs `1..4`, one authoritative base mass quantum per packet, unit
relation weights, and the already accepted local collective policy

```text
A = 3 * (K/G) / 20 with K/G=2,  B = 1/4.
```

The current packet positions are the exact authoritative image of a uniform
`1001/1000` dilation.  Thus every relation has `r/l0=1001/1000`, well inside
the sealed `2^-24` safe domain.  The accepted Path-B geometry, frozen symmetric
`H_force`, energy, conjugates, and relation forces are immutable inputs.
Mass is taken only from authoritative packet state.

Every exported binary64 value is serialized by its uint64 bit pattern.  The
independent oracle reconstructs those exact values rather than reparsing a
decimal rendering.

## 4. Mapping and round-trip gates

For every refinement and bounded packet:

1. exact raw-to-SI mapping is rational and invertible;
2. binary64 position, mass, momentum, energy, force, and time mappings record
   the exact rational decoding error;
3. nearest-even SI-to-raw conversion must recover every registered raw value;
4. the binary64 error must not cross a half-quantum decision boundary; and
5. mass used by every impulse and kinetic-energy row must equal the mapped
   authoritative mass.

An alias or mass substitution is a hard failure, never a tolerance pass.

## 5. Prescribed central impulse experiment

For every frozen relation coordinate, apply its Path-B relation force for the
exact interval `1,000,000,000 Tq = 1 s`, without changing position.  The exact
integer relation offset is reduced to its primitive integer direction `u`.
The only admissible authoritative impulse is `k u` for integer `k`; the first
packet receives `+k u` and the second receives `-k u`.  Hence raw linear
momentum and raw orbital angular momentum must cancel exactly.

For subdivision counts `N in {1,2,4,8,16}`, compare:

- **A — direct nearest:** nearest-even `k` independently for every subinterval;
  the discarded residual is evidence only.
- **B — fixed-point refinement:** the identical stateless nearest rule under
  the coherent `R` family.  The selected value is the smallest registered
  `R>1` passing every gate.
- **C — explicit remainder:** add the exact unrepresented scalar impulse to a
  relation-keyed causal remainder before nearest-even extraction.  The
  remainder is checkpointed, hashed, endpoint-canonical, permuted, and replayed
  in the lab.  It is ineligible unless B fails.
- **D — exact rational oracle:** independently implemented and permanently
  ineligible.

No candidate changes force, direction, mass, time, or energy law.

## 6. Refinement, subdivision, and selection gates

A selectable stateless refinement passes only if every relation/refinement row
has:

- exact raw `Delta P=0` and exact raw `Delta L=0`;
- componentwise total-impulse error strictly below `Pq(base)/32` at `R=16`;
- componentwise spread across the five subdivisions strictly below
  `Pq(base)/16`;
- monotonically shrinking registered worst-case impulse-error envelope as `R`
  increases;
- no hidden state, history input, or order-dependent residual;
- deterministic endpoint reversal, packet/relation permutation, and replay;
- binary64 agreement with the exact rational oracle on every nearest decision;
  and
- checked signed-64-bit representability.

The selected B refinement is the smallest `R>1` meeting the complete gate.
A failed coarser value remains preserved.  Candidate C additionally requires
bit-identical subdivision totals for all registered `N`, canonical
checkpoint/hash round trips, and a remainder balance identity.

## 7. Energy and flooring gates

For every row, independently compute the exact rational SI kinetic-energy
change caused by the applied raw impulses.  Compare it with:

```text
kinetic_energy_of(m, p, 1)
```

mapped through `Eq(R)`.  The integer result must equal the exact successive
floor convention.  The nonphysical flooring residual must be nonnegative,
strictly less than two `Eq(R)` for the two-packet update, and its registered
worst-case SI envelope must decrease as `R^-3`.  It is reported only as a
numerical residual; it is never stored as thermal, potential, or hidden energy.

The exact impulse-work identity

```text
Delta K = p1.J/m1 - p2.J/m2
          + |J|^2/(2m1) + |J|^2/(2m2)
```

is evaluated in rational SI units.  Lack of convergence under the coherent
scale family is `stop_authoritative_unit_contract_inconsistent`.

## 8. Mutation and formal gates

Independent mutations must reject altered quanta, nonunit raw scales, changed
mass/reference coordinates/`H`, direct Path-A geometry masquerading as Path B,
noncentral component rounding, unequal impulses, hidden or omitted remainder,
checkpoint/hash omission, subdivision-result relabeling, and altered
kinetic-energy division order.

Lean proves only exact rational unit identities, exact equal/opposite momentum,
central quantized orbital-angular-momentum conservation, and the explicit
remainder balance identity.  It makes no binary64 error or real force-work
claim.

## 9. Decision order

Apply the first matching outcome:

1. `stop_authoritative_unit_contract_inconsistent` on any dimensional
   contradiction or nonconvergent kinetic-energy floor.
2. `retain_direct_quantized_mechanics_bridge_for_research` if a stateless
   direct rule passes under the declared coherent refinement; select the
   smallest passing `R`.
3. `retain_explicit_mechanics_remainder_for_research` only if no stateless
   refinement passes and C is controlled, explicit, and replayable.
4. Otherwise `reconsider_fixed_point_authoritative_mechanics_state`.

Every disposition remains **NO PROMOTION TO DYNAMICS**.
