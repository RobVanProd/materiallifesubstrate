# Preserved input-seal implementation attempts

Candidate evaluations remain zero at these attempts. None changes the frozen
inputs, protocol or scientific disposition. NO_PROMOTION remains.

## Attempt at 3a3ea80822f4d43bf5a830ab8a14cff697fbc9f5

`build/occupied-geometry-input-staging-v2` passed its fresh byte/manifest audit.
The subsequent seal writer stopped before writing `input-root-seal.json` with
`KeyError: 'cube-k0-independent.log'`.

Cause: the newly included Cartesian replay stdout is byte-identical to the
earlier independent input receipt. Content addressing correctly stored those
bytes once, but the package's reverse alias map retained only the first source
path for that blob. The named gate lookup could not find the older alias.

Correction: retain an explicit source-path-to-blob map for every logical
reference, including aliases sharing identical bytes. The physical bytes and
their hashes remain unchanged. Both old staging directories and the failed
source commit remain preserved. A fresh staged package is required; the failed
attempt is not modified into a successful seal.
