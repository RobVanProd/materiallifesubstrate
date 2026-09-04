# Bounded Fractional Phase-State Lab result

## Disposition

```text
decision: bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved
selected precision: null
candidate: fixed_precision_variable_exponent_binary_phase_state
registered significand bits: 64, 96, 128, 192, 256
backend: gmpy2.mpfr 2.3.1 / MPFR 4.2.2
rounding: round-to-nearest, ties-to-even
adaptive precision: forbidden
causal residual/history state: none
highest-precision dynamics gate: pass
structure residuals: unresolved
World integration: none
promotion: NO_PROMOTION
```

Fixed-storage variable-exponent binary phase state restores the second-order
KDK behavior established by the exact-rational parent, including the K4
internal-velocity trajectory that defeated both integer phase-state
architectures. `B=96` is the first precision below the registered absolute
physical budgets, and all registered precisions recover the temporal
second-order window. Those positive results do not select a bounded phase
state: every registered precision is ineligible because the preregistered
Section 10 full-tail anchor does not qualify.

The `B=256` exact-prefix residuals are all below one-sixteenth of their
applicable budgets and the highest-precision analytic certificates pass, but
three required internal-trajectory `B=192` to `B=256` comparisons exceed the
factor-four unit-roundoff bound:

| timestep level | exact-prefix metric | observed ratio relative to the allowed bound |
|---:|---|---:|
| 1 | final position | `1.43386250822` |
| 2 | final representation-energy error | `2.09250187531` |
| 3 | representation-energy slope | `11.7673251523` |

Thus the evidence distinguishes recovered dynamics and very small absolute
errors from the still-unresolved structural convergence requirement. The
registered negative disposition is not a claim that the absolute or temporal
errors are large; it records that the comparator-free full tails cannot use
`B=256` as a qualified convergence anchor under the frozen rule.

The maximum signed-time recovery position error has a separate post-budget
irregularity: the `B=192` to `B=256` pair does not follow the factor-four
unit-roundoff ratio. That envelope was already below its physical budget at
`B=64`, decreases at every registered precision, and remains inside its
analytic bound. Sections 7 and 8 require later precisions only to remain below
budget, so this reversal ratio is a non-gating diagnostic. That ordinary
scaling-until-budget rule does not waive Section 10's explicit `B=192` to
`B=256` qualification requirement for the comparator-free long tails.

## Immutable parent and frozen mechanics

The only accepted parent is:

```text
source commit: 6f25d7428fde7420c1f4cbe1e3565c11a28e817c
evidence tag: explicit-fractional-phase-state-lab-evidence-v1
tag object: a0feca21f7676e0b6f1443c483bd62448d68c65b
decision: fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved
archive SHA-256: 77aad47e1842b4fe29760594ee247f609b5d1e88ae7e6b370d86c0bdbb6c71de
archive size: 31,142,852 bytes
```

The independent verifier reproduces the complete parent fingerprint and its
positive controls before evaluating this candidate. This lab changes only
the packet phase-coordinate storage and arithmetic. It preserves the accepted
relation graph, reference geometry, `H_force`, collective energy, Path-B
cancellation-resistant relation geometry, `r/l0 >= 2^-24` safe domain,
`R=128` physical unit basis, KDK stage order, scenarios, and smooth reference
problem.

Each trajectory uses one fixed precision for its complete lifetime. The six
packet phase components are canonical finite variable-exponent binary values.
There is no adaptive precision, remainder, discarded-bit ledger, rational
residual, causal cache, or history state. Every registered arithmetic
primitive is separately rounded. The independent implementation reconstructs
the exact dyadic meaning of the wire state and implements ties-to-even rounding
with integer/rational arithmetic rather than treating MPFR as its authority.

## Temporal result

The separately formulated 110-digit smooth ODE oracle remains the temporal
reference. At `B=96`, the first precision to satisfy the absolute component
budgets (but not a selected precision), the KDK endpoint errors and observed
orders over the five registered timestep levels are:

| scenario | five endpoint errors | four observed orders |
|---|---|---|
| K4 breathing | `1.4216263165e-6, 3.5519760682e-7, 8.8786355194e-8, 2.2195773607e-8, 5.5488924498e-9` | `2.000849, 2.000212, 2.000053, 2.000013` |
| K4 internal velocity | `1.5406149028e-6, 3.8491917761e-7, 9.6215151429e-8, 2.4052872923e-8, 6.0131610501e-9` | `2.000879, 2.000220, 2.000055, 2.000014` |
| Octahedron deformation | `1.8955017554e-6, 4.7359680909e-7, 1.1838180693e-7, 2.9594364810e-8, 7.3985232664e-9` | `2.000849, 2.000212, 2.000053, 2.000013` |

All four orders for every scenario lie in the preregistered `[1.6,2.4]`
interval. At the same precision the corresponding symplectic-Euler controls
remain first order, with orders decreasing from about `1.011` to `1.001`. The
internal-velocity trajectory therefore has a resolved temporal convergence
window rather than the integer-projection plateau.

## Representation and physical budgets

The frozen physical budgets are:

| quantity | exact budget | approximate budget |
|---|---:|---:|
| position | `1/134217728000000000` m | `7.4505805969e-18` m |
| momentum | `1/70368744177664` kg m/s | `1.4210854715e-14` kg m/s |
| angular momentum / centrality | `1/9007199254740992000000000` | `1.1102230246e-25` |
| energy | `1/9007199254740992` J | `1.1102230246e-16` J |
| energy slope | `1/144115188075855872` J/s | `6.9388939039e-18` J/s |

Maximum bounded-versus-exact-rational representation errors over every short
comparison and every retained exact-rational long-prefix comparison are:

| B | position (m) | momentum (kg m/s) | energy (J) |
|---:|---:|---:|---:|
| 64 | `3.3848328942e-17` | `3.8853448099e-17` | `3.1704443817e-18` |
| 96 | `2.5691967480e-28` | `8.7045940744e-30` | `1.3169643306e-31` |
| 128 | `4.61023e-38` | `2.14784e-39` | `3.04118e-41` |
| 192 | `2.5496201837e-57` | `9.6404843126e-59` | `1.4187613777e-60` |
| 256 | `1.7953624909e-76` | `6.5526550901e-78` | `8.1159335162e-80` |

`B=64` exceeds the position budget. `B=96` and every higher precision are
below all three absolute representation budgets, and their errors continue to
contract rather than reaching a precision-independent plateau.

## Conservation, centrality, and signed-time recovery

The verifier reconstructs exact dyadic total momentum, orbital angular
momentum, pair momentum, and relation centrality from every stored bounded
state. It independently sums local half-ULP bounds; producer pass labels are
not trusted.

Maximum total momentum and orbital-angular-momentum residuals include:

| B | total-P residual | total-L residual |
|---:|---:|---:|
| 64 | `1.6093625998e-19` | `8.9723375145e-20` |
| 96 | `1.9425699791e-29` | `3.5252141009e-29` |
| 256 | `1.3494013367e-77` | `1.6235090510e-77` |

Thus `B=64` fails the angular budget, while `B=96+` passes the absolute
momentum, angular, pair-momentum, and centrality budgets. All 425 registered
operation audits, covering 27,297,360 rounded primitives, are reproduced.
The compact evidence retains 449,305 invariant rows and 1,398,720 relation
force rows.

The analytic gate is compositional rather than a fit to those final
residuals. For frame and signed-time comparisons, the verifier pairs the two
causal KDK traces and propagates every relative subtraction, impulse
multiplication, endpoint accumulation, drift multiplication, and drift
accumulation half-ULP in stage order. It fails closed unless the paired
binary64 length/conjugate scalars and the registered signed-time coefficients
match exactly. For bounded-versus-rational energy it separately propagates
candidate-versus-exact phase radii, including rounded kick and drift
coefficients, and converts the momentum radii into a kinetic-energy bound;
the potential value reconstructed from binary64 must match exactly before
that reduction is allowed. Exact-prefix energy slopes are bounded
componentwise from the same
per-sample radii.

To keep these verifier-only recurrences finite, each nonnegative radius is
rounded downward to a canonical `B=256` dyadic witness. That rounding is never
assumed to preserve an upper bound by itself: the complete measured state is
checked against the inward witness after every generated stage. A passing
certificate therefore establishes

```text
measured residual <= inward B256 witness <= literal exact local-half-ULP recurrence.
```

Proper lattice rotations and packet permutations additionally require exact
stage-state and force-primitive equivariance, so a sampled zero residual alone
cannot satisfy their gate. Short energy, signed-time recovery, short frame,
long frame, and exact-prefix long-energy certificates all enter precision
eligibility; all five `B=256` certificate classes also enter the global
structure disposition.

The tested bounded KDK implementation is not bit-reversible on this corpus:
none of the 75 registered forward/backward trajectories returns
bit-identically. The exact stored-state errors do contract strongly with
precision. The decisive maximum position recovery errors are

```text
B=192:
9 / 23945242826029513411849172299223580994042798784118784000000000
= 3.7585753736e-61 m

B=256:
1 / 107839786668602559178668060348078522694548577690162289924414440996864000000000
= 9.2730153767e-78 m
```

Their exact ratio is `1/40532396646334464`. The unconditional adjacent-
precision diagnostic is `4*2^-64 = 1/4611686018427387904`, so the observed
ratio exceeds that diagnostic by exactly `1024/9`. The maximum recovery-
position envelope is already below the position budget at `B=64` and remains
below it thereafter. The preregistered rule requires factor-four scaling only
until the first budget pass; this post-budget reversal ratio therefore is not
one of the three blocking full-tail-anchor failures. No precision is selected
because those separate Section 10 failures remain.

## Frame, replay, and domain behavior

Maximum registered frame discrepancies include:

| B | relative position (m) | relative momentum (kg m/s) |
|---:|---:|---:|
| 64 | `4.2354088237e-17` | `4.8903883961e-17` |
| 96 | `2.471695080e-27` | `4.706664635e-29` |
| 256 | `2.548512596e-75` | `1.709101131e-77` |

`B=64` fails the position budget; `B=96+` passes. Proper signed-axis lattice
rotation and packet permutation are bit-exact in every registered short-run
profile. Translation and common-velocity-boost residuals contract with
precision, and the boosted timestep profiles reach the declared floor without
a resolved boost-dependent internal-motion plateau.

All 25 checkpoints reproduce their complete canonical decoded state, final
state, and subsequent event suffix. All 25 unsafe chords reject atomically:
time and state remain unchanged and no partial event or energy ledger is
emitted. Safe-domain certification continues to use the unchanged
`r/l0 >= 2^-24` contract.

## Long-run behavior

The exact-rational comparator reaches the same preregistered complexity
boundary as the parent: level zero completes 256 steps, while levels one
through four first cross at steps `405, 403, 400, 398`. After those exact
prefixes, the `B=256` trace is the registered candidate full-tail anchor.
Qualification is evaluated separately for the internal and boosted trajectory
at each tail-bearing timestep level.

Every applicable `B=256` exact-prefix position, momentum, and internal
representation-energy maximum/final/slope residual is below one-sixteenth of
its physical budget. All boosted anchors and the level-four internal anchor
qualify. The internal anchors at levels one, two, and three do not: respectively,
final position, final representation-energy error, and representation-energy
slope fail the mandatory `B=192` to `B=256` factor-four scaling comparison by
the factors reported in the disposition. Consequently
`all_required_exact_prefix_unit_roundoff_scaling` and
`all_required_full_tail_anchors_qualified` are false, and the `B=256` trace is
not a qualified global full-tail reference.

Aggregate long-run momentum, angular-momentum, boost, and representation-
energy slope diagnostics contract with precision, and `B=96+` satisfies the
absolute slope budgets. These diagnostics do not supersede the failed
per-level anchor metrics. Representative `B=64`, `B=96`, and `B=256` slope
envelopes are:

| quantity | B=64 | B=96 | B=256 |
|---|---:|---:|---:|
| total P | `1.01307e-20` | `1.25600e-30` | `1.07951e-78` |
| total L | `5.67091e-21` | `2.09564e-30` | `5.50439e-79` |
| boost position | `2.57314e-18` | `4.51499e-29` | `1.53243e-77` |
| boost momentum | `2.44074e-18` | `2.45790e-30` | `7.35682e-79` |
| exact-prefix representation energy | `8.80614e-21` | `8.80870e-34` | `6.45308e-82` |

For the physical 16-second KDK trajectory, the maximum mechanical-energy
excursion contracts from `6.1481441958e-9` J at level zero to
`2.4061687324e-11` J at level four. The fitted slope contracts from
`-3.8970387169e-12` to `-1.6751677917e-14` J/s. The trace is precision-stable
from `B=96` upward, and the physical KDK energy behavior contracts with
timestep. Nevertheless, the failed exact-prefix anchor scaling means this lab
does not certify the comparator-free full-tail structural residuals as
resolved. No discrepancy is moved into heat, stored energy, or hidden state.

## Fixed causal-state size

The canonical wire format uses exactly `5+B/8` bytes per component. Storage
is constant at initial state, step one, step 400, checkpoint, final state, and
signed-time recovery.

| B | component bytes | phase bytes per packet | complete bytes per packet | K4 state bytes | octahedron state bytes |
|---:|---:|---:|---:|---:|---:|
| 64 | 13 | 78 | 94 | 428 | 616 |
| 96 | 17 | 102 | 118 | 524 | 760 |
| 128 | 21 | 126 | 142 | 620 | 904 |
| 192 | 29 | 174 | 190 | 812 | 1,192 |
| 256 | 37 | 222 | 238 | 1,004 | 1,480 |

Causal cache and history storage are exactly zero bytes. MPFR scratch limbs
are transient arithmetic workspace and never persist between operations.
Oracle rationals, evidence rows, and replay metadata are noncausal observers;
none of these categories is persistent packet phase state.

## Compact evidence encoding

The first preliminary materialization used a scientifically redundant `v1`
serialization. Repeating huge exact numerator/denominator spellings produced
these three files:

```text
representation_error.csv: 5,038,776,177 bytes
force_audit.csv:           3,411,553,743 bytes
invariants.csv:              608,363,448 bytes
```

That output exposed a packaging and verification-cost problem, not a failed
trajectory or arithmetic gate. It is preserved as an unsealed local failed
attempt and is ineligible for the final bundle.

The retained `v2` encoding removes no invocation, sample, or Cartesian
component. Momentum, angular momentum, pair momentum, and all centrality
residuals retain their exact raw dyadic `x,y,z` components. For sampled
bounded-versus-exact errors, `v2` binds the full row identity and all three
canonical exact fractions with a domain-separated, length-framed SHA-256
commitment. The oracle independently reconstructs the fractions and checks
the commitment. Bounded round-to-nearest-even displays are diagnostic only
and cannot affect a gate.

The first complete `v2` precheck stopped before scientific disposition because
the verifier expected all short-run levels before all long-prefix rows, while
the deterministic producer emits each level's short rows followed by that
level's long prefixes. Both sides contained the same 33,700 unique identities.
The verifier was corrected to bind the producer's actual level-interleaved
order; no raw row, arithmetic result, or candidate behavior was changed.

A subsequent verifier attempt incorrectly applied the special unconditional
`B=192`/`B=256` long-tail-anchor ratio to every structural envelope, including
the one-second reversal-position envelope. That contradicted the preregistered
scaling-until-budget rule. The corrected verifier separates ordinary residual
convergence from the Section 10 anchor and qualifies each comparator-free tail
only from its exact-rational prefix. The superseded attempt is preserved as a
verifier failure; it did not change raw evidence or candidate arithmetic.

The next compact precheck was stopped before disposition when the final source
audit found that its local half-ULP accounting covered conservation and
centrality but had not yet supplied compositional certificates for signed-time
recovery, frame covariance, and representation-induced energy. The raw data
remain preserved; the stopped verifier attempt is recorded separately and is
scientifically ineligible. The final verifier propagates those bounds from the
registered local rounding sites rather than fitting them to observed
residuals.

The first branch-CI run on source
`506ee4b692b38041479a5781823f3c637483e50c`, run `33830169828`, completed all
three C++ jobs and the pinned Lean job successfully. Its Python exact-oracle
job verified the parent, restored and compared the fresh twins, and completed
the oracle through long-replay level 3. It began long-replay level 4 at
`2026-09-04T09:56:52Z`; the registered `18,600`-second oracle subprocess limit
then expired at `2026-09-04T09:58:39Z`, and the step ended with exit code
`124`. This was a branch-CI execution-time failure, not a scientific failure:
the complete local oracle independently reached the registered negative
disposition. The failed run and its partial always-uploaded oracle evidence are
preserved with null scientific disposition.

Mutation tests cover restored verbose assumptions, changed exact fractions,
commitment transplants, display aliases, rounded-only commitments, altered
candidate/control hashes, row deletion/duplication/reordering, force or parent
changes, false decisions, hidden state, and weakened domain/replay/scaling
claims.

## Formal and validation boundary

Lean proves exact accounting identities for approximate pair kicks and drifts:
independent endpoint errors give the total-momentum change; orbital-angular-
momentum change decomposes into ideal centrality and endpoint error moments;
and drift position error supplies the remaining angular defect when ideal
displacement is parallel to momentum. These theorems interpret the measured
residuals. They do not claim an MPFR implementation theorem, a floating-point
error bound, bit reversibility, or symplecticity.

The final evidence protocol independently regenerates byte-identical compact
raw twins, reconstructs the 110-digit and exact-dyadic oracle result, exercises
semantic and outer-seal mutations, builds the C++ gates under GCC, Clang, and
MSVC, and runs the pinned Lean build and trust report. The sealed bundle binds
the local annotated tag object and successful branch-CI identity. Tag-push CI,
deterministic public-archive identity, release state, and fresh-public-download
verification occur only after sealing and are bound by external publication
receipts. They are intentionally not predicted inside this pre-publication
source document.

This is also the explicit protocol clarification for preregistration Section
12's shorthand that "raw evidence" includes release and fresh-download
receipts. Those post-publication receipts are part of the complete evidence
set, but cannot be members of `raw-a/`, `raw-b/`, or the payload whose hash they
subsequently verify. No scientific gate, datum, budget, or decision rule is
changed by this clarification.

## Scientific interpretation

For the registered scenarios, horizons, and timestep hierarchy, the exact-
rational parent's successful dynamics is reproduced temporally by fixed-
storage variable-exponent fractional state. From `B=96` upward the measured
absolute physical budgets are satisfied, and the frame, replay, domain, and
fixed-storage checks remain positive. This establishes that bounded arithmetic
can remove the earlier integer-projection temporal plateau on this corpus, but
it does not establish a retained bounded authoritative phase representation.
The preregistered strict full-tail anchor scaling remains unresolved, so no
registered precision is eligible and no precision is selected.

The lab also does not authorize silently relaxing exact conservation or
reversibility. The bounded trajectories have measured residuals inside the
frozen absolute budgets and independently derived bounds at `B=96+`; they do
not make those residuals identically zero, and the failed tail-anchor scaling
prevents interpreting absolute smallness as a completed structural convergence
argument. Whether MLS ultimately accepts convergent bounded conservation
contracts or requires a separate invariant-preserving mechanism is an explicit
later architecture decision.

No result here installs mechanics in `World`, selects a production integrator,
or authorizes contact, fracture, gravity, chemistry, life, rendering, or GPU
execution.

**NO PROMOTION TO AUTHORITATIVE WORLD DYNAMICS.**
