# Conservative Force Consistency evidence schema v1

The canonical bundle is closed and self-contained.  All binary64 values use
canonical hexadecimal text.  High-precision decimal values include their
declared precision and scale.  CSV rows have a fixed canonical order.

| Path | Required contents |
|---|---|
| `summary.json` | bounded decision, row/failure counts, domain and prohibited-feature boundary |
| `provenance.json` | source/parent/evidence identity, inherited blobs, seed, tool and schema versions |
| `manifest.json` | SHA-256 of every payload and canonical pre-hash |
| `configurations.csv` | registered graph identity, role, packet/relation counts |
| `reference_packets.csv` | canonical and semantic packet IDs, mass quanta, reference coordinates |
| `relations.csv` | canonical/semantic endpoints, reference lengths, weights, relation index |
| `operators.csv` | operator ID, graph, family, target `K/G`, frozen coefficients |
| `h_matrix.csv` | complete `m*m` parent and frozen-symmetric H values plus correction, including exact exported zero entries |
| `current_packets.csv` | evaluation-bound current coordinates and velocity probes |
| `force_evaluations.csv` | energy, power, total force/torque, domain status, scales and gates |
| `relation_forces.csv` | relation extension, length, direction and one computed conjugate `g_a` |
| `packet_forces.csv` | complete semantic packet-force vector for every valid evaluation |
| `directional_derivatives.csv` | analytic/high-precision directional derivatives and convergence data |
| `reference_tangent.csv` | registered epsilon sequence and `-R0^T H R0` convergence |
| `finite_tangent.csv` | complete material/geometric/total Hessian and force-Jacobian entries |
| `metamorphic.csv` | objectivity, similarity, order, endpoint and ID probes |
| `compression.csv` | positive length-ratio path, conditioning/sensitivity, exact-coincidence status |

The manifest inventory is exact; undeclared files fail validation.  The
independent validator reconstructs semantic graphs, frozen `H`, finite energy,
analytic gradient, continuous balance identities, tangent terms, and selected
high-precision checks.  It may not accept producer pass fields or summary
counts as premises.

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
