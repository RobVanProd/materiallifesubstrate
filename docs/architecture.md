# Architecture and authoritative state contract

## Purpose

MLS is a mesoscale physical universe for testing whether composable material
laws can support life, ecology, learning, and cumulative external artifacts
without those outcomes being present in the engine API. It is not a literal
molecular model of Earth and it is not a game ontology with more detailed
graphics.

The fundamental split is:

```text
persistent material packets
          |
          v
 sparse voxel control volumes
  |       |       |       |       |
mechanics transport thermal chemistry fields
  \       |       |       |       /
          physical state
          /          \
   organisms       structures       <- observer descriptions only
          \          /
             ecology

Renderer reads snapshots. It never writes authoritative state.
```

## Hard decisions

| Question | MLS v0 decision | Consequence |
|---|---|---|
| Is a voxel a molecule or cell? | No. A voxel is a local control volume. | Crossing a cell boundary cannot replace a piece of matter with a new identity. |
| What carries matter and history? | Persistent Lagrangian material packets. | Composition, momentum, and material history follow matter. |
| How are local interactions solved? | Sparse Eulerian voxel bricks; an MPM-family transfer is a candidate, not a validated choice. | Packet/grid transfers must satisfy the ledger and convergence tests. |
| Is the target literal Earth physics? | No. Preserve selected causal balances through dynamic similarity. | Every scale transform declares which dimensionless groups it preserves and omits. |
| Is sparse allocation optional? | No. | Empty and uniform regions must not require a dense world allocation. |
| Can resolution follow the camera? | No. | Observation cannot change chemistry or mechanics. |
| Can v0 use lossy physics coarse-graining? | No. | Initial scaling uses sparse allocation, sleeping, exact paging, and local time stepping. |
| Can a reward or fitness API guide life? | No. | Selection must arise from persistence and reproduction under physical constraints. |
| Does the project begin with abiogenesis? | No. | MLS-1 may seed an engineered minimal cell and must say so. |
| Is UE5 authoritative? | No. | An engine may visualize or host interfaces, but it cannot define physical truth. |
| Is Warp authoritative? | No. | It may prototype kernels; state and laws must survive backend replacement. |
| Is a GPU backend authoritative? | No. | C++20 CPU/reference semantics and a portable state format define the contract. |

## Ontology

Only the following categories may be authoritative.

### Material packet

A packet has a stable identity and, at minimum:

- position, velocity, and mass derived from conserved constituents;
- non-negative inventory of virtual element types;
- compound/bond-graph state or references whose behavior is derived from that
  structure rather than a semantic material class;
- internal/thermal and chemical energy contributions;
- constitutive state needed by the chosen material model, such as deformation,
  damage, phase, or plastic history;
- optional physical charge or other explicitly conserved field source; and
- deterministic provenance sufficient to audit creation, split, merge, and
  exact paging operations.

A packet is a numerical carrier, not an atom, cell, organism, or rendered point.
Splitting and merging carriers may change discretization only when all extensive
state and required history are preserved.

### Sparse control volume

A voxel is an addressable local region used to accumulate packet contributions,
solve neighborhood interactions, and transfer changes back to packets. Grid
quantities are either derived scratch state or explicitly identified field state.
A voxel index has no biological or material meaning.

Sparse bricks may be allocated, slept, paged, or deallocated only through rules
that do not depend on the camera and do not discard authoritative information.
Sleeping and waking must be behaviorally identical to continuous integration for
the declared quiescence envelope.

### Compound graph

Chemistry begins with a small configured alphabet of conserved virtual elements
(the working target is 8–16, not a normative constant). Compounds are graphs of
those elements and bonds. A cached compound ID is permitted only as a hash or
interning key for the graph. Constitutive and reaction behavior must be computed
from structural features and universal configured laws, never from `WOOD`,
`FLESH`, `BONE`, or another privileged substance name.

### Field and boundary reservoir

Fields represent physically coupled quantities such as radiation, pressure, or
charge. Boundary reservoirs supply concentrated energy and accept degraded heat;
matter is closed by default but any configured matter exchange is explicit. Every
exchange crosses a typed, auditable ledger boundary.

### Observer state

Meshes, textures, names, lineage labels, species clusters, fitness analyses, and
artifact detectors are non-authoritative views. They may be deleted and rebuilt
from a checkpoint without changing the next physical state.

## Five physics domains

The domain split is an implementation boundary, not five kinds of reality.

1. **Mechanics:** momentum transfer, contact, deformation, elasticity,
   plasticity, damage, fracture, and gravity.
2. **Transport:** packet advection, diffusion, permeation, pressure-driven flow,
   and selective movement induced by physical structure.
3. **Thermodynamics:** internal energy, temperature, conduction, phase behavior,
   dissipation, and heat exchange with reservoirs.
4. **Dynamic chemistry:** graph-derived compounds, balanced bond formation and
   breakage, rearrangement, group transfer, catalysis, and reaction kinetics.
5. **Physical fields:** radiation and any explicitly modeled electrical,
   acoustic, or other fields, with sources, propagation, coupling, and ledgered
   work.

Every cross-domain conversion is a transaction. For example, active contraction
is not a `muscle` command: a chemical transition books free-energy loss, thermal
dissipation, and mechanical work through a material constitutive response.

## State-transition contract

Given checkpoint state `S_n`, configuration `C`, boundary inputs `B_n`, and an
explicit random stream position `R_n`, one accepted step produces

```text
(S_(n+1), ledger_n, diagnostics_n, R_(n+1)).
```

The update implementation must:

1. use only the no-cheating ABI described in
   [forbidden-semantics.md](forbidden-semantics.md);
2. make packet/grid scatter and gather conservative before constitutive changes;
3. book each constitutive or boundary change once in the appropriate ledger;
4. reject invalid reaction stoichiometry and negative inventories;
5. make update order and random draws reproducible from the checkpoint; and
6. emit sufficient diagnostics to localize any residual before advancing an
   accepted checkpoint.

Operator ordering is not prescribed yet. Any splitting scheme becomes part of
the tested numerical contract and must demonstrate timestep convergence.

## Energy gradient and world closure

A useful terrarium is not a closed equilibrium box. The intended topology is:

```text
radiation reservoir -> world -> chemical free energy -> work/ecology -> heat sink
```

Matter remains closed unless a scenario explicitly declares and records a matter
port. Energy is open only through declared reservoirs. No packet, organism, or
observer gets an unledgered power source.

Scenario/bootstrap code MAY seed or extract material only through explicit
boundary-port operations. Those operations are never exposed to controllers or
evolution, execute only under scenario authority, and transfer every constituent,
momentum, charge, and energy term to or from a named reservoir. “Remove” at that
boundary means ledgered extraction from the modeled domain; it never means death,
consumption, cleanup, or despawn.

## Backend independence

The checkpoint schema, unit system, permitted state transitions, and accounting
rules are the specification. CPU, HIP, another GPU API, and a future renderer
must consume that contract. Bitwise equality across backends may be unrealistic;
conserved inventories, convergence envelopes, and causal replay criteria are not
optional.
