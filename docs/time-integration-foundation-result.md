# Time Integration Foundation Lab result

## Disposition

```text
decision: temporal_convergence_blocked_by_authoritative_quantization
candidate: quantized_kick_drift_kick
negative control: symplectic_euler_control
coherent representation: R=128 (unchanged)
position/impulse remainder: none
World integration: none
promotion: NO_PROMOTION
```

The accepted `R=128` central kick and primitive-directional drift maps compose
into a deterministic, exactly reversible map that preserves raw total momentum
and orbital angular momentum. They do **not** compose into the preregistered
resolved second-order trajectory map. The decision order therefore stops at
`temporal_convergence_blocked_by_authoritative_quantization`. The lab does not
increase `R`, introduce remainder state, or hide the failure with a tolerance.

## Parent and composition fingerprints

The accepted `R=128` impulse corpus, `R=128` drift corpus, Cartesian drift
torque control, and safe/crossing chord classifications were reproduced before
trajectory evaluation. All emitted accepted kick, drift, and commit stages
preserved literal authoritative total momentum and orbital angular momentum.

Thirty registered forward/backward rows—six non-crossing trajectories over all
five timestep levels—recovered the initial phase state bit-for-bit. Checkpoint
decode/resume reproduced both the final state and every subsequent event hash.
The deliberately crossing relation returned `chord_domain_failure`, named
relation `(1,2)`, did not advance time, and returned the complete prior state.

## Independent trajectory result

The standard-library Decimal oracle used 110 decimal digits and independently
implemented the accepted smooth relation potential and force from exported
binary64 `H_force` bit patterns. Two six-level Richardson-extrapolated RK4
calculations agreed in the dimensionless endpoint norm by:

| scenario | independent-oracle refinement difference |
|---|---:|
| K4 breathing | `1.79656855064857e-34` |
| K4 internal velocity | `1.80029147550743e-34` |
| octahedron deformation | `2.39542473419810e-34` |

The first-order control exhibits the intended approximately first-order
behavior on the breathing and octahedron cases. The quantized KDK state errors
and observed orders were:

| scenario | errors for h=`1/16 ... 1/256` | four observed orders |
|---|---|---|
| K4 breathing | `1.32110e-6, 3.45211e-7, 1.85536e-7, 5.57677e-8, 1.17237e-7` | `1.936, 0.896, 1.734, -1.072` |
| K4 internal velocity | `1.27317e-3, 1.31030e-3, 1.32889e-3, 1.33827e-3, 1.34240e-3` | `-0.041, -0.020, -0.010, -0.004` |
| octahedron deformation | `1.76148e-6, 4.60297e-7, 2.47408e-7, 7.44377e-8, 1.56354e-7` | `1.936, 0.896, 1.733, -1.071` |

No scenario supplies three successive candidate orders in the preregistered
`[1.6,2.4]` interval. The internal-velocity trajectory is already dominated by
the evolving primitive lattice projection: refinement does not reduce its
state error. This is a representation/time-composition result, not instability
of the smooth reference problem; the largest timestep had
`omega_max*h = 0.0968246...`, far inside the real-valued Verlet stability
interval.

## Energy and frame diagnostics

The KDK energy envelopes likewise do not produce the required three-level
second-order window. On the registered sixteen-second K4 run, the energy error
was classified as secular:

```text
maximum excursion: 2.7941603136818187e-4 J
mean offset:        9.141123510907892e-5 J
final error:        2.7941603136818187e-4 J
least-squares slope: 2.7294217341955617e-7 J/sample
```

Translation and the proper 90-degree cubic-lattice rotation were exact at all
five timestep levels. The Galilean boost comparison produced raw position
discrepancies `0, 705760, 0, 0, 0` and zero relative-momentum discrepancy. The
resolved second-level excursion violates the preregistered post-floor envelope.
It is preserved as an additional frame-covariance warning, although temporal
convergence occurs earlier in the fixed decision order.

## Independent, mutation, and formal validation

The independent oracle reconstructs exact rational quanta, reference state,
topology, local collective `H`, endpoints, energy traces, invariants, timestep
inventory, covariance rows, checkpoint identity, and domain rejection. It
detects twenty registered mutations, including changed parent/refinement,
altered `H` or reference geometry, Cartesian substitution, unequal impulses,
false invariants/reversibility/order/covariance, omitted chord safety, partial
commit, odd timestep, hidden remainder, altered nearest-even ties, checkpoint
omission, and stored energy discrepancy.

Lean proves exact composition of invariant-preserving kick and drift maps,
signed-time reversibility under explicit inverse assumptions, and atomic
rejection. The new theorems introduce no axioms. No symplectic claim is made.

## Promotion boundary and next question

The force/impulse/drift representation remains accepted for its already sealed
single-operation claims. This experiment shows that its stateless projections
do not provide the required repeated second-order time map at fixed `R=128`.

Any next experiment must explicitly reconsider the authoritative
phase-space/time bridge—such as a separately authorized remainder or different
quantized integrator representation—rather than silently raising resolution or
proceeding to the Verlet-versus-energy-momentum bakeoff.

**NO PROMOTION TO AUTHORITATIVE WORLD DYNAMICS.**
