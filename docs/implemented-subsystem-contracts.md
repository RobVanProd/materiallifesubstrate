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
| Packet SoA | Persistent live handles, exact extensive stores, ballistic integer motion, explicit pair transfers. | Forces, contact, deformation, damage, fracture, constitutive material history. |
| Sparse grid | Disposable point-to-voxel index and exact extensive aggregation. | MPM scatter/gather, fields, pressure, interpolation, sparse bricks, sleeping/paging. |
| Ledger/boundaries | Baseline-plus-signed-boundary audit for elements, mass, total energy, and momentum. | Angular momentum, charge, transaction IDs, per-reservoir identities, numerical tolerances. |
| World/hash | Deterministic orchestration, locality guard, audit hooks, order-independent packet-state hash. | Autonomous physics scheduling, checkpoint serialization, renderer, agents, ecology. |

The implemented program therefore does **not** satisfy Gates 2–15. It supplies
reference accounting mechanisms and adversarial fixtures used on the path toward
Gates 0–1, plus limited scaffolds relevant to Gates 3–5 and 7.

## 1. Quantities and vectors

**Implementation:** `include/mls/quantity.hpp`.

### State variables

- `Scalar`: signed 64-bit integer (`int64_t`).
- `Quantity<DimensionTag>::value_`: one scalar count of caller-defined quanta.
- Tags: `Length`, `Mass`, `Time`, `Velocity`, `Momentum`, `Energy`,
  `Temperature`, and `HeatCapacity`.
- `Vector3<Q>`: component-wise `x`, `y`, and `z` quantities; currently used for
  position, velocity type declarations, and momentum.

### Units

Each raw value is a fixed-point quantum count. The conversion from one raw count
to a physical unit is scenario configuration and is not stored in `Quantity`.
The current world directly configures a voxel-edge length and an integer kinetic-
energy scale denominator. It does not contain a general unit registry.

`Time`, `Velocity`, and `Temperature` are defined types but are not used by the
current stepping law. A `Tick` is a separate unsigned step counter. Consequently,
the implementation does not yet establish relationships such as
`velocity = length / time` or `temperature = thermal energy / heat capacity`.

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
- `CompoundGraph`: ordered atom-site vector plus normalized, sorted bonds. Each
  bond stores two site indices and a positive 8-bit order.
- `CompoundId`: 64-bit FNV-1a cache key over atom-site order and normalized bond
  topology.
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
- atom-site ordering is part of identity; full graph-isomorphism canonicalization
  is not implemented;
- configured reaction definitions, not generic dynamic bond rearrangement;
- externally selected extent, with no rate law or transport coupling; and
- all reaction occurs inside one packet.

This is a structural accounting scaffold, not yet the dynamic chemistry required
by the MLS specification. A finite reaction catalogue can become a hidden crafting
system if treated as the final model.

### Failure modes and open review items

- unknown element, compound, or bond rule;
- empty graph, invalid site index, self-bond, zero-order bond, or duplicate bond;
- duplicate catalog definition or structural-hash collision;
- non-positive stoichiometric coefficient, empty side, negative extent, reactant
  overdraw, count overflow, or an unbalanced world reaction;
- configured binding energy greater than isolated energy;
- insufficient thermal energy for activation or structural-energy increase;
- graph-isomorphic compounds with different atom-site order receive different
  keys unless producers canonicalize them;
- FNV-1a is a cache hash, not a cryptographic identity;
- activation threshold behavior has no kinetic interpretation and does not debit
  activation energy; and
- no implemented equilibrium, reversible reaction, catalyst, stochastic kinetics,
  spatial diffusion, or chemical timestep convergence.

### Mapped tests

- `G0.G4/stoichiometric_balance_and_random_extents`
- `G4/compound_identity_is_structural_not_named_material`
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

For each axis, Euclidean division writes

\[
p=q m+r,\qquad 0\le r<m.
\]

One tick advances integer position by `q` plus any carry from `old_remainder + r`
and stores the new remainder. With constant mass and momentum, this retains the
sub-position-quantum residue of ballistic motion.

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
- pair impulse: `p1 += J`, `p2 -= J`; pay a quantized kinetic increase from the
  chosen participant's stored energy or deposit a decrease as heat in the chosen
  participant;
- composition replacement: require exact inventory and mass equality, then pair
  structural-energy change with thermal energy; and
- boundary energy/momentum adjustment primitives for world-mediated ledger use.

### Conservation law

Accepted internal heat and channel transfers preserve total packet energy. Pair
impulse preserves total momentum exactly and preserves total quantized energy by
the stored/thermal correction. Composition replacement preserves element
inventory, mass, and `structural + thermal` energy. Ballistic position advance
does not change any extensive total.

`PacketStore::create`, `erase`, and the boundary adjustment methods do not own a
conservation ledger. They are conservative only when invoked through the world's
scenario/boundary protocol. Direct use is intentionally useful for adversarial
tests but is not an agent ABI.

### Numerical/model approximation

- packets are point carriers without volume, deformation, stress, bonds between
  packets, or constitutive history;
- ballistic, force-free motion at an implicit one-tick interval;
- component position remainder but quantized kinetic-energy flooring;
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
- grid-scale locality is absent when callers bypass `World`;
- quantized kinetic energy may produce resolution-sensitive collision economics;
- no physical timestep/refinement parameter, force integration, or stability
  analysis;
- bounded history drops oldest events and history-disabled runs retain none;
- store operations are not a substitute for transactional world/checkpoint
  recovery under allocation or unexpected exceptions; and
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

Current gaps include stale-handle/ID exhaustion, negative momentum motion across
many mass values, quantized-energy exploit cycles, bounded-history eviction, and
failure atomicity under allocation or other non-arithmetic exceptions.

## 4. Sparse voxel control-volume index

**Implementation:** `include/mls/sparse_grid.hpp`, `src/sparse_grid.cpp`.

### State variables

- positive voxel-edge length;
- ordered map from signed integer `VoxelCoord{x,y,z}` to `VoxelCell`;
- per cell: live packet handles and exact aggregate element, mass, four energy-
  store, momentum, and packet-count totals.

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
its extensive state. `aggregate` sums requested cell totals. `face_local` accepts
the same cell or one of six face-adjacent cells (`Manhattan distance <= 1`).

### Conservation law

A complete rebuild contains each live packet once, so summing all cells must equal
a direct packet sum. Grid aggregation is extensive only; it never becomes packet
state and is never supplied to reactions. Rebuilding therefore cannot itself
move, create, merge, or transform matter.

### Numerical/model approximation

- nearest containing-cell assignment of a point packet;
- no particle-to-grid interpolation or grid-to-particle transfer;
- no MPM mass/momentum solve, pressure, heat, chemistry, or field state;
- a full ordered-map rebuild rather than sparse bricks or incremental updates;
- no sleep, page, refinement, or local-time-step mechanism; and
- locality approximated by cell identity/face adjacency, not physical distance or
  a support kernel.

### Failure modes and open review items

- interactions can change discontinuously at voxel boundaries;
- same/face-adjacent packets may be physically far apart, while diagonal packets
  may be arbitrarily close but rejected;
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

These tests do not establish MPM behavior, transport accuracy, arbitrary-angle
isotropy, or safe coarse graining.

## 5. Conservation ledger and boundary ports

**Implementation:** `include/mls/ledger.hpp`, `src/ledger.cpp`, and boundary
orchestration in `World`.

### State variables

- `baseline`: extensive element, mass, structural/stored/thermal/kinetic energy,
  momentum, and packet-count totals at the selected reference state;
- `boundary`: signed net element, mass, total-energy, and momentum ingress since
  the baseline (`ingress > 0`, `egress < 0`); and
- `ConservationReport`: exact error values and booleans for elements, mass, total
  energy, and momentum.

The current audit does not compare packet count or individual energy channels,
although those values exist in baseline totals.

### Units

Ledger entries use the same exact element counts, mass quanta, energy quanta, and
momentum quanta as packets. There is no tolerance or floating residual in this
reference ledger: an audited error must equal integer zero.

### Update and audit law

For each audited quantity `Q`:

\[
Q_{expected}=Q_{baseline}+Q_{boundary},\qquad
error_Q=Q_{current}-Q_{expected}.
\]

Material ingress/egress rejects negative extensive amounts, then records its
element inventory, mass, total energy, and momentum together. Energy-only and
momentum-only ports record signed changes;
world momentum exchange also records the corresponding change in quantized
kinetic energy.

`World` applies ledger and packet changes to a complete candidate world and
commits only after rebuild/audit. Introduction and extraction are
scenario/open-boundary ports, not material-agent operations. Baseline reset clears
all accumulated boundary net values and is likewise scenario authority.

### Conservation law

An audit passes iff current element inventories, mass, total energy, and momentum
all exactly equal baseline plus signed boundary net. Internal energy may move
between structural, stored, thermal, and kinetic channels without changing the
audited total.

### Numerical/model approximation

- global exact reconciliation, not a spatially resolved transaction ledger;
- one net boundary accumulator, not named reservoirs or per-event double entries;
- no angular momentum, charge, field source, entropy, surface energy, or numerical
  residual accounting; and
- no tolerance model because current arithmetic is integral.

### Failure modes and open review items

- direct packet-store boundary mutation bypasses the ledger and is detected only
  when audit runs;
- recording an incorrect sign or amount can make a physical error appear closed;
- no transaction ID ties a local debit to a credit;
- cancellation in the global net can hide large opposite local errors;
- total-energy closure can hide an incorrect channel conversion;
- baseline reset can legitimize an already corrupted state if scenario authority
  invokes it without a prior successful audit;
- packet count/identity changes are not audited (numerical packet split/merge
  would require separate provenance); and
- direct packet-store mutation remains outside the staged world transaction.

### Mapped tests

- `G0.G1.G3/unified_ledger_closes_internal_and_boundary_energy`
- `adversarial/unauthorized_material_duplication_and_loss_are_detected`
- `adversarial/all_boundary_channels_round_trip_through_one_ledger`
- `adversarial/zero_state_and_zero_tick_are_stable`
- `adversarial/failed_step_overflow_preserves_tick_and_state`
- `hard-contract/deterministic_replay_and_state_hash`
- exact-reference 100,000 energy-ledger cases

Current gaps include wrong-sign injection, baseline-reset misuse, local
transaction reconciliation, angular momentum, multiple named reservoirs, and
direct-store exception recovery.

## 6. World orchestration and physical-state hash

**Implementation:** `include/mls/world.hpp`, `src/world.cpp`.

### State variables

- `WorldConfig`: voxel edge, positive kinetic-energy scale denominator, packet
  history limit, and audit-after-each-operation flag;
- unsigned `tick`;
- immutable-by-interface element catalog and compound registry after construction;
- packet store, disposable sparse grid, and conservation ledger; and
- no random stream, renderer, observer, agent, reward, or semantic world state.

`MaterialSeed` supplies boundary position, momentum, composition, stored energy,
and thermal energy. Inventory, mass, heat capacity, and structural energy are
derived rather than accepted from the caller.

### Units

The world inherits all fixed quanta above. One call to `step()` is one implicit
ballistic tick. There is no physical timestep quantity. `voxel_edge` maps position
quanta to control-volume indices; the kinetic denominator maps mass/momentum raw
values to the reference energy convention.

### Update law

- constructor validates every registered compound against the element/bond
  catalog, builds an empty grid, and establishes an empty baseline;
- every mutating world operation first copies the complete reference world,
  applies packet/grid/ledger changes to that candidate, and commits by no-throw
  move assignment only after rebuild and any configured audit succeed;
- material boundary ports derive packet properties and pair packet creation or
  removal with ledger ingress/egress inside that candidate;
- heat and pair-momentum operations require packets in the same or face-adjacent
  voxel, delegate to the packet store, rebuild the grid, and optionally audit;
- energy conversion and balanced single-packet reaction delegate similarly;
- energy/momentum boundary exchange precomputes the ledger delta, mutates the
  candidate packet, rebuilds, and optionally audits; and
- each step increments the tick, advances every live packet ballistically by one
  integer tick, rebuilds the grid, and optionally audits.

No force, contact, thermodynamic transport, reaction scheduling, or physical field
is autonomously evaluated by `step`.

### Conservation law

Every world-mediated internal transaction is intended to preserve element
inventory, mass, total energy, and momentum. Every open-boundary transaction is
paired with the signed ledger delta. Arithmetic, allocation, rebuild, or audit
failure before commit leaves the original world unchanged. With audit mode
enabled, a failed candidate audit raises an error; with it disabled, callers must
audit explicitly.

The locality guard is a modeling constraint, not a conservation law.

### Physical-state hash law

The 64-bit FNV-1a hash includes:

- tick, voxel edge, and kinetic-energy scale denominator;
- ordered element properties and bond rules;
- compound IDs, ordered atom sites, and normalized bonds; and
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
- voxel face-locality instead of geometric support/contact;
- one-tick ballistic stepping without force integration;
- whole-grid rebuild after operations;
- full-world copy staging on every mutating operation, deliberately favoring
  exception atomicity over production performance;
- FNV-1a 64-bit regression hash with finite collision probability; and
- no checkpoint encoding or cross-version schema.

### Failure modes and open review items

- public C++ boundary and baseline methods rely on API/policy separation; the type
  system does not yet issue scenario-only capabilities;
- disabling automatic audit permits an invalid state to persist until explicit
  audit;
- direct `PacketStore` use is not covered by world-level copy staging, and
  debug-history allocation failure is not fault-injection tested;
- grid locality is discontinuous and resolution-dependent;
- the hash omits ledger state, so equal physical hashes can have different audit
  histories or expected baselines;
- FNV collisions are possible and hashes are not tamper evidence;
- no save/load round trip, version migration, backend replay, or independent hash
  implementation is tested; and
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
- `mls_headless` is an executable audit demonstration, not a test of physical
  validity

## Review rule

All six subsystem records must be updated when their public state, operation,
formula, or test mapping changes. A release review must compare this document to
the actual headers and implementation and must list unmapped behaviors. Use the
[publication/review evidence template](review-evidence-template.md) for every
claim-bearing run.
