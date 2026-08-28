# Accounting invariants

Accounting is part of the world definition, not post-hoc telemetry. Each accepted
step must close its local transactions and its global ledger. Conservation is
necessary but, as the coarse-graining counterexample shows, not sufficient for
causal fidelity.

## Conserved constituent inventory

Let `q[p,e]` be the exact amount of virtual element `e` carried by packet `p` and
let declared reservoirs be included in the accounting domain. For every element:

\[
N_e = \sum_p q_{p,e} + \sum_r q_{r,e}.
\]

`N_e` is invariant in a materially closed scenario. A boundary matter port may
change it only by an equal, typed ledger entry. Transport, packet/grid transfer,
packet split/merge, sleep/paging, chemistry, construction, reproduction, and
death cannot otherwise change it.

Use integer counts or another exact representation for discrete constituent
inventories. Floating-point tolerance is not an excuse for creating atoms.

## Stoichiometric balance

Let matrix `A[e,s]` give the count of element `e` in compound species/graph `s`,
and let reaction vector `nu[s]` contain signed stoichiometric changes. A reaction
is admissible only when

\[
A\nu = 0.
\]

If `n' = n + xi nu` for a legal extent `xi`, then `An' = An`. The implementation
must also prove or check that all post-reaction inventories are non-negative and
that bond changes meet the configured kinetics and energy conditions. Balance
alone does not make a reaction physically valid.

## Mass and representation changes

Mass is a configured function of conserved constituents and any explicitly
modeled binding convention. Packet split, merge, grid transfer, and aggregation
must preserve the sum of every extensive quantity and the material history needed
to reproduce later constitutive behavior. A representation change may not erase
segregation, interfaces, bonds, damage, or another latent affordance.

## Linear and angular momentum

For an internal pair impulse `J`:

\[
p_i' = p_i + J, \qquad p_j' = p_j - J,
\]

so total linear momentum is unchanged. Global change must equal declared boundary
impulse. Internal torques and packet/grid transfers must likewise conserve total
angular momentum up to a predeclared, convergent numerical residual; boundaries
book angular impulse explicitly.

## Energy ledger

The world ledger distinguishes at least kinetic, elastic/mechanical, internal
thermal, chemical/bond, and modeled field/radiative energy. Reservoir energy is
included in the closed accounting universe. For one accepted step:

\[
\Delta E_{world} + \Delta E_{reservoirs} = r_E.
\]

`r_E` is a numerical residual, not a hidden energy source. Its norm, sign, spatial
origin, and solver stage are recorded. Acceptance bounds are declared before an
experiment, tighten under timestep/refinement studies, and are tested against
repeated exploit cycles. Conversion terms appear once as paired debits and
credits: chemical-to-work, fracture-to-surface/heat, damping-to-heat, radiation
absorption, and boundary heat exchange.

## Charge and other field sources

If charge or another conserved field source is enabled, it receives the same
treatment as constituent inventory: local continuity, boundary flux entries, and
global closure. A field solver may redistribute energy and momentum but cannot
silently source them.

## Positivity and admissibility

Accepted states satisfy:

- non-negative constituent and compound amounts;
- non-negative mass and physically admissible density/volume;
- non-negative absolute temperature and internal energy under the selected
  equation of state;
- reaction extents bounded by available reactants;
- finite state values and valid packet/grid ownership; and
- material parameters inside their declared domain.

Clamping after the fact is normally an unledgered mutation. If a positivity
repair is unavoidable, it is explicit, booked, bounded, and treated as a failed
accuracy condition until convergence removes it.

## Local-to-global closure

Every internal transfer creates equal and opposite local entries with a shared
transaction ID. Reducing local ledgers must reproduce the global change. This
supports fault localization and prevents a globally small residual from hiding
large canceling errors.

At checkpoint acceptance, record:

```text
state/configuration hash
step and simulated time
solver/backend/build identity
random-stream position
constituent totals
linear and angular momentum totals
energy totals by store and reservoir
boundary fluxes
residuals by operator and spatial brick
positivity repairs or rejected operations
```

## Determinism and replay

Randomness is explicit state. Parallel reductions use a specified deterministic
mode for reference runs. Cross-backend runs need not be bit-identical, but the
same checkpoint and intervention must satisfy conservation, convergence, and the
cross-fidelity causal criteria in the validation plan.

## What these invariants do not prove

They do not prove correct continuum equations, stable discretization, isotropy,
fracture realism, chemical expressivity, affordance preservation, life,
evolvability, ecology, or open-endedness. Those are numerical and empirical gates;
a green formal result cannot promote a red gate.
