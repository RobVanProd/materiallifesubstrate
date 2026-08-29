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

`relations.csv`

```text
configuration_id,relation_index,relation_id,relation_kind,center_id,first_id,second_id,third_id,selection_status,selection_source,reference_value,reference_units,selection_score_m4
```

`operator_status.csv`

```text
operator_id,configuration_id,candidate,operator_role,observable_kind,build_status,packet_count,relation_count,row_count,column_count,raw_exported,operator_payload_sha256,row_normalization_complete,first_invalid_row,rank_applicable,b_rank_eligible,generic_solid_gate,decision_driving,promotion_eligible
```

`operator_entries.csv`

```text
operator_id,row_index,column_index,domain_kind,domain_id,velocity_component,row_kind,row_owner_id,row_component,value,units
```

`moment_diagnostics.csv`

```text
operator_id,packet_id,neighbor_count,m00_m2,m01_m2,m02_m2,m10_m2,m11_m2,m12_m2,m20_m2,m21_m2,m22_m2,symmetry_residual,smallest_eigenvalue_m2,largest_eigenvalue_m2,condition_number,condition_kind,inverse_residual_normalized,inverse_residual_tolerance,status,inverse_emitted
```

`affine_objectivity.csv`

```text
operator_id,test_id,test_kind,field,packet_id,relation_id,component,measured_value,target_value,absolute_error,normalization_scale,normalized_error,operation_count,roundoff_bound,pass,units
```

`invariance.csv`

```text
comparison_id,base_operator_id,transformed_operator_id,transform_kind,scale,lookup_phase,topology_match,relation_ids_match,rank_match,nullity_match,normalized_residual_delta,max_scaled_singular_value_delta,tolerance,canonical_bytes_match,pass
```

`rigid_basis.csv`

```text
operator_id,basis_kind,mode_index,dof_index,domain_kind,domain_id,velocity_component,value
```

`rank_status.csv`

```text
operator_id,record_kind,pivot_step,permuted_column_index,diagonal_magnitude,accepted_pivot,status,row_count,column_count,rank,nullity,rigid_rank,nonrigid_nullity,threshold,ambiguity_lower,ambiguity_upper,rank_ambiguous,rank_method,rank_is_certified,basis_complete,rigid_in_kernel,kernel_equals_rigid_subspace,normalized_rigid_residual,normalized_null_residual,normalized_nonrigid_residual,rigid_orthogonality_residual,residual_tolerance,generic_observability_pass,promotion_eligible
```

One `record_kind=summary` row is followed by the complete
`record_kind=pivot` trace.  Summary fields are identical on every row for the
same operator.

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

`exact_reference.csv`

```text
reference_id,configuration_id,candidate,operator_id,arithmetic,precision_digits,row_count,column_count,rank,nullity,rigid_rank,nonrigid_nullity,rigid_in_kernel,kernel_equals_rigid_span,source,pass,promotion_eligible
```

Relations include retained and deleted edges.  Only retained relations enter
an operator.  An edge uses `first_id,second_id`; a volume relation uses
`center_id,first_id,second_id,third_id`.  Candidate-A entries use
`domain_kind=grid_node`; packet-domain operators use `domain_kind=packet`.

The deletion-order preimage is the UTF-8 byte sequence
`260828|configuration_id|low_id|high_id`, with IDs in canonical decimal.

Each grouped payload digest begins with its ASCII domain followed by LF.  Each
emitted group row then contributes, in header order, NUL followed by the UTF-8
cell text for every field, followed by LF.  The four domains are
`MLS-MECHANICAL-OBSERVABILITY-PACKETS-v1`,
`MLS-MECHANICAL-OBSERVABILITY-NEIGHBORS-v1`,
`MLS-MECHANICAL-OBSERVABILITY-RELATIONS-v1`, and
`MLS-MECHANICAL-OBSERVABILITY-OPERATOR-v1`.  Groups are by configuration ID
for the first three and by operator ID for the last.

Candidate A uses transient quadratic-grid spacing equal to the configuration's
scaled `nominal_spacing_m`; its origin is the registered componentwise phase
times that spacing.  Exact-control packet IDs are one-based, so the
preregistered square index tuple `(0,1,2,3)` is emitted as packet-ID tuple
`(1,2,3,4)` without changing its geometry or orientation.

## Summary and manifest

`summary.json` has exactly these top-level members:

```text
schema,mode,producer,seed,source_sha,parent_sha,branch,dirty,
registered_configuration_ids,registered_operator_ids,
checkpoint_round_trip_all_pass,diagnostics_read_only_all_exact,
neighbor_lookup_all_agree,negative_control_reproduced,
affine_objectivity_all_pass,finite_objectivity_all_pass,
invariance_all_pass,decisive_rank_rows_all_unambiguous,
raw_decision_rows_all_exported,independent_reference_all_pass,
nondeterminism_detected,candidate_findings,decision,promotion,row_counts,
tolerances
```

The schema is `mls.mechanical-observability.summary.v1`, the producer is
`cpp_mechanical_observability_lab`, and promotion is always false.  Smoke
output is provisional and not sealable.  Candidate findings are keyed
exactly `A`, `B`, `C`, and `D`.  Overall decisions are limited to the four
outcomes frozen in the preregistration.

`manifest.json` has exactly `algorithm`, `files`, `pre_hash_sha256`, and
`schema`.  Its schema is `mls.mechanical-observability.manifest.v1`; it covers
the fifteen CSV files and `summary.json` using SHA-256.  This manifest and a
later outer seal are integrity records, not signatures.
