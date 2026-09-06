# Relation-Coordinate Defect Tail Certification — preregistration

Parent: `99d979334f0b931401d451beba70029d6bca52d7`.
Branch: `relation-coordinate-defect-tail-certification-lab`.
NO_PROMOTION TO AUTHORITATIVE WORLD DYNAMICS.

## Frozen boundary and proof-first order

All inherited mechanics, B96 wire arithmetic, units, topology, H_force,
reference geometry, binary64 Path B, KDK, domain r/l0 >= 2^-24, physical
budgets, precisions and registered trajectories remain unchanged. No B256
truth, branching, correction state, increased precision or adaptive horizon.
The exact incidence/common-mode, kick/drift closure and defect induction Lean
statements compile before implementing this verifier. Formal statements are
exact algebra with explicit fixed-cell assumptions, not an executable proof.

## Coordinates and orientation

Use raw coordinates. D has -1 at first endpoint and +1 at second endpoint.
The center observables are r = D^T x and v = D^T M_raw^-1 p, calculated as
exact rationals from independently decoded canonical B96 wire states.
Their target-minus-candidate errors q and s are stored directly. Never
reconstruct these propagated error coordinates from packet interval boxes.

For a half-kick duration t_raw, define the exact rational alpha_a as
t_raw*TQ*LQ/PQ times the reconstructed binary64 g_a/length_a. The actual
frozen first endpoint receives +alpha_a*r_a. Thus p' = p-D*diag(alpha)*r
and v' = v-D^T*M_raw^-1*D*diag(alpha)*r. Drift r' = r+t_raw*v.
These raw formulas derive from the inherited coherent SI units, not new units.
Construct both operators by exact rational arithmetic. At each stage compute
the complete observable defect A*c-c_next exactly. Sum every matrix row
exactly before rounding its enclosure endpoints outward to 512 bits.

In parallel propagate the inherited packet-component defect enclosure for
absolute budgets. It MUST NOT choose force cells. Both systems are checked
against the independently evolved exact comparator after generation. No
post-hoc symmetry, endpoint equality or exact target enters propagation.
Relation 5's x cancellation must follow its own recurrence or fail openly.
Dependency among distinct relation coordinates is not assumed preserved.

Force inputs use exact candidate r plus q. Certify full SI intervals in one
exact binary64 RN-even cell. No proximity guess constitutes certification.
Potential uncertainty and straight chord safety use direct relation boxes;
kinetic uncertainty uses packet momentum boxes. Stream signed energy-slope
enclosures, not absolute-before-sum surrogates. Failed domain enclosure is
inconclusive, not a domain violation.

## Frozen controls, resources and gates

Authenticate the accepted source/tag/manifest and inherited negative controls.
Same short corpus: internal/boosted, levels 0..4, starts 0/8/32, lengths 1/4/16.
Initialize each short block from exact checkpoint-minus-candidate differences,
never reset an unknown full-tail uncertainty. Require all 90 blocks and every
available stage to contain exact packet AND relation position/velocity states.
All 30 time-zero cases must pass the first step's second kick. If the short
gate remains unresolved, preserve every case and do not launch full tails.

Only after 90/90: ten B96 16-second tails from time zero. Same physical
budgets, all required observers, no comparator feeding continuation. Logical
state is 6*N packet intervals plus 6*E relation intervals, fixed matrices and
streaming observer slots, independent of elapsed steps. No historical DAGs,
generators or causal provenance. Verifier endpoints have 512 significand bits
and exponent range [-16384,16384]. Scratch exact arithmetic is stage-local.
Per process: 2 GiB address space, 900 seconds per short case; full-tail budget
3600 seconds per case. At most four processes. Resource exhaustion is never
a pass or physical failure. Repeat scientific records byte-for-byte; external
clock/RSS fields remain separate. No resource adjustment after outcomes.

## Independent checks and decisions

Known-answer controls precede trajectory data: exact relation closure against
packet propagation, oriented signs, common translations/velocity boosts,
arbitrary-center defects, signed accumulation, outward rounding, cell ties.
Mutations must reject missing defects, endpoint subtraction replacing direct
relation state, incorrect orientation/mass, inward rounding, target/candidate
substitution, unproved cell assumptions, zero checkpoint resets, omitted
relation coordinates, B256 truth and unresolved/resource outcomes as passes.

Decision order: parent/inherited controls fail ->
`stop_inconclusive_or_wrong_parent`; escaped exact relation state ->
`stop_relation_coordinate_certificate_unsound`; unresolved short gate ->
`stop_relation_coordinate_short_control_inconclusive`; full-tail cell failure ->
`stop_relation_coordinate_force_cell_inconclusive`; resource ->
`stop_relation_coordinate_resource_inconclusive`; sound actual budget violation ->
`b96_bounded_tail_budget_exceeded`; all ten full tails inside every frozen
budget -> `retain_b96_bounded_phase_state_for_research` with selected precision
96. Otherwise selected precision remains null. Every outcome is NO_PROMOTION.
Preserve attempts, independent replay/mutations, CI, deterministic sealed
evidence and public verification. Do not repair a failed experiment in place.
