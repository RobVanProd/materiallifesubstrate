# Correlation-aware tail certificate — implementation checkpoint

This is **not a sealed result**. Selected precision remains null and promotion
remains NO_PROMOTION. No physical-budget certificate has been produced.

## Parent and repository identity

Remote main was fast-forwarded without rewriting history to
`761c2dd6505f99a953f143a43221393370feebd0`. The requested branch begins at that
exact source. Preregistration was committed as `5285eaa` before new candidate
trajectory data. The old verifier and mechanics sources are unchanged.

The accepted bundle check passed for all 359 payload files against its source.
The unchanged record verifier reproduced 4,018 signed record samples, all
1,320 withheld stage checks, 60/90 completed blocks, ten full pilots stopping
at step 1 second kick, and no full-tail certificate. The parent anchor audits
and rounding controls were reconstructed from authenticated inputs. This did
not repeat the optional full exact-prefix trajectory replay.

## Preliminary implementation checks

- Sixteen exact-arithmetic/core mutation tests pass.
- All ten time-zero, one-step C blocks pass all three joint stage checks.
- Internal L1 four-step B block passes 12 joint checks.
- Internal L1 sixteen-step B and C blocks pass 48 joint checks each.
- No branch was needed in these completed blocks.
- Original and incrementally cached retrospective witness implementations
  produce identical sixteen-step C JSON results (570 symbols).
- Eight exact Lean lemmas build with the pinned toolchain; the whole build
  reports 2,141 jobs. Formal trust scan passes. These are algebraic lemmas,
  not a proof of the executable floating-point implementation.

Joint containment uses one common exact assignment to all shared symbols,
reconstructed AFTER generation. Coordinate-by-coordinate interval containment
alone is not the check. The assignment never enters force conversion,
branch selection, affine propagation, rounding or candidate state.

The core currently produces reference-state inclusions only. Full physical
observers, signed energy-slope trajectory bounds, complete branching mutation
coverage and the complete withheld inventory remain pending. Thus even a
completed state-only run cannot select B96 or claim budgets are certified.

## Preserved execution-order mistake

An internal L1 full-horizon C pilot was launched before the complete withheld
inventory finished. It was explicitly interrupted (exit 130) before any result
was produced. Its output file was empty. It is INELIGIBLE exploratory work,
not a canonical full-tail attempt and not scientific evidence. Preserve its
record; do not silently count it as a completed or failed certificate. No
arithmetic, precision or resource threshold was changed based on that run.

## Next gates

Additional implementation work (not a trajectory result): five polynomial
observer tests, three inventory-guard tests and four independent binary64-cell
tests pass. A ninth Lean lemma bounds a signed common-generator numerator.
The observer module is not yet connected to full trajectories. Its initial
common-noise slope fixture exposed unnecessary pre-summation rounding; the
corrected implementation combines signed coefficients before rounding. This
was a known-answer unit-test failure, not a change to any physical budget or
candidate trajectory.

The first implementation CI at `270cfbd8f05a2ad872822e3782796e1088056e71`
is run `33998667531`; its three compiler gates passed while Python and Lean
were still running at this checkpoint. The withheld-v1 inventory uses the
unchanged core and checker from that source. Additional observer/proof files
are not imported by the running inventory and cannot affect its results.

Complete the 90 withheld C blocks (both scenarios, all levels, starts 0/8/32,
lengths 1/4/16) with 900-second subprocess and 2 GiB address-space ceilings.
Preserve every subprocess receipt, including exhaustion. Inspect independent
checks and any failures before launching eligible full tails. Do not create a
release or merge this implementation checkpoint as a completed experiment.
