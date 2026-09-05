# Bounded Phase Tail Certification Lab — preregistration

Parent: `17532284c2f0878e908f6a613f4c2e3baa47cbcd`.
Branch: `bounded-phase-tail-certification-lab`.
Status: staged verification experiment; no scientific disposition yet.

The accepted parent retains its negative disposition, null selection, and
NO_PROMOTION. All candidate source, force law, topology, reference geometry,
H_force, unit definitions, operation order, rounding, exponent range, precision
inventory, physical budgets and safe domain are frozen byte-for-byte. Only
new verifier, proof, test, and evidence files may be added. The old evidence
and tag are immutable. Main incorporated the eight accepted commits by
protected fast-forward; no protection was changed.

## Stage one: exact extraction and targeted replay

Authenticate the parent summary by SHA-256
`24d5d2fadd30b49cc2aab49506510d6e6c423fe312b01fbba3b561668a112554`.
Extract every level and both internal and boosted controls, not just failures.
Recompute the mandatory 192-to-256 gate with exact rational arithmetic.
Preserve the separate, non-gating reversal irregularity.
Replay only needed exact prefixes to recover signed coordinate argmax,
per-sample signed energy errors, force-scalar correspondence, and the actual
least-squares numerator and sum of absolute contributions. A sign change or
small aggregate error alone is insufficient to establish a cancellation cause.
Missing diagnostics stay explicitly unresolved.

Calibration inventory, frozen before tail computation: 1/201 at 192/256 bits;
1+2^-10 at 4/8 bits; 1/3 at 4/8; -1/201 at 192/256; 17/16 at 4/8.
Nearest-even results and half-ULP bounds use integer quotients/remainders.
Signed-sum controls use each ordered sequence (1, 1/201, -1),
(1, 2^-10, -1), and (1/3, -1/3, 1/201), at 192 and 256 bits.
Keep justified upper bounds distinct from realized error ratios.

## Verifier-only enclosure pilot

The target is the parent's exact-rational KDK map with its registered binary64
force evaluation, separately from the smooth ODE oracle. A certificate may
use exact rational endpoints rounded outward to a fixed 512-bit dyadic
significand after interval operations. This is verifier arithmetic only.
Begin with exact initial rational states. Carry uncertainty through every
operation and block; never initialize from a bounded state with zero radius.

First implementation: an interval box propagated through the exact linear
kick and drift maps conditional on certified binary64 coordinate conversions.
For each relation form the complete raw relative interval, multiply by exact
Lq, and compare correctly rounded binary64 endpoint values. If endpoints
produce the identical bit pattern, monotonic nearest rounding certifies that
input conversion. Evaluate the frozen deterministic force graph only on these
certified inputs. Require all such conversions; otherwise report the precise
first unresolved conversion and stop that trajectory as inconclusive.
No smooth-force assumption or substitution of the B256 trace is allowed.
The first implementation does not branch across unresolved rounding cells.

Include exact safe-domain tests for each relation box and complete drift
chord. Any inability to prove safety is inconclusive, not a certified physical
domain violation. Interval arithmetic must be outward; inward parent witnesses
are not reused. State-energy and least-squares slope bounds must be derived
from the enclosures, not borrowed from prefix contraction.

Inventory: internal and boosted levels 0–4; affected internal L1,L2,L3 first,
then internal L4 and all remaining controls. All horizons are 16 seconds.
Each case has a 900-second wall limit and a 2 GiB verifier memory target;
the total pilot allowance is 3 hours. No adaptive verifier precision or
case-dependent multiplier. A resource limit or unresolved rounding cell
means incomplete certification, never a physical-defect claim.

Before tail use, exact-prefix tests must check enclosure at every kick/drift
stage; generation must not read comparator states. Withhold intervals beginning
at steps 0, 8, and 32 of lengths 1, 4, and 16, where available. Preserve the
incoming radius at each block. Negative controls omit a rounding allowance,
round an endpoint inward, reset a nonzero radius, assume an uncertified force
scalar, or misclassify a crossing chord. Every control must be rejected.

Lean covers enclosure induction, explicit nonnegative rounding slack, and
least-squares sample-envelope propagation. It does not prove MPFR or the
executable implementation. No full-inventory claim is permitted if any
applicable tail is unresolved.

## Dispositions and completion

Allowed final outcomes: anchor_ratio_failure_explained_but_tail_uncertified;
registered_bounded_phase_tails_certified_within_error_budgets;
bounded_phase_tail_error_exceeds_frozen_budget;
stop_certificate_unsound_or_inconclusive. All remain NO_PROMOTION.

Completion requires exact failure reproduction and explanation or explicit
non-explanation, withheld-prefix validation, full-tail coverage or a precise
inconclusive boundary, independent arithmetic and mutation checks, Lean gates,
and a separately sealed result. This document and pilot contract must be
committed before evaluating new tails.

References: MPFR 4.2.2 manual, https://www.mpfr.org/mpfr-4.2.2/mpfr.html;
S. M. Rump, Verification methods: Rigorous results using floating-point
arithmetic, Acta Numerica (2010), DOI 10.1017/S096249291000005X.
