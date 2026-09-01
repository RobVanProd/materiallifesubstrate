# Authoritative Mechanics State Bridge Lab contract

## Status

This is a bounded, read-only experiment rooted at
`2cc26e9a6e2aff8f40dec9787fe7e6e0e6b63f21`.  It tests the numerical and
dimensional bridge between accepted SI relation mechanics and exact packet
quanta.  It does not add a `World` force API, update momentum, integrate
position, advance physical time, or promote dynamics.

## Frozen inputs

The selected cancellation-resistant Path B, `r/l0 >= 2^-24` domain, Candidate-C
relation graph, local collective energy, symmetric `H_force`, and central force
equation are immutable.  The bridge may observe only frozen relation force,
authoritative packet position/momentum/mass, exact rational unit scales, and a
prescribed rational interval.

## Authoritative representation

Packet quantities remain checked signed-64-bit integer quanta.  A bridge result
contains an equal/opposite integer impulse pair and diagnostics.  No discarded
residual is causal.  Candidate C is the sole exception under test: its remainder
is explicitly named state and must appear in its checkpoint, state hash,
permutation, and replay.  It cannot be smuggled into a floating accumulator or
debug history.

Centrality is exact in raw units.  Given integer separation `d`, an admissible
impulse is an integer multiple of the primitive vector `d/gcd(d)`.  Rounding
Cartesian components independently is forbidden because it may manufacture
orbital torque.

## Exact unit profile

The base `Lq`, `Mq`, and `Tq` and every derived unit are the positive rationals
fixed by the preregistration.  Existing raw integration and kinetic-energy
configuration values are accepted only when they embed in those equations.
Configuration positivity alone is not a dimensional proof.

## Energy semantics

The bridge reports the exact SI kinetic-energy change, exact impulse work, the
integer `kinetic_energy_of` result, and their quantization residual separately.
It does not create a physical energy channel for rounding error and does not
reuse the actuated/dissipative impulse scaffold.

## Forbidden mechanisms

This branch forbids force or tangent changes, epsilon directions, force caps,
contact, hidden residuals, stochastic rounding, mass inference from SI force
data, altered `H`, topology changes, position integration, time integration,
and uncheckpointed causal state.  A representation refinement may add bits of
resolution only in this lab; it changes no SI state or physical law.

## Evidence boundary

All binary64 inputs are bit-pattern serialized.  The C++ evaluator, exact
rational Python oracle, evidence validator, and Lean exact proofs remain
separate.  Twin materializations must be byte-identical.  The completed branch
stops after deterministic evidence is sealed and publicly reverified.
