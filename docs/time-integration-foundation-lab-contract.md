# Time Integration Foundation Lab contract

## Scope

This laboratory is the first bounded repeated application of the accepted
force, impulse, and drift bridges. It evaluates an experimental signed-time
phase map outside `World`; it does not install authoritative dynamics or add a
production force API.

The frozen parent is source
`ffefb2ea9ee0f032946af4ed23acd12883f20cfe`, evidence tag
`authoritative-drift-state-bridge-lab-evidence-v1`, and tag object
`5a6237a9dcbe676aa4c89c10d5f9f94e935507e6`. The accepted representation is
`R=128`, with cancellation-resistant relation geometry and force domain
`r/l0 >= 2^-24`.

## Candidate map

The selectable candidate is signed kick-drift-kick Störmer/velocity Verlet.
Both half kicks use exact integer half-duration counts, frozen-state relation
forces, and the accepted stateless primitive-central impulse rule. Drift uses
the accepted stateless primitive-momentum directional rule. A first-order
kick-drift splitting is a permanently ineligible convergence control.

No position or impulse remainder, force cap, coordinate clamp, hidden energy,
automatic substep, contact law, topology change, or higher resolution is
permitted.

## Transaction boundary

Each step is evaluated on a copy. Initial relations must satisfy the accepted
force domain. Before drift is committed, every complete straight relation
chord is checked against the same domain. The second force evaluation and kick
occur only after all chords pass. Any domain or arithmetic failure returns the
prior phase-state bytes and unadvanced physical time.

The experimental checkpoint contains only time and canonical packet ID,
position, momentum, and mass integers. It contains no model cache, relation
geometry, numerical remainder, or energy ledger.

## Required evidence

Every accepted kick, drift, and complete step must preserve literal raw total
momentum and orbital angular momentum. Registered forward/backward trajectories
must recover the initial state bit-for-bit. Translation and proper cubic-lattice
rotations are exact controls. Common-velocity boosts are evaluated as a bounded
finite-resolution Galilean-covariance test, not assumed to pass.

An independent standard-library 110-decimal-digit oracle reconstructs exported
binary64 `H_force` entries from their bit patterns and integrates the smooth
accepted potential independently. It is refinement-checked before use as a
trajectory target. Candidate state and energy errors must show the preregistered
second-order window; the first-order control must be distinguishable.

Physical energy is a diagnostic only. No discrepancy becomes thermal, stored,
structural, or hidden energy.

## Formal boundary

Lean proves exact invariant-preserving composition, reversibility conditional
on signed inverse laws, and atomic rejection. It proves no binary64 bound,
temporal convergence, empirical reversibility, or finite-lattice symplectic
property.

## Promotion boundary

Even the successful decision would retain only an experimental integrator
candidate for a later integrator-family comparison. This contract never
promotes the map to authoritative `World` dynamics.

**NO PROMOTION TO AUTHORITATIVE WORLD DYNAMICS.**
