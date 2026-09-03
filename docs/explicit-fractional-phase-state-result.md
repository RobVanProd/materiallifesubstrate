# Explicit Fractional Phase-State Lab result

## Disposition

```text
decision: fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved
candidate: exact_reduced_rational_packet_phase_state
rational backend: gmpy2.mpq 2.3.1
coarse state: signed64
fractional state: exact reduced unbounded rationals
relation remainder: none
World integration: none
promotion: NO_PROMOTION
```

Explicit fractional packet phase state removes the generic temporal
quantization obstruction that defeated both fixed-`R=128` integer state and
order-matched integer co-refinement. The previously decisive internal-velocity
trajectory recovers a clean second-order KDK window, exact invariants, exact
signed-time recovery, and exact registered frame covariance.

The representation nevertheless fails its preregistered bounded-state gate.
Exact rational numerator/denominator complexity grows roughly linearly with
the number of force updates and crosses the 131,072-bit per-state median limit
after about 400 long-run steps. The decision order therefore stops at
`fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved`.

## Reciprocal integer-lattice obstruction

Lean formalizes the architecture constraint behind the parent failures. For
integer raw relation and momentum vectors with component gcds `g_r,g_p`, the
minimum squared exact-central kick and exact-orbital-L drift satisfy

```text
J_min^2 dx_min^2 = |r|^2 |p|^2 / (g_r^2 g_p^2).
```

Both `Lq` and `Pq` cancel. For primitive raw vectors the product cannot be
driven to zero by unit refinement. The proof connects explicit Bézout
primitivity to the minimum nonzero integer multiple and uses exact rational
algebra; it makes no binary64, integration-order, or bounded-state claim.

## Independent temporal result

The separately formulated 110-digit smooth oracle was internally refined to
approximately `1.8e-34` for both K4 cases and `2.4e-34` for the octahedron.
Endpoint errors and observed KDK orders were:

| scenario | five endpoint errors | four observed orders |
|---|---|---|
| K4 breathing | `1.42163e-6, 3.55198e-7, 8.87864e-8, 2.21958e-8, 5.54889e-9` | `2.00085, 2.00021, 2.00005, 2.00001` |
| K4 internal velocity | `1.54061e-6, 3.84919e-7, 9.62152e-8, 2.40529e-8, 6.01316e-9` | `2.00088, 2.00022, 2.00005, 2.00001` |
| Octahedron deformation | `1.89550e-6, 4.73597e-7, 1.18382e-7, 2.95944e-8, 7.39852e-9` | `2.00085, 2.00021, 2.00005, 2.00001` |

The diagnostic symplectic-Euler control remains first order, with observed
orders converging from about `1.010` to `1.001`. This cleanly distinguishes the
candidate’s recovered second-order regime from the control.

Short-run KDK energy envelopes also contract at second order. In the internal
case they decrease from `5.54972e-9` to `2.16814e-11` J over the five levels.
No discrepancy is stored as heat or hidden state.

## Exact accounting and covariance

All 10,446 recorded kick, drift, and committed invariant stages preserve exact
rational total momentum and orbital angular momentum. All 35,712 relation
force rows retain exact centrality. All 15 signed-time trajectories recover the
complete canonical initial state, including every reduced residual numerator
and denominator. Five independently reconstructed checkpoints reproduce their
canonical bytes, final states, and event suffixes. All five crossing chords
reject atomically without advancing time or mutating phase state.

Translation, proper signed-axis rotation, packet permutation, and the common
velocity boost have exactly zero relative position and momentum discrepancy at
all five levels. This is stronger than the registered convergent envelope but
does not claim arbitrary `SO(3)` isotropy.

## State-complexity result

The exact long-run state results are:

| level | requested physical horizon | recorded steps | recorded time | maximum bits | maximum per-state median bits | status |
|---:|---:|---:|---:|---:|---:|---|
| 0 | 16 s | 256 | 16 s | 82,476 | 82,271 | accepted |
| 1 | 16 s | 405 | 12.65625 s | 131,389 | 131,171.5 | complexity ceiling |
| 2 | 16 s | 403 | 6.296875 s | 131,461 | 131,237.5 | complexity ceiling |
| 3 | 16 s | 400 | 3.125 s | 131,354 | 131,147.5 | complexity ceiling |
| 4 | 16 s | 398 | 1.5546875 s | 131,328 | 131,119 | complexity ceiling |

The 262,144-bit maximum-component and 8,388,608-byte checkpoint ceilings do not
fire first; the frozen 131,072-bit per-state median does. The largest canonical
checkpoint at a crossing is 788,219 bytes. Refinement moves the crossing to a
shorter physical time while leaving it near 400 force steps, identifying
operation-count-driven rational complexity rather than a timestep floor.

No denominator was truncated, snapped, capped, or replaced. The exact crossing
state is present in the evidence, after which the registered trajectory stops.

## Failed implementation attempt and backend boundary

The first exact implementation used Python’s standard `fractions.Fraction`.
It remained CPU-bound for 2 hours 8 minutes without completing level zero and
was stopped as an evidence-generation performance failure. It produced no
scientific result. The retained implementation pins `gmpy2.mpq==2.3.1`, which
uses the same reduced exact rational semantics and completed the registered
experiment without changing physics, units, thresholds, or serialization.

## Scientific interpretation

This lab causally separates two facts:

1. the accepted matter/force/KDK stack is capable of convergent generic
   dynamics once the single Cartesian integer lattice is no longer discarding
   phase information; and
2. unrestricted exact rational packet phase state is not a bounded practical
   authoritative representation under repeated binary64-derived force updates.

The integer obstruction is real, and exact rationals cure it mathematically,
but denominator growth becomes the next architecture boundary. A later lab may
evaluate an explicitly bounded fractional representation or a different exact
state algebra. This branch authorizes neither.

**NO PROMOTION TO AUTHORITATIVE WORLD DYNAMICS.**
