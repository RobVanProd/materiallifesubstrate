# Material Life Substrate v0.1 integrated specification

**Status:** research specification; implementation and validation are incomplete.

Normative words `MUST`, `MUST NOT`, `SHOULD`, and `MAY` describe MLS v0.1
requirements. This document integrates the focused contracts linked below. An
unresolved conflict between normative files blocks the affected gate; it is not
permission to choose the easier interpretation.

## 1. Research object

MLS MUST be a persistent, sparse, three-dimensional material substrate in which
the same low-level matter represents environment, organisms, remains, and
artifacts. It is intended to test composability and evolvability, not to reproduce
Earth molecule by molecule or to maximize visual plausibility.

## 2. Claim boundary

MLS v0 MUST NOT be described as life, abiogenesis, open-ended evolution, or a
validated physical world. Claims MUST name the relevant purity level, gate,
implementation/configuration, evidence column, and falsifier. Nearby prior art
MUST be credited and no novelty claim follows from this architecture.

## 3. Hard decisions

Literal `voxel = molecule/cell`, dense allocation, camera-dependent physics LOD,
lossy coarse physics in v0, high-level reward, origin-of-life-first development,
UE5 authority, and Warp authority are rejected. Persistent Lagrangian packets,
sparse voxel control volumes, exact state paging, dynamic similarity, and a
backend-independent state/law contract are accepted. MPM-family coupling and HIP
are candidates requiring validation, not decisions that define reality. The full
decision table is in [architecture.md](architecture.md#hard-decisions).

## 4. Authoritative ontology

Authoritative state MAY contain material packets, conserved virtual-element
inventories, compound/bond graphs, mechanical and thermal history, sparse control
volumes, modeled fields, boundary reservoirs, ledgers, solver state needed for
replay, and deterministic random-stream state. It MUST NOT contain a causal
organism, species, body-part, resource, artifact, goal, or fitness class. See
[architecture.md](architecture.md#ontology).

## 5. State transition

An accepted step MUST be a reproducible mapping from prior checkpoint,
configuration, boundary inputs, and explicit random state to next checkpoint,
ledger, diagnostics, and next random state. Every cross-domain or boundary change
MUST be booked exactly once. Invalid or unclosed steps MUST be rejected rather
than silently repaired.

## 6. Mechanics

Mechanics MUST arise from generic mass, momentum, contact, deformation,
constitutive response, damage, fracture, and gravity. Cutting, tensile support,
bending, rotation, leverage, and elasticity MUST emerge from configuration and
load. Mechanics MUST pass convergence and rotation/isotropy gates before it is
used for an evolutionary claim.

## 7. Transport

Advection, diffusion, permeation, pressure-driven flow, and selective transport
MUST operate through local material/field couplings. No controller MAY request
teleportation, ingestion, excretion, or targeted delivery as a semantic action.

## 8. Thermodynamics

Temperature and internal energy MUST be physical state linked by a declared
equation of state. Conduction, phase behavior, dissipation, and heat exchange MUST
be ledgered. A positivity clamp is not an acceptable heat source.

## 9. Dynamic chemistry

Chemistry MUST begin from conserved virtual elements and structurally represented
compounds. Reactions MUST conserve element inventory (`A nu = 0`), obey bounded
extents and configured kinetics, and book energetic changes. Cached compound IDs
MUST NOT become semantic material types. Catalysts MUST change kinetics without
net consumption.

## 10. Physical fields and energy gradient

Radiation and any electrical, acoustic, or other enabled field MUST declare
sources, propagation, coupling, energy/momentum accounting, and resolution. A
terrarium SHOULD receive concentrated energy from a reservoir and reject degraded
heat to a sink. Matter is closed by default; all configured boundary flows are
explicit.

## 11. Forbidden semantics and ABI

The authoritative ABI MUST expose only local physical state, universal configured
laws, explicit boundary inputs, numerical accuracy metadata, and physical random
processes. It MUST NOT expose semantic queries, named functional components,
reward/fitness, observer labels, or target information. The complete review rules
are in [forbidden-semantics.md](forbidden-semantics.md).

## 12. Life cycle grounding

Reproduction MUST gather world matter, construct a second bounded system, copy
hereditary material with physical cost and error, partition contents, and separate
mechanically. It MUST NOT call clone/spawn. Death MUST be loss of maintenance and
ordinary material recycling, never despawn.

## 13. Sensing, control, and learning

Information available to a controller MUST arrive through modeled physical
couplings: radiation, molecules, stress/strain, temperature, pressure waves, or
other declared fields. MLS-1 MAY use a privileged minimal interpreter only when
declared; it remains constrained by physical rates, matter, and energy. Local
plasticity requires a matched no-plasticity control for H5.

## 14. Rendering and observation

Rendering and scientific observers MUST be read-only and reconstructible from
authoritative checkpoints/events. Camera location, visibility, frame rate,
classification, lineage analysis, and metrics MUST NOT alter physics state,
resolution, scheduling, or random draws.

## 15. Multiscale contract

MLS v0 MUST scale first through sparse allocation, verified quiescent sleeping,
exact paging, and conservative local time stepping. It MUST NOT merge state merely
because extensive totals match. Any future coarse model MUST face matched legal
interventions and preserve declared causal observations across horizons. The
separated-reactant counterexample in
[coarse-graining.md](coarse-graining.md) is a mandatory regression.

## 16. Dynamic similarity

Scenario scaling MUST declare transformed units/constants and the dimensionless
groups preserved and omitted. The initial transform targets Reynolds, Froude²,
Peclet, and first-order/effective Damkohler invariance. It does not establish
general Earth equivalence. See [dynamic-similarity.md](dynamic-similarity.md).

## 17. Accounting

Constituent inventory is exact. Internal momentum exchanges are equal/opposite;
external impulse is explicit. Energy stores and reservoirs close with localized,
convergent residuals. Charge and other conserved sources receive equivalent
treatment when enabled. Split/merge, transfer, sleep/wake, paging, chemistry,
reproduction, and death MUST preserve the contracts in
[accounting-invariants.md](accounting-invariants.md).

## 18. Affordances and exploit quarantine

Before life, manually built raw matter MUST pass the knife/rope/cup/membrane/
spring/catalyst acceptance set and the full 12-item Gate 7 gauntlet. With physics
frozen, held-out affordances proceed to blind rediscovery. Unexpected functions
MUST face ledger reconstruction, timestep/resolution changes, grid rotation,
deterministic replay, causal ablation, controls, and an alternate implementation
where practical. See [affordance-gauntlet.md](affordance-gauntlet.md) and
[exploit-quarantine.md](exploit-quarantine.md).

## 19. Purity ladder

MLS-0 contains no life. MLS-1 seeds a minimal cell/controller. MLS-2 makes the
controller/genome interpreter material and evolvable. MLS-3 removes the privileged
biological interpreter. The project MUST NOT attribute a claim from a purer level
to evidence produced at a scaffolded level.

## 20. Gates 0–15

Progression is: formal accounting; conservation stress; mechanics benchmarks;
transport; chemistry; rotation/isotropy; fracture/cutting; affordance gauntlet;
blind rediscovery; cross-fidelity replay; bootstrap cell; physical reproduction;
persistent ecology; niche-construction sham; long-run activity; and the
indefinite-scaling challenge. Exit evidence and stop conditions are normative in
[roadmap.md](roadmap.md#gates-015).

## 21. H1–H6 and controls

The hypotheses are substrate composability, seeded-life evolvability, causal
niche construction, frontier expansion under scaling without ABI changes, causal
local learning, and cumulative durable external affordances. Each MUST be tested
against its explicit falsifier and matched controls in
[hypotheses.md](hypotheses.md). Positive-looking trajectories without those
controls are observations, not confirmations.

## 22. Evidence, implementation, and prior art

Formal, exact-executable, numerical, and empirical/evolutionary evidence are
independent columns. Formal green MUST NOT promote numerical or empirical red.
The pinned Lean project completed a captured kernel build on 2026-08-28 with no
`sorry` or `admit` tokens in its sources. That formal result remains confined to
the encoded statements and does not promote numerical or empirical evidence.
The exact v0 arithmetic provenance has been reproduced, but no simulator or life
claim follows. The intended implementation is C++20 reference semantics with a
narrow replaceable GPU backend. Evidence language and current status are in
[validation-status.md](validation-status.md); research lineage and non-novelty
discipline are in [prior-art.md](prior-art.md).

The exact state variables, update equations, approximations, failure modes, and
test traceability of the current C++ scaffold are audited separately in
[implemented-subsystem-contracts.md](implemented-subsystem-contracts.md). That
implementation record cannot weaken any normative requirement in this
specification.
