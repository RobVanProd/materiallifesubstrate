# Raw-matter affordance gauntlet

The gauntlet is the MLS-0 kill test. Construct each target using only configured
virtual elements, compound graphs, packet placement, initial physical fields, and
boundary fixtures available to every experiment. The simulator receives no
target label. Success is a measured response under load, not visual resemblance.

## Required constructions

| Observer label | Physical success criterion | Essential controls |
|---|---|---|
| Sharp edge | Concentrates contact stress and produces convergent damage/separation in a weaker target at lower total load than a blunt equal-mass control. | Rotate both setups; sweep tip radius, target strength, grid spacing, and timestep. |
| Fiber/rope | Carries sustained tensile load primarily along its axis and fails according to local stress/damage rather than an attachment flag. | Equal-mass disconnected and transverse arrangements. |
| Beam | Carries bending load with a stiffness/failure response derived from geometry and material structure. | Same material as an unstructured pile; orientation and span sweeps. |
| Vessel/cup | Retains a fluid against gravity and predictable pressure for a declared duration and leak threshold. | Cracked wall, inverted geometry, and resolution controls. |
| Wheel/axle | Supports load while rotating with materially lower resistance than a sliding equal-load control. | Locked axle, noncircular body, rotated grid. |
| Spring | Stores mechanical energy under deformation and returns a declared fraction on release, with the remainder booked as heat/damage. | Plastic and disconnected equal-mass controls. |
| Lever | Transfers force/displacement according to geometry and contact without a lever constraint primitive. | Remove or move fulcrum; equal-material pile. |
| Pipe | Produces greater directed fluid transport than unbounded diffusion/flow under the same pressure or concentration difference. | Broken and obstructed pipe controls. |
| Membrane | Produces reproducibly different transport rates for physically different compounds while remaining materially bounded. | No membrane, ruptured membrane, swapped solutes. |
| Insulator | Reduces heat flux under a matched temperature gradient because of its material structure. | Equal-thickness conductive control. |
| Conductor | Transmits a modeled physical signal/charge with lower attenuation or resistance than a matched control. | Broken path and nonconductive equal-mass control. |
| Catalyst | Changes a balanced reaction rate without net catalyst consumption or hidden energy/matter injection. | No catalyst, inactive structural analogue, equilibrium/energy checks. |

The initial headline acceptance set is knife/sharp edge, rope, cup, membrane,
spring, and catalyst. The full table is Gate 7.

## Protocol

For every construction:

1. register target metric, load envelope, duration, tolerances, and negative
   controls before running;
2. generate it through the same public matter-configuration interface available
   to blind search, with no semantic component IDs;
3. inspect all matter, momentum, energy, and field ledgers;
4. repeat across timestep and spatial resolution;
5. rotate relative to the grid and translate across brick boundaries;
6. perturb geometry and composition to show a response surface, not one lucky
   configuration;
7. replay in deterministic mode and, where practical, another solver/backend;
8. archive the initial state, interventions, build/config hash, result, and
   observer analysis separately; and
9. send any surprising or exploit-like outcome to quarantine.

## Blind rediscovery

After Gate 7, freeze physics, constants, chemistry grammar, ABI, and evaluation
infrastructure. A separate experiment owner selects held-out affordances and
provides only physical interventions and outcome measurements. Search may arrange
raw matter but may not invoke target names, recipes, components, pretrained
examples, semantic sensors, or shaped intermediate rewards that encode a design.

Use matched budgets and null controls. Report failure and search sensitivity.
Rediscovery supports substrate composability; it does not establish life or
open-ended evolution.
