# Preserved post-seal pilot attempts

These are implementation pilots, not completed rows, selected candidates or a
final disposition. The input root remains
`8ec8ba42956f7664c66de26ce2f760be650cba76ef7fe0820d92396206e84516`.
NO_PROMOTION remains.

- Cover-construction audit after `334b457`: the A/C implementation expanded
  per-axis extrema but had not enlarged shorter sides to make the preregistered
  root a cube. The existing volume pilots used symmetric cube inputs and are
  unchanged. Before extending volume covers to asymmetric inputs, the root now
  uses the greatest side length about each axis midpoint. Both independent
  cover replayers reconstruct that enclosing cube. This implements the frozen
  covering rule; it does not alter occupied geometry or any budget.

- `2b34d80`: the first Cartesian full-query driver incorrectly required query
  storage order to equal ID order. It passed the first thirty cube variants but
  rejected the frozen reversed-order stream before answering it. The attempt
  is preserved in `build/occupied-geometry-b-query-batch-k0-scratch-v1` and its
  partial evidence directory. The correction checks unique bounded IDs and
  canonicalizes outputs by ID; the independent reader joins by explicit ID.
  No geometry, query input, numerical answer or protocol changes.

- `701862f`: the first isolated C startup lacked gmpy2's package-metadata mount.
  It failed during import, before geometry execution. The failed directory is
  `build/occupied-geometry-candidate-c-pilot-v1`. Adding only the pinned metadata
  directory permits startup without exposing oracle/control/repository paths;
  the corrected amplitude pilot has identical twins and an independent
  512-bit outward audit. The failed source and logs remain preserved.
- `40e093d`: the first B Cartesian boundary pilot computed the correct occupied
  set and volume, but six of twelve triangle windings opposed their explicit
  outward normals. `build/occupied-geometry-b-cartesian-pilot-v1` retains both
  raw twins. The correction swaps the last two emitted vertices when their
  cross product opposes the outward normal. It does not move any point, change
  a normal or volume, or alter the frozen input/certificate. The independent
  oriented-boundary audit detects this failure and its explicit mutation.

The A and next-level C volume-cover pilots exhaust the fixed work allowance
before obtaining the registered volume width. Their remaining volume is kept
as an outward unresolved enclosure, not discarded. Independent proof-tree
replays verify the partial enclosures and work accounting. These pilot resource
limits are not geometry rejection or completed inventory results.

The inherited material/World baseline replay separately passed all forty cases
and 255 invocations at source `54dba01f81a7a9bb330e4eabd0c3ced1bf7561f5`.
That is the unchanged-mechanics baseline, not yet the full enabled/disabled/
cache-rebuild geometry-observer comparison.
