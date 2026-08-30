# Relational Observability evidence schema

**Schema version:** `v1`  
**Candidate:** central-distance relational representation (Candidate C only)  
**Claim boundary:** every verdict is `NO PROMOTION` to mechanics.

The producer emits canonical UTF-8 CSV with LF line endings, hexadecimal
binary64 values, lowercase SHA-256 digests, canonical ascending configuration/
packet/relation order, and legacy input-only checkpoint bytes. The independent
validator rejects missing, duplicate, reordered, noncanonical, or unexpected
fields.

## Files

| File | Role |
|---|---|
| `configurations.csv` | complete inherited and derived configuration inventory |
| `packets.csv` | all packet IDs, exact mass quanta, positions, and zero/test velocities |
| `relations.csv` | complete Candidate-C edge topology and raw-row norm gates |
| `observability.csv` | CPQR/SVD/rank/nullity/rigid quotient and margin summary |
| `spectra.csv` | every singular value, including explicit zero tail to `3N` |
| `nullspace.csv` | residual, partition, and acceptance result for every CPQR kernel-vector candidate |
| `nullspace_vectors.csv` | every binary64 component of every CPQR kernel-vector candidate |
| `metamorphic.csv` | operator, spectrum, finite bond-length, ordering, and ID-renaming equivalence controls |
| `id_bijections.csv` | complete old/new/inverse label mappings |
| `topology_path.csv` | every one-edge deletion state, rank-reference certification, and fixed transition markers |
| `lookup.csv` | brute-force versus lookup-grid edge enumeration |
| `checkpoints.csv` | byte hashes for original, round-tripped, and post-diagnostic state |
| `checkpoints/*.bin` | canonical `MLSMOBS1` v1 state with packets, bonds, and zero volumes |
| `tolerances.json` | frozen arithmetic constants, probes, and decision order |
| `summary.json` | source provenance, counts, gate totals, verdict, and no-promotion boundary |
| `manifest.json` | exact inventory, per-file hashes, row counts, and bundle pre-hash |

Candidate-B matrices/results and Candidate-D volume relations/results are not
valid files or columns in this schema.

`nullspace_vectors.csv` is ordered by ascending configuration ID, mode index,
canonical packet ID, and axis order `x,y,z`. `component_index` is exactly
`3*packet_index+axis_index`, and `value` is the canonical hexadecimal binary64
component. Each `(configuration_id,mode_index)` has exactly `3N` rows. The
corresponding `nullspace.csv.vector_sha256` is SHA-256 over those components'
raw binary64 bit patterns serialized in component-index order as little-endian
unsigned 64-bit words. This makes every claimed kernel residual, rigid
projection, orthogonality result, and vector hash independently recomputable.

`source_configuration_id` is semantic lineage. An inherited identity row
points to itself; an inherited translation/rotation/scale row points to its
accepted identity base. Every derived perturbation, deformation, deletion, or
ID-bijection row likewise points to the inherited configuration from which its
physical state was constructed.

`metamorphic.csv.finite_length_scale` is the registered expected multiplicative
change in every central-distance observable. Its residual compares actual and
expected finite bond lengths after semantic edge canonicalization. It is one
for objectivity and label/order controls, one-half/two for the registered
similarity scale controls, and participates in `pass` at the same recorded
roundoff tolerance as the corresponding operator/spectrum comparison.

`topology_path.csv.rank_reference_kind` is exactly one of
`exact_fraction_rref`,
`modular_lower_bound_matches_structural_upper_bound`, or
`modular_lower_bound`. `rank_certified=true` is permitted only for the first
two kinds. The full registered transition labels are fixed at deletion steps
52, 53, 54, 55, and 158; smoke transition labels are all `none`.

## Numeric encoding

Finite binary64 values use C/Python hexadecimal form. `NA` is allowed only for
registered inapplicable probe metadata. Positive infinity is allowed only for
`null_threshold_separation` when the largest resolved numerical zero is
exactly zero. NaN and all other infinities are forbidden.

`spectra.csv` contains exactly `3N` rows per configuration. A direct SVD of a
wide matrix returns only `min(rows,columns)` values; the remaining structural
tail is emitted as exact zero with the same `resolved_zero` classification as
any other value below the frozen lower threshold. No separate wire literal may
make structural zeros bypass the numerical classification gate.

## Checkpoint binding

For configuration ID `c`, the file is `checkpoints/c.bin`. IDs may contain only
the schema's safe identifier characters and never a path separator. The
checkpoint is the existing canonical little-endian Mechanical Observability
input format, magic `MLSMOBS1`, version one. It contains the support radius,
canonical packet state, canonical bond topology, and an empty volume list.
Operator matrices, rank factorizations, spectra, null modes, lookup cells,
and verdicts are excluded.

The before hash is the original serialization. The round-trip hash is
`serialize(deserialize(before))`. The after hash serializes the same
authoritative state after all diagnostics. All bytes and all three hashes must
be identical.

## Nested hashes

The `summary.json` pre-hash is SHA-256 of UTF-8 lines, sorted by relative POSIX
filename:

```
filename=lowercase_sha256\n
...
verdict=exact_verdict_literal\n
```

It covers every payload except `summary.json` and `manifest.json`. The manifest
pre-hash uses the same sorted-line construction over every payload except
`manifest.json`, so it also binds the completed summary. The outer evidence
seal separately snapshots source, full twin bundles, local/CI logs, and
provenance, then hashes its complete inventory.

## Decision vocabulary

The only verdict literals, in evaluation order, are:

1. `stop_inconclusive_or_implementation_failure`
2. `reject_central_relational_representation`
3. `retain_only_as_mathematically_rigid_numerically_unsafe`
4. `retain_central_relational_representation_for_research`

The summary must also state `no_promotion=true`,
`candidate_b_decision_input_count=0`, and
`candidate_d_instantiated=false`.

The outer seal snapshots the complete tracked Git tree at `source_sha` using
canonical committed blob contents. Its provenance contains the full
path-to-Git-blob mapping, and verification requires exact source-file inventory
and blob equality. Seal creation also requires clean repository status, the
registered branch, exact `HEAD`, and a successful CI record with the same
`headSha`, `headBranch`, and run ID. The raw source commit object is sealed; its
object ID and declared tree are verified against a tree reconstructed from the
complete path/mode/blob inventory. Path-aware working-tree Git hashes must
equal the committed blobs even when an index flag could hide a modification
from ordinary status output.

The source, two full-run inputs, logs, and destination must be pairwise
non-overlapping roots, and the twin inputs must validate byte-for-byte equal.
Each local receipt is closed-schema JSON containing an exact command array,
absolute working directory, source SHA/branch, UTC interval, integer exit code,
UTF-8 output byte count/hash, and captured output. Command-specific validation
requires successful configure/build/full unfiltered CTest, distinct full
producer destinations, independent byte comparison, validation and mutations,
Lean compilation/axioms, formal trust, and exact C++/CMake/Python/Lean versions.
These local receipts are sealed execution claims rather than authentication;
independent CI and semantic replay remain mandatory. `ci-run.json` has a closed field
inventory and must exactly equal a fresh GitHub Actions API response containing
successful GCC, Clang, MSVC, Python-oracle, and pinned-Lean jobs. The canonical
public repository, branch, and evidence tag must resolve to `source_sha` during
creation; later verification requires the immutable tag and exact CI attempt,
so advancing the development branch does not invalidate the artifact.
`provenance.json`, bundle summaries, and the
outer manifest reject extra contradictory fields. Final verification accepts
an externally recorded expected pre-hash and rejects any internally consistent
replacement seal with a different value. Seal creation stages outside the
canonical path, revalidates the copied payload, runs full verification, and
atomically renames only after success.
