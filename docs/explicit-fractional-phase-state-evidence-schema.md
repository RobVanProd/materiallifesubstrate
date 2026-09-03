# Explicit Fractional Phase-State evidence schema

The sealed bundle contains exactly seven payload groups plus
`outer-seal.json`:

- `raw-a/` and `raw-b/`: independently materialized byte-identical candidate
  evidence;
- `oracle/`: 110-digit oracle result and semantic mutation receipt;
- `parent-corefinement/`: the complete immutable accepted parent bundle;
- `source/`: deterministic source archive and identity receipt;
- `receipts/`: CI, compiler, Python, Lean, twin, build, and failed-attempt
  receipts; and
- `docs/`: preregistration, contract, result, and this schema.

Each raw directory contains:

| file | role |
|---|---|
| `metadata.csv` | immutable parent, candidate, backend, limits, and promotion identity |
| `units.csv` | exact fixed `R=128` SI unit basis and canonical residual interval |
| `parent_fingerprint.csv` | exact hashes of all accepted parent raw files |
| `reference_packets.csv` | frozen parent reference packet bit/integer state |
| `relations.csv` | frozen oriented relation topology and rest-length bits |
| `force_operator.csv` | frozen accepted `H_force` binary64 bit patterns |
| `initial_states.csv` | complete canonical initial coarse-plus-rational state |
| `endpoints.csv` | complete canonical candidate/control endpoints |
| `checkpoint_states.csv` | complete canonical interior checkpoint state |
| `recovery_states.csv` | complete canonical signed-time recovery state |
| `energies.csv` | short mechanical-energy traces as binary64 bit patterns |
| `invariants.csv` | exact stage totals, hashes, and equality decisions |
| `force_audit.csv` | relation force bits, exact coefficient/impulse hashes, bit lengths, and centrality |
| `state_complexity.csv` | every-step component hashes/bit lengths and checkpoint size |
| `reversibility.csv` | signed-time complete-state comparisons |
| `covariance.csv` | exact relative position/momentum discrepancies |
| `checkpoint.csv` | canonical replay and event-suffix receipt |
| `domain.csv` | deterministic atomic chord-rejection result |
| `long_energy.csv` | registered long energy traces and stop status |
| `obstruction.csv` | exact squared reciprocal kick/drift identities |

All integers and rational numerators/denominators are decimal lexical integers.
Binary64 values are exported as unsigned 64-bit integer bit patterns. Booleans
are exactly `true` or `false`. CSV uses UTF-8, LF endings, one header, and no
locale-dependent formatting.

Canonical state serialization uses a fixed magic, little-endian fixed-width
packet identity/coarse fields, and sign-plus-minimal-big-endian-magnitude
encoding for arbitrary integers. Equivalent rational spellings are rejected;
only reduced positive-denominator fractions can produce a state hash.

`outer-seal.json` inventories the path, byte count, and SHA-256 of every payload
file. Its pre-hash is computed with `outer_pre_hash` set to JSON null, and the
seal fixes parent/source/tag/decision/candidate/complexity/promotion semantics.
