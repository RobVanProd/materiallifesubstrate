# Conservative Force Consistency evidence schema v1

The canonical bundle is closed and self-contained.  All binary64 values use
canonical hexadecimal text.  High-precision decimal values include their
declared precision and scale.  CSV rows have a fixed canonical order.  The
final bundle preserves the complete closed C++ producer bundle under
`producer/`; the independent stage never rewrites those bytes.

| Final path | Required contents |
|---|---|
| `summary.json` | bounded decision, row counts, predicate-failure event counts, inconclusive reasons, domain and prohibited-feature boundary |
| `provenance.json` | independent-stage identity plus source/parent/evidence identity, inherited blobs, seed, tool and schema versions |
| `manifest.json` | SHA-256 of every payload and canonical pre-hash |
| `independent_directional_derivatives.csv` | every registered raw 100-decimal step, extrapolated derivative, independently derived analytic work, exported-C++ directional work, and their separate convergence/agreement gates |
| `independent_finite_tangent.csv` | every registered raw 100-decimal step and extrapolated material/geometric/total/Jacobian comparison |
| `producer/manifest.json` | exact closed manifest emitted by C++ before independent work |
| `producer/raw_summary.json` | raw counts, explicit pending high-precision stage, no final decision |
| `producer/raw_provenance.json` | source/parent/inherited-blob/compiler/raw-schema identity |
| `producer/configurations.csv` | registered graph identity, role, packet/relation counts |
| `producer/reference_packets.csv` | canonical and semantic packet IDs, mass quanta, reference coordinates |
| `producer/relations.csv` | canonical/semantic endpoints, reference lengths, weights, relation index |
| `producer/operators.csv` | operator ID, graph, family, target `K/G`, frozen coefficients |
| `producer/h_matrix.csv` | complete `m*m` parent and frozen-symmetric H values plus correction, including zeros |
| `producer/current_packets.csv` | evaluation-bound current coordinates and velocity/direction probes |
| `producer/force_evaluations.csv` | binary64 energy, power, total force/torque, domain status, scales and gates |
| `producer/relation_forces.csv` | relation extension, length, direction and one computed conjugate `g_a` |
| `producer/packet_forces.csv` | complete semantic packet-force vector for every valid evaluation |
| `producer/reference_tangent.csv` | registered epsilon sequence and binary64 `-R0^T H R0` convergence |
| `producer/finite_tangent.csv` | material/geometric/total Hessian, force Jacobian, and binary64 raw steps |
| `producer/metamorphic.csv` | objectivity, similarity, order, endpoint and ID probes with explicit maps |
| `producer/compression.csv` | positive length-ratio path, conditioning/sensitivity, exact-coincidence status, and producer-only `binary64_gradient_error_n` diagnostic |

Both manifest inventories are exact; undeclared files fail validation.  The
independent validator reconstructs semantic graphs, frozen `H`, finite energy,
analytic gradient, continuous balance identities, tangent terms, and selected
high-precision checks.  It may not accept producer or materialiser pass fields
or summary counts as premises.

The raw compression table must not contain a field named
`independent_gradient_error_n` or otherwise claim a high-precision oracle.
High-precision collapse-gradient verification is recomputed by the final
validator from producer inputs and recorded in the validator receipt/decision;
it is not a trusted C++ field.  This pre-data clarification changes no case,
tolerance, or decision rule.

For compression rows, `force_norm_n` is the Euclidean norm of the complete
`3N` force vector.  Material, geometric, and total tangent norms are Frobenius
norms of the complete matrices.  The final directional table contains distinct
`cpp_analytic_derivative_n` and `cpp_gradient_residual_n` fields so the
high-precision energy check is bound to the implemented C++ force as well as
to the independent Decimal analytic gradient.

Producer row `pass` values are local binary64 diagnostics only.  The validator
recomputes those exact local predicates for integrity, but independently found
gradient, conservation, tangent, or collapse failures remain valid scientific
outcomes and feed the registered decision order; they are not rejected merely
because the producer did not or could not make the high-precision judgment.

The accepted parent bundle's selected top-level tables are the sole producer
fixture.  Metamorphic maps and submitted packet ordering are evidence, but not
premises: the validator reconstructs every registered transform from semantic
case identity and seed and checks the exported ordering, endpoints, relation
coordinates, reference scaling, and `H` permutation against it.

`H` is relation-coordinate data.  The validator first reconstructs and checks
the registered `(H_parent+H_parent^T)/2` freeze, its correction bound, and
byte-identical mirrored entries.  A permutation row must carry the explicit
old/new semantic relation map needed to compare `P H P^T`, `P e`, and `P g`.
Packet-ID bijections similarly carry canonical semantic IDs.  Missing or
duplicate semantic coordinates fail closed.

Every metamorphic row also carries the SHA-256 digest of the reconstructed,
coordinate-transformed `H`; the validator recomputes it.  Torque balance uses
the larger absolute-term sum about the two registered origins.  Power balance
uses both elementary endpoint relation-work terms and relation-rate terms, so
the scale is retained before packet-force cancellation.

The producer provenance freezes an eight-byte, 53-significand-bit IEC-559
binary64 contract, explicit operation order, and disabled contraction.  The
new evaluator/producer and independent binary64 emulator do not use native
`long double`.  Same-toolchain twin trees are byte-identical.  GCC, Clang, and
MSVC CI results are tolerance-based cross-toolchain replications, not byte
twins.

`current_packets.csv` velocity columns are virtual velocities in m/s for the
power identity.  A `direction.*` semantic row also binds the same independently
reconstructed normalised numeric pattern as dimensionless displacement `d` in
`x+alpha d`, with `alpha` in metres.

Summary keys `inconclusive_failure_events`,
`energy_gradient_failure_events`, `force_conservation_failure_events`,
`finite_consistency_failure_events`, and `degeneracy_failure_events` count
failed independent predicates rather than rows or cases.
`producer_failure_rows` is retained separately, and `inconclusive_reasons`
contains sorted distinct reason tokens.

No force entry is permitted for an evaluation whose status is
`coincident_relation`; the manifest must instead bind the deterministic domain
failure record.  The summary must contain the exact token `NO_PROMOTION` and
must state that no integration, authoritative force installation, damping,
contact, fracture, damage, gravity, chemistry, organisms, rendering, GPU, or
thermal conversion was added.

Every four-level high-precision sequence remains in the bundle and must improve
until its registered floor, then remain below that floor; a later re-emergence
cannot be hidden by extrapolation.  Compression ratios below `2^-32` are
diagnostic-only and cannot alter the decision.  Smoke bundles are reduced
integration fixtures; a canonical claim requires `summary.full=true` and the
complete eight-graph, 24-operator inventory.

## Outer evidence boundary

The outer evidence directory contains the two byte-identical full bundles, a
complete committed-source snapshot, and an exact `logs/` inventory.  The logs
inventory contains one structured receipt for each configure, build, unfiltered
CTest, raw-producer, materialisation, twin comparison, validator and mutation
regression, exact oracle and regression, Lean build/axiom report, formal trust
scan, compiler/tool identity, and accepted-parent verification command.  It
also contains `ci-run.json`, `ci-artifacts.json`, and `ci-artifacts/` with the
five required public CI artifact archives and their safely expanded contents.

Command receipts are integrity and path-binding records, not signatures or an
independent witness of operating-system execution.  The sealer therefore
requires a successful public run at the exact source SHA and, at creation time,
downloads the exact run attempt's artifacts again.  Stable artifact IDs/names
and every expanded file commitment must match the captured copy before the
outer seal is created.  Archive container bytes need not match because GitHub
may regenerate ZIP containers around identical files.  Offline verification
then checks the sealed source, receipts, archives, expanded contents, run
record, artifact commitments, public tag, and outer manifest without silently
refetching or rewriting evidence.
