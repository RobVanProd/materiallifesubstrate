# Roadmap, purity levels, and validation gates

MLS advances by evidence gates, not by visual milestones. A later-stage demo does
not waive an earlier failure, and a proof of an accounting identity does not
validate a numerical solver or an evolutionary claim.

## Purity ladder

| Level | Permitted scaffold | Question it may address | Claim it may not make |
|---|---|---|---|
| **MLS-0** | No life; manually configured matter and external benchmark fixtures. | Is the substrate conservative, stable, expressive, and materially composable? | Evolution, life, or abiogenesis. |
| **MLS-1** | Explicitly seeded minimal cells/controllers and a fixed genome interpreter, constrained by physical interfaces. | What can evolution do after a viable reproducer is placed in the world? | Spontaneous origin of life or evolution of the interpreter. |
| **MLS-2** | Initial seeding is allowed, but controller/genome interpretation is embodied in material and evolvable. | Can control architecture and development themselves evolve? | Unseeded abiogenesis. |
| **MLS-3** | No privileged biological interpreter. | Can an artificial chemistry support origin-of-life processes? | Success unless replication and heredity arise through the same material laws. |

Every run records its purity level and every deviation. Results from one level do
not inherit the claims of a purer level.

## Experimental sequence

1. **Matter:** validate mechanics, transport, thermodynamics, chemistry, fields,
   and generic material affordances.
2. **Protocell:** require a seeded minimal organism to acquire energy and matter,
   maintain itself, repair, reproduce physically, and die materially.
3. **Development:** evolve multicellular form through construction and local
   signaling rather than body-part allocation.
4. **Ecology:** establish persistent material and energy cycles; predator,
   competitor, producer, and decomposer remain observer labels.
5. **Niche construction:** test causal environmental inheritance against an
   equal-action, equal-energy sham.
6. **Learning:** add local plastic physical signaling and compare matched
   no-plasticity controls.
7. **Tools:** permit only generic matter rearrangement, heating, fracture,
   binding, and field coupling; never crafting recipes.
8. **Culture:** test durable copying, modification, and combination of useful
   external structures or behavior.

## Gates 0–15

The names and order are normative. Each gate requires versioned scenarios,
predeclared tolerances, machine-readable results, hashes, build/configuration
identity, and replayable seeds.

| Gate | Name | Minimum exit evidence |
|---:|---|---|
| 0 | **Formal accounting** | Definitions and proof candidates cover local conservative transfer, admissibility, stoichiometric balance, energy/reservoir transactions, aggregation, and the stated similarity transforms. A real Lean kernel build with no `sorry`/`admit` is required before saying “verified.” |
| 1 | **Conservation stress** | Independent executable tests exercise long/repeated transfers, reactions, conversions, boundaries, packet/grid transfers, split/merge, sleep/wake, and checkpoint/restart. Exact quantities remain exact; numerical residuals satisfy predeclared convergence envelopes. |
| 2 | **Mechanics benchmarks** | Standardized momentum, contact, elasticity, plasticity, gravity, deformation, and energy-dissipation cases converge against analytic results or trusted references across timestep and resolution. |
| 3 | **Transport** | Advection, diffusion, permeation, pressure flow, heat transport, and configured field propagation pass conservation, positivity, rate, and convergence benchmarks. |
| 4 | **Chemistry** | Every reaction is element-balanced; kinetics, equilibrium tendencies, energy coupling, graph-derived variation, and catalyst non-consumption pass independent tests without semantic material IDs. |
| 5 | **Rotation/isotropy** | Rotating and translating benchmark setups relative to the voxel grid does not change qualitative outcomes or exceed preregistered quantitative anisotropy bounds. |
| 6 | **Fracture/cutting** | Stress-driven damage and separation converge; a raw-matter sharp edge cuts weaker matter for physical reasons and survives rotation, resolution, and solver checks. |
| 7 | **Affordance gauntlet** | Manual raw-matter constructions demonstrate the full gauntlet without semantic helpers. Negative controls and ABI audits pass. |
| 8 | **Blind rediscovery** | With physics frozen and some targets hidden, an independent search/evolution procedure rediscovers held-out useful structures more reliably than matched controls; no target-specific API or shaping leaks. |
| 9 | **Cross-fidelity replay** | Candidate discoveries retain their causal function under smaller timesteps, finer discretization, rotated grids, deterministic mode, and an alternate solver/backend where practical. |
| 10 | **Bootstrap cell** | A declared MLS-1 minimal cell maintains a bounded nonequilibrium state, captures energy, transports matter, runs chemistry, repairs damage, and remains fully ledgered. |
| 11 | **Physical reproduction** | A cell gathers world matter, copies hereditary material with measurable errors and energy cost, constructs and partitions a second bounded system, and separates without clone/spawn/despawn operations. |
| 12 | **Persistent ecology** | Replicated continuous runs sustain multiple generations, material recycling, energy throughput, and interacting lineages without scripted population maintenance. |
| 13 | **Niche-construction sham** | Environmental-write runs diverge reproducibly from equal-action/equal-energy suppressed-write shams on preregistered evolutionary measures. |
| 14 | **Long-run activity** | Nonequilibrium activity, diversity, innovation measures, and ledger integrity persist beyond preregistered durations and exceed drift/null controls without numerical exploit dependence. |
| 15 | **Indefinite-scaling challenge** | Increasing available space, matter, duration, and compute expands the observed innovation frontier without changing the no-cheating ABI or adding named affordances; saturation and failures are reported, not patched semantically. |

“Pass” applies only to the exact implementation, configuration family, tolerance,
and evidence bundle tested. It is never a permanent badge for the project.

## Stop conditions

Pause feature expansion and redesign the substrate when:

- a gauntlet affordance requires a privileged component or operation;
- useful behavior depends on grid orientation, camera state, timestep, or an
  unbounded conservation residual;
- chemistry collapses into a finite named crafting catalogue;
- scaling invents or removes material affordances;
- seeded reproduction uses hidden cloning, reward, or matter creation; or
- a surprising evolutionary result fails exploit quarantine.
