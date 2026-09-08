# Pre-data runtime-validity accounting escalation

No candidate has been evaluated. This is not a geometry result, completed input
seal, final lab disposition, or request to change the accepted mechanics.
**NO_PROMOTION remains.** Governing documents are unchanged.

## Input closure progress

The separate staged package at source
`591118f5b48290c17a71398a12b1123792234c88` has passed a fresh-copy byte/manifest
audit: 507 payload files, 1,155 registered runs, 2,310 I1/I2 views, and
8,534,507,833 stored bytes including its manifests. This leaves 55,426,759 bytes
under 8 GiB at this checkpoint. New evidence/source/receipts still consume that
same ceiling; this is not a guarantee the final lab archive will fit.

The independent run audit passed 11,550 stream comparisons and rejected six
mutations (missing run, I1 vertex leakage, changed digest, seed, pose and oracle
join). Global transforms and storage/ID variants were independently decoded in
C++, and the complete sphere connectivity/centroid/weight joins pass at all five
levels. The current input unit suite passes 13 tests. The earlier pinned Lean
build of 2,146 jobs remains preserved; no new formal claim is added here.

Fresh-package receipt:
`build/occupied-geometry-input-attempt-v1/fresh-package-independent-v1.json`
has SHA-256
`73f2e6345f5d5d9fcf9ad1963dedd7df10151873c85274e07529ad9230370182`.
The package is `build/occupied-geometry-input-staging-v1`. It deliberately has
no root seal/data-gate authorization. Its earlier source snapshot remains
unchanged; this later audit does not rewrite that staged attempt.

## Newly identified mandatory-row consequence

The resource amendment exempts loading and canonical decoding of frozen input
primitives. This audit does **not** charge those operations or reinterpret that
amendment to count input cells themselves.

However, Candidate B requires rejection of invalid tetrahedra and incidence.
Addendum section 8 charges each evaluated primitive validity predicate as
runtime work. It further states that input-generation validation cannot
establish candidate validity merely by generating the input. Reusing a cached
certificate cannot make its creation cost disappear or introduce a free
cross-candidate/level cache.

Under a candidate validity pass that checks each tetrahedron, even the weakest
count of one predicate per cell gives:

| Mandatory B row | Stored tetrahedra | Validity work, at least | Frozen cap |
| --- | ---: | ---: | ---: |
| Cube k=4 | 12,582,912 | 12,582,912 | 4,194,304 |
| Slab k=4 | 12,582,912 | 12,582,912 | 4,194,304 |

Both are three times the cap before any incidence, overlap, union, boundary,
normal, distance or swept-query certification. The count comes from the raw
kind-2 headers and exact file lengths, independently checked against six
tetrahedra per Cartesian cell. The same count survives each of the 33 variants.

The exact audit is reproducible using:

```sh
PYTHONDONTWRITEBYTECODE=1 python tools/occupied_geometry_b_validity_preflight.py \
  build/occupied-geometry-input-attempt-v1 . /tmp/b-validity-audit-new.json
```

Preserved receipt:
`build/occupied-geometry-input-attempt-v1/b-validity-runtime-preflight-v1.json`,
SHA-256 `51c1c76f0322a6af5c5eb7ec8acba11a63c269d3c1d41f4486c710e11a00d0c5`.

This is a protocol/validation-path accounting consequence, **not a universal
complexity lower bound** on geometry algorithms. A different compressed proof
or proof-carrying validity contract would need explicit review of its permitted
input information and work charges; it cannot silently be treated as free
canonical decoding or borrow oracle shape knowledge.

## Why this is escalated before data

The predeclared C all-sample resource consequence is already accepted. This B
candidate-validity consequence was not separately accepted. It affects the
remaining potential full-inventory continuum selection, because a required
resource-inconclusive row blocks that selection under section 9. It would be
misleading to silently exempt the checks, or to run the lab and describe this
predetermined limitation as evidence against explicit material domains.

The standing authorization requires an escalation when a mandatory row becomes
impossible for a reason not already preregistered. Accordingly, pause before
issuing the input root seal or executing candidates. The narrow pending choice
is whether to explicitly accept these B rows as resource-inconclusive and run
the unchanged protocol for its remaining bounded findings, or authorize a
pre-data validity/accounting amendment. No amendment is implemented here.

Main, source mechanics, World state, physical inputs, thresholds and scientific
dispositions are untouched. All staged inputs and prior attempts are preserved.
