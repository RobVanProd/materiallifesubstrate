# Coarse-graining can invent affordances

Conserving extensive totals is not sufficient for a safe physics level of detail.
Spatial correlations, interfaces, and material history can determine which
interactions are possible.

## Minimal counterexample

Suppose a local reaction requires `A` and `B` in the same reaction volume:

\[
A + B \rightarrow C.
\]

Two neighboring fine cells contain

\[
x_1=(A=1,B=0), \qquad x_2=(A=0,B=1).
\]

The total inventory is `A=1, B=1`, but each fine-cell reaction capacity is

\[
r(x)=\min(A(x),B(x)), \qquad r(x_1)+r(x_2)=0.
\]

A coarse cell produced by summing the inventories contains

\[
C(x_1,x_2)=(A=1,B=1)
\]

and therefore

\[
r(C(x_1,x_2))=1.
\]

The compression exactly conserved both elements and still invented a reaction.
The same class of error can erase or invent a membrane, sharp interface, crack,
catalyst geometry, charge separation, or mechanical linkage.

The Lean proof-candidate encodes this finite counterexample in
[`formal/MLSFormal/CoarseGraining.lean`](../formal/MLSFormal/CoarseGraining.lean).
That theorem establishes the arithmetic example only; it does not certify a
general coarse solver.

## v0 decision

MLS v0 forbids aggressive lossy physics LOD. In particular:

- resolution and update rate never depend on camera distance or visibility;
- no coarse voxel replaces mixed fine state merely because totals match;
- sleeping is permitted only for a proved/tested quiescence envelope;
- paging preserves exact authoritative state;
- sparse allocation removes empty storage, not physical detail; and
- local time stepping must preserve coupling and ledger contracts at temporal
  boundaries.

## Research relation

For fine dynamics `F`, coarse dynamics `G`, compression `C`, observations `O`, a
legal intervention sequence `a[0:h]`, and horizon `h`, the desired condition is
closer to

\[
O_f(F^h(x,a_{0:h})) \approx
O_c(G^h(C(x),a_{0:h}))
\]

than to conservation alone. A useful criterion must quantify:

- the legal interventions being preserved;
- observations and tolerances;
- time horizons and failure probabilities;
- reconstruction of latent interfaces and history; and
- compositional behavior when a region re-enters fine simulation.

This resembles model reduction and approximate simulation/bisimulation. MLS does
not claim a new theory. The open research difficulty is that evolution may exploit
a tiny detail thousands of generations later; selecting “relevant” observations
in advance can itself close the adjacent possible.

No lossy scheme is admissible merely because it satisfies the abstract relation
on a convenient current benchmark set. Gate 15 treats preservation of unknown
future affordances as a challenge, not a solved feature.
