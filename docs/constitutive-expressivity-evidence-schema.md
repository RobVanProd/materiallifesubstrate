# Constitutive Expressivity evidence schema v1

The canonical bundle is self-contained. Independent review must not need the
producer's external parent fixture after production.

## Closed file inventory

| Path | Contents |
|---|---|
| `summary.json` | decision, row/failure counts, prohibited-feature boundary |
| `provenance.json` | source/parent identity, compiler, frozen inherited blobs, complete-parent hashes, and selected-subset hashes/mode |
| `manifest.json` | SHA-256 of every payload and a canonical pre-hash |
| `configurations.csv` | bounded configuration IDs, registered role, packet/relation counts |
| `packets.csv` | canonical IDs, exact mass quanta, binary64 reference coordinates |
| `relations.csv` | canonical endpoints and binary64 reference lengths |
| `basis_vectors.csv` | complete producer-used rigid and accepted `R`-null bases, keyed by canonical packet ID |
| `bulk_expressivity.csv` | pair Cauchy and collective two-modulus summary rows |
| `tangent.csv` | complete 6x6 actual/expected Kelvin tangents and gates |
| `strain_energy.csv` | Kelvin, mixed, and rotated-control energies |
| `graph_energy.csv` | finite-graph locality, Euclidean H-support extent, positivity bounds, R/LR rank/kernel diagnostics |
| `spectra.csv` | every direct `L R` singular value and classification |
| `metamorphic.csv` | objectivity, similarity, order, endpoint-orientation, and ID controls |
| `checkpoints.csv` | canonical checkpoint size/hash/round-trip rows |
| `checkpoints/<configuration>.bin` | actual input checkpoint bytes |

No undeclared file may enter a canonical bundle. Binary64 values are emitted
as canonical hexadecimal strings; integers, booleans, IDs, and SHA-256 values
are exact text. CSV ordering is deterministic and semantically canonical.

`basis_vectors.csv` has columns
`configuration_id,basis_kind,basis_index,packet_id,x,y,z`. The registered
`basis_kind` values are `rigid_orthonormal` and
`r_nullspace_accepted_cpqr`. A basis vector is reconstructed by sorting its
rows by the exported canonical packet order and concatenating `(x,y,z)`.
Every rigid basis column and every accepted `R`-null column actually used by
the producer's energy residual gate is present exactly once per packet.

For a full run, `provenance.json.selected_subset_sha256` records mode
`accepted_parent_subset` and the three frozen producer-format table hashes in
the preregistration. For smoke it records mode `builtin_smoke` and explicit
`builtin_smoke` markers; smoke evidence makes no accepted-parent-subset claim.

## Decision-bearing inventories

The full bundle contains two pair-separable bulk controls and eight local-
collective bulk controls: two independently shaped symmetric cubatures times
four preregistered positive `K/G` targets. Every control includes its full
Kelvin tangent and registered finite strain energies.

The finite graph table contains five rows per selected graph: one pair
negative-control row and four local collective rows. The bounded full graph
inventory is exactly the two exact rigid controls, regular bulk, BCC-like
bulk, jittered bulk, free surface, relation deletion, and one intentionally
floppy graph named in the preregistration.

Metamorphic rows cover pair and local collective energy for common
reference/current translation, proper rotation, and rotation-plus-translation
covariance; current-only translation and proper-rotation objectivity with the
reference fixed; half/double similarity; two packet
permutations, relation reversal, deterministic relation permutation, endpoint
orientation reversal, and three full packet-ID bijections.

## Independent verification boundary

The validator hashes every declared file, rejects extras/missing fields, and
reconstructs packet geometry/topology from the exported tables. It independently
recomputes the cubature moments, pair restriction, collective parameter maps,
finite energies, local `H`, direct factor `L`, `R`, selected exact/high-
precision ranks and spectra, locality, complete basis dimensions,
orthonormality and R-kernel/rigid-span semantics, independently recomputed
rigid/null energy residuals, checkpoint decoding/round trip, metamorphic
transformations, and decision ordering. Every selected large configuration is
checked at both registered collective-coefficient extremes. C++ summary fields
are observations to compare, never premises.

The Euclidean locality field is the maximum distance between any endpoints of
every relation-coordinate pair coupled by a nonzero `H` entry. Diagonal
entries count, so pair-separable relations report their bond length rather
than zero. Relation-space adjacency is reported separately by the `H`
sparsity and graph-hop fields.

Twin full bundles are closed-tree-compared before numerical validation. Once
byte identity is established, the independent numerical audit runs once over
the single integrity-checked canonical content tree; repeating identical
high-precision work cannot add content coverage. Mutation regression proves a
twin mismatch is rejected before an otherwise-invalid primary bundle reaches
semantic validation. Mutation regression must also reject at
least altered energy/tangent, locality, target ratio, ID mapping, kernel/rank,
basis/residual data, selected-parent commitment, checkpoint bytes, source
provenance, twin payload, manifest, and final decision.

The decision string
`retain_local_collective_relational_energy_for_research` is valid only when
every registered gate passes. It always coexists with `no_promotion=true` and
does not authorize force application or dynamics.

## Outer command receipts

The outer seal preserves integrity-bound command receipts. It binds each
receipt's exact argv, working directory, exit status, combined output, and
output hash to the sealed source SHA. It also records and rechecks these path
relationships: configure/build/CTest use one resolved build directory;
producer outputs equal the two registered bundle directories; and both the
twin comparator and independent validator consume exactly those two bundle
directories. The accepted-parent subset derivation receipt binds its exact
parent-bundle argument and the three frozen selected-table hashes.

These receipts provide tamper-evident provenance and internally consistent
command/path relationships. They do **not** cryptographically authenticate
that the operating system executed the recorded argv. Public CI replication,
the immutable source tag, independent validators, and the closed outer
manifest are separate evidence layers.

Summary counts distinguish pair-control failures, collective bulk-span
failures, and all other implementation/metamorphic/checkpoint failures. A
clean collective-only span failure maps to
`local_collective_constitutive_parameterization_or_locality_failure`; a
pair/Cauchy or implementation failure maps to
`stop_inconclusive_or_implementation_failure`. Dense-global rows are always
zero in this producer, so the dense-only decision branch is not reachable.
