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
| `nullspace.csv` | residual and rigid/non-rigid component of every accepted CPQR kernel vector |
| `metamorphic.csv` | similarity, ordering, and ID-renaming equivalence controls |
| `id_bijections.csv` | complete old/new/inverse label mappings |
| `topology_path.csv` | every one-edge deletion state and transition markers |
| `lookup.csv` | brute-force versus lookup-grid edge enumeration |
| `checkpoints.csv` | byte hashes for original, round-tripped, and post-diagnostic state |
| `checkpoints/*.bin` | canonical `MLSMOBS1` v1 state with packets, bonds, and zero volumes |
| `tolerances.json` | frozen arithmetic constants, probes, and decision order |
| `summary.json` | source provenance, counts, gate totals, verdict, and no-promotion boundary |
| `manifest.json` | exact inventory, per-file hashes, row counts, and bundle pre-hash |

Candidate-B matrices/results and Candidate-D volume relations/results are not
valid files or columns in this schema.

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

