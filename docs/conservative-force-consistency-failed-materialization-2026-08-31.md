# Conservative Force Consistency failed materialisation — 2026-08-31

## Classification

`invalid_preseal_materialization`

This record preserves an evidence-pipeline implementation failure.  It has no
accepted scientific disposition and is not a rejection of the relational force
law.  It is also not a failed CI run: the source's public CI completed
successfully.

## Frozen identities

| Item | Identity |
|---|---|
| Source SHA | `6ca432abcf4dad86b3eb9711ff2d9396f9decbd9` |
| Public CI | run `33359711745`, success |
| Byte-identical raw-twin pre-hash | `827bda97fa1c00073c9412c64b3bd38efe5d68bb6b207248c17d82f589f6868b` |
| Generated full-A pre-hash | `1279bdbe5c545bc5b9f030c95b5c396a77865f2946b33beda49159e3341694c0` |
| Materialise receipt output SHA-256 | `bb4936a3af0650f51b1309b79a909db791d90e62255abf798ad8f85cf95cfa14` |

The original raw twins, full-A bundle, manifests, provenance, and command
receipt are preserved byte-for-byte outside the later canonical evidence.  No
file from this attempt may be reused as a corrected source-bound receipt or
bundle.

## Failure fingerprint

The materialiser emitted `reject_force_implementation` from 27 reported energy-
gradient events, represented by 108 false rows over four derivative step
levels.  Every event was a rigid-rotation probe:

```text
3 selected high-precision graphs
× 3 collective K/G policies
× 3 rotation axes
= 27 events
```

The independently reconstructed analytic derivative, extrapolated derivative,
and raw-convergence sequence otherwise agreed.  Only the exact-rigid zero-work
predicate failed.

## Root cause and independent reproduction

`independent_rigid_direction` was called before entering the declared
`localcontext(prec=100)`.  Its centroid, length, and normalisation therefore
used Python Decimal's ambient default precision of 28 digits.  Those rounded
directions produced virtual-work magnitudes from `1.46e-31` to `2.24e-29 N`,
which correctly fail the unchanged `1e-55 N` high-precision bound.

Constructing the same directions entirely at Decimal-100 gives virtual-work
residuals from zero through `5.6e-101 N` and a maximum rigidity residual of
`1.9000e-100`; all 27 probes pass.  The exact oracle already performed its
direction construction inside the 100-digit context and corroborates that
scale.

## Corrective boundary

The correction moves rigid translation/rotation centroid, norm, and
normalisation arithmetic inside an explicit Decimal-100 context and adds an
ambient-precision regression.  It does not change the force evaluator,
constitutive energy, relation graph, tolerance, registered inventory, or
decision order.  Fresh source-bound raw twins, materialised twins, local gates,
public CI, tag, and outer seal are required before any lab result is accepted.
