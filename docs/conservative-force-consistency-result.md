# Conservative Force Consistency Lab result

## Bounded decision

`retain_force_but_block_dynamics_on_degeneracy`

This is a finite-energy-gradient result on an explicit noncoincident domain.
It is **NO PROMOTION** to mechanics or dynamics. The lab installs no force in
the authoritative World, advances no clock, and adds no damping, contact,
collapse treatment, damage, fracture, gravity, chemistry, organism, renderer,
thermal conversion, or GPU path.

For frozen reference topology, lengths, weights, coefficients, and symmetric
constitutive coordinates, the experimental evaluator uses

```text
e_a = |x_j-x_i| - l0_a
U   = (1/2) e^T H e
g   = H e
f_i += g_a n_a
f_j -= g_a n_a
```

Each conjugate `g_a` is computed once in canonical relation coordinates and
can depend collectively on neighboring extensions through `H`. The evaluator
therefore remains the gradient of the accepted collective energy; it does not
replace that energy with independent springs.

## Result summary

Across the bounded graph inventory and the low, intermediate, and high
registered `K/G` policies, all noncollapse/nondegeneracy energy-gradient,
continuous force/torque/power, reference-tangent, finite-tangent, objectivity,
scale, label, and ordering gates passed. The only registered noncoincident
failures are the seven collapse-resolution predicates reported below. In
particular:

- the independently reconstructed Decimal-100 analytic gradient and
  high-precision directional derivatives agreed with `f=-grad U`;
- every tested internal-force sum and torque sum about both registered origins
  remained inside its arithmetic bound;
- the virtual-power identity `g dot (R v) = -(f dot v)` held;
- the reference limit joined `-R0^T H R0`, while finite tangents included and
  separately reported the material and geometric terms;
- high-precision mixed partials retained the symmetry required by a scalar
  potential;
- common proper rotation/translation preserved energy and rotated force,
  accepted uniform similarity followed `U -> s^2 U` and `f -> s f`, and
  packet IDs, packet/relation order, and endpoint orientation remained labels
  rather than physics;
- K4-minus-edge did not acquire a fabricated linear restoring force along its
  accepted true mechanism.

The deterministic full producer inventory contains 8 configurations, 24
operators, 2,094 force evaluations (2,088 valid noncoincident evaluations and
6 exact-coincidence failures), 876 reference-tangent rows, 168,696 finite
tangent rows, 312 metamorphic rows, and 84 compression rows. Exact coincidence
failed closed in all six registered operator paths without partial physical
output or an invented direction.

The positive collapse approach did not pass completely. Seven distinct
registered rows exposed numerical-domain limitations:

- all three octahedron policies failed to distinguish the selected relation's
  length after the registered one-ULP coordinate perturbation at
  `r/l0 = 1`; and
- the three octahedron policies plus K4 at `K/G=1/3` had an unresolved tangent
  condition classification at the registered `r/l0 = 2^-32` floor.

The three adjacency failures are also producer failure rows. Under the frozen
event accounting, the seven distinct rows produce seven independent
degeneracy-failure events; the three producer rows are reported separately and
are not double-counted as scientific predicates. There are no inconclusive,
energy-gradient, force-conservation, or finite-consistency failure events.
The registered decision order therefore requires
`retain_force_but_block_dynamics_on_degeneracy`, not the unrestricted
noncoincident retain result.

## Formal boundary

The finite Lean model defines the actual linearized relation conjugate and
force transitions and proves:

- `g=H e` and `f=-R^T g` imply `f=-R^T H e`;
- relation conjugate power equals negative packet-force power;
- a rigid virtual motion in `ker R` performs zero internal virtual work;
- the inherited symmetric/positive material-tangent and kernel results remain
  intact; and
- a finite collection of equal-and-opposite central relation forces has zero
  total force and zero total torque, without assuming either conclusion.

The exported axiom report is required to show only Lean/Mathlib's standard
`propext`, `Classical.choice`, and `Quot.sound` dependencies. These algebraic
theorems do not formalize square-root differentiation, floating-point
conditioning, a time integrator, or physical material validity.

## Preserved pre-final failures

Pre-final failures remain outside canonical evidence. Earlier local runs found
and corrected a floppy-mechanism tangent comparison against a binary64-noisy
target instead of its exact registered zero target. A later full preflight
failed closed because the producer's condition diagnostic called an inherited
native-`long double` singular-spectrum routine despite this lab's explicit
binary64 contract. After that call was replaced with a lab-local binary64
diagnostic, another preflight exposed an unjustified direct numeric equality
assumption between the raw binary64 and independent Decimal condition values.
The final design authenticates the raw diagnostic through an independent
binary64 reconstruction, keeps the Decimal classification separate, and
records any registered classification disagreement as degeneracy.

These corrections did not alter the retained energy, graph inventory,
positive-domain floor, physical tolerances, or decision order. Failed raw and
materialization paths and the earlier failed public CI run remain identified
in the evidence receipts/result handoff rather than being rewritten as passing
runs.

## Interpretation and limitations

The bounded positive result is that the accepted finite distance-relation
energy admits an objective, deterministic, conservative spatial gradient with
the expected continuous linear/angular momentum and power identities on the
declared domain `|x_j-x_i|>0`. The negative result is equally binding: the
tested binary64 representation loses decisive length/conditioning resolution
within the registered collapse inventory, including one ordinary-scale
octahedron adjacency probe. Dynamics are therefore blocked.

No conclusion here licenses time integration, stability claims, contact or
collapse handling, a continuum material calibration, or a production
mechanics solver. Exact coincidence remains outside the force domain; a future
collapse/contact design requires a separately authorized experiment and may
not be smuggled in as epsilon normalization, hidden repulsion, or tangent
regularization.
