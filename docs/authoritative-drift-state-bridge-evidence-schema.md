# Authoritative Drift State Bridge evidence schema

## Outer identity

The immutable outer seal is
`mls.authoritative-drift-state-bridge.outer-seal.v1`.  It binds the exact source
SHA, accepted parent source/tag/tag object, branch, evidence tag, CI run,
decision, selected path/refinement, no-remainder disposition, force safe domain,
promotion boundary, complete payload inventory, and canonical pre-hash.

## Payload groups

- `raw-a/`, `raw-b/`: independently materialized deterministic CSV twins;
- `oracle/`: exact-rational JSON/CSV result and mutation receipt;
- `parent-mechanics-bridge/`: immutable accepted parent evidence and identity;
- `source/`: exact source archive and source identity;
- `receipts/`: compiler, CTest, Python, Lean, CI, archive, and download receipts;
- `docs/`: preregistration, contract, result, and this schema.

Every file other than `outer-seal.json` is covered by path, byte size, and
SHA-256.  Symlinks and unsafe paths are forbidden.  No ignored or extra file is
permitted after sealing.

## Raw schema

The raw schema is `mls.authoritative-drift-state-bridge.raw.v1`:

- `metadata.csv` binds immutable provenance and scientific disposition;
- `units.csv` records the coherent exact rational unit family through `R=128`;
- `parent_fingerprint.csv` records the inherited exact-pass/fractional-reject
  ballistic behavior;
- `inventory.csv` records base authoritative packet integers;
- `evaluations.csv` records all 2,016 candidate/refinement/horizon/subdivision
  rows, exact rational inputs, applied displacements, errors, torque, kinetic
  identity, and overflow margin;
- `equal_velocity.csv` and `center_of_mass.csv` record translation gates;
- `impulse_regression.csv` records the rerun inherited bridge at fallback
  refinements;
- `domain_chords.csv` records exact safe-domain chord inputs/classifications;
- `overflow_controls.csv` and `rounding_controls.csv` record fail-closed and
  nearest-even controls; and
- `candidate_summary.csv` records the mechanically selected refinement.

Binary64 diagnostic values are unsigned 64-bit encodings.  All authoritative
decisions are independently reconstructed from integer fields and exact
rationals rather than decimal renderings.

## Independent oracle

The oracle schema is `mls.authoritative-drift-state-bridge.oracle.v1`.  It
independently re-derives coherent units, signed nearest-even decisions, primitive
directions, displacements, component/vector/COM errors, exact orbital changes,
unchanged momentum/kinetic energy, inherited impulse gates, exact chord minima,
overflow classification, and the final `R=128` selection.  The fresh validator
rematerializes the oracle and requires byte identity with the sealed artifacts.
