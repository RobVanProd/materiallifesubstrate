# Authoritative Drift State Bridge Lab contract

## Scope

This laboratory evaluates the read-only, force-free mapping

```text
x_next = x + (p/m) dt
```

for fixed authoritative integer momentum and mass.  It does not call a force
evaluator, alter momentum, mutate `World`, apply an impulse, or select a time
integrator.  Its only selectable numerical operation is an integer displacement
evaluator constrained by the accepted coherent mechanics representation.

## Frozen parent

The parent is exact source
`d8fca8b0bf59a92382048bfb1389126552ac92f3`, evidence tag
`authoritative-mechanics-state-bridge-lab-evidence-v1`, and tag object
`0a920fbb080525123d29dbea0a81b3bee3b9eec6`.  The inherited `R=16` impulse
bridge, kinetic-energy convention, Path-B relation geometry, and force safe
domain `r/l0 >= 2^-24` are immutable.

## Candidate contract

Cartesian component rounding is a torque-producing negative control and cannot
be selected.  The stateless candidate reduces nonzero momentum to `p=g*u`,
nearest-even rounds only `g*dt/m`, and applies the resulting scalar multiple of
the primitive direction `u`.  Zero momentum produces zero displacement.  All
integer multiplication, addition, rounding, position addition, and cross
products are checked; overflow rejects instead of wrapping.

An explicit position remainder is outside the active candidate set unless all
registered stateless refinements fail.  No existing remainder field receives
causal semantics merely by being present in the packet schema.

## Claimed invariants

For a selectable row, momentum, mass, and kinetic energy are bit-for-bit
unchanged.  Displacement is exactly parallel to momentum in authoritative raw
arithmetic, so point-state orbital angular momentum is exactly unchanged.  No
rounding residual is transferred to any physical energy channel.  Equal exact
velocities produce equal displacement under the declared representation above
the selected spatial resolution.

Subdivision accuracy is a preregistered bounded numerical claim, not an exact
semigroup claim.  Exact full/substep equality is not asserted unless the integer
data establish it.  Error and spread are measured in the base physical length
quantum and must shrink under the coherent refinement envelope.

## Force-domain boundary

The straight relative-position chord is checked independently against the
accepted noncoincident force boundary.  A step whose chord crosses below
`2^-24` is classified as a future dynamics domain event.  This laboratory does
not clip, regularize, reject a `World` step, or change a packet endpoint.

## Promotion boundary

Passing this contract establishes only a deterministic research bridge from
fixed momentum to prescribed displacement.  It does not connect accepted force
to repeated impulses and displacements.  The disposition is always
**NO PROMOTION TO DYNAMICS**.
