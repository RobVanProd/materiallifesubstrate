# Material Life Substrate

Material Life Substrate (MLS) is a research program for a three-dimensional,
matter-grounded artificial-life substrate. Persistent conserved material packets
move through sparse voxel control volumes; low-level mechanics, transport,
thermodynamics, chemistry, and physical fields determine what happens. Biology,
artifacts, and ecology must be configurations of that same matter. Rendering is
an observer and never an authority.

This repository is at the MLS-0 substrate-bootstrap stage. It contains a small
deterministic fixed-point accounting and ballistic packet/grid reference, plus
narrow machine-checked accounting theorems. It does **not** contain an MPM or
continuum solver, validated physical material behavior, artificial life,
organisms, ecology, rewards, fitness, or open-ended evolution.

## MLS acceptance test

Before evolving a creature, raw MLS matter must support a manually constructed
knife, rope, cup, membrane, spring, and catalyst without any named component or
engine operation for cutting, tension, containment, selective transport, elastic
storage, or catalysis. Physics is then frozen and held-out affordances are targets
for blind rediscovery. Failure is a substrate-design result, not an invitation to
add semantic helpers.

## Non-negotiable boundary

The authoritative engine may know quantities such as packet composition,
position, momentum, deformation history, temperature, bonds, stress, and local
field state. It may not know `food`, `plant`, `animal`, `species`, `muscle`,
`stomach`, `weapon`, `tool`, `wheel`, `bridge`, `reproduce`, `mate`, `fitness`,
or `reward`. Those may exist only as observer interpretations.

## Start here

- [MLS v0.1 integrated specification](docs/specification-v0.1.md)
- [Architecture and state contract](docs/architecture.md)
- [Implemented subsystem contracts](docs/implemented-subsystem-contracts.md)
- [Physical interaction support contract](docs/physical-support-contract.md)
- [Point-interaction angular-momentum contract](docs/angular-momentum-contract.md)
- [Exact physical-time and checkpoint contract](docs/time-checkpoint-contract.md)
- [Particle/grid transfer laboratory contract](docs/transfer-lab-contract.md)
- [Sealed Time + Transfer bakeoff protocol](docs/time-transfer-preregistration.md)
- [Affine Advection Lab implementation contract](docs/affine-advection-lab-contract.md)
- [Affine Advection Lab preregistration](docs/affine-advection-preregistration.md)
- [Moving APIC limit diagnostic contract](docs/moving-apic-limit-contract.md)
- [Moving APIC limit preregistration](docs/moving-apic-limit-preregistration.md)
- [Projection Foundation Lab contract](docs/projection-foundation-lab-contract.md)
- [Projection Foundation Lab preregistration](docs/projection-foundation-preregistration.md)
- [Projection Exactness + Nullspace Lab contract](docs/projection-exactness-nullspace-contract.md)
- [Projection Exactness + Nullspace Lab preregistration](docs/projection-exactness-nullspace-preregistration.md)
- [Projection Exactness + Nullspace Lab result](docs/projection-exactness-nullspace-result.md)
- [Constitutive Expressivity Lab contract](docs/constitutive-expressivity-lab-contract.md)
- [Constitutive Expressivity Lab preregistration](docs/constitutive-expressivity-preregistration.md)
- [Constitutive Expressivity primary-source audit](docs/constitutive-expressivity-source-audit.md)
- [Forbidden-semantics contract](docs/forbidden-semantics.md)
- [Accounting invariants](docs/accounting-invariants.md)
- [Research roadmap and gates](docs/roadmap.md)
- [Affordance gauntlet](docs/affordance-gauntlet.md)
- [Exploit quarantine](docs/exploit-quarantine.md)
- [Coarse-graining hazard](docs/coarse-graining.md)
- [Dynamic similarity](docs/dynamic-similarity.md)
- [Hypotheses and falsifiers](docs/hypotheses.md)
- [Validation and proof boundary](docs/validation-status.md)
- [Cross-environment replication gate](docs/replication-gate.md)
- [Publication/review evidence template](docs/review-evidence-template.md)
- [2026-08-28 MLS-0 baseline evidence](docs/review-evidence-2026-08-28-baseline.md)
- [2026-08-28 baseline-hardening evidence](docs/review-evidence-2026-08-28-hardening.md)
- [Prior-art debts](docs/prior-art.md)

The historical, hardening, affine-advection, moving-APIC-limit, projection,
and nullspace Python oracles under `reference/` import no C++ bindings or
production implementation modules. Their role is independent exact
cross-checking, not validation of physical behavior.

## Intended implementation boundary

The authoritative reference state is implemented in C++20 at the accounting and
ballistic packet/grid level, with a narrow GPU backend only after that reference
model is trustworthy. HIP/ROCm is a candidate
backend, not part of the laws of the world. MPM-family particle/grid coupling is
a candidate, not a validated solver choice. OpenVDB-like sparse storage may
inspire data structures but does not define physical adaptivity. UE5, Warp, and
the renderer are not authoritative.

The Lean project under [`formal/`](formal/) is pinned to Lean and Mathlib
`v4.33.0-rc1`. On 2026-08-28 the pinned project compiled successfully with no
`sorry` or `admit` tokens in its Lean sources. This kernel result applies only to
the encoded accounting, scaling, coarse-graining, and simulation-relation
statements; it does not verify the C++ implementation or physical validity.

## License and citation

No license or academic citation claim has been selected yet. Do not assume that
repository availability grants reuse rights, and do not make novelty claims from
this specification.
