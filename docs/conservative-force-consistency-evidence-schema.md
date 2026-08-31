# Conservative Force Consistency evidence schema v1

The canonical bundle is closed and self-contained.  All binary64 values use
canonical hexadecimal text.  High-precision decimal values include their
declared precision and scale.  CSV rows have a fixed canonical order.  The
final bundle preserves the complete closed C++ producer bundle under
`producer/`; the independent stage never rewrites those bytes.

| Final path | Required contents |
|---|---|
| `summary.json` | bounded decision, row/failure counts, domain and prohibited-feature boundary |
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

No force entry is permitted for an evaluation whose status is
`coincident_relation`; the manifest must instead bind the deterministic domain
failure record.  The summary must contain the exact token `NO_PROMOTION` and
must state that no integration, authoritative force installation, damping,
contact, fracture, damage, gravity, chemistry, organisms, rendering, GPU, or
thermal conversion was added.
