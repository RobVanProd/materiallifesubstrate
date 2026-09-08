# World Material Phase Unification Lab — preregistration

Parent: `64a5fb7cbb6355d6aa8ad32ec4ef5ca2a5ab138f`.
Branch: `world-material-phase-unification-lab`.
Parent tag: `authoritative-world-mechanics-integration-lab-evidence-v1`.
Parent archive: 905443734 bytes, SHA-256
`ce3d4eb4e95131415f83cfac1f65e2ba061c2905f0e5db147c5663ce90d83e05`.
Parent manifest: `5fdca79ff604bb4755c7a57b6e906d7e41c23f7d428ccf5cf0f31f9de1ae9eca`.

**NO_PROMOTION TO AUTHORITATIVE WORLD DYNAMICS.** Commit and push this
protocol before implementation or candidate trajectory evaluation. This is
ownership/representation verification, not a new mechanics/chemistry model.

## Frozen mechanics and units

Preserve the accepted kernel/header/app byte-for-byte: B96 wire/arithmetic,
Path-B conversions and force graph, H_force, reference state, relation topology,
KDK stage order, accepted domain and complete-chord rejection, budgets and
scientific event bytes. The inherited ineligible Euler control remains a
control. No integrator selection, new precision, remainder, synchronization
reservoir, projection, cap, clamp, topology or physical law change.

Use the inherited raw/SI units exactly: Lq=1/128000000000 m,
Mq=1/524288 kg, Tq=1/1000000000 s, Pq=1/67108864 kg m/s,
Eq=1/8589934592 J. Material catalog mass and extensive energy quanta in this
research profile mean Mq and Eq; no independent rescaling is permitted.

## Single ownership contract

Extend research-capable material packet storage with a phase-tagged material
record owned through World's PacketStore and its persistent PacketHandle
namespace. A B96 material record contains composition, derived exact element
inventory, mass, heat capacity, structural/stored/thermal energy, and exactly
one six-component B96 phase payload. It has no legacy integer position,
momentum or position remainder slot. Legacy packets remain unchanged in their
existing storage. Do not create a legacy placeholder and synchronize it.

Initialization loads the registered fixed inventory transactionally; it is not
a runtime creation/deletion/migration model. After binding, creation/deletion,
reactions, split/merge, impulses outside the kernel, and constitutive changes
are forbidden. No implicit conversion of existing integer matter is claimed.

Relations have an explicit immutable mechanics-ID to material-handle mapping,
including generation. Tests must deliberately use noncoincident numeric IDs
and reorder seed/binding inputs. World derives mass from its composition and
catalog and requires exact agreement with every corresponding kernel mass.
Missing/duplicate/swapped/stale bindings or mass mismatch fail atomically.

The mechanics request is constructed transiently from the material records.
No second persistent whole-state wire may serve as a causal phase copy. The
accepted kernel alone computes the next phase; World validates IDs/masses,
commits the resulting phase back to those same records and advances clocks
atomically. Retained scientific event strings are explicitly noncausal.

Default core/World remain unchanged. A separate OFF-by-default research build
option and explicit runtime enable gate unification. The already accepted
isolated World research path remains available unchanged. Legacy phase,
grid/checkpoint/accounting APIs that cannot represent unified B96 matter must
reject, not silently omit it or return an authoritative integer projection.
Material-only snapshots return copies with no legacy x/p fields.

## Material coexistence and accounting

Freeze a synthetic catalog using monatomic material with unit raw mass 1,
heat capacity 2 and structural energy 3. Each registered mechanics packet's
composition count equals its positive raw mass. These material parameters do
not select or modify H_force. Nonzero stored/thermal inventories distinguish
packets and exercise accounting. They are not a new constitutive claim.

Maintain an exact material-only ledger of inventory, mass and structural plus
stored plus thermal energy. B96 kinetic and relational potential energy belong
only to the inherited mechanics observer, never the integer material ledger.
Do not expose their sum as an exact integer conservation claim. If a combined
observer is unavailable, report that explicitly rather than inventing zero.

Exercise ordinary World heat transfer and stored/thermal conversion on the
bound material packets between mechanics steps. Heat support must be tested
from complete B96 geometry, not an integer surrogate; register a generous
fixed support radius of 2^48 raw length units for the corpus. Transfers of one
raw energy quantum alternate direction each step; stored/thermal conversion
likewise alternates. These operations preserve total material energy and all
frozen mechanics inputs. Compare against a no-operation twin: every mechanics
byte/event must remain identical. Negative amount, insufficient energy,
unknown/stale/cross-domain handles and unsupported operations fail closed.

## Checkpoints and decisive inventory

A versioned canonical research checkpoint must contain laws, schedule, exact
material records, explicit binding, B96 phase, material ledger and noncausal
observer state. Serialize each causal phase once. Canonical restart in a fresh
process requires no reference trace. Mutated checksum, count, binding,
generation, mass or omitted phase must reject. Equivalent insertion orders
must yield identical canonical bytes; there is no lossy legacy checkpoint.

Authenticate the unchanged accepted parent. Rerun the entire 40-case corpus:
30 one-second trajectories / 2976 steps and ten 16-second tails / 15872 steps,
including 47616 long KDK stages. Require exact complete mechanics streams
against the parent, direct owned-phase comparison, twins, neutral-operation
twins, canonical checkpoint twins and complete separate-process suffix replay.
Require the inherited three atomic failure controls and malformed-wire/runtime
controls. Check material inventories, exact mass, energy ledger, IDs, clocks,
bindings and single phase ownership at each committed step.

Compiled mutations must include swapped identity, stale binding, incorrect
mass, duplicate phase authority, legacy-coordinate feedback, omitted phase,
observer feedback and corrupted binding. Do not count compile failures as
detected runtime mutants. Add independent record/inventory mutations.

Require GCC/Clang/MSVC complete mechanics and checkpoint hash agreement,
default and research-capable/runtime-disabled legacy suites, inherited Python
exact oracle and pinned Lean/trust gates on exact final source. No theorem
claims formal verification of this C++ ownership implementation. Retain the
2 GiB executable resource backstop and 16 MiB checkpoint/observer limits.

## Decisions and seal

Wrong parent/control: `stop_inconclusive_or_wrong_parent`.
Two causal phase representations, hidden synchronization or projection:
`reject_single_authority_material_phase_contract`.
Any first mechanics byte divergence: `stop_material_phase_semantic_divergence`.
Mass, identity, accounting, atomicity or checkpoint failure:
`reject_material_mechanics_ownership_contract`.
Incomplete/resource/platform gate: `stop_material_phase_unification_inconclusive`.
All gates: `retain_single_authority_material_mechanics_world_state_for_research`.
All outcomes remain NO_PROMOTION.

Preserve failed attempts and first divergences before transparent corrections.
Seal source, inputs, full evidence, failures, mutations and CI; independently
pack byte-identical archives and perform fresh bundled executable rebuild/replay.
Stop locally sealed for independent review. No self-publication or main merge.
No contact, fracture, plasticity, reactions, transport law, topology evolution,
optimization, GPU or production activation is authorized by this lab.
