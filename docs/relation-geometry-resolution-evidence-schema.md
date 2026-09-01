# Relation Geometry Resolution evidence schema

The public evidence is a directory with one deterministic outer seal.  Every
payload file is covered by exact byte count and SHA-256 in `outer-seal.json`.
No file may appear outside that inventory.

Required payload groups are:

- `raw-a/` and `raw-b/`: byte-identical C++ producer twins containing only
  uint64 binary64 encodings for authoritative numerical inputs and outputs;
- `oracle/`: the 420-digit result JSON and row-complete CSV;
- `parent-force-producer/`: the hash-verified tables copied from the immutable
  Conservative Force Consistency evidence release;
- `source/`: the exact committed source archive and source identity;
- `receipts/`: command, compiler, test, oracle, mutation, Lean, CI, archive,
  and fresh-verification outputs; and
- `docs/`: the contract, preregistration, and result.

`outer-seal.json` uses schema
`mls.relation-geometry-resolution.outer-seal.v1` and records:

- accepted force source and evidence tag;
- exact lab source SHA, branch, public evidence tag, and CI run ID;
- decision, selected path, safe-domain exponent, intrinsic-boundary result,
  and `NO_PROMOTION`;
- a sorted payload inventory; and
- `outer_pre_hash`, the SHA-256 of the canonical seal object with that field
  replaced by `null`.

The verifier rejects missing, extra, symlinked, renamed, truncated, or mutated
payloads.  Scientific validation additionally requires byte-identical raw
twins, the sealed parent table hashes, a fresh independent oracle replay, the
registered decision, and the mutation regression.
