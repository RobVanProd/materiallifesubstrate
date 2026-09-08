# Post-seal measurement progress — incomplete lab

The input seal remains
`8ec8ba42956f7664c66de26ce2f760be650cba76ef7fe0820d92396206e84516`.
Neither the seal nor the accepted mechanics/main has changed. This receipt is
not a result document, candidate selection, full regression claim, or release.
NO_PROMOTION remains.

## Cartesian B query path

The proof-carrying precondition supplies only validity and decoded-input hashes.
The isolated candidate reads actual vertices, derives its frame and extents,
constructs the exterior boundary, and charges runtime geometry work. An
independent oracle checks oriented boundary coverage, volume, every closest
set, membership result and normal cone against the registered physical box.

All 198 cube/slab rows across levels 0–2 and all 33 variants passed isolated
twins and independent checks of all 2,339 queries each. Their losslessly
compressed records are in the corresponding
`build/occupied-geometry-b-query-batch-k*-evidence-*` directories. Levels 3–4
remain in progress; the finest identity cube already passed the same complete
query stream with 2,163,087 runtime work units, below the unchanged 2^22 cap.

Five query/boundary record mutations are rejected by the independent check.
The earlier boundary-winding and query-storage-order implementation failures
remain preserved as described in the pilot-attempts document.

## General-mesh B controls

The general path does **not** accept the Cartesian precondition. It validates
orientation, incidence, full-facet connectivity and within-complex overlap at
runtime, with charged bounding-tree and exact pair-predicate work. It does not
reinterpret cross-complex penetration as invalid or claim that component
boundaries alone are the occupied-union boundary.

For the coarse sphere, a separate rational intersection-vertex/rank oracle
checked all 2,016 pairs: 952 disjoint, 1,064 touching, zero positive-volume
overlap. Its 1,344 nontrivially enclosed pairs used exact vertex enumeration,
not the candidate's separating-axis/BVH algorithm. The static-query pilot then
passed independent exact replay of all 2,707 queries and all 32 boundary
triangles. This is still a pilot, not the full geometry/refinement/CCD gate.

Twenty input/runtime/primitive unit tests currently pass, including 128 exact
pair-predicate comparisons against an independently implemented oracle.

## Outstanding work

The complete A/B/C inventory, non-Cartesian moving-union/CCD obligations,
global physical-error/refinement decisions, observer-enabled/disabled/cache
regressions, platform CI, final independent mutation inventory, evidence closure
and final disposition remain unfinished. The forty-case inherited mechanics
baseline passed, but that does not substitute for observer coexistence tests.
Resource-inconclusive pilots are not physical geometry failures.
