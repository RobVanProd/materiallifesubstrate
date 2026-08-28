# Point-interaction angular-momentum contract

Status: implemented reference contract for the narrow MLS-0 accounting and
ballistic scaffold. This is not a contact, force, elasticity, or field model.

## State variables and units

For packet `i`, the relevant authoritative state is integer fixed-point position
`r_i` (length quanta), linear momentum `p_i` (momentum quanta), positive mass
`m_i` (mass quanta), stored and thermal energy (energy quanta), and the positive
kinetic-energy scale denominator `d`. Orbital angular momentum is recomputed as

`L = sum_i (r_i x p_i)`

in angular-momentum quanta equal to one configured length quantum times one
configured momentum quantum. MLS-0 has no packet spin, applied couple, or torque
state. The boundary ledger therefore carries both `momentum_net` and
`angular_momentum_net`; it does not infer a missing couple.

Kinetic energy uses the packet contract's checked integer convention
`K(p,m,d) = floor(floor((px^2+py^2+pz^2)/m)/d)/2`. See
[material packet update laws](implemented-subsystem-contracts.md#3-material-packet-structure-of-arrays-store)
for the exact division order and representability limits.

## Update and conservation law

The only accepted internal point-impulse scaffold updates

`p_1' = p_1 + J` and `p_2' = p_2 - J`.

Its orbital angular-momentum change is exactly

`Delta L = (r_1 - r_2) x J`.

The `World` transition accepts this update only when that checked cross product
is zero. Thus a separated point pair accepts only a central impulse; coincident
points may accept an impulse because their orbital lever arm is zero. A future
non-central interaction is blocked until its torque is balanced through explicit
spin/couple state.

A boundary point impulse `J` at position `r` records both `J` and `r x J` in the
same staged boundary transaction. Material ingress and egress likewise include
the material's orbital angular momentum in their extensive totals. The accepted
world audit requires both linear and angular momentum to close.

## Energy semantics

`apply_actuated_dissipative_central_impulse` is deliberately not named or
specified as generic mechanics. For impulse `J`, it computes

`Delta K = K(p1+J,m1,d) + K(p2-J,m2,d) - K(p1,m1,d) - K(p2,m2,d)`.

If `Delta K > 0`, that exact amount is debited from a selected participating
packet's stored-energy channel. If `Delta K < 0`, `-Delta K` is irreversibly
deposited as heat in a selected participating packet. The tested nonzero-excursion
forward/reverse momentum cycle therefore returns the momenta but converts stored
energy to heat. A zero quantized kinetic excursion converts nothing. This is an
actuated/dissipative test scaffold only.

Conservative elastic or field interactions must not reuse this operation. They
will require a future reversible potential/field-energy channel and an update
law that closes kinetic plus potential/field energy without automatic heating.

## Numerical approximation and representability

All ledger arithmetic and cross products use checked signed 64-bit integer
quanta. An intermediate product or sum outside that range rejects the complete
staged transition with `std::overflow_error`; wrapping is never accepted.

The current ballistic reference step is intentionally narrower than the former
remainder integrator. It accepts only zero existing position remainders and a
momentum component exactly divisible by packet mass on every axis. The resulting
integer displacement is parallel to momentum and therefore preserves orbital
angular momentum exactly. A fractional displacement is rejected rather than
allowing rounded integer positions to manufacture a torque. This is a baseline
limitation, not a proposed production integrator.

MLS-0 still has no dimensioned physical timestep, so a `dt/2` convergence test
cannot be performed without adding a new physics contract forbidden by this
hardening branch. An adversarial scheduling test does show that applying an
otherwise identical boundary impulse before versus after one discrete tick
changes position. Timestep convergence therefore remains RED rather than being
inferred from exact tick batching.

## Failure modes and tests

Known limitations are the finite representable cross-product range, no spin or
couple state, no conservative force primitive, no fractional ballistic
integration, and quantized kinetic energy.

`tests/angular_momentum_tests.cpp` records:

- the non-central equal/opposite impulse counterexample;
- rejection without mutation of a non-central world transition;
- acceptance and audit closure of a central transition;
- explicit boundary orbital-angular-momentum accounting;
- the dissipative closed-cycle result;
- exact ballistic preservation and fractional-step rejection; and
- checked cross-product overflow rejection.
- rejection of dimensioned-timestep claims and a within-tick impulse-phase
  sensitivity witness.

Passing these tests establishes only the stated exact transition/accounting
contract. It does not establish physical validity for a future mechanics solver.
