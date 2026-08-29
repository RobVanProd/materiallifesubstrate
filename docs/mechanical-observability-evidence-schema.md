# Mechanical Observability evidence wire contract

**Frozen before the final producer run:** 2026-08-29.  This file is the
producer/validator boundary.  It does not add a candidate or change a decision
rule in the preregistration.

All CSV files are UTF-8 with LF line endings, the exact header order below,
RFC-4180 quoting, and deterministic lexicographic row order.  Integers use
canonical decimal text, booleans are `true` or `false`, unavailable cells are
`NA`, and binary64 values use canonical lowercase C99 hexadecimal notation.
Zeros omitted from `operator_entries.csv` are exactly zero.

## Table headers

`configurations.csv`

```text
configuration_id,base_configuration_id,family,variant,profile,transform,lookup_phase,packet_count,nominal_spacing_m,support_radius_m,geometry_scale,affine_span_rank,connected,edge_count,edge_lower_bound,min_incident_direction_rank,rigid_generator_rank,generic_solid_gate,intentionally_flexible,decision_driving,packet_payload_sha256,neighbor_payload_sha256,relation_payload_sha256,input_checkpoint_sha256_before,input_checkpoint_sha256_after,diagnostics_read_only_exact
```

`packets.csv`

```text
configuration_id,packet_index,packet_id,mass_quanta,x_m,y_m,z_m,vx_m_per_s,vy_m_per_s,vz_m_per_s,jitter_dx_m,jitter_dy_m,jitter_dz_m
```

`neighbor_pairs.csv`

```text
configuration_id,lookup_phase,low_packet_id,high_packet_id,distance_squared_m2,support_radius_squared_m2,brute_force_eligible,lookup_eligible,agreement,weight
```

`grid_nodes.csv`

```text
sampling_operator_id,derivative_operator_id,configuration_id,lookup_phase,node_index,node_id,grid_i,grid_j,grid_k,x_m,y_m,z_m
```

`relations.csv`

```text
configuration_id,relation_index,relation_id,relation_kind,center_id,first_id,second_id,third_id,selection_status,selection_source,reference_value,reference_units,selection_score_m4
```

For every non-original registered configuration, the independent validator
reconstructs from `packets.csv` and `relations.csv` the affine rank,
connectivity, retained-edge count and lower bound, minimum incident-direction
rank, rigid-generator rank, generic-solid gate, and sorted canonical retained
relation IDs. Each value must equal the independently reconstructed value for
the registered base configuration. Producer configuration fields and
`invariance.csv` claims do not participate in that comparison. These are exact
topology equalities over emitted binary64 state; there is no comparison
tolerance.

`operator_status.csv`

```text
operator_id,configuration_id,candidate,operator_role,observable_kind,build_status,packet_count,relation_count,row_count,column_count,raw_exported,operator_payload_sha256,row_normalization_complete,first_invalid_row,rank_applicable,b_rank_eligible,generic_solid_gate,decision_driving,promotion_eligible,failure_stage,failure_reason,failure_witness_row,failure_witness_column,failure_witness_value,failure_witness_ieee754_bits,failure_witness_class
```

`operator_entries.csv`

```text
operator_id,row_index,column_index,domain_kind,domain_id,velocity_component,row_kind,row_owner_id,row_component,value,units
```

The seven operator failure fields use a closed convention. A successful built
row uses `NA` in all seven. A non-triggered D row uses
`not_attempted,global_d_not_triggered,NA,NA,NA,NA,none`. A B local-moment
failure uses stage `local_moment`, reason equal to its build status
(`singular_local_moment`, `ill_conditioned_local_moment`, or
`numerical_failure`), the first canonical failing packet ID as witness row,
`NA` column/value/bits, and class `moment_diagnostics`; the full witness is in
`moment_diagnostics.csv`. B then has no operator matrix, `raw_exported=false`,
and `rank_applicable=false`. Its `decision_driving` is true only when the
configuration independently has `generic_solid_gate=true`; lower-dimensional,
intentionally flexible, and exact validation controls retain the failure but
do not drive the scientific B decision. Candidate D is likewise
decision-driving only on independently generic-solid configurations when the
global D trigger is active; non-generic and exact enriched D operators are
diagnostic only. Every attempted Candidate C row remains decision-driving.

An attempted A/C/D row-normalization failure has
`build_status=numerical_failure`, stage `row_normalization`, and reason
`zero_row_norm` or `nonfinite_row_norm`. A zero row records its row index,
`NA` column, value `0x0.0p+0`, bits `0000000000000000`, and class
`finite_zero`. A nonfinite norm from a completely finite raw row records value
`NA`, the exact 16-digit lower-case IEEE-754 bits, and class
`positive_infinity`, `negative_infinity`, `quiet_nan`, or `signaling_nan`.
The complete finite pre-normalization sparse operator/digest/dimensions remain
exported, while rank is inapplicable. A and C failures remain decision-driving;
B and D use their generic-solid-only decision rule. A
nonfinite constructed cell instead uses stage `operator_construction`, reason
`nonfinite_operator_cell`, row and column, value `NA`, exact bits/class, and no
claim of complete raw export. It is valid negative evidence only when the
independent reference formula reproduces the same witness. Unsupported status
or witness combinations make the bundle invalid rather than a convenient
failure.

Candidate A is one attempted sampling/derivative pair. Its sampling status has
`rank_applicable=true` if and only if both the sampling operator and derivative
operator have `build_status=built`; its derivative status always has
`rank_applicable=false`. If either half fails construction or normalization,
neither half has rank, nullspace, or gauge rows. The successfully built half
still exports its complete raw operator, and the failed half retains its full
closed failure witness and any independently valid pre-normalization raw
operator. The incomplete pair forces `negative_control_reproduced=false`,
`decisive_rank_rows_all_unambiguous=false`, and the inconclusive implementation
STOP.

`moment_diagnostics.csv`

```text
operator_id,packet_id,neighbor_count,m00_m2,m01_m2,m02_m2,m10_m2,m11_m2,m12_m2,m20_m2,m21_m2,m22_m2,symmetry_residual,smallest_eigenvalue_m2,largest_eigenvalue_m2,condition_number,condition_kind,inverse_residual_normalized,inverse_residual_tolerance,status,inverse_emitted
```

Moment validation keeps the ideal-Decimal reconstruction and its frozen
`2e-12*max(1,lambda_max)` spectrum bound. It also interprets every emitted
binary64 moment cell as an exact Decimal, independently solves that `M64`, and
checks the emitted spectrum under the same bound. The emitted condition field
is the exact binary64 quotient of the emitted largest and smallest eigenvalue,
not a direct numerical-equality claim against the ideal-Decimal condition
number. The ideal-Decimal spectrum, high-precision `M64` spectrum, and emitted
estimate must agree on the frozen singular and `1e10` condition
classifications. Any disagreement is invalid. This is cross-arithmetic
classification validation; it changes no scientific threshold or registered
tolerance.

`affine_objectivity.csv`

```text
operator_id,test_id,test_kind,field,packet_id,relation_id,component,measured_value,target_value,absolute_error,normalization_scale,normalized_error,operation_count,roundoff_bound,pass,units
```

For `finite_bond_length`, `operation_count=72`; for
`finite_oriented_volume`, `operation_count=134`. Measured, target, and error
use the binary64 path in the subsystem contract. `normalization_scale` is the
dimensioned forward-error operand scale, not `max(1,...)` and not a
result-only relative scale. Let
`P_a(x)=|s|*((|Q_a0*x_0|+|Q_a1*x_1|)+|Q_a2*x_2|)+|t_a|`,
`R_a(p,c)=|x_p,a|+|x_c,a|`, and
`T_a(p,c)=P_a(x_p)+P_a(x_c)`, preserving the written binary64 grouping. A
bond emits
`max(minnormal, (((|s|*((R_x+R_y)+R_z))+((T_x+T_y)+T_z))`
`+|measured|)+|target|))`. Define
`E(a,b,c)=((a_x*(b_y*c_z+b_z*c_y)+a_y*(b_x*c_z+b_z*c_x))`
`+a_z*(b_x*c_y+b_y*c_x))`. A volume emits
`max(minnormal, (((((|s|*|s|)*|s|)*E(R1,R2,R3))`
`+E(T1,T2,T3))+|measured|)+|target|))`. The scale has units `m` or `m3`.
`normalized_error=absolute_error/normalization_scale`, and
`roundoff_bound=256*gamma(operation_count)*normalization_scale`
`+256*minnormal`. These cells cover only the five registered transforms.

The affine aggregate for B remains `affine:<field>:aggregate`, component
`ALL`, units `per_s`; C remains the same ID/component with units `m_per_s`.
D never emits a mixed-dimension aggregate. For every field it emits
`affine:<field>:bond_aggregate`, component `BOND_ALL`, units `m_per_s`, and,
when volume rows exist, `affine:<field>:volume_aggregate`, component
`VOLUME_ALL`, units `m3_per_s`. Each row uses only its homogeneous operator
block, measured values, target values, Frobenius norm, and row count to derive
its independent normalization, tolerance, and pass. Either D block failing
fails the affine contract.

`invariance.csv`

```text
comparison_id,base_operator_id,transformed_operator_id,transform_kind,scale,lookup_phase,topology_match,relation_ids_match,rank_match,nullity_match,base_build_status,transformed_build_status,build_status_match,metrics_available,normalized_residual_delta,max_scaled_singular_value_delta,tolerance,canonical_bytes_match,pass
```

For a metamorphic B/C/D comparison, `rank_match` and `nullity_match` are exact
and both linked rank summaries must be unambiguous. Singular values are sorted
descending, and `max_scaled_singular_value_delta` is the maximum of
`abs(s1[i]-s2[i])/max(s1[i],s2[i],1)` over every index below that common rank
(zero for common rank zero). Values in the numerical null tail are not folded
into this magnitude. They remain decision-driving through exact rank/nullity
agreement and the independently checked complete-nullspace evidence. A pass
also requires both the resolved-spectrum delta and normalized-residual delta
to be at most the unchanged invariance tolerance
`16384*max(m,n)*epsilon64`.

Every registered base/variant B/C/D pair and every attempted C lookup-phase
self-comparison has an invariance row even when an operator is unavailable.
`metrics_available=true` only when both operators
are built, both ranks are analyzed/unambiguous, and dimensions are comparable.
Otherwise rank/nullity matches are false, numerical metrics and tolerance are
`NA`, and canonical bytes are false. Such a row may pass only as closed status
parity: both operators are unavailable and their independently derived build
status and complete failure tuple (stage, reason, row, column, value, bits,
and class) match. Mandatory decision-driving unavailability (all attempted C,
generic B, and triggered generic D) still forces `invariance_all_pass=false`
and the overall lab stop even when its status-parity row itself passes.

`rigid_basis.csv`

```text
operator_id,basis_kind,mode_index,dof_index,domain_kind,domain_id,velocity_component,value
```

`rank_status.csv`

```text
operator_id,record_kind,pivot_step,permuted_column_index,diagonal_magnitude,accepted_pivot,status,row_count,column_count,rank,nullity,rigid_rank,nonrigid_nullity,threshold,ambiguity_lower,ambiguity_upper,rank_ambiguous,rank_method,rank_is_certified,basis_complete,rigid_in_kernel,kernel_equals_rigid_subspace,normalized_rigid_residual,normalized_null_residual,normalized_nonrigid_residual,rigid_orthogonality_residual,residual_tolerance,generic_observability_pass,promotion_eligible,failure_stage,failure_reason
```

One `record_kind=summary` row is followed by the complete
`record_kind=pivot` trace.  Summary fields are identical on every row for the
same operator.

The independent QRCP audit replays the complete claimed permutation before it
derives the frozen threshold and ambiguity limits from the first diagonal. It
enforces maximal/tied pivot selection while the independently measured suffix
norm is at or above `ambiguity_lower`; below that already registered limit, pivot
ordering is unresolved but the claimed path and every diagonal are still
replayed. Structural-zero suffixes cannot be permuted. A separate greedy QRCP
factorization must match the claimed path's rank-at-lower, rank-at-upper, and
ambiguity classification. This is a cross-arithmetic trace-classification
rule, not a new rank tolerance or a relaxation of basis/residual gates.

The rank-status state machine is closed. `status=analyzed` requires
`failure_stage=failure_reason=NA`. `status=ambiguous` requires
`rank_estimation,ambiguity_band_overlap`, has `basis_complete=false`, retains
the complete pivot trace and only the raw rigid generators (none for A), and
leaves rigid/kernel/residual/orthogonality/generic cells `NA`.
`status=numerical_failure` requires `failure_stage=basis_construction` with
reason exactly `incomplete_kernel`,
`rigid_span_failure`, `nonrigid_quotient_failure`, or `nonfinite_basis`.
Whenever rank factorization ran, the pivot trace remains complete. A basis
failure exports the complete raw rigid generators but no orthonormal rigid,
kernel, non-rigid, or per-mode metric rows; its `basis_complete=false`, and
the unevaluated rigid/kernel/residual/generic-pass summary cells are `NA`.
When a completed basis instead measures rigid visibility, status remains
`analyzed`: `rigid_in_kernel=false`, `nonrigid_nullity=NA`,
`kernel_equals_rigid_subspace=false`, and generic pass is false. Complete
kernel modes/metrics remain, while non-rigid quotient modes/metrics and their
residual fields are omitted/`NA` because the quotient is undefined.

`nullspace_modes.csv`

```text
operator_id,basis_kind,mode_index,dof_index,domain_kind,domain_id,velocity_component,value
```

`nullspace_metrics.csv`

```text
operator_id,basis_kind,mode_index,operator_image_l2,operator_denominator,normalized_operator_residual,rigid_projection_l2,rigid_orthogonality_residual,roundoff_bound,pass,promotion_eligible
```

`grid_gauge.csv`

```text
operator_id,sampling_operator_id,derivative_operator_id,mode_index,representative_component,sampling_residual_normalized,derivative_max_per_s,derivative_rms_per_s,derivative_roundoff_bound_per_s,visibility_ratio,gradient_visible,accepted,pass,promotion_eligible
```

Candidate A passes only with a nonempty emitted gauge basis and `pass=true` on
every row for every registered phase. Even after both A operators build, gauge
rows exist only when the sampling rank is independently `analyzed`,
unambiguous, and basis-complete. An ambiguous or numerical-failure sampling
rank emits its closed pivot/failure evidence but no grid-gauge rows, makes the
negative control false, clears the decisive-rank gate, and forces STOP.
Candidate B/C/D rank aggregation applies only to decision-driving rows and
requires analyzed unambiguous rank, complete basis, rigid containment, all
four aggregate residuals within the registered bound, and `pass=true` on every
applicable complete-kernel and non-rigid metric row.
`decisive_rank_rows_all_unambiguous` also includes the independent exact-
reference agreement; the latter remains separately reported rather than being
hidden inside the aggregate.

`exact_reference.csv`

```text
reference_id,configuration_id,candidate,operator_id,arithmetic,precision_digits,row_count,column_count,rank,nullity,rigid_rank,nonrigid_nullity,rigid_in_kernel,kernel_equals_rigid_span,source,pass,promotion_eligible
```

`checkpoints.csv`

```text
configuration_id,checkpoint_kind,encoding,byte_count,payload_sha256,payload_hex
```

`permutation_controls.csv`

```text
control_id,operator_id,configuration_id,permutation_kind,permutation_seed,packet_order,relation_order,row_count,column_count,entry_count,raw_payload_sha256,raw_dense_payload_sha256,canonical_payload_sha256,baseline_payload_sha256,canonical_bytes_match,promotion_eligible
```

`permutation_entries.csv`

```text
control_id,operator_id,row_index,column_index,domain_kind,domain_id,velocity_component,row_kind,row_owner_id,row_component,value,units
```

Relations include retained and deleted edges.  Only retained relations enter
an operator.  An edge uses `first_id,second_id`; a volume relation uses
`center_id,first_id,second_id,third_id`.  Candidate-A entries use
`domain_kind=grid_node`; packet-domain operators use `domain_kind=packet`.

The deletion-order preimage is the UTF-8 byte sequence
`260828|configuration_id|low_id|high_id`, with IDs in canonical decimal.

Each grouped payload digest begins with its ASCII domain followed by LF.  Each
emitted group row then contributes, in header order, NUL followed by the UTF-8
cell text for every field, followed by LF.  The five domains are
`MLS-MECHANICAL-OBSERVABILITY-PACKETS-v1`,
`MLS-MECHANICAL-OBSERVABILITY-NEIGHBORS-v1`,
`MLS-MECHANICAL-OBSERVABILITY-RELATIONS-v1`, and
`MLS-MECHANICAL-OBSERVABILITY-OPERATOR-v1`, plus
`MLS-MECHANICAL-OBSERVABILITY-PERMUTATION-OPERATOR-v2`. Groups are by
configuration ID for the first three, by operator ID for the primary
operator, and by control ID for the permutation operator.

An operator with `raw_exported=false` has
`operator_payload_sha256=NA` and no `operator_entries.csv` rows. There is no
empty-group digest. A built/decision-driving B/C/D row must instead export its
complete nonzero primary operator.

Candidate A uses transient quadratic-grid spacing equal to the configuration's
scaled `nominal_spacing_m`; its origin is the registered componentwise phase
times that spacing.  Exact-control packet IDs are one-based, so the
preregistered square index tuple `(0,1,2,3)` is emitted as packet-ID tuple
`(1,2,3,4)` without changing its geometry or orientation.

For candidate A, `grid_gauge.operator_id` equals `sampling_operator_id`; there
is no synthetic gauge operator. Node IDs are `node_index+1` and are scoped to
one sampling/derivative operator pair. The complete scalar sampling-null basis
is lifted into all three velocity components and exported in
`nullspace_modes.csv`. Both the sampling and derivative matrices are exported
in full. The validator rebuilds both matrices from packet and grid-node
geometry before accepting a gauge counterexample.

Each configuration has exactly three canonical `MLSMOBS1` version-1
little-endian checkpoint rows, sorted in this closed kind order:
`authoritative_before`, `round_trip_reserialized`, `after_diagnostics`. Every
row independently binds its lower-case hex bytes, byte count, and SHA-256; the
validator parses and canonically reserializes each payload. Packet, relation,
and configuration semantic input tables bind `authoritative_before`.
`input_checkpoint_sha256_before` binds that row and
`input_checkpoint_sha256_after` binds `after_diagnostics`.
`checkpoint_round_trip_all_pass` is derived from byte equality of the before
and reserialized rows; `diagnostics_read_only_all_exact` is derived from byte
equality of before and after. A structurally valid canonical mismatch is
preserved as negative evidence and forces a stop. A malformed, noncanonical,
missing, or extra checkpoint row makes the bundle invalid.

The D inventory is global and exact. The exact enriched-square D operator is
always built. Otherwise, the validator derives the trigger from independently
ranked `generic_solid_gate=true` C rows. Every such non-exact C must first have
a built/normalized operator, analyzed unambiguous rank, complete accepted null
basis, rigid containment, resolved quotient, and all registered residual gates
passing. Any invalid generic C blocks D and forces the implementation stop.
With no accepted resolved generic C non-rigid mode, every non-exact D status is
`not_triggered` and no non-exact volume tuple is present. If an accepted
generic C row triggers D, every non-exact configuration
inherits the selector result frozen on its original/base geometry, and every
metamorphic variant retains those physical relation IDs. D is built exactly
when that selected tuple set is nonempty; an empty set remains
`not_triggered`. Non-generic D rows are diagnostic only. The final scientific
decision ranges over the complete generic D inventory.

Every built B/C/D operator has exactly one permutation control, with
`control_id=permutation.<operator_id>` and the same identifier in
`invariance.csv`. `permutation_kind` is exactly
`sha256_packet_relation_permutation_v2` and `permutation_seed` is `260828`.
The packet permutation is derived per configuration. For every
canonical packet ID, hash the exact UTF-8 ASCII preimage
`260828|packet_permutation|<configuration_id>|<packet_id>`, sort ascending by
`(SHA-256 digest bytes, packet_id)`, and, only if this is still the canonical
ascending order and there is more than one packet, rotate the result left by
one. `packet_order` joins the resulting canonical-decimal IDs with `:`.
Identity packet evidence is invalid for a multi-packet configuration.

For C and D, independently hash every relevant retained canonical relation ID
using the exact UTF-8 ASCII preimage
`260828|relation_permutation|<configuration_id>|<candidate>|<relation_id>`,
sort by `(SHA-256 digest bytes, relation_id)`, and rotate left once if the
result is still the canonical relation order and there is more than one
relation. `relation_order` joins those IDs with `:`. It is `NA` for B.
Identity relation evidence is invalid when more than one relation exists.

The producer rebuilds the operator from packets supplied in the actual packet
order, then exports an order-sensitive raw storage layout. B rows are
`packet_order` blocks of six and its columns are `packet_order` blocks of
three. C/D rows follow `relation_order`, and their columns follow
`packet_order` blocks of three. In every `permutation_entries.csv` row,
`row_index` and `column_index` are these raw storage indices, while
`row_owner_id`, `domain_id`, and components bind each block to its semantic
identity. Every nonzero raw entry is exported. A copied canonical primary
matrix interpreted under these raw mappings is invalid.

`raw_payload_sha256` is the grouped-entry digest above.
`raw_dense_payload_sha256` hashes ASCII
`MLS-MECHANICAL-OBSERVABILITY-RAW-PERMUTED-OPERATOR-v2` followed by LF,
little-endian uint64 row and column counts, then every raw row-major IEEE-754
binary64 bit pattern as little-endian uint64, including zeros. Every numerical
zero is encoded as positive zero because sparse entries do not bind a signed
zero. The independent
validator derives packet/relation orders, rebuilds this raw matrix and both
raw hashes, then canonicalizes through the exported semantic mappings rather
than accepting the producer's equality flag.

For the two canonical matrix hashes, semantic packet and relation identities
first restore canonical row and column order. The byte payload is ASCII
`MLS-MECHANICAL-OBSERVABILITY-CANONICAL-OPERATOR-v1` followed by LF, then
little-endian uint64 row count and column count, then every row-major IEEE-754
binary64 bit pattern as little-endian uint64. Positive zero is canonical.
`canonical_payload_sha256` binds the alternate run and
`baseline_payload_sha256` binds the primary operator; they must match exactly.

## Summary and manifest

`summary.json` has exactly these top-level members:

```text
schema,mode,provisional,sweep_complete,producer,seed,source_sha,parent_sha,branch,dirty,
registered_configuration_ids,registered_operator_ids,
checkpoint_round_trip_all_pass,diagnostics_read_only_all_exact,
neighbor_lookup_all_agree,negative_control_reproduced,
affine_objectivity_all_pass,finite_objectivity_all_pass,
invariance_all_pass,decisive_rank_rows_all_unambiguous,
raw_decision_rows_all_exported,independent_reference_all_pass,
nondeterminism_detected,candidate_findings,decision,promotion,row_counts,
tolerances
```

The schema is `mls.mechanical-observability.summary.v2`, the producer is
`cpp_mechanical_observability_lab`, and promotion is always false. The closed
mode/flag tuples are `full,false,true`, `smoke,true,false`, and
`failure_fixture,true,false` for `mode,provisional,sweep_complete`. Only full
output is sealable. The validation-only smoke subset is
exactly `base.filament.r205.original`,
`base.filament.r205.original.translation`, and
`exact.planar_square_plus_diagonal_and_volume`. It is a compact positive wire
fixture that exercises the A gauge, a genuine metamorphic comparison,
built-D/non-rigid quotient, checkpoint, and exact-reference paths without
changing the full 59-configuration experiment. The filament `.rotation`
variant remains mandatory in the full matrix; smoke exclusion neither hides
nor reclassifies its result. Candidate findings are keyed exactly `A`, `B`,
`C`, and `D`. Overall decisions are limited to the four outcomes frozen in the
preregistration.

The diagnostic-only command
`--a-pair-failure-fixture {sampling,derivative} --output DIR` uses that same
three-configuration inventory and cannot be combined with `--smoke`, a full
run, or either audit action. It replaces exactly one finite pre-normalization
matrix with zeros: `base.filament.r205.original.A.p000.S` for `sampling` or
the corresponding `.D` operator for `derivative`. The other half remains the
ordinary built/raw operator, the `p037_011_029` pair is unchanged, and no
other subsystem is altered. This authentic failure-wire fixture is permanently
unsealable and may be used only for validator regression; it cannot support a
scientific candidate outcome.

`manifest.json` has exactly `algorithm`, `files`, `pre_hash_sha256`, and
`schema`.  Its schema is `mls.mechanical-observability.manifest.v1`; it covers
the nineteen CSV files and `summary.json` using SHA-256.  This manifest and a
later outer seal are integrity records, not signatures.

## Canonical validator findings

The independent validator can emit
`results/mechanical-observability-findings.json` with schema
`mls.mechanical-observability.validator-findings.v1`. Its canonical document
encoding is UTF-8 JSON produced with `ensure_ascii=false`, `sort_keys=true`,
indent 2, and exactly one final LF. Floats, duplicate members, nonstandard JSON
constants, CRLF, compact formatting, a missing final LF, and extra members are
invalid. Because object keys are sorted, the exact top-level wire order is:

```text
bundle_structural_valid,candidate_findings,claim_mismatches,
comparison_status,decision,derived_gates,first_manifest_pre_hash,mismatches,
mode,producer_claims_sha256,promotion,result_sha256_before_hash_field,schema,
second_manifest_pre_hash,source_sha,validator_sha256
```

The fields and closed types are:

- `bundle_structural_valid`: an array of one or two Booleans, matching bundle
  cardinality. An outer seal requires exactly `[true,true]`.
- `candidate_findings`: exactly the four string members `A`, `B`, `C`, and
  `D`, in that canonical order. The closed values are:
  - A: `negative_control_reproduced` or `negative_control_failed`;
  - B: `reject_averaged_single_gradient_packet_kinematics`,
    `no_resolved_eligible_nonrigid_mode`, or `inconclusive`;
  - C: `retain_central_relational_representation_for_research`,
    `generic_nonrigid_mode_triggers_d`, or `inconclusive`;
  - D: `not_triggered`,
    `retain_volume_enriched_relational_representation_for_research`,
    `stop_reconsider_packet_abstraction`, or `inconclusive`.
- `claim_mismatches`: a sorted, unique array of closed claim identifiers.
- `comparison_status`: `single`, `byte_identical`, or `nondeterministic`.
  Outer sealing permits only the two-bundle latter two values.
- `decision`: exactly one of
  `retain_central_relational_representation_for_research`,
  `retain_volume_enriched_relational_representation_for_research`,
  `stop_inconclusive_or_implementation_failure`, or
  `stop_reconsider_packet_abstraction`.
- `derived_gates`: the exact Boolean object listed below.
- `first_manifest_pre_hash`: lowercase 64-hex SHA-256.
- `mismatches`: a path-sorted array of exact objects
  `{first_sha256,path,second_sha256}` in canonical key order. Each digest is
  lowercase 64-hex and the two digests differ. A path must be one of the
  manifest-bound nineteen CSVs, `summary.json`, or `manifest.json`; both
  compared inventories must otherwise be identical.
- `mode`: `smoke`, `failure_fixture`, or `full`; an outer seal requires
  `full`.
- `producer_claims_sha256`: lowercase 64-hex SHA-256.
- `promotion`: the Boolean `false` only.
- `result_sha256_before_hash_field`: lowercase 64-hex SHA-256.
- `schema`: the findings schema literal above.
- `second_manifest_pre_hash`: lowercase 64-hex for a comparison and JSON
  `null` only for a single-bundle finding. An outer seal requires a digest.
- `source_sha`: exactly 40 lowercase hexadecimal characters.
- `validator_sha256`: lowercase 64-hex SHA-256 of the exact validator bytes.

The exact canonical `derived_gates` key order is:

```text
affine_objectivity_all_pass,
checkpoint_round_trip_all_pass,
decisive_rank_rows_all_unambiguous,
deterministic_repeatability,
diagnostics_read_only_all_exact,
finite_objectivity_all_pass,
independent_basis_agreement,
independent_reference_all_pass,
invariance_all_pass,
negative_control_reproduced,
neighbor_lookup_all_agree,
producer_claims_consistent,
raw_decision_rows_all_exported
```

Every value is Boolean. The first/second per-bundle gates are combined by
logical AND. `deterministic_repeatability` additionally requires an empty byte-
mismatch inventory. `producer_claims_consistent` is true exactly when
`claim_mismatches` is empty. `independent_basis_agreement` is false when a
well-formed producer basis/rank construction outcome disagrees with the
independent reconstruction; such disagreement is retained as an
implementation/oracle failure and forces STOP. It does not turn malformed
producer failure evidence into valid evidence.

The closed claim mismatch identifiers are
`comparison.nondeterminism_detected` and `first.<claim>` or `second.<claim>`,
where `<claim>` is one of the ten producer summary contract Booleans,
`candidate_findings`, `decision`, or the validator-only disagreement token
`independent_basis_agreement`:

```text
checkpoint_round_trip_all_pass,diagnostics_read_only_all_exact,
neighbor_lookup_all_agree,negative_control_reproduced,
affine_objectivity_all_pass,finite_objectivity_all_pass,invariance_all_pass,
decisive_rank_rows_all_unambiguous,raw_decision_rows_all_exported,
independent_reference_all_pass,candidate_findings,decision
```

`independent_basis_agreement` is not a producer-summary member. The validator
adds `first.independent_basis_agreement` and/or
`second.independent_basis_agreement` when its reconstruction disagrees with a
well-formed producer basis outcome. That token makes
`producer_claims_consistent=false` as an explicit cross-implementation claim
disagreement, also clears the decisive-rank gate, and forces the canonical
inconclusive STOP quarantine.

The array is sorted and unique. A byte-identical comparison that claims
nondeterminism is invalid; differing bundles require the exact path/digest
inventory and make deterministic repeatability false.

`producer_claims_sha256` is SHA-256 over compact canonical UTF-8 JSON of the
ordered complete producer summaries `[first]` or `[first,second]`, after
removing validator-private keys. Compact canonical JSON means
`ensure_ascii=false`, `sort_keys=true`, separators `,` and `:`, and no final
LF or domain prefix. `result_sha256_before_hash_field` uses the same compact
encoding and raw SHA-256 over the complete findings object before that field
is inserted. The pretty findings document itself is separately bound by its
file SHA-256.

The validator accepts `--validator-sha256 <lowercase64>` and emits that pin
verbatim after executing those exact bytes; without the option it hashes its
own file. The frozen release-validator SHA-256 is
`6fc972fb9510a6ee2d50a475f0978a9b1ce4d944d918f59eabbbd7e811bba7a7`.
The outer seal always supplies and rechecks that exact pin. A valid claim
disagreement, byte divergence, or failed derived gate is evidence and produces
no promotion; malformed structure, noncanonical bytes, invalid provenance, an
incomplete mismatch inventory, or an unsupported failure tuple is INVALID
rather than a preserved negative.

### Basis-construction disagreement

A producer `basis_construction` failure remains structurally valid only with
the closed rank status, reason, pivot trace, basis suppression, nullable cells,
and raw-generator evidence defined above. If the independent reconstruction
successfully resolves that same operator, `independent_basis_agreement=false`
and the outcome is `stop_inconclusive_or_implementation_failure`; a preferred
independent basis is not silently substituted into producer evidence. If the
independent reconstruction also fails in agreement with the producer's valid
failure, agreement may be true, but the incomplete producer basis still makes
the decisive-rank gate false and forces STOP. A missing pivot,
fabricated/partial basis, impossible reason, malformed nullable cell, or other
failure-witness inconsistency is INVALID and cannot use this disagreement
route.

## Outer evidence seal v3

`outer-manifest.json` uses schema
`mls.mechanical-observability.outer-evidence-seal.v3`. The outer manifest,
`metadata.json`, `ci/metadata.json`, both inner manifests, and validator
findings use the same pretty canonical UTF-8/LF document encoding above.
Other captured files, including producer summaries, remain opaque bytes bound
by size and SHA-256 rather than being rewritten by the sealer. The outer
manifest's exact canonical key order is:

```text
algorithm,claim_scope,files,metadata_path,pinned_validator_sha256,
pre_hash_sha256,schema,validator_findings
```

`algorithm` is `SHA-256`; `claim_scope` is
`integrity_and_independent_local_semantic_validation_only`; `metadata_path` is
`metadata.json`; and `pinned_validator_sha256` is the frozen lowercase digest
of the validator bytes. `files` is the complete path-sorted regular-file
inventory below the seal root excluding `outer-manifest.json`. Each record has
exact canonical keys `{path,sha256,size}`: a portable relative path, lowercase
SHA-256, and nonnegative JSON integer byte count. Missing, extra, duplicate,
case-colliding, linked, oversized, or digest/size-mismatched files are invalid.

The outer `pre_hash_sha256` is raw SHA-256 of compact canonical UTF-8 JSON for
the exact outer payload with every outer member except
`pre_hash_sha256`; there is no LF or domain prefix in this preimage. The outer
`validator_findings` value is the exact ten-member binding below and must be
identical to the binding in `metadata.json` and to a fresh isolated execution
of the pinned validator:

```text
binding_kind,comparison_status,decision,evidence_route,findings_path,
findings_sha256,promotion,result_sha256_before_hash_field,
validator_log_path,validator_log_sha256
```

The literals are `binding_kind=fresh_pinned_validator_replay`,
`findings_path=results/mechanical-observability-findings.json`,
`validator_log_path=logs/full-bundle-validator.log`, and `promotion=false`.
`comparison_status` is `byte_identical` or `nondeterministic`;
`evidence_route` is `deterministic_success` or `preserved_negative`; `decision`
uses the closed four-value enum; and all three hash fields are lowercase
64-hex. Captured findings and validator stdout must match fresh pinned replay
byte-for-byte and by digest.

Pinned replay runs the frozen validator bytes through isolated Python with
`-I -S -B -X utf8`, the validator program supplied on standard input, bounded
temporary paths, and `--bundle`, `--compare`, `--findings-output`, and
`--validator-sha256`. Standard error must be empty and standard output is
UTF-8/LF with exactly two lines: the first begins
`MECHANICAL OBSERVABILITY BUNDLE VALID:` and the second is exactly
`findings_sha256=<captured-findings-file-sha256>`.

`metadata.json` uses schema
`mls.mechanical-observability.outer-evidence-metadata.v3` with exact canonical
top-level keys:

```text
captured_external_ci,commands,local,schema,seal_claim_scope,source,
validator_findings
```

`seal_claim_scope` repeats the outer claim-scope literal. `source` has exact
keys `authentication_status,branch,claim_kind,repository_url,sha,tag,
tag_target_sha`; its claim kind is `captured_external_git_metadata`, its
authentication status is `not_authenticated_by_offline_seal`, its branch and
SHA match both bundles, its tag resolves to that SHA, and its repository is
`https://github.com/RobVanProd/materiallifesubstrate`.

`commands` is a nonempty array of exact `{argv,cwd,name}` objects with unique
names. It covers `full_bundle_a`, `full_bundle_b`,
`bundle_compare_validator`, `configure`, `build`, `ctest`, `exact_oracle`,
`validator_mutation`, `lean_build`, `lean_axiom_report`, `source_scan`, and
`git_provenance`. The validator command names `--bundle`, `--compare`,
`--findings-output`, and `--validator-sha256` exactly once and binds the frozen
pin and findings path.

`local` has exact keys `authentication_status,claim_kind,execution_context,
result_summaries,tool_versions`. Its literals are
`captured_local_execution_metadata`, `not_authenticated_by_offline_seal`, and
`local`. Tool versions include at least Python, CMake, CTest, C++, Git, Lean,
and Lake. Every required command has one result summary with exact keys
`evidence_paths,exit_code,status,summary`; required release results are
`status=pass`, `exit_code=0`, and bind their nonempty logs/results.
`captured_external_ci` has exact keys
`authentication_status,claim_kind,metadata_path`, points to
`ci/metadata.json`, and remains explicitly unauthenticated by the offline
seal. That CI document uses schema
`mls.mechanical-observability.captured-external-ci-metadata.v1`, binds the
repository, branch, head SHA, run ID/URL/conclusion and required GCC, Clang,
MSVC, Python-oracle and Lean job identities/results. `validator_findings` is
the exact replay binding above.

The CI document's exact canonical key order is:

```text
authentication_status,claim_kind,conclusion,head_branch,head_sha,jobs,
repository_url,run_id,run_url,schema
```

`run_id` is a positive JSON integer;
the SHA/branch/repository and derived run URL match the outer source; conclusion
is `success`. Each job has exact canonical keys
`conclusion,database_id,id,name,url`, a positive integer `database_id`, unique
ID/name, URL below the declared run, and `success`. JSON arrays, including
commands, evidence paths, jobs, and mismatch records, retain their declared
order; only the file and mismatch inventories have an additional required
path sort.

### Evidence routes

`deterministic_success` is available only when both full bundles are byte-
identical, claim mismatches are empty, every derived gate is true, and the
decision is one of the two `retain_*_for_research` outcomes. This remains a
NO-PROMOTION research-direction result.

Every other structurally valid outcome uses `preserved_negative`. Byte-
identical evidence with a failed gate therefore remains a preserved negative;
it is not mislabeled deterministic success. A conclusive, byte-identical
`stop_reconsider_packet_abstraction` also uses `preserved_negative` while
retaining its meaningful candidate findings. Differing bundles may be sealed
only when both validate independently, their exact mismatch inventory is
complete, and fresh findings quarantine the result as
`stop_inconclusive_or_implementation_failure`, B/C/D `inconclusive`, and
`promotion=false`. Claim mismatch or a failed derived gate uses the same
inconclusive STOP quarantine. Structurally malformed divergence is INVALID and
cannot be preserved. The outer seal is an integrity and fresh local semantic-
validation record, not a signature and not authentication of captured GitHub,
Git, command, tool, or CI metadata.
