# Time Integration Foundation evidence schema

## Outer identity

The outer seal schema is `mls.time-integration-foundation.outer-seal.v1`. It
binds the exact source, immutable accepted parent evidence, branch, evidence
tag, CI run, decision, `R=128` representation, force domain, complete payload
inventory, canonical pre-hash, and no-promotion boundary.

## Payload groups

- `raw-a/` and `raw-b/`: independently materialized deterministic CSV twins;
- `oracle/`: 110-digit independent result and mutation receipt;
- `parent-drift-bridge/`: independently downloaded accepted parent evidence;
- `source/`: exact source archive and identity;
- `receipts/`: build, test, formal, CI, archive, and download receipts; and
- `docs/`: preregistration, contract, result, and this schema.

Every file other than `outer-seal.json` is bound by relative path, byte size,
and SHA-256. Symlinks, unsafe paths, ignored files, and extra files are rejected.
`source/source-identity.json` binds the exact source archive, commit, tree, and
branch. `receipts/ci-run.json` binds the successful branch CI run and the exact
five required GCC, Clang, MSVC, Python-oracle, and pinned-Lean jobs.
Raw materialization accepts the authorized branch name or Git's detached
`HEAD` spelling used by immutable-tag CI; sealed public evidence itself must
carry the authorized branch name and exact source SHA.

## Raw schema

The raw schema is `mls.time-integration-foundation.raw.v1`:

- `metadata.csv`, `units.csv`, `parent_fingerprint.csv`, and
  `rounding_controls.csv` bind provenance and frozen numerical semantics;
- `reference_packets.csv`, `relations.csv`, and `force_operator.csv` export the
  complete exact model state and binary64 operator bits;
- `initial_states.csv`, `endpoints.csv`, and `energies.csv` contain the complete
  registered trajectory hierarchy;
- `reversibility.csv` records every signed-time recovery;
- `covariance.csv` records translation, Galilean-boost, and exact lattice
  rotation controls;
- `checkpoint.csv` records canonical resume and event-stream identity;
- `domain.csv` records the atomic crossing failure; and
- `long_energy.csv` records the complete sixteen-second energy trace.

All authoritative state is integer. Binary64 values are serialized only as
unsigned 64-bit encodings. Decimal text is never the mathematical source for a
floating-point value.

## Independent oracle

The oracle schema is `mls.time-integration-foundation.oracle.v1`. It reconstructs
binary64 values exactly, independently rebuilds the accepted local collective
operator, evaluates the smooth ODE at 110 decimal digits, verifies its own
refinement, re-derives state/energy convergence, and applies the preregistered
decision order. A valid failure disposition is evidence; the validator must not
rewrite it as a passing dynamics claim.
