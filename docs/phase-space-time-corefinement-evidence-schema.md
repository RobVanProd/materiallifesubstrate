# Phase-Space/Time Co-Refinement evidence schema

## Outer identity

The outer seal schema is `mls.phase-space-time-corefinement.outer-seal.v1`.
It binds the exact source and tree, accepted parent source/tag/tag object,
authorized branch and evidence tag, successful CI run, negative scientific
decision, complete payload inventory, canonical pre-hash, and no-promotion
boundary.

## Payload groups

- `raw-a/` and `raw-b/`: independently materialized deterministic CSV twins;
- `oracle/`: 110-digit independent result and 33-mutation receipt;
- `parent-time-integration/`: freshly reproduced and independently fingerprinted
  accepted parent raw evidence;
- `source/`: exact Git source archive and identity;
- `receipts/`: local build/test/formal, CI, archive, and fresh-download receipts;
  and
- `docs/`: preregistration, contract, result, and this schema.

Every file other than `outer-seal.json` is bound by relative path, byte size,
and SHA-256.  Symlinks, unsafe/case-colliding paths, unexpected groups, ignored
files, and extra files are rejected.  The source identity binds commit, tree,
branch, archive digest, and exact file inventory.  The CI receipt binds the
successful GCC, Clang, MSVC, Python-oracle, and pinned-Lean jobs to that commit.

## Raw schema

The raw schema is `mls.phase-space-time-corefinement.raw.v1` and contains 18
files:

- `metadata.csv`, `units.csv`, `parent_fingerprint.csv`, and `mapping.csv` bind
  provenance, the exact unit family, parent seams, and signed-width outcomes;
- `reference_packets.csv`, `relations.csv`, `force_operator.csv`, and
  `initial_states.csv` export all accepted scientific inputs and exact raw
  mappings;
- `endpoints.csv` and `energies.csv` contain the complete registered short
  trajectories;
- `primitive_diagnostics.csv` records momentum gcd and minimum drift quanta;
- `relation_primitive_diagnostics.csv` records relation gcd, primitive central
  directions, target/applied kick multiples, and minimum impulses;
- `reversibility.csv`, `covariance.csv`, `checkpoint.csv`, `domain.csv`, and
  `bridge_contracts.csv` record the exact composition gates; and
- `long_energy.csv` contains every sample of all five sixteen-second energy
  traces.

All authoritative state fields are decimal encodings of integers.  Every
binary64 quantity is serialized by its unsigned 64-bit object representation,
never by decimal re-parsing.  Unit quanta are exact rational strings.

## Independent oracle

The oracle schema is `mls.phase-space-time-corefinement.oracle.v1`.  It
reconstructs exact rational units, anchors level zero to the accepted parent,
reconstructs binary64 inputs from bit patterns, recomputes integer invariants
and gcd diagnostics with unbounded Python integers, and separately evaluates
the smooth ODE at 110 decimal digits with refinement checks near `1e-34`.

It re-derives convergence orders, physical energy behavior, covariance,
signed-width classification, and the fixed decision order.  It rejects 33
registered mutations.  A negative decision is valid evidence and must never be
relabeled as successful dynamics.
