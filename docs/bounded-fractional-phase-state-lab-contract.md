# Bounded Fractional Phase-State Lab contract

## Scope and immutable parent

This experiment starts only from accepted source
`6f25d7428fde7420c1f4cbe1e3565c11a28e817c` and evidence tag
`explicit-fractional-phase-state-lab-evidence-v1`. Before candidate results are
interpreted, the complete immutable parent bundle and both raw twins must match
their sealed hashes and reproduce
`fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved`.
A mismatch is `stop_inconclusive_or_wrong_parent`.

The lab tests only whether fixed-storage, variable-exponent fractional packet
phase state retains the dynamics recovered by exact rationals. It does not
change topology, reference geometry, `H_force`, collective energy, the central
force law, Path-B relation geometry, `r/l0 >= 2^-24`, the KDK stage order,
units, scenarios, or material model. It does not install mechanics in `World`
or relax the accepted conservation specification. Every outcome is **NO
PROMOTION TO AUTHORITATIVE WORLD DYNAMICS**.

## Candidate state and arithmetic

The complete registered significand precisions are

```text
B = 64, 96, 128, 192, 256 bits.
```

No precision is added or removed after trajectory data are known. One
trajectory uses one fixed precision. The reference backend is
`gmpy2==2.3.1` with MPFR 4.2.2, round-to-nearest/ties-to-even, and no registered
fused operations. The normalized leading-bit exponent is restricted to
`[-16382,16383]`, corresponding to MPFR context `emin=-16381`, `emax=16384`.
NaN, infinity, invalid, division by zero, underflow, overflow, or an
out-of-range exponent rejects the complete step atomically. Adaptive precision,
floating expansions, rational residuals, compensation, discarded-bit logs,
and causal side history are forbidden.

Each raw position or momentum component has the unique finite representation

```text
value = (-1)^sign M 2^(E-(B-1)),
2^(B-1) <= M < 2^B.
```

Its wire record is sign `u8`, precision `u16le`, leading exponent `i16le`, and
exactly `B/8` big-endian significand bytes. Canonical zero has positive sign,
zero exponent, and zero significand. Packet order is ascending ID; component
order is `xx,xy,xz,px,py,pz`. The component occupies `5+B/8` bytes, so the six
phase components occupy `{78,102,126,174,222}` bytes and a packet including
`u64` ID and `i64` mass occupies `{94,118,142,190,238}` bytes across the five
registered precisions. Causal state size must remain constant for the complete
run.

The state encoding begins with `MLS-BOUNDED-BINARY-PHASE-v1\0`, followed by
`u16le version=1`, `u16le B`, `i16le minimum E=-16382`, `i16le maximum
E=16383`, `i64le time_raw`, `u64le packet_count`, and packet records. Decoding
and re-encoding must reproduce every byte exactly.

The source bound by `source_sha` defines slots-only causal objects with exact
shape `State(precision,time_raw,packets)` and
`Packet(identifier,mass_raw,x[3],p[3])`. Runtime checks require those exact
types and `__slots__` tuples, exact three-component vectors, unique positive
packet IDs, positive signed-64 masses, and finite canonical MPFR components at
the state's registered precision. Metadata binds the versioned shape string
and its SHA-256. Fixed wire-state size, canonical checkpoint decode/re-encode,
and byte-identical checkpoint replay then make zero causal cache/history bytes
a source-and-state-shape conclusion, not a claim trusted because a receipt
contains two zero integers.

## Frozen map

All runs use the accepted `R=128` exact unit basis. At each relation, subtract
packet positions at precision `B`, scale that already-relative vector by the
once-rounded `Lq_B`, then correctly round the relative SI components to
binary64 for the unchanged Path-B evaluator. Absolute positions may never pass
through binary64. The returned binary64 length and conjugate are reconstructed
as exact dyadics and converted exactly to `B` bits. Each precision receipt
contains the complete canonical component/wire encoding of `Lq_B`, its exact
rational value, the immediately captured conversion-inexact boolean, and a
versioned one-record rounding-audit SHA-256.

For signed raw kick duration `q`, evaluate separate correctly rounded
operations in this order:

```text
c_kick = RN_B(q*Tq*Lq/Pq)
a       = RN_B(c_kick*g)
alpha   = RN_B(a/r)
J[k]    = RN_B(alpha*r_raw[k])
p_i[k]' = RN_B(p_i[k]+J[k])
p_j[k]' = RN_B(p_j[k]-J[k]).
```

The identical stored `J` is applied at both endpoints, but it is not claimed
exactly central after component rounding. Drift is

```text
c_drift = RN_B(q/mass_raw)
d[k]    = RN_B(c_drift*p[k])
x[k]'   = RN_B(x[k]+d[k]),
```

with momentum copied exactly. KDK remains half kick, full drift, half kick;
the ineligible first-order control remains full kick then full drift. Only a
fully checked state commits.

The registered causal operation counts for `n` packets and `m` relations are
`17m+1` per kick, `7n` per drift, `34m+7n+2` per KDK step, and
`17m+7n+1` per control step. Evidence records both totals and the complete
nonzero category map. Category maps use lexicographically sorted ASCII
`name=count` entries joined by semicolons; total equality cannot substitute for
category equality. It also records the complete nonzero inexact-category map,
inexact and exact totals, audit-record count, and versioned audit digest.

The accepted-run operation inventory is exactly 425 rows: 150 primary short,
75 reverse, 75 transformed (translation, common boost, and proper lattice
rotation), 25 packet permutation, 50 checkpoint (first and resumed halves), and
50 long internal/boosted runs. The deliberately rejected domain-crossing step
is noncommitted arithmetic and is excluded from this accepted-run inventory;
its atomicity is recorded separately in the domain receipt.

`invariants.csv` and `force_audit.csv` cover that same complete 425-ID
accepted inventory. Each KDK invocation with `N` completed steps emits
`1+4N` invariant rows and `2mN` relation-force rows; the first-order control
emits `1+3N` and `mN`, respectively. Thus every operation-audited reverse,
covariance, permutation, checkpoint-half, and long invocation carries exact
`P`, `L`, pair-momentum, centrality, and relation-angular evidence.

## Exact-rational comparator coverage

The ineligible exact-rational control has the same frozen complexity ceilings
as its accepted parent: maximum component numerator/denominator bit length
`262144`, median component numerator/denominator bit length `131072`, and
canonical checkpoint size `8388608` bytes. Each long `k4_internal` and
`k4_boosted` control at each timestep level advances independently through and
including its first crossing state, or to the complete 16-second horizon if no
ceiling is crossed.

The ten scenario/level receipts record requested and completed steps, sample
count, status, first crossing, last within-ceiling step, last comparator sample,
first comparator-free sample, last comparator time and state hash, observed
maximum complexity, first-crossing complexity, the frozen limits, and whether
the crossing state is included. A first crossing is the last comparator sample;
the following sample begins the comparator-free interval. The sealed internal-
velocity status and crossing step must reproduce at every level. The common-
boost control receives its own measured crossing and may not inherit or infer
the internal trajectory's cutoff.

## Independent observation and gates

The candidate clears arithmetic flags around every registered primitive,
captures MPFR `inexact` immediately after the operation and before diagnostic
conversion, reconstructs the primitive's exact rational result, verifies the
signed rounded-minus-exact error, and checks its registered half-ULP bound. A
versioned digest cryptographically binds each primitive's causal order,
category, exact result, rounded result, signed error, half-ULP bound, and
inexact boolean. Committed local step digests are merged as versioned,
count-bearing segments, so the run digest also binds step segmentation without
turning rounding history into causal state.

The verifier reconstructs every stored value independently as an exact dyadic,
implements ties-to-even rounding with integer/rational arithmetic, and must
reproduce every candidate state hash, endpoint, checkpoint, complete canonical
observer-event suffix, residual row, inexact classification, and rounding-audit
digest. The replay stream includes every ordered relation force audit and each
first-kick, drift, second-kick, and
committed invariant record, followed by the post-step mechanical-energy
observation bound to the committed state; both its event count and versioned
framed SHA-256 must agree after checkpoint/resume. For result leading exponent
`E`, it checks every primitive against `half_ulp = 2^(E-B)` and independently
sums local bounds in operation
order. It also enforces the preregistered magnitude envelopes
`|x_raw|<2^48`, `|p_raw|<2^40`, `|r_raw|<2^49`, and `|J_raw|<2^40`; these are
fail-closed evidence bounds, not clamps.

Checkpoint-resumed audit rows retain their unique
`checkpoint:resumed:B<precision>:L<level>` identity and absolute checkpoint
step. The replay observer projection alone uses the uninterrupted primary
`short:k4_internal:...` identity, original invariant baseline, and absolute
step labels so its suffix hashes remain directly comparable. The arithmetic is
executed only once.

The exact observer measures total momentum, orbital angular momentum, relation
centrality, signed-time recovery, and covariance without feeding those values
back into state. For endpoint accumulation errors `eps_i,eps_j`, it verifies

```text
Delta P = eps_i + eps_j
Delta L = (x_i-x_j) cross J + x_i cross eps_i + x_j cross eps_j.
```

It also verifies the corresponding component-rounded centrality and drift
identities. Every measured residual must lie inside the independently summed
half-ULP bound and contract with increasing precision at the registered
unit-roundoff rate until below its physical budget.

Exact fraction and vector hashes retain the accepted parent preimage. For
nonnegative `v`, `encode_unsigned(v)` is a `u64le` byte count followed by the
minimal big-endian magnitude, with a zero count and no magnitude bytes for
zero. `encode_signed(v)` is sign byte `0` or `1` followed by
`encode_unsigned(abs(v))`, with `1` used exactly for negative values.
`encode_fraction(q)` concatenates the signed reduced numerator and the unsigned
positive reduced denominator. A fraction hash is SHA-256 of that record. Every
evidence vector has exactly three components, and its hash is SHA-256 of the
three fraction records concatenated in `x,y,z` order without a textual
conversion.

The exact budgets use `q_budget=2^-20`:

| quantity | budget |
|---|---:|
| position | `Lq*2^-20` |
| momentum | `Pq*2^-20` |
| orbital angular momentum / centrality | `Lq*Pq*2^-20` |
| representation-induced energy | `Eq*2^-20` |

The 16-second slope budgets divide the corresponding quantity by 16 seconds.
Meeting a budget does not waive precision scaling or analytic error bounds.

The candidate reuses the three one-second scenarios, five timestep halvings,
110-digit smooth ODE oracle, exact-rational KDK control, first-order control,
16-second internal-velocity runs, common boost, translation, proper signed-axis
rotation, packet permutation, signed-time recovery, interior checkpoint, and
domain-crossing case. A selectable precision must:

- make the physical component envelopes
  `R_x=max|Lq*(x_B-x_Q)|` and `R_p=max|Pq*(p_B-p_Q)|`, together with the scaled
  complete-state norm, decrease strictly with `B` until below KDK truncation
  error `T`; before the first budget pass each adjacent pair must satisfy
  `R(B_high) <= 4*2^(-(B_high-B_low))*R(B_low)`;
- satisfy `R_state <= 0.1*T` at all five levels and remain within every physical
  component budget;
- recover three consecutive KDK orders in `[1.6,2.4]` for all three scenarios,
  while the control retains at least two orders in `[0.6,1.4]`;
- keep conservation, centrality, reversal, frame, and energy residuals inside
  independently derived bounds with no precision-independent or secular term;
- preserve exact-domain atomic rejection, deterministic replay, canonical
  serialization, and constant causal-state size; and
- be the smallest registered precision satisfying every gate.

The exact safe-chord predicate is evaluated from reconstructed dyadics using
`|A+tD|^2 >= 2^-48|r0|^2` over the complete chord. An uncertified chord rejects
without advancing time or changing state, hashes, observations, or events.
The comparison aligns dyadics to one base-two exponent and uses fail-closed
integer scratch. For precision `B`, its mechanically derived universal cap is

```text
W_domain(B) = 4*(B + (16383-(-16382))) + 64 bits.
```

Here `B+(Emax-Emin)` bounds an aligned stored component, two carry bits cover
endpoint/chord differences, the factor four covers the quartic interior
predicate, and the 64-bit allowance covers the frozen `2^-48` comparison plus
carry slack. Every initial-force predicate and complete-chord predicate checks
the cap. The domain receipt exports both maximum reserved and permitted bits;
crossing the cap rejects rather than falling back to unbounded causal
arithmetic. Rejected-step invariant/force rows and semantic observer events are
collected locally, and both measured externally emitted counts must be zero.
The prior and returned mechanical-energy observations are independently framed
and hashed; their exact tuples and SHA-256 values must agree, and the receipt
must mark the observation unchanged.

## Decision order

Apply the first matching disposition:

1. `stop_inconclusive_or_wrong_parent`;
2. `reject_bounded_binary_fractional_phase_state`;
3. `bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved`;
4. `bounded_phase_state_converges_but_required_precision_unresolved`;
5. `retain_bounded_variable_exponent_phase_state_for_research`.

Twin evidence, GCC, Clang, MSVC, the independent Python verifier, pinned Lean,
semantic and seal mutations, immutable-tag CI, and fresh public-download
verification must all pass before sealing and stopping.
