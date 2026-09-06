# Bounded Integrator Bakeoff Lab — preregistration v1

Status: **PREREGISTRATION ONLY; IMPLEMENTATION AND TRAJECTORIES NOT AUTHORIZED YET**.
Branch: `bounded-integrator-bakeoff-lab`.
Parent: `a5f83d13c276bd1f41f6121e4d3bc50dc7287983`.
Every outcome: **NO_PROMOTION TO AUTHORITATIVE WORLD DYNAMICS**.

## 1. Commit barrier and immutable inputs

This document is the entire next commit. Commit and push it, then stop for
head-agent review. Do not implement midpoint, discrete gradients, solver tests,
new Lean proofs, or generate trajectory data in this preregistration turn.
Implementation requires subsequent approval of these exact equations, branches,
tolerances and decisions. An amendment must be a new reviewed preregistration
commit, never an unrecorded implementation choice or a post-data adjustment.

Accepted parent evidence:

```text
tag: relation-coordinate-defect-tail-certification-lab-evidence-v1
annotated tag object: b7a09a70d10c9096500ab9737c964948680331f0
source: a5f83d13c276bd1f41f6121e4d3bc50dc7287983
archive bytes: 459157937
archive SHA-256: 8d0d57824377b92f9e8d20de9b1ade06140c0b9055e561bd4690a6ef9b33fb19
manifest SHA-256: 6f33d5586dc75250ca4356aedb6cc58da62f8b153e62bf6b4d55e620ea12e818
decision: retain_b96_bounded_phase_state_for_research
selected representation precision: 96
scope: registered finite inventory and 16-second horizons only
```

Authenticate source, manifest and inherited fixtures before interpreting any
candidate. Preserve every sealed source, tag, release, failure and disposition.
The parent fingerprint is 90/90 short blocks, 1,890 joint short-stage checks,
ten certified tails, 15,872 full steps / 47,616 stages, no cell/resource failure.
Authentication and bounded control replay suffice initially; do not regenerate
old archives. Candidate A must reproduce every reused B96 state/event hash.

The parent archive's `parent/parent/parent/inputs` directory is the frozen
fixture root (not a mutable working-directory discovery rule):

| Relative fixture | SHA-256 |
|---|---|
| `raw-a/reference_packets.csv` | `907cc08a3f6a8db48143e35d0ee247dccf687cc42ba617f28ff213219312994f` |
| `raw-a/relations.csv` | `5b50a04399f9868a9fdc0fe3e263e162aa3a4d52b0be03b11a6cb17a689bece0` |
| `raw-a/force_operator.csv` | `d5d9a19ea6f8a5cdd25810f2e6a1e35ed039e45463d56a3f208c8b9151698ed7` |
| `raw-a/initial_states.csv` | `98d39386f57935b83fc52e5fc704db628bf94400f60ca301971d44554ed773d2` |
| `parent-explicit-fractional/raw-a/initial_states.csv` | `d9864ce96b8d80a70c5494311b74ee392feaefdcae1c70c875f5192713ccdf8a` |

Use B96 rows only, selected by explicit precision/scenario fields. The exact
initial values, packet IDs, relation orientation/order, masses, rest lengths,
reference coordinates and every `H_force` binary64 bit are defined by these
authenticated rows, not by recreating similar geometries from decimal prose.
K4 has six complete-graph edges; octahedron has twelve non-antipodal edges;
all masses are 1 kg; the inherited collective policy is K/G=2, A=3/10, B=1/4.
No topology rebuild, constitutive refit, force-law or reference-state change.

## 2. Frozen representation, arithmetic and units

Only B96 persistent phase state is eligible. Keep the parent canonical wire
format, positive-zero encoding, packet ID/mass/time fields and phase shape.
Six phase components occupy 102 bytes per packet (118 including ID and mass),
not a claim about runtime memory. No residual, compensation, adaptive precision,
solver warm-start history, energy reservoir or authoritative scratch survives
a committed step. Checkpoints contain all and only the inherited phase state
and fixed candidate/configuration identity; replay reconstructs scratch afresh.

`gmpy2==2.3.1`, MPFR 4.2.2, separately rounded primitives, RN ties-to-even,
no FMA or other fusion. B96 leading exponent is inclusively [-16382,16383]
(MPFR emin=-16381, emax=16384). No subnormals. Inspect flags per primitive;
inexact is logged, all invalid/nonfinite/division-zero/range/underflow/overflow
events fail closed. Preserve parent sanity bounds abs(x_raw)<2^48,
abs(p_raw)<2^40, abs(r_raw)<2^49, abs(J_raw)<2^40 as rejection gates, not clamps.
For B/C the impulse limit applies to each relation's proposed full-step impulse.

```text
Lq = 1/128000000000 m       Mq = 1/524288 kg
Tq = 1/1000000000 s         Pq = 1/67108864 kg m/s
Eq = 1/8589934592 J         Fq = 1953125/131072 N
Pq = Mq*Lq/Tq; Eq = Pq^2/Mq; Fq*Tq = Pq
```

All physical equations below use these exact SI units. Raw timestep is the
signed integer n=h/Tq. All component ordering is ascending packet ID then
x,y,z (positions before momenta); relation operations use frozen relation
index, then axis. Sum left-to-right, initial accumulator +0. No parallel
reduction, data-dependent reordering, reassociation or ambient context.

Path B is the parent's cancellation-resistant binary64 geometry, including its
compensated squared-distance difference, stable norm, reference denominator,
binary64 H multiplication/conjugates and binary64 potential reduction order.
Never substitute direct norm subtraction, smooth high-precision lengths or
absolute-position binary64 conversion. Domain remains r/l0 >= 2^-24.

Candidate A uses its exact existing B96 relative-subtract, Lq96 multiply,
binary64 conversion and force/impulse/drift operation graph without alteration.
For B/C only, nonlinear-stage scratch is fixed at S=256, including stage
coordinates, relative subtraction and multiplication by Lq_S=RN_S(Lq), then
RN64 conversion of the relative result. This is an explicitly declared stage
evaluation contract, not a new persistent phase precision or a change inside
Path B. Restore old B96 components exactly into scratch; never first round
absolute SI positions to binary64. Exact binary64 outputs are decoded as dyadics
before scratch operations. Final proposed phase components are rounded once
to B96; subsequent steps read only those B96 components.

## 3. Inventory and physical budgets

One-second convergence: `k4_breathing`, `k4_internal`,
`octahedron_deformation`, each at all five levels. Same physical initial states
and horizons for A/B/C. K4 breathing is the inherited 1001/1000 deformation;
the internal velocities and octahedron offsets are the exact fixture values.

| Level | h (seconds) | n (raw time) | One-second steps | 16-second steps |
|---:|---:|---:|---:|---:|
| 0 | 1/16 | 62500000 | 16 | 256 |
| 1 | 1/32 | 31250000 | 32 | 512 |
| 2 | 1/64 | 15625000 | 64 | 1024 |
| 3 | 1/128 | 7812500 | 128 | 2048 |
| 4 | 1/256 | 3906250 | 256 | 4096 |

Ten long trajectories per eligible candidate: `k4_internal` and `k4_boosted`,
levels 0..4, exactly 16 seconds. The common boost is the inherited
(1,-1,1)/128 m/s. Keep inherited translated, rotated, permuted, endpoint-reversed,
domain-crossing and signed-time controls at all five short levels. A rotation
is the inherited (x,y,z)->(-y,x,z) applied to both x and p; additionally test
all 24 determinant-positive signed axis permutations on the short internal
case. These are cubic controls, not arbitrary SO(3) certification. Reference
geometry is semantically transformed with a rotation; its scalar constitutive
bits and topology are not recomputed or fitted. Checkpoint at N/2 of every
short and long run; recover complete state and subsequent scientific stream.

The old tangent/mass frequency bound sqrt(2.4) s^-1 and h0=1/16 s are inherited,
not retuned. The old first-order kick-drift control remains ineligible and is
replayed to test order discrimination. No extra systems or easier horizons.

Let b=2^-20. Frozen componentwise infinity-norm physical budgets:

| Quantity | Exact SI budget |
|---|---|
| position, relative position, recovery position | Lq*b = 1/134217728000000000 m |
| momentum, total P, relative/recovery momentum | Pq*b = 1/70368744177664 kg m/s |
| orbital L and relation impulse centrality | Lq*Pq*b = 1/9007199254740992000000000 kg m^2/s |
| representation energy | Eq*b = 1/9007199254740992 J |
| 16-second representation-energy slope | Eq*b/16 = 1/144115188075855872 J/s |

Total-P/L slope limits are their table budgets divided by 16 seconds. Apply
state budgets to representation error, not time-discretization error. Apply
the same dimensional budgets to translation, rotation, permutation, reversal
and boost discrepancies. These values cannot be enlarged by a solver tolerance.

## 4. Candidate A — unchanged KDK baseline

Use `tools/run_bounded_fractional_phase_state_lab.py`, its `one_step`, `kick`,
`drift`, `force_and_energy`, profile and wire routines at the parent source.
File SHA-256: `c4ac14cdcd46f948c1640535164c5bee400b4811868a572fe3873646cbed06de`.
No refactor or replacement by an equivalent-looking KDK. Instrumentation may
only read exported records or wrap calls without changing inputs, arithmetic,
order or exceptions. Existing short/long hashes are mandatory regression gates.
The parent certificate remains a KDK-only certificate, not a certificate for B/C.

## 5. Candidate B — implicit midpoint

For old/new SI phase (x,p),(y,v), solve simultaneously:

```text
q = (x+y)/2
y = x + h M^-1 (p+v)/2
v = p + h F_B(q)
```

For relation r=q_j-q_i, Path B provides length ell and conjugate g. Its ideal
stage contribution is +(g/ell)r at i, opposite at j. This is the inherited
force definition, not a differentiable replacement for binary64 force cells.
The midpoint equations define the method; a finite solver iterate is only a
proposal, subject to Section 7. No claim that the bounded executable is
symplectic or exactly reversible follows from the classical midpoint method.

## 6. Candidate C — conditional relation-coordinate discrete gradient

Prior-art basis: Gonzalez's discrete chain-rule construction, and the radial
two-endpoint discrete gradient described by LaBudde–Greenspan and in Section
4.1 of *Discrete gradients in short-range molecular dynamics simulations*.
The following coupled-H lift is this lab's stated derivation, not an assertion
that the literature already certifies MLS's rounded force graph.

For SI endpoint relation vectors r_a^- and r_a^+, write delta r=r^+-r^-.
In exact real geometry let ell^±=|r^±|, e^±=ell^±-ell0,
U(e)=e^T H e/2, H=H^T. Define

```text
gbar = H (e^-+e^+)/2
w_a = (r_a^-+r_a^+)/(ell_a^-+ell_a^+)
fbar_i += gbar_a*w_a; fbar_j -= gbar_a*w_a
y = x + h M^-1 (p+v)/2
v = p + h fbar(x,y)
```

Proof obligations BEFORE ANY C executable interpretation: positive denominators;
w_a dot delta r_a = delta e_a; delta U=sum_a gbar_a*delta e_a;
therefore delta U=-sum_i fbar_i dot (y_i-x_i). Prove the quadratic kinetic
identity and cancellation giving delta(K+U)=0 for an exact solution, total-P
cancellation and midpoint-position angular cancellation. Include equal-radius
and zero-increment cases. Symmetry under endpoint-time exchange is conditional
on the same assumptions. State explicitly which hypotheses do not follow for
binary64 evaluations. Lean must compile these statements without sorry, admit,
new axioms, or assuming the desired energy result as a premise.

### 6.1 Frozen Path-B compatibility is a first-class eligibility gate

For MLS, obtain ell_B^±, e_B^±, g_B^± and U64^± by the frozen endpoint Path-B
graph. Do not replace them with exact norms or a re-evaluated H. Define the
proposed executable scalar gbar_B=(g_B^-+g_B^+)/2 and
w_B=(r^-+r^+)/(ell_B^-+ell_B^+), using exact dyadic reconstructions for the
independent eligibility test. Vectors r^± here are the COMPLETE physical
endpoint relation vectors before binary64 conversion, not their rounded
surrogates. The following exact checks are mandatory:

1. For EVERY relation, `w_B dot delta r == e_B^+ - e_B^-`.
2. For the exact algebraic diagnostic U_H(e)=e^T H e/2, using the SAME frozen
   H bits, `U_H(e_B^+)-U_H(e_B^-) == sum gbar_B*delta e_B`.
3. The actual accepted potential observer must also correspond:
   `U64^+ - U64^- == sum gbar_B*delta e_B`.

All comparisons use exact rational values reconstructed from wire/float bits;
their tolerance is ZERO. Record signed residuals for all three identities.
U_H is a diagnostic for separating endpoint-geometry, conjugate-reduction and
potential-reduction incompatibilities, never a replacement physical energy.
At identical endpoints gbar_B=g_B and w_B=r/ell_B, so the proposed diagonal
force agrees with the frozen instantaneous force before scratch rounding.

Check compatibility first on the authenticated A first-step endpoint pair for
each of the 15 short cases, plus identical-endpoint controls, in scenario order
listed in Section 3 then ascending level. These are existing sealed data,
not newly generated C trajectories. A failure disqualifies THIS registered
C formula from the frozen-geometry domain; it is not a no-go for every possible
discrete gradient. Stop C immediately as
`candidate_c_incompatible_with_frozen_path_b`, with subcode
`extension_chain`, `conjugate_chain` or `potential_observer_chain` and the first
exact witness. No C solver or C trajectory is then implemented/run. A/B may
proceed only after the post-preregistration implementation authorization.
If controls pass, certify the same identities for every proposed accepted C
step and its reference enclosure; an undecidable identity is inconclusive,
not a pass. Intermediate solver trials are not claimed to conserve energy.

No Gonzalez-style added defect-direction correction, secant fitted to rounded
energy, division by squared-length change to force the identity, endpoint
energy replacement, rescaling of gbar, or H adjustment is allowed in this
candidate. The test is deliberately capable of rejecting a formally valid
real-arithmetic formula on the frozen rounded mechanics.

### 6.2 Degeneracy branches (no tolerance-based substitutions)

If ell^-+ell^+ is nonpositive/nonfinite, reject. Exact coincidence or an
unsafe chord rejects independently. The formula never divides by delta ell
or delta e: equal positive lengths use the same sum-denominator expression.
If delta e=0 but w dot delta r is nonzero, compatibility fails; do not use a
derivative fallback. If r^-+r^+=0 with nonzero endpoints, the straight chord
crosses coincidence and is rejected even if the algebra gives w=0. Exact
unchanged positions use the diagonal formula. Zero h is an identity diagnostic
only, not a trajectory sample. Signed nonzero h uses the same algorithm.

## 7. Frozen nonlinear solver and output acceptance (B and eligible C)

Use full-vector simultaneous Picard/Jacobi iteration, not Newton, line search,
Gauss–Seidel, finite-difference Jacobians or a solver library's hidden defaults.
Scratch S=256 for the candidate, leading exponent bounds as in Section 2;
fixed operation order, RN-even, no fusion. No arbitrary-precision rational
arithmetic in the causal solver. Exact arithmetic is verifier-only.

Initial guess: v0=p; y0_i=RN_S(x_i+RN_S(RN_S(n/m_raw_i)*p_i)), the ballistic
guess, from the current B96 state alone. One sweep reads only the entire old
guess and writes an entirely separate new guess. For each component:

```text
y_next = RN_S(x + RN_S(RN_S(n/(2*m_raw))*RN_S(p+v_guess)))
```

For B form each midpoint component as RN_S(RN_S(x+y_guess)/2), then the frozen
relative conversion and Path B. Initialize v_next=p. In relation/axis order:

```text
c = RN_S(n*Tq*Lq/Pq)                  # one exact-rational constant conversion
alpha = RN_S(RN_S(c*g_B)/ell_B)
J = RN_S(alpha*r_mid_raw)
v_next_i = RN_S(v_next_i+J); v_next_j = RN_S(v_next_j-J)
```

For C evaluate Path B at old and proposed endpoints; compute
gbar_S=RN_S(RN_S(g_B^-+g_B^+)/2), denom=RN_S(ell_B^-+ell_B^+),
alpha=RN_S(RN_S(c*gbar_S)/denom),
J=RN_S(alpha*RN_S(r_raw^-+r_raw^+)), then identical endpoint accumulation.
Each r_raw is separately rounded endpoint subtraction at S. The exact theorem
and compatibility test still concern complete endpoint vectors; all scratch
defects are measured, not mistaken for exact centrality. Binary64 H/energy
accumulation stays in Path B, never silently promoted to S.

For convergence scale positions by 1 m and momenta by 1 kg m/s. Let D_j be
the max absolute scaled iterate update and R_j the max absolute scaled
fixed-point residual, evaluated with a fresh complete sweep at the NEW guess.
The residual sweep is counted and its proposal is not silently substituted.
Let Z_j=max(1, norm_inf(scaled initial state), norm_inf(scaled new guess)).
Require BOTH `D_j <= 2^-180 + 2^-180*Z_j` and
`R_j <= 2^-180 + 2^-180*Z_j`. Evaluate these at S and independently verify
their outward bounds. Maximum 128 sweeps including residual-evaluation sweeps;
no early acceptance on unchanged iterates alone. First passing guess wins.
Two-cycle, stagnation, discontinuous force-cell switches or noncontraction
do not enable another method: exhaust the same ceiling or reject earlier on
an explicit invalid arithmetic/domain condition. Every force call is counted.

At acceptance recompute the relation impulses for that guess, retain them for
centrality accounting, and round its y,v once to B96. The 256-bit solver alone
supplies the candidate proposal. Solve independently from the SAME B96 input
with verifier-only S=384, same guess/order/128-sweep ceiling, but both tolerances
`2^-300 + 2^-300*Z_j`. It must yield identical RN96 output components AND valid
cell/domain certificates. Report both residuals, iterations, scalar-bit traces
and output hashes. The 384-bit run can only veto; it cannot choose, repair,
average, refine or replace the proposed B96 state, nor feed a later step.
No post-outcome precision increase or tolerance change.

Agreement of two solvers is NOT existence/uniqueness proof or a full-tail error
bound. Independently at 384-bit outward verifier precision, construct a root
box around the verifier iterate with scaled component radius 2^-160. Certify
all binary64 cells over the box, the actual fixed-cell map T, T(box) subset
box, and scaled infinity-norm contraction bound <=1/2. For B, T is affine
within fixed midpoint cells; for eligible C it is affine conditional on BOTH
endpoint cell sets. Include every verifier-rounding slack. No derivative of a
rounded force map across a cell boundary is admissible. Require the unique
root enclosure to round wholly to the proposed RN96 output, with exact
ties-to-even cell endpoint handling. To avoid mistaking an interval around an
exact structural zero for an uncertain nonzero result, independently assemble
the conditioned affine coefficients as exact rationals from the certified
binary64 scalars, exact units and exact B96 input. Solve (I-A)z=b by exact
Gaussian elimination, columns in state order and first nonzero row pivot in
ascending row order. This is verifier-only, stage-local algebra, not higher
precision solver state. Require the exact root to lie in the certified box,
satisfy the exact equations/cells and match every proposed RN96 component.
No singular pivot fallback. Reduced rational numerator/denominator sizes are
capped at 262144 bits each; exceeding this or the process limit is verifier
inconclusive. Discard the exact local root after checking, never substitute it
for the 256-bit proposal. A wide enclosure, unproved force cell,
unproved C identity, multiple/unproved root, or output rounding ambiguity
rejects the step as `solver_certificate_inconclusive`; not a physical failure.

No commit until all candidate arithmetic, solver, output, range and full-chord
checks pass. Any failure returns exact prior B96 state/time and does not alter
momentum, energy ledgers or an accepted event suffix. Diagnostic failure records
are separate. No smaller-step retry, clipping, fallback to A, skipped step or
acceptance based solely on a small residual.

## 8. Complete-segment domain certification

For every proposed position change use complete relative vectors a and b and
the ENTIRE chord a+t(b-a), 0<=t<=1. With d=b-a, the exact squared minimum is
|a|^2 if d=0 or a dot d>=0; |b|^2 if a dot d<=-|d|^2; otherwise
|a|^2-(a dot d)^2/|d|^2. Compare without square roots to
`2^-48 * |reference_relation|^2`, using the inherited exact reference convention.
Equality at the allowed boundary passes; no epsilon margin changes the model.

A keeps its existing drift-chord test. B/C test old-to-proposed endpoint chords
(which include the midpoint), including every trial before evaluating its
force and the final rounded B96 endpoint before commit. Exact trial dyadics
can be checked with bounded integer scratch under the inherited domain logic;
verifier target boxes use outward enclosures of the SAME complete segment,
never endpoints or nominal paths only. For target uncertainty, a lower bound
above threshold certifies; an upper bound below threshold proves violation;
overlap is `domain_certificate_inconclusive`. A solver's unsafe trial is a
solver rejection, not proof that the true trajectory crosses the domain.
Retain the inherited exact safe/unsafe/interior-crossing controls and test
atomicity on all candidates. No absolute positions rounded away in these tests.

## 9. Three references, three different questions

1. **Smooth ODE oracle:** inherited independent 110-decimal-digit potential/ODE,
   exact reconstructed input bits/units, two Richardson-extrapolated RK4
   integrations with base counts 128 and 256 and six refinement levels.
   Require endpoint agreement <=2^-70 in inherited normalized state norm.
   This measures time-discretization plus representation error, not the
   representation error alone. Reuse authenticated results where identical.
2. **Same-integrator target/reference:** each candidate has its own exact
   discrete definition, retaining binary64 Path-B conversion/force outcomes.
   A uses the sealed exact-rational KDK definition. B/C use the selected unique
   root of THEIR stated fixed-cell equations, not KDK or a smooth-force solve.
   Construct an independent 512-bit outward full-trajectory enclosure, with
   stage-local exact rational algebra where feasible; no historical expression
   growth. The nominal high-precision reference is not truth without inclusion.
3. **B96 executable:** only the candidate's canonical stored state advances.
   Solver scratch is temporary. Neither ODE, high-precision reference nor
   verifier error intervals may influence candidate state.

Carry uncertainty from the exact initial state through every step of each
same-integrator reference. No zero-radius restart at a bounded checkpoint.
Include force-rounding alternatives or stop inconclusive; this lab registers
NO branch search. Conditional affine relation-coordinate propagation may be
reused algebraically, but KDK's certificate cannot simply be assigned to B/C.
Before full tails, test new inclusion on exact known-answer fixed-cell maps
and withheld independently solved short intervals. Require all available
exact states contained; a containment failure stops the verifier. Unknown
coverage is never filled by the B256 trace. No candidate B128/B192/B256 runs.

Certify throughout all samples max/final position and momentum representation
error, energy error/slope, P/L/centrality, first-packet-relative AND COM-relative
frame quantities and safe chords. Potential observers retain binary64 U64;
use certified force/observer cells, not an invented smooth energy difference.
Use exact quadratic kinetic identities. Energy slopes use a streaming SIGNED
sum of (t_n-tbar)*deltaE_n and exact sum (t_n-tbar)^2. Include sample zero and
every complete step. A sum of absolute terms is a separately labeled weaker
bound, never a signed slope or an explanation of cancellation.

## 10. Hard gates and energy semantics

For all three one-second cases require observed endpoint orders
`log2(error_k/error_(k+1))` in [1.6,2.4] on THREE CONSECUTIVE halvings. Use
the inherited normalized Euclidean norm (1 m, 1 kg m/s, divided by packet
count inside the square root). An error pair is resolved only above 64 times
the certified combined reference/representation uncertainty. Require that
uncertainty <=0.1 times time-discretization error at all five levels. Exact
zero/interval overlap cannot manufacture an order. First-order control needs
two successive orders in [0.6,1.4] and maximum order at least 0.5 below each
eligible second-order candidate. Below a certified floor, plateau within
budget is allowed, but three successive >5% error increases are not.

Directly reconstruct exact dyadic P, L, and relation impulse centrality from
candidate wires at every physical stage/complete step, not solver trial
iterates. A centrality lever is its actual kick relation; B/C use the complete
midpoint lever (r^-+r^+)/2 for the two-endpoint impulse. Also export endpoint
lever diagnostics separately; do not confuse endpoint torque with the
midpoint angular identity. Accumulation and position-update defects are
included in L bounds. Same relation impulse is used at opposite endpoints;
separately audit their actually stored deltas. Every residual must be inside
its frozen budget AND an independently derived rounding/solver-error bound.
No exact conservation or exact reversibility claim from a tolerance pass.

Run forward N steps and backward N steps at -h. Report bit recovery literally;
require position/momentum recovery budgets, not fabricated bit identity.
Replay/twins, in contrast, MUST be byte-identical after canonical serialization.
Check first-packet-relative and COM-relative frame observables, translation,
all registered proper lattice rotations, packet/relation reorder and endpoint
reversal under semantic inverse maps. Above the certified floor require
frame discrepancy to shrink on each halving; below the frozen dimensional
budgets it must remain below them. Persistent resolved frame bias fails.

Mechanical energy is exact SI kinetic energy plus the accepted U64 observer.
Report short and long maximum excursion, signed mean offset, final error,
signed least-squares slope, quarter-window means and the inherited secular
classification. Separately report representation energy versus SAME method
and same force semantics. Do not require A/B to conserve energy exactly, nor
reward C for violating compatibility to do so. Where an energy envelope is
resolved, require non-worsening under refinement and contraction from level
0 to 4; floor-dominated values may plateau inside certified uncertainty.
Representation energy and its slope must meet Section 3 for every long run.
For this contraction gate, compare outward enclosures of the absolute maximum
excursion and absolute final energy error: a resolved increase means the finer
lower bound exceeds the coarser upper bound. Reject any such adjacent increase;
require a strict level-0 to level-4 decrease when both are resolved above 64
times their observer/reference uncertainty. An unresolved comparison is not
evidence of contraction; floor-dominated endpoints are exempt from the strict
decrease only when both lie within that certified floor. Report mean and slope
as additional Pareto metrics rather than imposing an adjacent signed-error
ratio. Physical energy behavior is not the sole selection rule.
No discrepancy becomes thermal energy, stored energy, a correction or a ledger.

## 11. Cost, resources, validation and Pareto rule

Fixed limits per process: 2 GiB address space; 3600 seconds per short case,
7200 seconds per long case including its independent certificate; at most four
processes. Causal solver sweeps <=128; root box and contraction limits fixed
above. No resource increase after outcomes. Exhaustion is inconclusive, not
evidence of a mechanics defect. Resource/timing/RSS diagnostics stay outside
deterministic scientific hashes. Current verifier state has fixed dimensions
for a scenario; stream historical evidence rather than retain causal DAGs.

Count Path-B relation evaluations, full force/energy evaluations, MPFR
operations by scratch precision, solver/residual sweeps, failures, certificate
cost and peak memory separately. For runtime, use one untimed warmup then five
timed full repetitions of each eligible case, serial on the same host,
candidate order A,B,C, fixed single-thread arithmetic. Report median and range;
retain all attempts. Verification time must not be concealed in candidate time
or used as a feedback signal. No compiler-specific optimization of A.

Only candidates passing ALL hard gates enter the Pareto set. Compare matched
scenario/level/horizon rows, not differently accurate timesteps. Lower is better
for certified state error, normalized P/L/centrality/recovery/frame maxima,
force/primitive evaluation counts, solver iterations, runtime, peak scratch,
long-run maximum/absolute-final energy error and absolute signed slope.
For exact counts use literal ordering; for interval-certified metrics require
nonoverlap to claim strict superiority. Runtime distinguishes candidates only
when their five-run ranges do not overlap; otherwise it is tied/incomparable.
Dominance requires no worse on EVERY registered comparison dimension/row and
strictly better on at least one. No fitted weighted score or energy-only winner.
Publish all nondominated candidates. Multiple survivors mean tradeoff unresolved,
not permission to choose retrospectively. A sole A survivor means retain the
baseline, not improvement. A C incompatibility cannot be hidden as zero cost.

Independent verification consumes exact wire/IEEE bit patterns, never decimal
displays. Test mutations for altered parent/fixture/H/units/B96, changed A graph,
scratch widening, warm-start state, wrong order/fusion, false residual convergence,
iteration overflow, accepting mismatched 384 output, nominal-only root/cell/chord,
wrong or ambiguous root, false C chain/equal-length derivative fallback,
energy correction, partial rejection, reset uncertainty, missed relation impulse,
false centrality/frame/order, false signed slope, incomplete inventory,
noncanonical checkpoint, resource failure relabeled pass and NO_PROMOTION removal.
Each mutation must fail for its intended reason, with positive controls passing.

Lean, after implementation authorization: C exact chain/kinetic/angular theorem
FIRST; midpoint fixed-cell equations; enclosure/root-to-budget implications;
complete chord minimum; signed slope accumulation; atomic reject/replay state
identities. No proof of MPFR or finite B96 symplecticity is claimed. Preserve
the pinned Lean/Mathlib toolchain and trust audit. GCC/Clang/MSVC, Python exact
arithmetic, pinned Lean, mutations and deterministic twins are required before
sealing a later result. This preregistration alone reports none of them run.

## 12. Decision order and stopping boundaries

Apply global integrity checks first, then classify EACH candidate in order;
an ineligible candidate never participates in Pareto ranking. Preserve all
subcodes/failed rows; do not collapse verifier limits into mechanics rejection.

1. Parent/fixture/A fingerprint mismatch -> `stop_inconclusive_or_wrong_parent`.
2. Any independent containment, arithmetic, mutation or evidence-integrity
   failure -> `stop_bakeoff_verifier_unsound` (global stop).
3. C proof missing/false -> `stop_candidate_c_chain_rule_unproved`; C frozen
   compatibility fails -> `candidate_c_incompatible_with_frozen_path_b` (stop C,
   never modify geometry; retain separate A/B eligibility).
4. Non-atomic rejection or changed physical energy semantics ->
   `reject_integrator_accounting_or_domain_safety`.
5. Solver arithmetic/convergence/output mismatch -> `reject_integrator_solver`;
   unproved root/cell/domain/certificate or resource limit ->
   `stop_integrator_certification_inconclusive`. No tail launch for that candidate.
6. Proved unexpected physical domain violation -> `reject_integrator_force_domain`.
   Expected diagnostic rejection passes only if atomic and correctly identified.
7. Missing resolved second-order window -> `reject_integrator_temporal_order`.
   Failure of the separately registered physical-energy contraction gate ->
   `reject_integrator_long_run_energy_behavior`; insufficient uncertainty
   resolution to decide that gate -> `stop_integrator_certification_inconclusive`.
8. Frozen representation, P/L/centrality, recovery or frame budget violation ->
   `reject_integrator_frozen_budget`; unresolved upper enclosure alone ->
   `stop_integrator_certification_inconclusive`, NOT a proved violation.
9. Replay/twin failure -> `reject_integrator_determinism`; incomplete full
   reference coverage -> `stop_integrator_certification_inconclusive`.
10. All eligible candidates -> publish the Pareto set as
    `retain_bounded_integrator_pareto_set_for_research`; an A-only set is
    `retain_existing_b96_kdk_baseline_for_research`. No eligible candidate ->
    `no_bakeoff_candidate_fully_qualified`; this does not revoke the parent.

Selected persistent precision is fixed at 96, not selected anew. No production
integrator is selected here. All dispositions keep NO_PROMOTION. Seal later
results and stop; publication requires its own approval. This turn stops
immediately after this document is committed and pushed, BEFORE any solver,
C proof implementation, test trajectory, or new candidate result.

## References and limits of the prior-art claim

- O. Gonzalez, *Time Integration and Discrete Hamiltonian Systems* (1996),
  [author PDF](https://web.ma.utexas.edu/users/og/PUBLICATIONS/paper_DisHamSys.pdf).
  Discrete chain rules motivate the conditional energy argument, not a claim
  about the MLS binary64 graph.
- *Discrete gradients in short-range molecular dynamics simulations*,
  [paper](https://doi.org/10.1007/s11075-023-01717-4),
  [repository PDF](https://publikationen.bibliothek.kit.edu/1000167557/152088221),
  Sections 3.1 and 4.1. The radial two-endpoint construction is the prior-art
  ingredient; the coupled quadratic-H compatibility checks above are explicit
  MLS obligations. Exact-arithmetic properties do not certify bounded execution.
- [MPFR 4.2.2 manual](https://www.mpfr.org/mpfr-4.2.2/mpfr.html).
  Correct rounding bounds individual operations; no adjacent-realized-error
  ratio is used as a necessary qualification rule in this preregistration.
