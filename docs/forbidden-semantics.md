# Forbidden-semantics contract

## Rule

Push functionality out of the simulator and into configurations of matter. A
behavior is admissible only when it follows from low-level state and laws that
apply to all matter of the same physical configuration.

The authoritative engine must not contain concepts or privileged operations for:

```text
food       plant      animal      predator    prey        species
muscle     stomach    weapon      tool        wheel       bridge
reproduce  mate       fitness     reward      organism    corpse
```

The list is illustrative, not exhaustive. Renaming `food` to `resourceClass7` or
`reproduce` to `splitController` does not make it physical.

## No-cheating ABI

Authoritative update kernels may read only:

- local packet and control-volume physical state;
- state in an explicitly bounded physical neighborhood;
- universal/configured low-level laws and dimensioned constants;
- declared boundary-reservoir inputs;
- the deterministic random stream assigned to a physical stochastic process;
  and
- solver metadata needed for accuracy, never observer or camera state.

They may write only:

- evolved packet, grid, field, bond, and reservoir state;
- typed matter, momentum, angular-momentum, charge, and energy ledger entries;
- numerical diagnostics and rejection reasons; and
- provenance for representation-preserving split, merge, sleep, wake, or page
  operations.

Scenario initialization and declared boundary ports are a separate, privileged
harness interface. They may introduce or extract matter only by paired reservoir
transactions and are never agent-visible. Runtime biology cannot call, obtain a
handle to, or indirectly trigger those harness operations; death and consumption
remain ordinary in-world transformations.

The ABI must not expose semantic queries such as nearest resource, enemy
distance, target visibility, parent identity, species membership, task score,
crafting recipe, or desired morphology. It also must not expose a generic
`raycast_to_target` whose target came from an observer label.

## Required grounding examples

| Apparent function | Required physical grounding |
|---|---|
| Wheel | Geometry, contact, load, and low rotational resistance. |
| Blade | Contact stress and fracture response of weaker material. |
| Vessel or stomach | A bounded reactor whose walls alter transport and whose chemistry transforms compounds. |
| Muscle | Chemical free-energy conversion into active material stress, with heat and work booked. |
| Plant-like growth | Radiation capture coupled to chemistry and construction from ambient matter. |
| Reproduction | Matter gathering, genome-polymer copying, growth and partition of a second bounded region, then physical separation. |
| Death | Loss of maintenance followed by ordinary reactions, fracture, diffusion, and material recycling; never despawn. |
| Vision | Coupling of incident radiation to a physical receptor and internal signal. |
| Smell | Diffusing compounds binding to physical receptors. |
| Touch and proprioception | Local stress, strain, and internal physical signals. |
| Sound | Pressure waves coupled to a structure; introduced only when that field is physically modeled. |

## Controllers and genomes

MLS-1 may seed a minimal controller and genome interpreter. That interpreter is
an explicitly declared experimental scaffold, not evidence of abiogenesis. It
may trigger local physical reactions and stresses only through the same energy,
matter, transport, and rate limits as any other mechanism. It may not clone an
organism, allocate body parts, read semantic labels, receive reward, or bypass
construction.

MLS-2 moves interpreter behavior into evolvable material organization. MLS-3
removes the privileged biological interpreter. Claims must identify the active
purity level.

## Observer quarantine

Observers may classify matter as organisms, species, tools, food, or artifacts
for analysis. To remain non-causal:

- observer outputs are stored outside authoritative checkpoints;
- solver code cannot import observer packages or read observer buffers;
- renderer visibility, camera location, selection state, and frame rate cannot
  affect physics resolution or scheduling;
- metrics and lineage reconstruction run from immutable snapshots or event logs;
- deleting all observer data cannot change replay; and
- interventions use physical coordinates and state predicates, with any semantic
  selection resolved and frozen before a matched experiment begins.

## Review test for a proposed feature

Reject or redesign a feature if any answer is “yes”:

1. Does its name describe a biological role, artifact, goal, or game mechanic?
2. Could two physically identical configurations behave differently because of
   a label, owner, lineage, or class ID?
3. Does it create, destroy, move, sense, or transform matter without a ledgered
   local physical path?
4. Does it give a controller information that no modeled field delivers?
5. Does it add a useful action directly instead of making the material substrate
   capable of realizing the action?
6. Does it change the authoritative trajectory when a camera, renderer, metric,
   or analysis process changes?
