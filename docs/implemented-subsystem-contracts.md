# Implemented subsystem contracts

**Scope:** C++20 reference implementation present in `include/mls/` and `src/`.
This is an implementation audit, not a description of the eventual MLS physics.
When this document says “exact,” it means exact over checked integer quanta under
the implemented operation; it does not mean physically accurate.

A mapped test name means source exists that exercises the stated behavior. It is
not a pass claim unless a separate evidence record captures the build and result.
Even a passing unit test establishes only the encoded assertion, never physical
validity, convergence, chemistry expressivity, or an MLS gate by itself.

## Implemented-scope summary

| Subsystem | Implemented now | Explicitly not implemented now |
|---|---|---|
| Quantities | Dimension-tagged signed 64-bit fixed quanta with checked arithmetic. | Unit metadata, conversions, dimensional products/quotients, uncertainty. |
| Structural chemistry | Conserved element counts, compound graphs, additive properties, configured balanced reaction extents. | Dynamic bond search, kinetics, equilibrium, diffusion, catalysis, molecular geometry. |
| Packet SoA | Persistent live handles, exact extensive stores, exactly representable dimensioned-time ballistic motion, explicit pair transfers. | Rounded/fractional integration, forces, contact, deformation, damage, fracture, constitutive material history. |
| Sparse grid | Disposable point-to-voxel index and exact extensive aggregation. | MPM scatter/gather, fields, pressure, interpolation, sparse bricks, sleeping/paging. |
| Physical support | Exact spherical point-support predicate from packet positions and a dimensioned radius. | Smooth kernels, packet extent/shape, contact, neighbor-search acceleration. |
| Ledger/boundaries | Baseline-plus-signed-boundary audit for elements, mass, total energy, linear momentum, and orbital angular momentum. | Spin/couples, charge, transaction IDs, per-reservoir identities, numerical tolerances. |
| World/hash | Deterministic orchestration, physical-support guard, dimensioned fixed-point clock, audit hooks, order-independent packet-state hash. | Autonomous physics scheduling, renderer, agents, ecology. |
| Checkpoint | Canonical versioned little-endian authoritative restart image with exact replay. | Version migration, cryptographic authenticity, debug-history persistence. |
| Transfer laboratory | Isolated deterministic binary64 PIC/APIC/FLIP diagnostic candidates and separate residuals. | Authoritative world integration, constitutive mechanics, physical validation, candidate promotion. |
| Mechanical-observability laboratory | Read-only corrected local-gradient, explicit distance-relation, and conditional objective-volume operators with complete numerical kernel diagnostics. | Constitutive law, force, stiffness, stress, time integration, contact, fracture, grid-derived mechanics state, candidate promotion. |

This file contains nine numbered implementation records. Additional bounded records are the
[physical interaction support contract](physical-support-contract.md), kept
separate because it constrains every future pair law. Orbital angular momentum
is a cross-cutting packet/ledger/world contract documented in
[point-interaction angular momentum](angular-momentum-contract.md). Exact time
and restart are specified in the
[time/checkpoint contract](time-checkpoint-contract.md), and non-authoritative
transfer candidates are specified in the
[transfer-lab contract](transfer-lab-contract.md).

The implemented program therefore does **not** satisfy Gates 2–15. It supplies
reference accounting mechanisms and adversarial fixtures used on the path toward
Gates 0–1, plus limited scaffolds relevant to Gates 3–5 and 7.

## 1. Quantities and vectors

**Implementation:** `include/mls/quantity.hpp`.

### State variables

- `Scalar`: signed 64-bit integer (`int64_t`).
- `Quantity<DimensionTag>::value_`: one scalar count of caller-defined quanta.
- Tags: `Length`, `Mass`, `Time`, `Velocity`, `Momentum`, `AngularMomentum`, `Energy`,
  `Temperature`, and `HeatCapacity`.
- `Vector3<Q>`: component-wise `x`, `y`, and `z` quantities; currently used for
  position, velocity type declarations, linear momentum, and orbital angular
  momentum.

### Units

Each raw value is a fixed-point quantum count. The conversion from one raw count
to a physical unit is scenario configuration and is not stored in `Quantity`.
The current world directly configures voxel-edge and interaction-radius lengths
and an integer kinetic-energy scale denominator. It does not contain a general
unit registry.

`Time` now represents exact configured physical-time quanta. A separate rational
configuration declares seconds per quantum, while another explicit rational
bridge relates raw momentum/mass/time quanta to displacement quanta. `Tick`
remains a distinct unsigned operation counter. `Velocity` and `Temperature`
remain type declarations without authoritative state or update laws; there is
still no general unit registry.

### Update law

Addition, subtraction, negation, and multiplication by an integer operate on raw
counts and throw before signed overflow. Division by an integer rejects zero and
the `INT64_MIN / -1` overflow; otherwise C++ integer division truncates toward
zero. Vector operations apply these scalar operations component by component.

There is no implicit conversion between dimensions and no floating-point path in
this layer. `from_raw` deliberately accepts any signed raw count; domain-specific
callers enforce positivity.

### Conservation law

The type layer does not itself conserve anything. It prevents accidental direct
addition of different tagged dimensions and gives higher layers checked exact
arithmetic. Conservation arises only from paired update laws and ledger audits.

### Numerical approximation

- fixed resolution set by externally chosen quanta;
- integer division truncation;
- finite signed 64-bit range; and
- no representation of sub-quantum uncertainty.

Changing a quantum scale changes range and resolution and therefore requires a
new configuration identity and validation. Type tags do not prove that configured
scales are dimensionally consistent.

### Failure modes and open review items

- overflow/underflow throws rather than saturates;
- negative mass or energy can be constructed with `from_raw` until rejected by a
  higher-level operation;
- multiplication does not create a derived dimension;
- general division can silently discard a remainder;
- no serialized unit-scale metadata currently accompanies state; and
- heat capacity and temperature have no implemented thermodynamic relation.

### Mapped tests

- `G0/fixed_point_arithmetic_rejects_overflow`
- `G0.G1/conservative_pair_transfer_and_nonnegativity`
- `G0.G1.G2/equal_and_opposite_momentum_exchange`
- exact-reference pair-transfer, momentum, ledger, and similarity cases

No test currently calibrates raw quanta against a physical unit system.

## 2. Structural chemistry and configured reactions

**Implementation:** `include/mls/chemistry.hpp`, `src/chemistry.cpp`, with world
coupling in `World::apply_reaction`.

### State variables

- `ElementId`: unsigned 16-bit configured element key.
- `ElementInventory`: ordered map from element key to non-negative signed 64-bit
  count; zero entries are removed.
- `CompoundGraph`: a connected labeled graph with at most eight atom sites in
  the bounded reference model. Construction canonicalizes site numbering into
  a deterministic labeled-graph encoding. Each stored bond has two canonical
  site indices and a positive 8-bit order.
- `CompoundId`: 64-bit FNV-1a cache key over the canonical labeled-graph
  encoding. It is not authoritative identity: the registry compares canonical
  graphs and rejects hash collisions.
- `ElementProperties`: per-element mass, heat capacity, and isolated structural
  energy.
- `ElementCatalog`: element properties and symmetric element-pair/bond-order
  dissociation-energy rules.
- `CompoundRegistry`: cache-key-to-graph map with collision detection.
- `CompoundMixture`: compound key to non-negative molecule count.
- `ReactionDefinition`: normalized positive reactant/product coefficients and a
  non-negative activation-energy threshold per extent.

### Units

Element and molecule amounts are exact integer counts. Mass, heat capacity, and
energy use their configured fixed quanta. Bond order is a discrete label. There
is no concentration, volume, rate, temperature, time, free energy, entropy, or
reaction-probability unit in the implemented chemistry.

### Update law

For compound graph `g`:

\[
formula_g(e)=\#\{\text{atom sites in }g\text{ labeled }e\},
\]

\[
m(g)=\sum_{a\in g}m_a,\quad
C(g)=\sum_{a\in g}C_a,
\]

\[
E_s(g)=\sum_{a\in g}E_{isolated,a}-
       \sum_{b\in g}E_{dissociation,b}.
\]

Mixture properties are molecule-count-weighted sums. The catalog rejects a graph
whose configured total binding energy exceeds its isolated structural energy.

For structural identity, construction enumerates every permutation mapping a
new site index to an input site index. Each candidate is encoded as the atom-label
vector in new-site order followed by the complete upper-triangle bond-order
vector in `(0,1), (0,2), ..., (n-2,n-1)` order, including zeros for absent bonds.
The canonical encoding is the lexicographically smallest pair of vectors.
Canonical storage retains that atom vector and emits only nonzero bonds while
scanning the same upper triangle. This bounded algorithm, rather than input site
numbering or input bond-list ordering, defines graph equality in MLS-0. Bond-order
values remain part of the canonical encoding and therefore part of identity.

`CompoundId` applies 64-bit FNV-1a (offset basis
`14695981039346656037`, prime `1099511628211`) to the following canonical fields:
64-bit atom count, each 16-bit element value, 64-bit stored-bond count, then each
bond's 32-bit first index, 32-bit second index, and 8-bit order. Every integer is
fed least-significant byte first for exactly its declared width. This is a cache
encoding only; full canonical-graph comparison remains authoritative and a hash
collision is rejected.

A reaction extent `xi` is bounded by

\[
\xi_{max}=\min_{r}\left\lfloor\frac{n_r}{c_r}\right\rfloor,
\]

then reactant counts decrease and product counts increase by `coefficient * xi`.
`ReactionDefinition::apply` performs only this count update. `World::apply_reaction`
first requires zero element delta, computes the new derived inventory/properties,
and asks the packet store to replace structural state.

For an activation value `Ea * xi`, current behavior is a **threshold**:
`thermal_energy >= Ea * xi` must hold. The threshold is not consumed. The actual
structural-energy difference is debited from or credited to thermal energy, so
`structural + thermal` remains constant under the accepted replacement.

### Conservation law

For world-mediated reactions:

- the reaction element delta must be exactly zero;
- recomputed element inventory must equal the packet's prior inventory;
- recomputed mass must equal prior mass exactly; and
- structural-energy change is paired with the opposite thermal-energy change.

Heat capacity may change as composition changes; no temperature state currently
needs to be reconciled. Direct use of `ReactionDefinition::apply` outside `World`
does **not** enforce stoichiometric balance.

### Numerical/model approximation

- integer molecule counts and extents;
- additive atom properties and pair-bond structural energy;
- deterministic graph-isomorphism canonicalization by exhaustive site
  permutation, bounded to at most eight atom sites (`8!` candidates);
- disconnected graphs are rejected because this model has no explicit spatial
  complex representation; and
- at most one bond, with one order, may connect any pair of atom sites;
- configured reaction definitions, not generic dynamic bond rearrangement;
- externally selected extent, with no rate law or transport coupling; and
- all reaction occurs inside one packet.

This is a structural accounting scaffold, not yet the dynamic chemistry required
by the MLS specification. A finite reaction catalogue can become a hidden crafting
system if treated as the final model.

### Failure modes and open review items

- unknown element, compound, or bond rule;
- empty graph, more than eight atom sites, invalid site index, self-bond,
  zero-order bond, disconnected graph, or multiple bonds between one site pair;
- duplicate catalog definition or structural-hash collision;
- non-positive stoichiometric coefficient, empty side, negative extent, reactant
  overdraw, count overflow, or an unbalanced world reaction;
- configured binding energy greater than isolated energy;
- insufficient thermal energy for activation or structural-energy increase;
- factorial canonicalization cost is deliberately contained by the eight-site
  bound; raising the bound requires replacing or re-validating this algorithm;
- FNV-1a is a cache hash, not a cryptographic identity;
- activation threshold behavior has no kinetic interpretation and does not debit
  activation energy; and
- no implemented equilibrium, reversible reaction, catalyst, stochastic kinetics,
  spatial diffusion, or chemical timestep convergence.

### Mapped tests

- `G0.G4/stoichiometric_balance_and_random_extents`
- `G4/compound_identity_is_structural_not_named_material`
- `hard-contract/compound_identity_is_invariant_under_site_renumbering`
- `hard-contract/compound_identity_rejects_disconnected_molecular_graph`
- `hard-contract/compound_identity_rejects_parallel_bond_encodings`
- `hard-contract/compound_canonicalization_has_an_explicit_size_bound`
- `hard-contract/deterministic_replay_and_state_hash` exercises repeated world
  reaction application
- exact-reference six balanced definitions and 100,000 random extents

Current gaps include dedicated tests for bond-energy configuration, activation
threshold edges, graph-hash collision handling, heat-capacity changes, and
exception atomicity across a complete world reaction.

## 3. Material packet structure-of-arrays store

**Implementation:** `include/mls/packet_store.hpp`, `src/packet_store.cpp`.

### State variables

The store keeps parallel lanes for ID, generation, live flag, three position
components, three integration remainders, three momentum components, compound
mixture, element inventory, mass, heat capacity, structural/stored/thermal energy,
and optional bounded history. It also holds a monotonic next ID, live count,
ID-to-slot map, history limit, and kinetic-energy scale denominator.

`PacketSnapshot` derives kinetic energy on read. Packet history and handles are
audit/debug/ownership metadata; stepping does not read history. Erased slots are
marked dead and are not currently reused.

All mutation methods are private to `World`; production callers receive only the
const packet-store view exposed by `World::packets()`. A separately defined
test-only friend seam exercises raw SoA failure behavior without making those
operations part of the authoritative public transition ABI.

### Units

- position: length quanta;
- position remainder: untagged integer remainder for the momentum/mass ballistic
  quotient;
- momentum: momentum quanta;
- mass, heat capacity, and energy stores: corresponding fixed quanta;
- composition/inventory: integer molecule/element counts; and
- tick: unsigned operation/step index, not a configured physical time.

The configuration must make `momentum_raw / mass_raw` correspond to length quanta
per tick and must make
`momentum_raw^2 / mass_raw / kinetic_scale_denominator / 2` correspond to energy
quanta. The code checks positivity, not the physical consistency of that choice.

### Update laws

For each axis, an accepted ballistic tick requires a zero stored remainder and
`momentum_raw % mass_raw == 0`. It then advances position by the exact integer
quotient. A fractional displacement is rejected transactionally. This narrow
rule makes the point-state orbital-angular-momentum audit exact; it is not a
production integration scheme.

Kinetic energy is

\[
K=\left\lfloor\frac{
 \left\lfloor(p_x^2+p_y^2+p_z^2)/m\right\rfloor}
 {d}\right\rfloor/2
\]

using successive integer divisions and configured positive denominator `d`.

Other implemented transactions are:

- heat transfer: `thermal_from -= E`, `thermal_to += E`;
- channel conversion: debit one of stored/thermal and credit the other;
- actuated/dissipative central pair impulse: require
  `(r1-r2) x J == 0`, apply `p1 += J`, `p2 -= J`, pay a quantized kinetic increase
  from the chosen participant's stored energy, or irreversibly deposit a decrease
  as heat in the chosen participant;
- composition replacement: require exact inventory and mass equality, then pair
  structural-energy change with thermal energy; and
- boundary energy/momentum adjustment primitives for world-mediated ledger use.

### Conservation law

Accepted internal heat and channel transfers preserve total packet energy. The
accepted central point impulse preserves linear and orbital angular momentum
exactly and preserves total quantized energy by the stored/thermal correction.
Composition replacement preserves element
inventory, mass, and `structural + thermal` energy. Ballistic position advance
does not change any extensive total.

Packet creation, erasure, and boundary adjustment do not own a conservation
ledger. They are accepted only through the world's staged scenario/boundary
protocol. The test-only friend seam can deliberately bypass that protocol for
adversarial ledger tests but is not production API.

### Numerical/model approximation

- packets are point carriers without volume, deformation, stress, bonds between
  packets, or constitutive history;
- ballistic, force-free, exact-integer motion at an implicit one-tick interval;
- rejection of fractional displacement and quantized kinetic-energy flooring;
- heat amounts and impulses are selected by callers, not solved from gradients,
  contact, or fields;
- channel conversion is lossless and has no entropy/rate model; and
- sequential transaction order is authoritative except where commutation is
  separately demonstrated.

### Failure modes and open review items

- non-positive mass, empty structure, negative extensive stores, stale handle, or
  exhausted ID/generation; removed-packet history is available only through the
  audit-only `debug_history(PacketId)` path;
- arithmetic overflow while squaring momentum or updating state;
- heat/channel overdraw and insufficient stored energy for a kinetic increase;
- invalid energy source/sink not participating in the impulse pair;
- the test-only friend seam bypasses physical support and ledger policy by design;
- no spin/couple state exists, so non-central point impulses are rejected;
- the actuated/dissipative impulse scaffold is not conservative mechanics;
- quantized kinetic energy may produce resolution-sensitive collision economics;
- no physical timestep/refinement parameter, force integration, or stability
  analysis;
- bounded history drops oldest events and history-disabled runs retain none;
- raw test-seam store operations are not allocation-failure atomic; authoritative
  `World` operations stage them on a copy before commit; and
- creation/removal is representation control, not biological birth/death.

### Mapped tests

- `G0.G1/packet_heat_transfer_closes_energy_and_rejects_overdraw`
- `G0.G1.G2/packet_momentum_exchange_closes_momentum_and_energy`
- `G0/fixed_point_arithmetic_rejects_overflow`
- `adversarial/independent_update_order_commutes`
- `adversarial/interacting_update_order_dependence_is_explicit`
- `adversarial/tick_batching_is_exact_but_not_a_convergence_claim`
- `G5/adversarial_rational_off_axis_rotation_preserves_ballistic_invariants`
- `hard-contract/deterministic_replay_and_state_hash`
- `adversarial/all_boundary_channels_round_trip_through_one_ledger`
- `adversarial/failed_step_overflow_preserves_tick_and_state`
- `hardening/abi/world_exposes_only_const_packet_store`, plus configure-time
  negative compile probes for creation, heat transfer, and boundary momentum
- `hardening/angular/noncentral_equal_opposite_impulse_counterexample`
- `hardening/angular/accepted_pair_transition_requires_central_impulse`
- `hardening/angular/actuated_dissipative_impulse_cycle_is_not_conservative_mechanics`
- `hardening/angular/ballistic_step_accepts_only_exact_displacement_and_preserves_L`
- `hardening/angular/cross_product_overflow_is_rejected`
- `hardening/timestep/impulse_phase_within_a_tick_changes_position`
- `hardening/timestep/no_dimensioned_refinement_claim_exists`

Current gaps include stale-handle/ID exhaustion, negative momentum motion across
many mass values, wider resolution sweeps for quantized-energy economics beyond
the completed closed-cycle witness, bounded-history eviction, and failure
atomicity under allocation or other non-arithmetic exceptions.

## 4. Sparse voxel control-volume index

**Implementation:** `include/mls/sparse_grid.hpp`, `src/sparse_grid.cpp`.

### State variables

- positive voxel-edge length;
- ordered map from signed integer `VoxelCoord{x,y,z}` to `VoxelCell`;
- per cell: live packet handles and an optional diagnostic fixed-width extensive
  total; and
- a private disposable packet-snapshot grouping used only for diagnostic
  aggregation.

This entire structure is disposable derived state. `PacketStore` is authoritative.

### Units

Voxel edge and packet position use the same length quantum. Coordinates and packet
counts are dimensionless integers. Cell totals use the packet quantity/count units.

### Update law

For each axis,

\[
cell_i=\left\lfloor position_i/voxelEdge\right\rfloor,
\]

including mathematical-floor behavior for negative positions. `rebuild` clears
the prior map, snapshots every live packet, assigns it to one point cell, and sums
its diagnostic extensive state when that cell's true result fits the reporting
range. `aggregate` refolds requested packet snapshots. The grid exposes no
physical-locality predicate; candidate indexing and interaction authorization
are deliberately separate.

### Conservation law

An authoritative world total folds `PacketStore` snapshots directly, independent
of voxel groups. Signed linear/angular components use a cancellation-safe order,
so an intermediate cell or packet order cannot overflow when the final total is
representable. Grid aggregation is diagnostic only; it never becomes packet
state, authorizes a transition, supplies reactions, or defines the world ledger.
Rebuilding therefore cannot itself move, create, merge, or transform matter.

### Numerical/model approximation

- nearest containing-cell assignment of a point packet;
- no particle-to-grid interpolation or grid-to-particle transfer;
- no MPM mass/momentum solve, pressure, heat, chemistry, or field state;
- a full ordered-map rebuild rather than sparse bricks or incremental updates;
- no sleep, page, refinement, local-time-step, or candidate-neighbor mechanism;
  and
- fixed-width per-cell totals may be unavailable when the cell result is outside
  range, without rejecting an otherwise representable authoritative world total.

### Failure modes and open review items

- any future candidate-neighbor implementation must be a conservative superset of
  the independent physical-support predicate;
- duplicate coordinates passed to `aggregate` are rejected rather than counted
  repeatedly;
- extensive aggregation can invent chemical/mechanical affordances and therefore
  must remain observational;
- large numbers of occupied cells incur ordered-map and full-rebuild cost;
- cell packet ordering follows packet snapshot/slot ordering and is not specified
  as a future parallel reduction order; and
- no benchmark yet establishes isotropy or convergence beyond limited integer
  rotation/translation scaffolds.

### Mapped tests

- `G1/sparse_grid_hierarchical_extensive_aggregation`
- `G7/coarse_graining_false_affordance_counterexample`
- `adversarial/uniform_grid_translation_preserves_extensive_outcomes`
- `G5/proper_cubic_rotation_equivariance_scaffold`
- `G5/adversarial_rational_off_axis_rotation_preserves_ballistic_invariants`
- `hardening/support/voxel_membership_neither_authorizes_nor_rejects_interaction`
- `hardening/support/eligibility_is_invariant_across_fractional_voxel_phases`
- `hardening/grid/diagnostic_cell_overflow_cannot_gate_authoritative_totals`

These tests do not establish MPM behavior, transport accuracy, arbitrary-angle
isotropy, or safe coarse graining.

## 5. Conservation ledger and boundary ports

**Implementation:** `include/mls/ledger.hpp`, `src/ledger.cpp`, and boundary
orchestration in `World`.

### State variables

- `baseline`: extensive element, mass, structural/stored/thermal/kinetic energy,
  linear momentum, orbital angular momentum, and packet-count totals at the selected reference state;
- `boundary`: signed net element, mass, total-energy, linear-momentum, and
  orbital-angular-momentum ingress since
  the baseline (`ingress > 0`, `egress < 0`); and
- `ConservationReport`: exact error values and booleans for elements, mass, total
  energy, linear momentum, and orbital angular momentum.

The current audit does not compare packet count or individual energy channels,
although those values exist in baseline totals.

### Units

Ledger entries use the same exact element counts, mass quanta, energy quanta,
momentum quanta, and derived length-times-momentum quanta as packets. There is no
tolerance or floating residual in this reference ledger: an audited error must
equal integer zero.

### Update and audit law

For each audited quantity `Q`:

\[
Q_{expected}=Q_{baseline}+Q_{boundary},\qquad
error_Q=Q_{current}-Q_{expected}.
\]

Material ingress/egress rejects negative extensive amounts, then records its
element inventory, mass, total energy, linear momentum, and orbital angular
momentum together. Energy-only ports record signed changes. A boundary point
impulse records `J`, `r x J`, and the corresponding quantized kinetic-energy
change in one staged world candidate.

`World` applies ledger and packet changes to a complete candidate world and
commits only after rebuild/audit. Introduction and extraction are
scenario/open-boundary ports, not material-agent operations. Baseline reset clears
all accumulated boundary net values and is likewise scenario authority.

### Conservation law

An audit passes iff current element inventories, mass, total energy, linear
momentum, and orbital angular momentum all exactly equal baseline plus signed
boundary net. Internal energy may move
between structural, stored, thermal, and kinetic channels without changing the
audited total.

### Numerical/model approximation

- global exact reconciliation, not a spatially resolved transaction ledger;
- one net boundary accumulator, not named reservoirs or per-event double entries;
- no spin/couple, charge, field source, entropy, surface energy, or numerical
  residual accounting; and
- no tolerance model because current arithmetic is integral.

### Failure modes and open review items

- the non-production test friend can bypass the ledger so adversarial corruption
  remains testable; production mutation is private to staged `World` operations;
- recording an incorrect sign or amount can make a physical error appear closed;
- no transaction ID ties a local debit to a credit;
- cancellation in the global net can hide large opposite local errors;
- total-energy closure can hide an incorrect channel conversion;
- baseline reset can legitimize an already corrupted state if scenario authority
  invokes it without a prior successful audit;
- packet count/identity changes are not audited (numerical packet split/merge
  would require separate provenance); and
- the raw test-only packet-store seam remains outside the staged world transaction.

### Mapped tests

- `G0.G1.G3/unified_ledger_closes_internal_and_boundary_energy`
- `adversarial/unauthorized_material_duplication_and_loss_are_detected`
- `adversarial/all_boundary_channels_round_trip_through_one_ledger`
- `adversarial/zero_state_and_zero_tick_are_stable`
- `adversarial/failed_step_overflow_preserves_tick_and_state`
- `hard-contract/deterministic_replay_and_state_hash`
- exact-reference 100,000 energy-ledger cases

Current gaps include wrong-sign injection, baseline-reset misuse, local
transaction reconciliation, spin/couple accounting, multiple named reservoirs, and
direct-store exception recovery.

## 6. World orchestration and physical-state hash

**Implementation:** `include/mls/world.hpp`, `src/world.cpp`.

### State variables

- `WorldConfig`: voxel edge, positive physical interaction radius, positive
  kinetic-energy scale denominator, positive dimensioned physical timestep,
  rational seconds/time-quantum scale, rational raw momentum/mass/time-to-length
  bridge, packet history limit, and audit-after-each-operation flag;
- unsigned ballistic-step sequence `tick` and distinct signed fixed-point physical time;
- immutable-by-interface element catalog and compound registry after construction;
- packet store, disposable sparse grid, and conservation ledger; and
- no random stream, renderer, observer, agent, reward, or semantic world state.

`MaterialSeed` supplies boundary position, momentum, composition, stored energy,
and thermal energy. Inventory, mass, heat capacity, and structural energy are
derived rather than accepted from the caller.

### Units

The world inherits all fixed quanta above. One call to `step()` applies the
configured positive `Time` timestep and increments the independent `Tick`
counter once. Seconds per time quantum and the momentum/mass/time-to-length raw
bridge are explicit rational configuration. `voxel_edge` maps position quanta
to disposable control-volume indices; `interaction_radius` defines independent
spherical point support; the kinetic denominator maps mass/momentum raw values
to the reference energy convention.

### Update law

- constructor validates every registered compound against the element/bond
  catalog, builds an empty grid, and establishes an empty baseline;
- every mutating world operation first copies the complete reference world,
  applies packet/grid/ledger changes to that candidate, and commits by no-throw
  move assignment only after rebuild and any configured audit succeed;
- material boundary ports derive packet properties and pair packet creation or
  removal with ledger ingress/egress inside that candidate;
- heat and actuated/dissipative central-impulse operations require packet
  positions inside the configured spherical support, delegate to the packet
  store, rebuild the grid, and optionally audit;
- energy conversion and balanced single-packet reaction delegate similarly;
- energy/boundary-point-impulse exchange precomputes the linear, angular, and
  energy ledger delta, mutates the
  candidate packet, rebuilds, and optionally audits; and
- each step advances physical time by the configured exact timestep, increments
  the separate tick, advances every live packet by an exactly representable
  dimensioned ballistic displacement, rebuilds the grid, and optionally audits.

No force, contact, thermodynamic transport, reaction scheduling, or physical field
is autonomously evaluated by `step`.

### Conservation law

Every world-mediated internal transaction is intended to preserve element
inventory, mass, total energy, linear momentum, and orbital angular momentum.
Every open-boundary transaction is
paired with the signed ledger delta. Arithmetic, allocation, rebuild, or audit
failure before commit leaves the original world unchanged. With audit mode
enabled, a failed candidate audit raises an error; with it disabled, callers must
audit explicitly.

The physical-support guard is a modeling constraint, not a conservation law.

### Physical-state hash law

The 64-bit FNV-1a hash includes:

- tick, physical time, voxel edge, interaction radius, kinetic-energy scale
  denominator, timestep, and both explicit rational unit scales;
- ordered element properties and bond rules;
- compound IDs, canonical atom sites, and canonical bonds; and
- every live packet's position, integration remainder, momentum, mass, heat
  capacity, structural/stored/thermal energy, and compound counts.

Packet word vectors are sorted before hashing, so packet slot/ID order is excluded
while multiplicity remains. Kinetic energy and element inventory are omitted
because they are derived. Packet IDs, generations, histories, grid cells, ledger
baseline/boundary state, audit flag, and history limit are intentionally omitted.

The result is a deterministic physical-state regression fingerprint, not a
cryptographic digest, checkpoint, audit-evidence hash, or proof of equivalence.

### Numerical/model approximation

- sequential deterministic reference operations on checked integers;
- exact spherical point support without a smooth kernel, packet extent, or contact;
- dimensioned, exactly representable ballistic stepping without force integration;
- whole-grid rebuild after operations;
- full-world copy staging on every mutating operation, deliberately favoring
  exception atomicity over production performance;
- FNV-1a 64-bit regression hash with finite collision probability; and
- a separate canonical v2 checkpoint with an explicit physics-ABI version;
  its FNV trailer detects accidental corruption but provides no cryptographic
  authenticity.

### Failure modes and open review items

- public C++ boundary and baseline methods rely on API/policy separation; the type
  system does not yet issue scenario-only capabilities;
- disabling automatic audit permits an invalid state to persist until explicit
  audit;
- the raw test-only packet-store seam is not covered by world-level copy staging,
  and debug-history allocation failure is not fault-injection tested;
- the physical-support cutoff is discontinuous at its radius and has not been
  validated as a kernel;
- the hash omits ledger state, so equal physical hashes can have different audit
  histories or expected baselines;
- FNV collisions are possible and hashes are not tamper evidence;
- canonical v2 roundtrip and restart are tested, but version migration and
  backend replay remain unimplemented; and
- deterministic replay in present unit tests does not establish determinism under
  future parallel/GPU reduction, different compilers, or changed laws.

### Mapped tests

- `hard-contract/camera_and_renderer_invariance`
- `hard-contract/deterministic_replay_and_state_hash`
- `adversarial/all_boundary_channels_round_trip_through_one_ledger`
- `adversarial/failed_boundary_ingress_preserves_world_state`
- `adversarial/zero_state_and_zero_tick_are_stable`
- `adversarial/failed_step_overflow_preserves_tick_and_state`
- `adversarial/independent_update_order_commutes`
- `adversarial/interacting_update_order_dependence_is_explicit`
- `adversarial/uniform_grid_translation_preserves_extensive_outcomes`
- `G5/adversarial_rational_off_axis_rotation_preserves_ballistic_invariants`
- `adversarial/tick_batching_is_exact_but_not_a_convergence_claim`
- `hardening/abi/world_exposes_only_const_packet_store`
- `hardening/angular/boundary_point_impulse_accounts_for_orbital_angular_momentum`
- `hardening/angular/boundary_cross_overflow_rejects_whole_transition`
- `hardening/timestep/physical_dt_is_configured_not_passed_as_Tick`
- `time/physical_clock_is_dimensioned_and_not_Tick`
- `time/dt_dt2_dt4_agree_at_a_common_exact_physical_horizon`
- `time/invalid_scales_and_fractional_steps_reject_transactionally`
- `time/clock_and_displacement_overflow_reject_whole_batch`
- all `checkpoint/` canonical, replay, golden, and corruption cases
- the complete angular transition mapping in
  [point-interaction angular momentum](angular-momentum-contract.md)
- the grid-phase, rotation, edge/corner, extreme-coordinate, and voxel-authority
  mapping in [physical interaction support](physical-support-contract.md)
- `mls_headless` is an executable audit demonstration, not a test of physical
  validity

## 7. Center-only consistent projection laboratory

**Implementation:** `include/mls/projection_foundation_lab.hpp` and
`src/projection_foundation_lab.cpp`. This is an experimental reference layer,
not authoritative continuum mechanics and not a promoted transfer scheme.

### State variables

Persistent experimental state is limited to:

- `CenterParticle`: stable ID, exact positive mass quanta, binary64 center
  position, and binary64 center velocity;
- `ProjectionLabState`: transfer configuration, exact physical-time scale,
  exact elapsed time quanta, and canonically ordered center particles; and
- no persistent grid, mass matrix, RHS, factorization, solver iterate, affine
  or polynomial mode, spin, correction field, or numerical-energy reservoir.

`ProjectionSystem` is a deterministic transient reconstruction containing
ordered grid indices/positions, per-particle basis stencils, binary64 particle
masses, lumped nodal mass `D`, sparse consistent mass rows `M`, and RHS `q`.
It is builder-created and immutable to callers: audit code receives const
accessors, but cannot mutate `M`, `q`, `D`, or stencils independently of the
center state from which they were derived. It is absent from checkpoints.

### Units

- center position and grid spacing/origin: metres;
- center and grid velocity: metres per second;
- exact particle mass: signed positive integer quanta, with configured
  kilograms per quantum;
- `M` and `D`: kilograms;
- `q`: kilogram-metres per second;
- exact clock: unsigned time quanta with an explicit rational seconds/quantum
  scale; and
- center kinetic energy and the consistent-grid `q^T v / 2` diagnostic:
  joules.

The binary64 timestep must agree with the exact quantum count and scale. It is
not inferred from `Tick`.

### Update law

For `S_pi=N_i(x_p)` on the complete quadratic B-spline stencil:

\[
M=S^TWS,\qquad q=S^TWV,\qquad
D_{ii}=\sum_jM_{ij}.
\]

Active nodes are exactly the union of nonzero stencil weights and are ordered
lexicographically; particles are ordered by ID. The paths are:

- lumped/PIC: `v=D^-1 q`;
- full consistent: unregularized deterministic PCG solution of `Mv=q`, after
  structural and numerical rank/condition gates; and
- FMPM(1–4): the audited 2026 incremental recurrence
  `delta_1=D^-1q`, `delta_l=(I-D^-1M)delta_(l-1)`,
  `v_k=sum_l delta_l`.

All paths reconstruct `V'=Sv`. A successful physical-time lab step then uses

\[
x_p'=x_p+\tfrac12\Delta t(V_p+V_p'),
\]

stores `V_p'`, advances the exact clock, and discards the grid. A failed full
solve leaves center state and clock unchanged.

The experimental checkpoint is canonical little-endian center state with an
FNV-1a corruption trailer. It deliberately excludes every transient transfer
and solver value and does not change the authoritative World checkpoint ABI.

### Conservation and algebraic laws

- exact integer particle mass is unchanged by every successful and failed
  projection path;
- full normal-equation reconstruction preserves center linear momentum under
  partition of unity and fixed-position orbital angular momentum under linear
  reproduction;
- finite FMPM preserves linear momentum in exact algebra but has no generic
  orbital-angular invariant; its angular error is measured rather than
  corrected;
- `q-Mv_k=D delta_(k+1)` is an FMPM implementation identity; and
- affine full-mass recovery additionally requires an accurate unique solve.

No generic kinetic-energy conservation law is claimed. Projection energy
change and the consistent-grid `q^T v / 2` quantity are numerical diagnostics
only. For an exact full solve the latter also equals `v^T M v / 2`; that
identity is not assumed for PIC or finite FMPM.

### Numerical approximation

- binary64 assembly and reconstruction with long-double scalar reductions in
  selected norms/dots;
- deterministic serial sparse maps and PCG with lumped Jacobi preconditioning;
- complete symmetric Jacobi spectra for bounded small-system condition
  estimates, with Cholesky pivots retained only as floating rank evidence;
- explicit off-diagonal convergence checks for the dense eigen diagnostic,
  with an unresolved spectrum failing closed;
- at most 64 deterministic Lanczos steps for larger raw/preconditioned spectral
  estimates; these estimates report rank as unknown and are explicitly not
  certificates;
- exact integer mass/clock and byte-exact center-only checkpoint replay; and
- no regularization, pseudoinverse, lumped fallback, post-correction, parallel
  reduction, or numerical-loss-to-heat conversion.

### Failure modes and open review items

- active-node count above particle count proves structural rank deficiency,
  but the converse does not prove full rank;
- finite Lanczos/Ritz estimates can miss extreme modes, so a reported large
  system condition is diagnostic rather than certified and a solved status is
  not a nonsingularity proof;
- normal equations square the sampling operator's condition and PCG may
  break down, hit its iteration limit, or meet residual tolerance despite an
  imperfect condition estimate;
- FMPM can run when the full matrix is singular, but such a row has no eligible
  full-reference distance and cannot be promoted on plausibility;
- quadratic grid support is a projection basis, not permission for physical
  interaction;
- direct `V'=Sv` is the MLS experimental reconstruction, not Love–Sulsky's
  incremental Eq. (32);
- checkpoint FNV is accidental-corruption detection, not authentication;
- the Python evidence validator independently checks schema and cross-table
  consistency but does not independently recompute floating trajectories;
- the outer evidence seal detects mutation, omission, unexpected files, and
  disagreement between two full runs, but is not a cryptographic signature;
  and
- passing the unit suite establishes software contracts, not physical validity
  or continuum convergence.

### Mapped tests

- `projection foundation center state has no hidden persistent modes`
- `projection assembly is canonical under input permutation`
- `projection full mass recovers affine field and agrees with dense comparator`
- `projection full static cycle preserves center linear and orbital moments`
- `projection PIC and FMPM1 are identical and translation is reproduced`
- `projection FMPM recurrence satisfies residual identity at every frozen order`
- `projection production assembly and FMPM recurrence match rational cross-wire`
- `projection smooth nonaffine field is not falsely claimed exact`
- `projection singular systems and solver limits fail closed`
- `projection rejects invalid zero duplicate overflow and nonfinite inputs`
- `projection failed steps preserve unsorted center state byte-for-byte`
- `projection trapezoid step uses exact clock and has no numerical energy ledger`
- `projection checkpoint is canonical corruptible and excludes solver state`
- `projection checkpoint restart reproduces continued center evolution exactly`
- independent exact-rational full/FMPM oracle and its canonical digest
- projection full-family schema audit and bundle-validator mutation regression
- projection v2 physical-scale relation and re-manifested mutation checks
- outer evidence-seal deterministic-create and mutation regression

The final co-refinement, phase/orientation, particles-per-cell, compiler, and
independent evidence bundle remains necessary before any research-candidate
decision.

## 8. Projection exactness and Gram-nullspace diagnostic

**Implementation:** `include/mls/projection_exactness_nullspace_lab.hpp` and
`src/projection_exactness_nullspace_lab.cpp`. This is a read-only diagnostic
layer over the center-only projection laboratory. It adds no transfer law,
force, persistent particle mode, physical update, or promotion path.

### State variables and units

Authoritative input remains packet ID, exact mass quanta, center position in
metres, center velocity in metres per second, the dimensioned grid
configuration, and exact physical-time quanta. All nodal affine witnesses,
PCG iterates, double-double values, QR factors, null vectors, and gradients are
transient. A scalar null mode is normalized to `1 m/s`; its sampled center
value is in `m/s`, the basis gradient is in `m^-1`, and the induced mode
velocity gradient is in `s^-1`. Matrix residuals are in `kg m/s`.

### Diagnostic law and accounting boundary

Before any solve, the layer constructs `g_i=A(t)x_i+b(t)` and evaluates
componentwise `Mg-q`, the registered vector particle-mass norm `Sg-V`,
partition of unity, linear reproduction, and derivative of
partition. The unchanged historical PCG control is then assessed separately
for its frozen legacy residual/threshold/termination status, independently
recomputed backward error, nodal forward error, and center reconstruction
error. A
complete-pivot double-double solve promotes the exact assembled binary64
`M,q` without altering either and exports every accepted pivot magnitude and
row/column order. Householder column-pivoted QR diagnoses
`sqrt(W)S`; each constructed mode is checked through `Mz`, `Sz`, solution
residual change, center reconstruction change, and
`G_p(z)=sum_i z_i grad N_i(x_p)`.

There is no physical transition to conserve. The exact checkpoint hash before
and after every diagnostic must be identical. Numerical residuals are never
converted into heat, stored energy, or another physical ledger channel.

### Numerical approximation and failure modes

- binary64 assembly; twofold/double-double reductions for the evidence
  witness, solve, and null-mode metrics, with separate long-double core
  diagnostic cross-checks;
- normwise solve backward error
  `||Mv-q||/(||M||_F||v||+||q||)` kept distinct from measured forward error;
- approximately 106-bit FMA double-double complete-pivot elimination with the
  preregistered rank threshold and no shift, node drop, or regularization;
- binary64 Householder CPQR of `sqrt(W)S` with deterministic node order and an
  explicitly numerical—not certified—rank threshold; and
- an independent exact-rational oracle over its two canonical synthetic
  fixtures; and a strict evidence validator that reconstructs exported C++
  systems and Decimal-solves both exported micro systems without importing
  C++ solver code.

Failure is preserved for an affine witness mismatch, nonfinite arithmetic,
old-PCG structural/breakdown/iteration outcomes, high-precision rank ambiguity,
an unresolved `Mz` or `Sz` mode, incomplete null-basis evidence, a
center-invisible but gradient-visible mode, or any
checkpoint/schema/manifest/repeatability disagreement. A residual-only pass is
never labeled an accurate solve. A witness-first stop is recorded as
`not_run_witness_failure`, not fabricated as a numerical failure. Every selected
nullspace system has a status row even when QR cannot construct modes. Phase
and orientation labels are retained for analysis; this lab preregisters no
generic cross-system equivalence gate between their null bases.

### Mapped tests

- Lean `consistentMass_is_gram_operator`
- Lean `consistentMass_kernel_eq_interpolation_kernel`
- Lean `consistentProjection_solutions_have_equal_reconstruction`
- `projection exactness analytic witness bypasses every solver`
- `projection solve diagnostics separate backward from forward error`
- `projection exactness high precision retains auditable hi lo solution`
- `projection high precision preserves rank-deficient evidence`
- `projection Gram QR exhibits center invisible gradient visible modes`
- `projection exactness basis derivative controls and invalid inputs`
- `projection exactness diagnostic policies fail closed`
- the independent exact/nullspace oracle and canonical digest
- the bundle-validator positive and mutation regression
- the outer-seal deterministic-create and mutation regression

The Lean statements cover finite exact-rational operators. Kernel equality
requires strictly positive particle masses, and solution reconstruction
equality is conditional on two supplied exact solutions of the same system;
neither assumes matrix invertibility. They do not connect to C++ binary64/QR
or prove gradient visibility. Their reported dependencies are only `propext`,
`Classical.choice`, and `Quot.sound`, with no project-defined axioms or proof
placeholders.

## 9. Mechanical-observability laboratory

**Implementation:** `include/mls/mechanical_observability_lab.hpp` and
`src/mechanical_observability_lab.cpp`. This is an isolated read-only
representation diagnostic, not a mechanics solver or material model.

### State variables and units

The canonical laboratory input contains stable packet ID, exact positive mass
quanta, binary64 center position in metres, binary64 test velocity in metres per
second, one support radius in metres, canonical generic pair-relation IDs, and
canonical ordered four-packet volume-relation IDs. Mass is checkpointed for
input identity but intentionally does not weight a kinematic observable.

Moments, neighbor caches, lookup-grid buckets, linearized operators, row norms,
QR factors, pivot traces, rigid generators, and null vectors are transient.
The corrected moment has units `m^2`, its numerator `m^2/s`, and its gradient
`1/s`. A central relation observes length rate in `m/s`. An ordered triple
product is in `m^3` and its rate in `m^3/s`.

### Diagnostic laws

For packet offset `r_pq=x_q-x_p` inside the explicit spherical support,

\[
w_{pq}=(1-\lVert r_{pq}\rVert^2/H^2)^2,\quad
M_p=\sum_qw_{pq}r_{pq}r_{pq}^T,
\]

\[
G_p(v)=\left[\sum_qw_{pq}(v_q-v_p)r_{pq}^T\right]M_p^{-1}.
\]

The candidate-B operator retains `vec(sym G_p)`; the full `G_p` exists only for
affine-reproduction tests. Singular, nonpositive, nonfinite, or condition-
rejected moments produce no partial operator.

For explicit relation `(i,j)`, candidate C uses the actual length Jacobian
`n_ij dot (v_j-v_i)`. Conditional candidate D concatenates those rows with the
multilinear derivative of the explicit oriented triple product
`det(x_j-x_i,x_k-x_i,x_l-x_i)`. Neither relation defines energy or force.

Every nonzero row is normalized before deterministic Householder column-
pivoted QR. The complete threshold null basis is projected against the sampled
translation/rotation range. A full-dimensional generic representation is
observable only if its kernel equals that rigid-motion range. Candidate A
retains the sealed quadratic-grid sampling/gradient quotient failure as a
negative control and never constructs a preferred grid lift.

### Conservation and accounting boundary

The lab performs no physical update. It changes no packet mass, position,
velocity, relation, energy, momentum, or clock. Canonical checkpoint bytes are
required to remain identical across all diagnostics. Rank residuals and hidden
modes are numerical evidence and cannot enter a thermal, structural, or other
physical ledger channel.

### Numerical approximation

- binary64 geometry and operators with long-double accumulation in selected
  norms, dot products, cross products, and determinant calculations;
- a deterministic binary64 Householder CPQR numerical rank estimate, never a
  rank certificate;
- row normalization, which preserves an exact kernel but changes singular-value
  scale and therefore remains part of the registered diagnostic;
- a three-by-three symmetric moment eigendiagnostic and explicit inverse with a
  fixed condition ceiling, no shift or pseudoinverse;
- exact-rational Python RREF controls for selected WLS, graph, rigid-motion, and
  volume-enrichment cases; and
- an exact-rational Lean finite central-rigidity operator and selected K4
  observability proof, without a connection theorem to binary64 CPQR.

The disposable spatial grid may only enumerate neighbors for comparison with a
brute-force Euclidean cutoff. It supplies no gradient, strain, deformation,
stress, or persistent state.

### Failure modes and open review items

- malformed or duplicate packet/relation identity, nonpositive mass/support,
  zero-length edge, repeated volume site, or nonfinite geometry;
- moment singularity, ill-conditioning, inverse residual, or affine-
  reproduction failure;
- zero/nonfinite operator row, ambiguous rank pivot, incomplete null basis, or
  excessive rigid/null residual;
- a resolved non-rigid kernel in an adequately connected ordinary 3D row;
- intentionally flexible sheet, filament, deleted, or underconnected topology
  incorrectly relabeled as a generic solid;
- finite translation/rotation objectivity, scale covariance, packet
  permutation, or lookup-phase mismatch;
- checkpoint mutation, schema mismatch, independent-oracle disagreement, or
  non-byte-identical repeated evidence; and
- affine reproduction alone can hide corrected-gradient hourglass modes, while
  central-distance observability does not establish arbitrary-material
  constitutive capability.

No stabilization penalty, preferred null representative, regularization,
hidden affine mode, or unaccounted auxiliary state can turn a failure into a
pass.

### Mapped tests

- `mechanical observability corrected WLS reproduces affine fields`
- `mechanical observability WLS is deterministic and ignores mass`
- `mechanical observability WLS exposes singular lower dimensional support`
- `mechanical observability tetrahedron bond kernel is exactly rigid numerically`
- `mechanical observability objective volume removes planar square floppy mode`
- `mechanical observability affine relational predictions match operators`
- `mechanical observability finite relations are rigid objective`
- `mechanical observability preserves intentional and degenerate modes`
- `mechanical observability rejects malformed topology and state`
- `mechanical observability row and rank diagnostics fail closed`
- `mechanical observability checkpoint is canonical and diagnostics read only`
- independent Fraction oracle, bundle-validator mutation suite, repeated
  producer comparison, and outer-seal mutation suite
- Lean central matrix/operator, rigid-kernel, exact K4, and explicit
  missing-relation non-observability theorems

Passing these software checks cannot establish physical validity, a
constitutive response, or eligibility to begin mechanics.

## 10. Constitutive-expressivity laboratory

**Implementation:** `include/mls/constitutive_expressivity_lab.hpp` and
`src/constitutive_expressivity_lab.cpp`. This is an isolated, read-only energy
experiment over the retained central-distance relations. It is not an
authoritative material model, force API, stress update, or dynamics solver.

### State variables and units

Inputs are stable packet labels, reference/current packet centers in metres,
explicit undirected relation endpoints, positive dimensionless relation
weights, and positive experimental coefficients in J/m2. Linearized and
finite extension coordinates are in metres. The relation-space operator `H`
has units J/m2 and its explicit Gram factor `L` has units sqrt(J)/m.

`H`, `L`, local weighted length moment, dilatational projection, deviatoric
extension, energy, packet Hessian, and all spectra are transient laboratory
results. They are not packet fields or checkpointed kinematic history.

### Energy laws

The pair-separable negative control is

```
E_pair = 0.5 sum_a h_a e_a^2.
```

For each packet's one-relation-star, the selectable collective diagnostic is

```
m_i=sum_a w_a l_a^2, q_i=sum_a w_a l_a e_a, d_i=q_i/m_i,
E_i=0.5 A_i q_i^2/m_i + 0.5 B_i sum_a w_a(e_a-d_i l_a)^2.
```

All local quantities are rebuilt from current/reference distance relations on
every call. An off-diagonal relation-space coupling is legal only when the two
relations share a packet. The implementation emits `H=L^T L` and the direct
energy-observability operator `L R`; forming `K=R^T H R` is a verification-only
Hessian path. No operation applies `-grad E` to a packet.

### Conservation and accounting boundary

There is no state transition, clock, force, work transaction, damping, or
ledger write. The scalar output is a candidate stored-energy evaluation for a
supplied displacement/configuration, not energy created by the world. A
floating residual cannot be converted to heat or any other physical channel.

Actual-length evaluation is translation and proper-rotation objective. With
fixed coefficients in J/m2, a positive common similarity scale `s` applied to
both reference and current geometry gives the explicitly registered finite-
graph dimension law `E -> s^2 E`. Packet-ID and input ordering cannot affect
the result.

### Numerical approximation

- binary64 positions, extensions, matrices, and finite-length evaluation;
- long-double accumulation for quadratic forms;
- explicit Gram-factor construction for nonnegative sum-of-squares energy;
- direct `L R` analysis to avoid squaring conditioning merely to compare
  energy and relation kernels;
- two independently shaped symmetric bulk cubatures and six Kelvin strain
  directions for tangent reconstruction; and
- an independent exact `Fraction`/`Q(sqrt(2))` oracle for moments, Cauchy
  restriction, two-modulus maps, objectivity, scaling, and selected graph
  ranks.

No shift, regularization, pseudoinverse, surface correction, stiffness
restoration, or numerical stabilization is permitted. Removing a relation
removes its active terms; the registered `q^2/m` law makes uniform-dilation
energy decrease with surviving weighted relation length rather than silently
restoring the missing response.

### Failure modes and tests

The evaluator rejects duplicate/missing endpoints, nonpositive/nonfinite
weights or coefficients, zero/nonfinite reference lengths, incompatible
extension ordering/reference lengths, and nonfinite energy. Scientific gates
also fail on a broken isotropic moment control, pair response outside its
registered Cauchy ratio, bulk/shear cross coupling, nonpositive relation
energy, nonlocal `H`, a new non-rigid energy zero mode, removal of an existing
floppy mode, objectivity/scale/ID/permutation mismatch, or independent-oracle
disagreement.

Mapped tests include the two pair Cauchy controls, both four-ratio collective
bulk/shear inventories, six-by-six Kelvin tangents, deleted-relation response,
K4 and missing-edge kernel controls, finite objectivity/similarity/ID tests,
malformed-input fail-closed cases, exact-oracle deterministic verification,
and exact-oracle mutation rejection. Passing them establishes only the
registered algebraic expressivity claim; it cannot promote mechanics or
dynamics.

## Review rule

All records (the ten numbered records here plus the dedicated physical-support,
time/checkpoint, transfer-lab, and angular contracts) must be updated when their
public state, operation, formula, or test mapping changes. Changes to point
interaction, boundary, or ledger semantics must also update the cross-cutting
angular-momentum contract.
A release review must compare these documents to the actual headers and
implementation and must list unmapped behaviors. Use the
[publication/review evidence template](review-evidence-template.md) for every
claim-bearing run.
