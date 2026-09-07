# Authoritative Mechanics Kernel Parity Lab — frozen plan

Parent: `a1497dabf8ed8788e67cd0f739c13d0129d72977`.
Branch: `authoritative-mechanics-kernel-parity-lab`.
Parent evidence: `bounded-integrator-bakeoff-lab-evidence-v1`, archive
576118316 bytes, SHA-256
`113daf203bfcbc93dbd54cfe013a942aa6f75ac658c288254afef9b0fbeabcc0`.

NO_PROMOTION TO AUTHORITATIVE WORLD DYNAMICS. This is an isolated C++20
research implementation, not activation in World or selection for production.

## Frozen semantics

The complete accepted Python B96 implementation, Path-B operation graph,
reference topology/coordinates, H_force, unit definitions, 96-bit RN-even
precision, leading exponent range [-16382,16383], canonical positive zero,
raw evidence limits, KDK ordering, even raw timesteps, exact full-chord
safe domain r/l0 >= 2^-24, atomic failure and observer formats are inputs.
No physics, budgets, precision, integrator, reference or event-format change.

C++ packet phase components have fixed-size sign/exponent/96-bit significand
storage; no rational residual, remainder, ambient precision, or history.
Temporary exact integer/rational arithmetic may implement each RN96 primitive
and noncausal observers. It must round at precisely the reference operation
boundaries and discard intermediate precision. Binary64 operations retain
their explicit order, FMA only at the existing named sites, no contraction
elsewhere, RN-even environment. Dependencies and compiler flags are recorded.
No optimization experiment, GPU implementation or World API wiring.

The canonical state wire and scientific events are independently constructed
by C++, not computed by a Python adapter from candidate output. Python may
export immutable model inputs and compare bytes/hashes; it cannot supply any
force, kick, drift, target next-state, or observer value to the causal kernel.
The executable receives only model inputs, one initial state and invocation
identity/timestep/count. Checkpoint suffixes receive their actual checkpoint.

## Inventory and gates

Authenticate the accepted parent manifest and source hash first. Freeze all
three one-second scenarios at five levels for KDK and the ineligible first-order
control, all ten internal/boosted 16-second KDK cases, and inherited 120 cubic
rotation/70 additional controls. Reconstruct and compare every state byte,
stage order, force binary64 input/output, scientific event digest and complete
checkpoint suffix where registered. Compare the existing sealed reference
records; independently replay Python when a required diagnostic was not
exported. Such new diagnostics may not replace contradictory sealed records.

Test RN96 ties/carries/sign/zero/exponent traps and wire rejection separately;
test exact initial/final/interior chord branches, coincidence and atomic
domain failure. Preserve first divergence with scenario, step, stage, primitive
or field identity, input/output bytes and exact values. Stop trajectory
acceptance at a mismatch. Implementation defects may be corrected transparently
without changing this contract; preserve the failed executable/source and
records. A persistent discrepancy is an explicit negative parity result.

Require GCC/Clang/MSVC parity, deterministic scientific twins, checkpoint
replay, inherited Python/Lean gates and independent mutations (rounding mode,
omitted primitive, swapped endpoint/order, altered H/reference, force bits,
state/event bytes, ignored domain failure, partial commit, false pass).
Use a 2 GiB process backstop per registered run; exact domain scratch retains
the inherited bit ledger. No memory/performance or arbitrary-input claim
follows from corpus parity. A resource stop is inconclusive, never a pass.

## Disposition and evidence

Wrong parent: `stop_inconclusive_or_wrong_parent`.
Semantic discrepancy: `stop_cpp_kernel_semantic_divergence` with first witness.
Incomplete/resource/platform gate: `stop_cpp_kernel_parity_inconclusive`.
All registered gates: `retain_cpp_b96_path_b_kdk_kernel_parity_for_research`.
Every outcome remains NO_PROMOTION; no approximate pass is permitted.

Commit this plan before implementing/evaluating the kernel. Preserve all
attempts, independent comparison and mutation receipts, exact final-source CI,
deterministic twin archives and a fresh-extraction verifier. Seal locally and
stop for final review; no new release/tag or main merge is inferred here.
