# Authoritative Mechanics State Bridge evidence schema

## Outer identity

The immutable outer seal is
`mls.authoritative-mechanics-state-bridge.outer-seal.v1`.  It binds the exact
source SHA, accepted parent source/tag/tag object, branch, evidence tag, CI run,
decision, selected refinement, selected geometry path, no-remainder disposition,
promotion boundary, complete payload inventory, and canonical pre-hash.

## Payload groups

- `raw-a/`, `raw-b/`: independently materialized bit-pattern CSV twins;
- `oracle/`: exact-rational JSON/CSV result and mutation receipt;
- `parent-relation-geometry/`: immutable accepted parent identity/receipt;
- `source/`: exact source archive or bundle and source identity;
- `receipts/`: compilers, CTest, Python, Lean, CI, archive, and download checks;
- `docs/`: preregistration, contract, result, and this schema.

Every file other than `outer-seal.json` is covered by path, byte size, and
SHA-256.  Symlinks and unsafe paths are forbidden.  No ignored or extra file is
permitted after sealing.

## Raw schema

The raw schema is
`mls.authoritative-mechanics-state-bridge.raw.v1`:

- `metadata.csv` binds immutable provenance and scientific disposition;
- `units.csv` carries every exact rational base/derived quantum and existing raw
  scale factor;
- `packets_bits.csv` carries authoritative raw packet state and binary64 mapping
  bits;
- `relations_bits.csv` carries frozen Path-B geometry and relation-force bits;
- `h_bits.csv` carries the frozen symmetric `H_force` bits;
- `evaluations.csv` carries all 450 path/refinement/subdivision impulse,
  conservation, energy, residual, and remainder-checkpoint rows; and
- `candidate_summary.csv` carries the mechanical selection gate.

Human-readable decimal rendering is never the oracle source.  All binary64
values are unsigned 64-bit encodings.

## Independent oracle

The oracle schema is
`mls.authoritative-mechanics-state-bridge.oracle.v1`.  It reconstructs exact
binary64 rationals, re-derives every unit, primitive direction, nearest-even
decision, raw conservation identity, kinetic floor, residual bound, subdivision
classification, and final decision.  The validator rematerializes this result
and requires byte identity with the sealed oracle artifacts.
