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
