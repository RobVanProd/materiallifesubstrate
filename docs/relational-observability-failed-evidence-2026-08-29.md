# Preserved Relational Observability pre-evidence failures

These failures occurred before any final sweep and are not scientific
Candidate-C evidence. They are retained so implementation defects are not
silently erased from provenance.

## SHA-256 self-test failure

The first compilable producer draft built successfully with warnings treated
as errors, and the complete C++ unit executable reported `119/119 passed`.
However:

```
mls_relational_observability_diagnostic --schema-audit
```

failed closed with:

```
Relational Observability Confirmation failed:
SHA-256 implementation self-test failed
```

The defect was in the local SHA-256 round-constant table: the literal for
constant index 51 was truncated, while a temporary attempted correction wrote
the correct value to index 47. No bundle was generated or accepted with this
implementation. The required fix is to correct index 51 directly, retain the
known `sha256("abc")` gate, and rerun schema, smoke, independent-validator, and
twin gates before any final data.

## Environmental formal-check delay

Initial Lean checks on D: were terminated after bounded waits with no theorem
diagnostics and only a few CPU seconds consumed. Unrelated long-running
read-only searches saturated the physical drive queue. They were not killed,
suspended, reprioritized, or otherwise modified. The formal gate remains
required and delayed; this is not a Lean pass or failure and cannot be sealed
as evidence.

## Validator mutation-test invocation error

During pre-evidence integration, the bundle mutation regression was first
invoked without its required `--validator` and `--bundle` arguments. The
argument parser rejected that invocation before running a mutation. The
corrected explicit invocation then passed all nine registered mutations. This
was an operator/provenance error, not Candidate-C evidence, and is retained
here rather than omitted from the record.

## Concurrent Ninja regeneration failure

An isolated developer build directory was configured while another process
still held Ninja's generated files. CMake's regenerate step failed with
`ninja: error: failed recompaction: Permission denied`. The subsequent build
reported no work, and independent clean builds are still required before
evidence. This environmental/concurrency failure occurred before the final
sweep and is not a compiler or Candidate-C result.

## Adversarial pre-evidence review failures

The first end-to-end smoke implementation passed its own tests and verifier,
but a separate read-only source review found that the evidence boundary was
still too self-referential. Before any full run, the review identified:

- failed deliberately-flexible controls were counted but did not force the
  first, inconclusive verdict;
- deletion-transition markers were selected from an uncertified modular-rank
  lower bound rather than a separately certified exact transition;
- the verifier did not reconstruct perturbation/deformation coordinates or
  require the complete registered derived-configuration inventory;
- a Gram-matrix spectrum was incorrectly used as a mandatory independent
  gate despite the no-normal-equations preregistration;
- null-vector components were hashed but not exported, preventing independent
  recomputation of `Rz`, rigid projection, and span completeness;
- CI compiled the new path but did not yet run reproducible smoke twins and
  the independent mutation boundary;
- the producer emitted the registered branch literal instead of the actual
  configure-time branch, so provenance could be self-asserted;
- relation-order controls reversed and then immediately sorted the same
  canonical input without exercising noncanonical endpoint presentation;
- finite central-distance objectivity was inherited from an older test but was
  not bound into this lab's metamorphic evidence rows; and
- the outer seal checked the CI source SHA and conclusion but not the CI
  `headBranch` field.

These are evidence/implementation failures, not observations about Candidate
C. The provisional bundles remain unsealed. Each issue must be closed and
mutation-tested before the first full evidence run.

## Outer-seal adversarial review failures

A second read-only review of the provisional outer seal found that a valid
manifest could still overstate what had been independently established. The
initial draft accepted marker-only local logs, did not prove that twin paths
were distinct, did not reconstruct the sealed Git tree/commit relationship,
trusted a caller-supplied CI JSON object without comparing it to GitHub, and
could miss a modified working-tree file hidden by an index flag. Its JSON
schemas also tolerated contradictory extra fields, and verification had no
external pin for the outer pre-hash.

No evidence was sealed with that draft. Before the full run, the boundary was
hardened to require structured command/exit/output receipts, reject aliased or
overlapping roots, capture every commit blob plus the raw commit object,
reconstruct the Git tree ID, compare every working input's path-aware Git hash,
fetch the exact CI attempt from GitHub, verify the public branch/tag/repository,
enforce closed schemas, and accept an externally supplied pre-hash. Creation
now uses a staging directory, revalidates copied bytes, invokes full verify, and
publishes the canonical path only after success. The regression preserves 13
explicit failures including forged CTest/formal claims, a nonzero command exit,
selected CTest subsets, boolean CI attempt, wrong CI branch, twin aliasing,
hidden dirty input, payload
and inventory changes, extra provenance, and pre-hash replacement. These remain
provenance failures rather than Candidate-C observations.

## Descendant-branch Kelvin smoke failure

The first all-history CTest attempt on this branch preserved two failures in
the accepted Kelvin audit's smoke verifier. That validator correctly defaulted
to the sealed `kelvin-covariance-audit` branch while its smoke producer recorded
the current descendant branch. The validator and mutation test now accept an
explicit exact `--expected-source-branch` supplied by CMake for smoke only; the
default remains the original sealed branch. This removes the contradictory
test harness assumption without changing the Kelvin evidence or weakening its
default validation contract.

## First full Lean kernel failure

The first exact-source candidate for final execution,
`4a35e8a6294e4f309a58624f5fada040944c6b3c`, passed the complete 64-test C++/
Python suite and produced byte-identical full numerical twins. It is not
sealable: a fresh C-drive `lake --wfail build` failed in
`RelationalObservability.lean`. The preserved receipt records unresolved
relabel reductions, missing matrix-notation scope that caused two parse errors,
and downstream synthesized `sorry` warnings. The axiom-report command then
failed because the module had no compiled `.olean`. Static source trust had
passed, demonstrating why it cannot substitute for the Lean kernel.

The correction opens the existing Matrix notation scope and changes three proof
scripts so both sides reduce under the already stated relabel lemmas. No theorem
statement, premise, conclusion, trust boundary, or decision gate changed. A
fresh full build, numerical twin run, CI run, and outer seal are required at the
new source SHA; none of the `4a35e8a` output can be promoted or relabeled as
final evidence.

## First public cross-compiler candidate failure

The first pushed candidate after the Lean correction,
`af4010152c4441e129d2666d6b99c897a5d885ba`, failed the Linux/Clang job in
GitHub Actions run `33293438157`. Clang's warnings-as-errors gate rejected an
implicit signed-`char` to `unsigned char` conversion in the JSON string escaping
loop (`-Wsign-conversion`). The other jobs and any local work at that SHA do not
override the failed required compiler gate, so the SHA is not sealable.

The correction makes the byte conversion explicit inside the loop without
changing escaping behavior, numerical operators, registered configurations,
tolerances, or decision logic. The failed workflow remains public and is not
rerun or rewritten. All final numerical, formal, compiler, and provenance
evidence must be regenerated at a later source SHA.
