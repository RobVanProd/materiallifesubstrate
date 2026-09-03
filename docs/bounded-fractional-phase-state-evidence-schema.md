# Bounded Fractional Phase-State evidence schema

## Bundle identity and topology

The outer schema is `mls.bounded-fractional-phase-state.outer-seal.v1`. The
sealed bundle contains exactly these payload groups plus `outer-seal.json`:

- `raw-a/` and `raw-b/`: independently materialized, byte-identical candidate
  evidence;
- `oracle/`: independent exact-dyadic/110-digit result and semantic mutation
  receipt;
- `parent-explicit-fractional/`: the complete immutable accepted parent bundle;
- `source/`: deterministic source archive and source-identity receipt;
- `receipts/`: dependency, build, compiler, Python, Lean, twin, CI, tag,
  release, failed-attempt, and fresh-download receipts; and
- `docs/`: preregistration, lab contract, result, and this schema.

Every payload file is covered by relative path, byte count, and SHA-256.
Symlinks, unsafe or case-colliding paths, unexpected top-level groups, missing
files, and extra files are rejected. The seal binds the accepted parent source,
tag and tag object; exact candidate source and tree; branch and evidence tag;
raw-twin aggregate; final decision; selected precision or null; MPFR/gmpy2
versions; exponent contract; safe domain; physical budgets; and
`NO_PROMOTION`.

## Raw inventory

The raw schema is `mls.bounded-fractional-phase-state.raw.v1`. Each raw twin
contains exactly 25 UTF-8 CSV files:

| file | role |
|---|---|
| `metadata.csv` | schema, immutable parent, source, branch, candidate, backend, rounding, exponent, force-domain, decision-boundary, and promotion identity |
| `precisions.csv` | registered precision profiles, exponent context, unit roundoff, fixed component/packet storage sizes, exact-domain scratch cap, and the canonical once-rounded `Lq_B` conversion/audit |
| `units.csv` | exact inherited `R=128` SI unit basis and exact physical error budgets |
| `parent_fingerprint.csv` | expected and observed SHA-256 for every accepted parent raw file |
| `positive_control.csv` | explicit exact-rational parent invariant, centrality, recovery, covariance, domain, and complexity checks; raw hashes bind all remaining parent results |
| `reference_packets.csv` | frozen accepted packet reference state copied byte-for-byte from the parent |
| `relations.csv` | frozen oriented topology and binary64 rest-geometry inputs copied byte-for-byte from the parent |
| `force_operator.csv` | frozen accepted `H_force` binary64 bit patterns copied byte-for-byte from the parent |
| `initial_states.csv` | complete canonical bounded initial phase states |
| `endpoints.csv` | complete canonical one-second KDK and first-order endpoints |
| `checkpoint_states.csv` | complete canonical interior checkpoint states |
| `recovery_states.csv` | complete canonical signed-time recovery states |
| `long_endpoints.csv` | complete canonical 16-second bounded K4 internal and common-boost endpoints |
| `representation_error.csv` | sampled bounded-versus-exact-control position, momentum, and energy errors; the oracle derives scaling and smooth-reference comparisons |
| `rational_comparator.csv` | independently measured exact-rational comparator coverage and first complexity crossing for each long scenario and timestep level |
| `energies.csv` | registered short exact-rational kinetic, Path-B potential, and mechanical-energy samples |
| `long_energy.csv` | every registered 16-second bounded kinetic, potential, and mechanical-energy sample |
| `invariants.csv` | exact-dyadic total momentum and orbital-angular-momentum values and signed initial-state residuals for every accepted invocation |
| `force_audit.csv` | relation geometry/force bits, causal/exact offsets, stored and applied impulses, pair momentum, three centrality measures, and angular residuals for every accepted invocation |
| `reversibility.csv` | signed-time stored-state recovery errors and byte-identity observation |
| `covariance.csv` | translation, boost, proper lattice rotation, and packet-permutation relative-state discrepancies |
| `checkpoint.csv` | canonical round trip, resumed/uninterrupted final hashes, and event-suffix identity |
| `domain.csv` | deterministic complete-chord status and atomic rejection receipt |
| `state_size.csv` | fixed construction sizes and observed canonical state bytes at all registered lifecycle points |
| `operation_counts.csv` | expected, observed, exact/inexact, and rounding-audit counts and digests for every accepted trajectory invocation |

CSV headers are part of the schema. Files contain exactly one header, LF line
endings, RFC 4180 quoting, and deterministic row order. Empty data is encoded
as an empty field only where the schema permits it; a missing field is never
substituted for zero or false.

## Exact CSV headers

The compact notation `component_fields(xx,xy,xz,px,py,pz)` expands each prefix
in the displayed order by suffixes
`sign,E,significand_hex,wire_hex,exact_num,exact_den`. The notation
`vector_fields(prefixes)` expands each prefix in order to
`hash,raw_max_dyadic,raw_x_dyadic,raw_y_dyadic,raw_z_dyadic,max_num,max_den,`
`x_num,x_den,y_num,y_den,z_num,z_den` (13 fields exactly).

| file | ordered header |
|---|---|
| `metadata.csv` | `key,value` |
| `precisions.csv` | `precision,unit_roundoff,leading_exponent_min,leading_exponent_max,component_bytes,phase_bytes_per_packet,complete_packet_bytes,domain_scratch_bit_limit,lq_sign,lq_E,lq_significand_hex,lq_wire_hex,lq_exact_num,lq_exact_den,lq_conversion_inexact,lq_rounding_audit_sha256,rounding` |
| `units.csv` | `Lq,Mq,Tq,Pq,Eq,Fq,position_budget,momentum_budget,angular_centrality_budget,energy_budget,energy_slope_budget` |
| `parent_fingerprint.csv` | `file,sha256,expected_sha256,passed` |
| `positive_control.csv` | `check,passed,detail` |
| `reference_packets.csv` | `model_id,level,packet_id,x_raw,y_raw,z_raw,mass_raw` |
| `relations.csv` | `model_id,relation_index,first_id,second_id,rest_length_bits` |
| `force_operator.csv` | `model_id,row,column,h_bits` |
| five state tables | `precision,scenario_id,model_id,scope,path,level,dt_raw,steps,status,completed_steps,time_raw,state_hash,packet_id,mass_raw,component_fields(xx,xy,xz,px,py,pz)` |
| `representation_error.csv` | `scenario_id,scope,path,precision,level,dt_raw,sample,candidate_state_hash,control_state_hash,position_raw_error_num,position_raw_error_den,position_physical_error_num,position_physical_error_den,momentum_raw_error_num,momentum_raw_error_den,momentum_physical_error_num,momentum_physical_error_den,energy_error_num,energy_error_den` |
| `rational_comparator.csv` | `scenario_id,scope,path,level,dt_raw,requested_steps,completed_steps,comparison_samples,status,first_crossing_step,last_within_ceiling_step,last_comparator_sample,first_comparator_free_sample,last_comparator_time_raw,last_comparator_state_hash,maximum_component_bits,maximum_state_median_bits_num,maximum_state_median_bits_den,maximum_checkpoint_bytes,crossing_component_bits,crossing_state_median_bits_num,crossing_state_median_bits_den,crossing_checkpoint_bytes,maximum_component_bits_limit,median_component_bits_limit,maximum_checkpoint_bytes_limit,crossing_state_included` |
| two energy tables | `scenario_id,scope,path,precision,level,dt_raw,sample,potential_binary64_bits,kinetic_num,kinetic_den,kinetic_hash,potential_num,potential_den,potential_hash,mechanical_num,mechanical_den,mechanical_hash` |
| `invariants.csv` | `trajectory_id,precision,level,step,stage,state_hash,vector_fields(momentum,angular,delta_momentum,delta_angular)` |
| `force_audit.csv` | `trajectory_id,precision,level,step,stage,relation_index,first_id,second_id,length_bits,conjugate_bits,causal_offset_raw_hash,exact_stored_offset_raw_hash,ideal_impulse_raw_hash,first_actual_impulse_raw_hash,second_actual_impulse_raw_hash,vector_fields(pair_momentum_residual,stored_impulse_centrality_residual,first_actual_centrality_residual,second_actual_centrality_residual,relation_angular_residual)` |
| `reversibility.csv` | `scenario_id,precision,level,dt_raw,steps,forward_status,backward_status,initial_hash,recovered_hash,complete_state_identical,position_raw_error_num,position_raw_error_den,position_physical_error_num,position_physical_error_den,momentum_raw_error_num,momentum_raw_error_den,momentum_physical_error_num,momentum_physical_error_den` |
| `covariance.csv` | `kind,scope,precision,level,dt_raw,sample,baseline_hash,transformed_hash,bit_identical,relative_position_raw_num,relative_position_raw_den,relative_position_physical_num,relative_position_physical_den,relative_momentum_raw_num,relative_momentum_raw_den,relative_momentum_physical_num,relative_momentum_physical_den` |
| `checkpoint.csv` | `scenario_id,precision,level,dt_raw,steps,checkpoint_step,checkpoint_hash,checkpoint_bytes,decoded_hash,whole_final_hash,resumed_final_hash,whole_suffix_event_count,resumed_event_count,whole_suffix_event_sha256,resumed_event_sha256,event_suffix_identical,canonical_round_trip` |
| `domain.csv` | `scenario_id,precision,level,status,prior_hash,returned_hash,time_unchanged,state_unchanged,event_rows_emitted,energy_ledger_present,observer_events_emitted,prior_energy_observation_sha256,returned_energy_observation_sha256,energy_observation_unchanged,offending_relation_index,chord_minimum_case,comparison_lhs_num,comparison_lhs_den,comparison_rhs_num,comparison_rhs_den,domain_scratch_observed_bits,domain_scratch_limit_bits` |
| `state_size.csv` | `trajectory_id,precision,level,step,label,packet_count,component_bytes,phase_bytes_per_packet,complete_packet_bytes,state_bytes,state_hash,causal_cache_bytes,causal_history_bytes` |
| `operation_counts.csv` | `trajectory_id,precision,level,path,packet_count,relation_count,completed_steps,per_step_expected,expected_categories,observed_categories,inexact_categories,inexact_total,exact_total,rounding_audit_records,rounding_audit_sha256,categories_passed,total_expected,total_observed,passed` |

The five state tables are `initial_states.csv`, `endpoints.csv`,
`long_endpoints.csv`, `checkpoint_states.csv`, and `recovery_states.csv`. The
two energy tables are `energies.csv` and `long_energy.csv`. The copied parent
tables retain the exact accepted parent headers shown above.

In addition to the previously frozen identity fields, `metadata.csv` includes
`causal_state_shape`, `causal_state_shape_sha256`,
`causal_state_slots_only=true`, and the exact limits
`exact_comparator_maximum_component_bits=262144`,
`exact_comparator_median_component_bits=131072`, and
`exact_comparator_maximum_checkpoint_bytes=8388608`. `precisions.csv` binds the
canonical `Lq_B` component and conversion audit separately for every registered
precision as specified below.

## Scalar encodings

- Decimal integers have no leading `+`, no leading zero except literal `0`,
  and no exponent notation.
- Exact rational values use separate canonical numerator and positive
  denominator columns or the lexical form `numerator/denominator`; fractions
  are reduced and zero is `0/1`.
- Binary64 values are unsigned decimal encodings of their exact 64-bit object
  representation. Human-readable decimal values are diagnostic only.
- Compact exact dyadics are exactly `0` or
  `[-]0x<lowercase-odd-magnitude>@<base-two-exponent>`. Signed raw residual
  components use this spelling; neither candidate nor verifier reparses a
  decimal approximation.
- Booleans are exactly `true` or `false`. Enumerations and identifiers are
  case-sensitive ASCII. Hashes are lowercase hexadecimal SHA-256.

Exact parent fraction and vector hashes use these canonical binary preimages:

```text
encode_unsigned(v >= 0)
  = u64le(magnitude_byte_count) || minimal_big_endian_magnitude

encode_signed(v)
  = i8(sign) || encode_unsigned(abs(v))
  where sign = 1 exactly when v < 0, otherwise 0

encode_fraction(numerator/denominator)
  = encode_signed(reduced_numerator)
    || encode_unsigned(positive_reduced_denominator)
```

The minimal magnitude for zero has byte count zero and contributes no magnitude
bytes. A fraction hash is SHA-256 of exactly one `encode_fraction` record, with
no textual conversion or extra prefix. A vector hash is SHA-256 of the direct
concatenation of exactly three `encode_fraction` records in `x,y,z` order. The
parent helper accepts a general iterable, but every evidence vector is required
to have length three; that fixed cardinality and order are part of this schema.

## Canonical phase-state columns

State-table prefix columns identify the trajectory, scenario, path, precision,
timestep level, requested/completed step count, time, status, state hash,
packet ID, and signed-64 raw mass. Each phase component prefix in

```text
xx, xy, xz, px, py, pz
```

then expands in that order to:

```text
<component>_sign
<component>_E
<component>_significand_hex
<component>_wire_hex
<component>_exact_num
<component>_exact_den
```

For precision `B`, `significand_hex` contains exactly `B/4` lowercase hex
digits and `wire_hex` contains exactly `2*(5+B/8)` lowercase hex digits. The
wire bytes are sign `u8`, precision `u16le`, leading exponent `i16le`, and the
unsigned significand in exactly `B/8` big-endian bytes. A nonzero value obeys

```text
value = (-1)^sign * M * 2^(E-(B-1)),
2^(B-1) <= M < 2^B,
-16382 <= E <= 16383.
```

Zero alone has sign `0`, `E=0`, and all-zero significand. The exact rational
columns must equal the independently decoded wire value. Decode/re-encode must
reproduce `wire_hex`, and the complete state hash is over the canonical binary
state encoding, not the CSV spelling.

Canonical state order is ascending packet ID, with fields `u64le packet_id`,
`i64le mass_raw`, then the six components above. The state begins with
`MLS-BOUNDED-BINARY-PHASE-v1\0`, then `u16le version=1`, `u16le B`, `i16le
minimum E=-16382`, `i16le maximum E=16383`, `i64le time_raw`, and `u64le
packet_count`. For fixed model and `B`, no operation count, checkpoint, or
trajectory duration may change its encoded size.

Each `precisions.csv` row also encodes the once-rounded `Lq_B` value using the
same component fields and wire rules. `lq_conversion_inexact` is the MPFR
inexact flag captured immediately after that conversion, and
`lq_rounding_audit_sha256` binds its one-record rounding audit. The verifier
reconstructs the exact `Lq` input, repeats ties-to-even conversion, and requires
the decoded wire value, inexact classification, exact signed error, half-ULP
bound, and digest to agree.

## Relational and error-accounting rows

`representation_error.csv` identifies scenario, path, precision, level,
sample, scope, and comparator hashes. It carries exact rational maximum
component errors for raw and physical position and momentum, plus signed
bounded-minus-control mechanical-energy error. Complete state tables let the
oracle independently reconstruct scaled norms, endpoint/through-time maxima,
temporal truncation, budgets, adjacent-precision ratios, and pass/fail results;
those derived classifications belong to the oracle result, not extra raw CSV
columns.

`invariants.csv` identifies trajectory, precision, level, step, and map stage.
Its four exact physical vectors are current total `P`, current total orbital
`L`, and their signed deltas from the trajectory's initial values. Each vector
has a canonical hash, infinity-norm rational, and three signed rational
components. The verifier derives local half-ULP bounds and bound/budget
decisions independently. Rows are in causal stage order: initial, first kick,
drift, second kick, committed step. Diagnostic reads never affect state.
The trajectory-ID inventory is exactly the same 425 accepted invocations as
`operation_counts.csv`. A KDK invocation with `N` completed steps has exactly
`1+4N` invariant rows; a first-order-control invocation has exactly `1+3N`.
This includes every reverse, transformed, packet-permuted, checkpoint-first,
checkpoint-resumed, and long trajectory, not only the primary short runs.

For short trajectories every one of the 13 fields per invariant vector is
present. For long trajectories, absolute `momentum` and `angular` retain only
`hash` and `raw_max_dyadic`; their signed raw components and physical rational
fields are empty. Long `delta_momentum` and `delta_angular` retain `hash`,
`raw_max_dyadic`, and all three signed `raw_*_dyadic` fields; only their physical
`max_num/max_den` and component numerator/denominator fields are empty. These
are the only permitted invariant-vector omissions.

`force_audit.csv` adds relation index and oriented endpoint IDs. It records the
accepted binary64 length/conjugate bits; hashes of the causal rounded offset,
exact difference of stored endpoint positions, component-rounded relation
impulse, and two actual endpoint momentum deltas; and pair momentum,
stored-impulse centrality, first-actual centrality, second-actual centrality, and
complete relation angular residuals. Short rows fill all 13
fields for each residual vector. Long rows retain `hash`, `raw_max_dyadic`, and
all three signed `raw_*_dyadic` fields; only physical `max_num/max_den` and
physical component numerator/denominator fields are empty. The compact physical
omission keeps all relation kicks and signed raw residuals present without
duplicating roughly a million scaled exact component vectors. The verifier
reconstructs every omitted physical vector from the raw dyadics and exact unit
scale, then derives endpoint
rounding errors, local half-ULP bounds, and centrality classifications.
Relation rows follow frozen relation-index order inside each force stage.
For `m` relations and `N` completed steps, a KDK invocation has exactly
`2mN` force rows and a first-order-control invocation has exactly `mN`.
Its trajectory IDs must again equal the complete 425-ID operation inventory.

`operation_counts.csv` records packet and relation counts, integration path,
expected and observed rounded primitives, exact and inexact totals, a rounding
audit record count and digest, total equality, and category equality. Both
`observed_categories` and `inexact_categories` are serialized by
lexicographically ascending ASCII `name=count` entries joined by semicolons,
with zero-count categories omitted. `exact_total + inexact_total` and
`rounding_audit_records` must each equal `total_observed`. The exact registered
totals are `17m+1` per kick, `7n` per drift, `34m+7n+2` per KDK step, and
`17m+7n+1` per first-order control step.

The candidate clears the MPFR flags before every registered primitive and
captures `inexact` immediately after the operation, before any diagnostic
conversion. It reconstructs the operation's exact rational result, computes
`signed_error = rounded_result - exact_result`, requires the flag to equal
`signed_error != 0`, and requires `abs(signed_error)` not to exceed the
registered half-ULP. These checks occur before the record enters the audit.

The versioned rounding-audit SHA-256 binds causal record order, category, exact
result, rounded result, signed error, half-ULP bound, and inexact boolean. A
local audit begins with `MLS-BOUNDED-ROUNDING-AUDIT-v1\0`; each record contains
its one-based `u64le` sequence number and the six values above as canonical
UTF-8 fields, each preceded by its `u64le` byte count. A run audit merges each
committed step as a versioned segment, binding
`MLS-BOUNDED-ROUNDING-AUDIT-MERGE-v1\0`, the segment's `u64le` record count,
and its 32-byte local digest. Thus the run digest hierarchically commits to
both step segmentation and every primitive record without retaining discarded
bits as causal state.

There are exactly 425 accepted-run rows, with this frozen inventory:

- 150 primary short trajectories: three scenarios, two paths, five
  precisions, and five timestep levels;
- 75 signed-time reverse trajectories;
- 75 transformed trajectories: translation, common boost, and proper lattice
  rotation;
- 25 packet-permutation trajectories;
- 50 checkpoint trajectories: first half and resumed half; and
- 50 long trajectories: internal and boosted at five precisions and five
  timestep levels.

The domain-crossing probe is a deliberately rejected, noncommitted step. Its
attempted arithmetic is excluded from `operation_counts.csv`; it cannot be
misrepresented as an accepted zero-operation run. Its state, observer, energy,
and atomicity evidence is instead carried by `domain.csv`.

`rational_comparator.csv` has exactly ten rows: `k4_internal` and `k4_boosted`
at each of the five timestep levels. Every row has
`scope=long_exact_comparator` and `path=bounded_binary_kick_drift_kick`. Each
scenario/level control advances independently until the requested 16-second
horizon or until the first state that exceeds any frozen exact-state ceiling:

```text
maximum component numerator/denominator bit length <= 262144
median component numerator/denominator bit length  <= 131072
canonical checkpoint bytes                         <= 8388608
```

For each exact state, the component population comprises the numerator and
denominator bit lengths of every reduced fractional residual in all position
and momentum components. The median is exact and therefore stored as a reduced
numerator/denominator pair. `maximum_*` fields include every generated
comparator state, including a first crossing state.

When a ceiling is crossed, `status=complexity_budget_exceeded`,
`first_crossing_step=completed_steps`, `last_within_ceiling_step` is the prior
step, and `crossing_state_included=true`. That crossing state remains the last
comparison record: `comparison_samples=completed_steps+1`,
`last_comparator_sample=completed_steps`, its canonical hash and raw time are
retained, and `first_comparator_free_sample=completed_steps+1`. The three
`crossing_*` measurements identify which limit was exceeded. If no crossing
occurs, status is `accepted`, the crossing fields are empty,
`crossing_state_included=false`, and the first comparator-free sample is one
past the completed horizon.

The sealed parent's internal-velocity crossing step and status must reproduce
at every level before bounded results are interpreted. The boosted control is
not assigned that inherited cutoff: it is advanced and measured independently
and receives its own first crossing, comparator hash, and comparator-free
start. Thus absence of later `long_exact_prefix` rows is explained by the
matching scenario/level receipt rather than by a shared or inferred cutoff.

## Trajectory, conservation, and safety tables

Short rows cover K4 breathing, K4 internal velocity, and octahedron deformation
at five timestep levels for KDK and the ineligible first-order control. Long
rows cover every precision and level of the 16-second internal-velocity case.
`scope` distinguishes short, long, and exact-control-prefix rows. The presence
of a representation-error row makes exact-rational comparator availability
explicit; absence after the sealed rational complexity limit is never
represented as a zero error.

Energy rows export exact rational kinetic, Path-B potential, and total
mechanical energy with hashes, plus the potential's binary64 bits. Signed
bounded-minus-control error is in `representation_error.csv`. The verifier
derives maximum, endpoint, mean, and least-squares slope together with budget
and precision-scaling classifications. Exact signed invariant and centrality
components remain available for bias analysis; maxima alone cannot replace
them.

`reversibility.csv` compares the exact canonical initial state with the result
of `N(+h)` followed by `N(-h)`, retaining per-phase position/momentum envelopes,
physical/raw rational errors, and state-hash identity. The verifier adds
independent bounds, budgets, and precision-scaling results.
`covariance.csv` distinguishes translation, common boost, proper signed-axis
rotation, and packet permutation and records raw/physical relative position and
momentum errors plus a bit-identity observation. The verifier classifies
rotation only as bit-exact, exact-dyadic, or precision-bounded; no
arbitrary-rotation claim is encoded.

`domain.csv` records the deterministic domain status, prior and returned state
hashes, unchanged time/state booleans, emitted invariant/force-row and semantic
observer-event counts, absence of an energy ledger, prior and returned energy-
observation SHA-256 values and their equality classification, offending
relation, chord-minimum case, and exact rational sides of the squared-domain
comparison. The verifier independently reconstructs the
exact dyadic predicate from frozen inputs. Equality with the `r/l0=2^-24`
boundary is safe. It also records the maximum reserved integer scratch width
and the per-precision cap
`4*(B+(leading_exponent_max-leading_exponent_min))+64`; exceeding that cap is a
fail-closed domain error. `event_rows_emitted` is the measured combined size of
the rejected step's externally visible invariant and force-row collectors, and
`observer_events_emitted` independently measures the canonical semantic-event
collector; neither is a constant assertion. The prior and returned
mechanical-energy observations use the same canonical energy-event framing, so
`prior_energy_observation_sha256` and `returned_energy_observation_sha256`, the
underlying exact tuples, and `energy_observation_unchanged` must all certify no
change. `checkpoint.csv` includes uninterrupted, decoded, resumed, and final
hashes plus canonical and complete observer-event-suffix comparisons.

The checkpoint observer stream contains every accepted step's causal events in
this order: each first-kick relation audit in relation order, the first-kick
invariant, the drift invariant, each second-kick relation audit in relation
order, the second-kick invariant, the committed-state invariant, and the
post-commit mechanical-energy observation. Each event
starts with ASCII `MLS-BOUNDED-OBSERVER-EVENT-v1\0`, followed by its kind and
the complete corresponding `INVARIANT_FIELDS`, `FORCE_FIELDS`, or energy-event
record. The energy event binds the trajectory, precision, level, absolute
step, canonical state hash, potential binary64 bits, and exact
numerator/denominator/hash of kinetic, potential, and total mechanical energy.
The
kind, field count, and every field name and UTF-8 value are framed by an
unsigned 64-bit little-endian byte count before the event is SHA-256 hashed.
Thus invocation identity, absolute step, state hashes, geometry/force bits, and
all exact residual fields participate in replay identity.

The stream starts with ASCII `MLS-BOUNDED-OBSERVER-STREAM-v1\0`, followed by
unsigned 64-bit little-endian step-group and event counts. Each step group has
its own unsigned 64-bit event count followed by the ordered 32-byte event
digests. `whole_suffix_event_sha256` and `resumed_event_sha256` hash those
bytes. The resumed run retains the uninterrupted trajectory identifier,
absolute step numbers, precision/level, and original-trajectory invariant
baseline; equality therefore covers every framed field rather than a
context-free state-only projection. Counts, digests, ordered event lists,
post-step energy observations, and final canonical state must all agree.
The separately emitted audit rows for that same resumed arithmetic use the
unique `checkpoint:resumed:B<precision>:L<level>` identity and label their
initial checkpoint at the absolute checkpoint step. Only the observer-event
projection substitutes the uninterrupted `short:k4_internal:...` trajectory
identity required for suffix comparison. This explicit projection does not
duplicate arithmetic or alter any numerical field.

`state_size.csv` records precision, trajectory, lifecycle point, expected
component/phase/packet bytes, actual complete state bytes and hash, and derived
causal cache/history byte counts. Zero cache/history bytes are not trusted as
standalone CSV assertions. The source identified by `source_sha` must define
slots-only exact shapes

```text
State(precision,time_raw,packets)
Packet(identifier,mass_raw,x[3],p[3])
```

and metadata binds the exact `slots_only_v1` shape string and its SHA-256.
Runtime validation requires the exact `State` and `Packet` types, their exact
`__slots__` tuples, unique positive packet IDs, positive signed-64 masses,
three-component position and momentum vectors, and finite canonical MPFR
components at the state's registered precision. The only causal phase payload
is then the fixed wire state whose byte length and SHA-256 are measured at each
lifecycle point. Canonical decode/re-encode and interior checkpoint replay must
recover the same state and subsequent observer stream. Under that source-bound
shape and replay contract, `causal_cache_bytes=0` and
`causal_history_bytes=0` are derived conclusions; they are not evidence merely
because two integer cells contain zero. The registered complete packet sizes
for increasing `B` are `94,118,142,190,238` bytes.

## Independent verification and sealing

The independent verifier consumes canonical binary state and exported
binary64 bit patterns. It independently implements exact ties-to-even rounding,
reconstructs the complete operation graph, checks every local half-ULP error,
derives accumulated bounds before interpreting final residuals, reruns the
110-digit smooth ODE oracle, verifies parent positive controls, derives
precision and temporal convergence, and applies the frozen decision order.
Unbounded verifier integers and rationals are transient and never candidate
state.

The oracle schema is `mls.bounded-fractional-phase-state.oracle.v1`. Mutation
evidence must include deterministic positives and every class registered in
the preregistration, including altered parent/physics, precision/backend/
exponent/rounding, noncanonical state, hidden history, absolute-position
conversion, reordered or fused operations, false bounds/counts/scaling,
omitted observer state, false dynamics/conservation/frame/energy/domain/size/
replay results, changed budgets, and promotion relabeling.

`outer-seal.json` is canonical UTF-8 JSON. Its pre-hash is computed with
`outer_pre_hash` set to JSON null. The validator first checks inventory and
source identity, then raw twins, independent oracle, receipts, decision, and
no-promotion boundary. A negative or unresolved scientific decision is valid
evidence and may not be relabeled as retained dynamics.
