# Mechanical-observability failed evidence — 2026-08-29

Source `2e563edac0bb7dfe721e471a0c171ca84b8b9075` produced two byte-identical
full bundles with manifest pre-hash
`149d6769e98992656331821da585711a6033bec374c9bd43b2252bfe68850290`.
They remain preserved as rejected evidence and are not rewritten or promoted.

The first validator failure was
`base.jitter27.r105.original.B/4`. The producer emitted condition
`9687791.9056080281734466552734375`; an ideal-Decimal reconstruction from the
binary64 packet inputs produced
`9687791.90570671577456687692089690361150481731391321471395446611781911484183304482602287541035134761620861710149251111646`.
Their absolute difference was
`0.00009868760112022164745940361150481731391321471395446611781911484183304482602287541035134761620861710149251111646`,
while the former validator's unregistered direct-comparison budget was
`0.0000176219908202378351680943104294863710071305657955981748331526738595215384198854545699616527730051739852726132238035901598`:
`5.6002526687781869` times that budget.

All nine emitted moment cells reproduce the producer's binary64 assembly
byte-for-byte. A 120-digit solve of that exact emitted `M64` gives condition
`9687791.90564631853751939690953885329364442401134178181715461116783332433080921900741116613335421545788079962034162230155`.
The ideal-Decimal, high-precision `M64`, and emitted estimates all classify the
packet as `built`; it is more than three orders of magnitude below the frozen
`1e10` condition limit. The rejected result exposed an invalid direct equality
between condition estimates from different arithmetic paths, not a changed
scientific decision.

After that cross-arithmetic validator defect was corrected, the next failure
was the QRCP pivot order at step 99 of
`base.bcc35.r105.original.B`. The producer selected original column 1 while an
independent Decimal replay selected original column 24. Their suffix norms
were approximately `1.31e-15` and `1.41e-15`, respectively, but the frozen
ambiguity lower bound was `5.158849339689051e-12`. Both pivots were rejected;
both traces produced rank 99, nullity 6, rigid rank 6, non-rigid nullity 0,
and no ambiguity. The corrected validator preserves maximal-pivot checking at
or above the frozen lower bound, independently replays the claimed path and a
greedy path, and permits different pivot order only in a suffix wholly below
that bound. It does not change the rank threshold or residual gates.

With the condition and QRCP checks corrected, both untouched bundles reached
the same first substantive rejection:
`base.filament.r205.original.rotation_translation.C` reported a rigid basis of
width five even though exact dyadic analysis of its emitted binary64 packet
positions gave affine rank three and rigid-generator rank six. Coordinate-wise
rounding of the intended rational rotation and translation had made the
filament microscopically three-dimensional; several transformed sheets were
likewise microscopically nonplanar. Full-a rejected after `561.974 s` and
full-b after `688.688 s`. The 21-file trees remained byte-identical with zero
SHA-256 differences.

The rejected bundles were not repaired. Before a new full run, the diagnostic
fixture rule was amended to realize rational configurations on a common
`2^-50 m` dyadic affine lattice, with exact integer bounds and independent
topology replay. The generic jittered case has a measured worst departure from
the ideal rational coordinates of exactly
`31397/253327479039590400 m` (about `1.2393839041477703e-13 m`); this corrected
the narrower preliminary estimate without changing a scientific tolerance,
rank rule, candidate, or decision rule.

The first clean local build after that amendment, source
`c2d6500d2cd97f5fdf4b96e93a5a39870593c3ff`, preserved another validation
failure. CTest completed all 47 tests in `1298.88 s`; 46 passed and
`mls.mechanical_observability.smoke.verify` failed because `--allow-smoke`
incorrectly selected the legacy pre-q50 geometry for every non-full bundle.
The fresh smoke producer itself emitted q50 coordinates. The validator now
uses q50 by default for current smoke and full evidence. Byte-authentic legacy
synthetic fixtures require an explicit, default-off
`--legacy-pre-q50-test-fixture` flag together with `--allow-smoke`, and that
flag is rejected for full summaries. The failed CTest run is not reclassified
as a passing run.
