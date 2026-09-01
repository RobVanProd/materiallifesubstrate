# Authoritative Mechanics State Bridge Lab result

## Decision

```text
unit contract: coherent on the exact registered mechanics profile
base direct quantization: rejected as subdivision dependent
retained bridge: stateless central nearest quantization at coherent refinement R=16
explicit remainder: controlled but not selected and not authoritative state
kinetic floor: convergent bounded numerical residual, never physical energy
decision: retain_direct_quantized_mechanics_bridge_for_research
promotion: NO_PROMOTION
```

The accepted cancellation-resistant Path B, `r/l0 >= 2^-24` force domain,
relation graph, local collective energy, symmetric `H_force`, and central force
law were not changed.  No `World` momentum update, time step, or position
integration was added.

## Exact unit reconciliation

One coherent base profile embeds the existing authoritative conventions:

```text
Lq = 10^-9 m
Mq = 1/4096 kg
Tq = 10^-9 s
Pq = Mq Lq/Tq     = 1/4096 kg m/s
Eq = Mq Lq^2/Tq^2 = 1/4096 J
Fq = Mq Lq/Tq^2   = 1953125/8 N
```

It requires the existing default `PhysicalTimeScale{1,1000000000}`, raw
momentum/mass velocity scale `1/1`, and kinetic-energy denominator `1`.
Positive non-default raw scales are not silently admitted: they do not satisfy
this profile's derived units and fail with
`stop_authoritative_unit_contract_inconsistent`.

The coherent family

```text
Lq/R, Mq/R, Tq, Pq/R^2, Eq/R^3, Fq/R^2
```

preserves the exact SI packet state and both existing raw equations.  All
registered authoritative packet positions, zero initial momenta, and masses
round-tripped through binary64 to the same raw values.

## Impulse and conservation result

The lab evaluated six K4 relation impulses at five refinements, five interval
subdivisions, and three candidate paths: 450 independently checked rows.  Each
integer impulse was selected on the primitive authoritative relation lattice,
not by independent Cartesian component rounding.

All 450 rows had literal integer:

```text
Delta P = 0
Delta L = 0
```

The exact-rational oracle reconstructed every force and SI mapping input from
its binary64 bit pattern.  It agreed with every nearest-even integer decision,
energy floor, endpoint orientation, checkpoint hash, and decision label.

## Refinement and subdivision result

Worst component impulse error and subdivision spread, in base `Pq` units, were:

| R | worst error | subdivision spread | gate |
|---:|---:|---:|:---|
| 1 | `2767011611056743/1125899906842624` | `4` | fail |
| 2 | `3473176032627509/2251799813685248` | `2` | fail |
| 4 | `515211797371495/1125899906842624` | `1/2` | fail |
| 8 | `95476312099637/2251799813685248` | `1/16` | fail |
| 16 | `22630588127847/1125899906842624` | `1/32` | pass |

The worst-error envelope decreases strictly.  `R=8` fails the strict
preregistered error/spread boundary; `R=16` is the first complete stateless
pass.  The base direct path is a genuine negative control: different
subdivisions produce different total raw impulses.

Candidate C's explicit relation-keyed remainder makes every registered
subdivision total identical and passes canonical checkpoint/hash/replay tests.
It is not selected because stateless B succeeds.  Consequently no remainder
field enters authoritative packet state or checkpoints.

## Energy result

For every row, the oracle independently evaluated the exact SI kinetic change,
exact impulse-work identity, and the literal successive integer divisions in
`kinetic_energy_of`.  The two-packet floor residual is always nonnegative and
below `2 Eq(R)`.  The observed worst residuals include:

```text
R=4:  1/524288 J
R=8:  9/16777216 J
R=16: 25/268435456 J
```

The registered bound contracts as `R^-3`; the bridge therefore converges under
the coherent scale refinement.  The residual remains numerical accounting
error.  It is not heat, stored energy, potential energy, or hidden state.

## Independence and formal boundary

The independent regression rejects 12 mutations covering altered units, raw
scale inconsistency, changed mass/reference geometry/`H`, Path A relabeled as
Path B, noncentral rounding, unequal impulses, hidden remainder, omitted
checkpoint hashing, subdivision relabeling, and changed kinetic division order.

Lean proves exact rational derived-unit/refinement identities, equal/opposite
momentum, primitive-central orbital conservation, and remainder balance.  It
does not claim binary64 stability or a real force-work error theorem.

## Disposition

The smallest surviving bridge is a deterministic, stateless central
quantization rule on the coherent `R=16` representation.  This validates a
research bridge only.  It does not authorize a production fixed-point migration,
force installation, time integration, or dynamics.

**NO PROMOTION TO DYNAMICS.**
