import MLSFormal.Chemistry
import MLSFormal.Conservation
import Mathlib.Data.Fin.VecNotation
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

/-!
This file is deliberately small and executable. It connects the generic
algebraic lemmas to concrete transition functions shaped like the MLS-0
reference operations. Kinetic evaluation is a parameter so the same transition
law covers the C++ fixed-point/flooring evaluator without re-specifying that
algorithm here. This is not a model of continuum mechanics.
-/

abbrev Vec3 := Fin 3 → ℚ

/-- Exact three-dimensional cross product. -/
def cross (left right : Vec3) : Vec3 :=
  ![left 1 * right 2 - left 2 * right 1,
    left 2 * right 0 - left 0 * right 2,
    left 0 * right 1 - left 1 * right 0]

/-- Orbital angular momentum of one point packet. -/
def orbitalAngularMomentum (position momentum : Vec3) : Vec3 :=
  cross position momentum

/-- Compact executable state for the actual MLS transfer/energy/impulse shapes. -/
structure PacketLite where
  material : ℚ
  structuralEnergy : ℚ
  storedEnergy : ℚ
  thermalEnergy : ℚ
  position : Vec3
  momentum : Vec3

/-- A two-packet world plus one explicit boundary reservoir. -/
structure WorldLite where
  first : PacketLite
  second : PacketLite
  reservoirMaterial : ℚ
  reservoirEnergy : ℚ
  reservoirMomentum : Vec3
  reservoirAngularMomentum : Vec3

/-- Executable finite-species chemical state, separate from the mechanics model. -/
structure ChemicalPacketLite (Species : Type*) where
  amount : Species → ℤ

def WorldLite.materialTotal (world : WorldLite) : ℚ :=
  world.first.material + world.second.material + world.reservoirMaterial

/-- Total energy with caller-supplied derived kinetic evaluators for each packet. -/
def WorldLite.energyTotal
    (world : WorldLite) (firstKinetic secondKinetic : Vec3 → ℚ) : ℚ :=
  world.first.structuralEnergy + world.first.storedEnergy + world.first.thermalEnergy +
    firstKinetic world.first.momentum +
    world.second.structuralEnergy + world.second.storedEnergy + world.second.thermalEnergy +
    secondKinetic world.second.momentum + world.reservoirEnergy

def WorldLite.momentumTotal (world : WorldLite) : Vec3 :=
  world.first.momentum + world.second.momentum + world.reservoirMomentum

def WorldLite.angularMomentumTotal (world : WorldLite) : Vec3 :=
  orbitalAngularMomentum world.first.position world.first.momentum +
    orbitalAngularMomentum world.second.position world.second.momentum +
    world.reservoirAngularMomentum

/-- Move heat between the two packets, matching `World::transfer_heat`. -/
def transferHeat (world : WorldLite) (amount : ℚ) : WorldLite :=
  { world with
    first := { world.first with thermalEnergy := world.first.thermalEnergy - amount }
    second := { world.second with thermalEnergy := world.second.thermalEnergy + amount } }

/-- Apply an arbitrary stoichiometric reaction vector at an integer extent. -/
def applyReaction
    {Species : Type*}
    (packet : ChemicalPacketLite Species)
    (reaction : Species → ℤ)
    (extent : ℤ) : ChemicalPacketLite Species :=
  { amount := fun species => packet.amount species + extent * reaction species }

/-- Replace structural energy and put the exact opposite change in heat. -/
def replaceStructuralEnergy (world : WorldLite) (newStructuralEnergy : ℚ) : WorldLite :=
  { world with
    first :=
      { world.first with
        structuralEnergy := newStructuralEnergy
        thermalEnergy :=
          world.first.thermalEnergy +
            (world.first.structuralEnergy - newStructuralEnergy) } }

/-- Admit material through the boundary while debiting the reservoir. -/
def boundaryMaterialTransfer (world : WorldLite) (amount : ℚ) : WorldLite :=
  { world with
    first := { world.first with material := world.first.material + amount }
    reservoirMaterial := world.reservoirMaterial - amount }

/-- Exchange heat with the boundary reservoir. -/
def boundaryEnergyTransfer (world : WorldLite) (amount : ℚ) : WorldLite :=
  { world with
    first := { world.first with thermalEnergy := world.first.thermalEnergy + amount }
    reservoirEnergy := world.reservoirEnergy - amount }

/-- Apply an equal/opposite point impulse without claiming it is admissible. -/
def rawPairImpulse (world : WorldLite) (impulse : Vec3) : WorldLite :=
  { world with
    first := { world.first with momentum := world.first.momentum + impulse }
    second := { world.second with momentum := world.second.momentum - impulse } }

/-- A point-pair impulse is admissible exactly when it is central (zero couple). -/
def CentralPairImpulse (firstPosition secondPosition impulse : Vec3) : Prop :=
  cross (firstPosition - secondPosition) impulse = 0

/--
The implemented actuated/dissipative energy rule for a representative choice of
first packet as source and second packet as heat sink. `firstKinetic` and
`secondKinetic` may be the C++ quantized/flooring evaluators. If kinetic energy
rises, stored energy pays the delta; if it falls, `-delta` is deposited as heat.
-/
def actuatedDissipativePairImpulse
    (world : WorldLite)
    (impulse : Vec3)
    (firstKinetic secondKinetic : Vec3 → ℚ) : WorldLite :=
  let firstAfter := world.first.momentum + impulse
  let secondAfter := world.second.momentum - impulse
  let kineticDelta :=
    firstKinetic firstAfter + secondKinetic secondAfter -
      (firstKinetic world.first.momentum + secondKinetic world.second.momentum)
  if 0 ≤ kineticDelta then
    { world with
      first :=
        { world.first with
          momentum := firstAfter
          storedEnergy := world.first.storedEnergy - kineticDelta }
      second := { world.second with momentum := secondAfter } }
  else
    { world with
      first := { world.first with momentum := firstAfter }
      second :=
        { world.second with
          momentum := secondAfter
          thermalEnergy := world.second.thermalEnergy - kineticDelta } }

/--
A boundary point impulse records opposite linear/orbital amounts and pays the
derived kinetic change from the explicit reservoir.
-/
def boundaryPointImpulse
    (world : WorldLite) (impulse : Vec3) (firstKinetic : Vec3 → ℚ) : WorldLite :=
  let firstAfter := world.first.momentum + impulse
  let kineticDelta := firstKinetic firstAfter - firstKinetic world.first.momentum
  { world with
    first := { world.first with momentum := firstAfter }
    reservoirEnergy := world.reservoirEnergy - kineticDelta
    reservoirMomentum := world.reservoirMomentum - impulse
    reservoirAngularMomentum :=
      world.reservoirAngularMomentum - cross world.first.position impulse }

theorem transferHeat_preserves_energy
    (world : WorldLite) (amount : ℚ)
    (firstKinetic secondKinetic : Vec3 → ℚ) :
    (transferHeat world amount).energyTotal firstKinetic secondKinetic =
      world.energyTotal firstKinetic secondKinetic := by
  have moved := pairTransfer_preserves_total
    world.first.thermalEnergy world.second.thermalEnergy amount
  simp only [WorldLite.energyTotal, transferHeat]
  calc
    world.first.structuralEnergy + world.first.storedEnergy +
          (world.first.thermalEnergy - amount) + firstKinetic world.first.momentum +
          world.second.structuralEnergy + world.second.storedEnergy +
          (world.second.thermalEnergy + amount) + secondKinetic world.second.momentum +
          world.reservoirEnergy =
        (world.first.thermalEnergy - amount) +
          (world.second.thermalEnergy + amount) + world.first.structuralEnergy +
          world.first.storedEnergy + firstKinetic world.first.momentum +
          world.second.structuralEnergy + world.second.storedEnergy +
          secondKinetic world.second.momentum + world.reservoirEnergy := by ring
    _ = (world.first.thermalEnergy + world.second.thermalEnergy) +
          world.first.structuralEnergy + world.first.storedEnergy +
          firstKinetic world.first.momentum + world.second.structuralEnergy +
          world.second.storedEnergy + secondKinetic world.second.momentum +
          world.reservoirEnergy := by rw [moved]
    _ = world.first.structuralEnergy + world.first.storedEnergy +
          world.first.thermalEnergy + firstKinetic world.first.momentum +
          world.second.structuralEnergy + world.second.storedEnergy +
          world.second.thermalEnergy + secondKinetic world.second.momentum +
          world.reservoirEnergy := by ring

theorem applyReaction_preserves_element
    {Element Species : Type*} [Fintype Species]
    (composition : Element → Species → ℤ)
    (packet : ChemicalPacketLite Species)
    (reaction : Species → ℤ)
    (extent : ℤ)
    (balanced : StoichiometricallyBalanced composition reaction)
    (element : Element) :
    elementInventory composition (applyReaction packet reaction extent).amount element =
      elementInventory composition packet.amount element := by
  exact balancedReaction_preserves_elements
    composition packet.amount reaction extent balanced element

theorem replaceStructuralEnergy_preserves_energy
    (world : WorldLite)
    (newStructuralEnergy : ℚ)
    (firstKinetic secondKinetic : Vec3 → ℚ) :
    (replaceStructuralEnergy world newStructuralEnergy).energyTotal
        firstKinetic secondKinetic =
      world.energyTotal firstKinetic secondKinetic := by
  have converted := chemicalThermalConversion_preserves_energy
    world.first.structuralEnergy world.first.thermalEnergy
    (world.first.structuralEnergy - newStructuralEnergy)
  simp only [WorldLite.energyTotal, replaceStructuralEnergy]
  calc
    newStructuralEnergy + world.first.storedEnergy +
          (world.first.thermalEnergy +
            (world.first.structuralEnergy - newStructuralEnergy)) +
          firstKinetic world.first.momentum + world.second.structuralEnergy +
          world.second.storedEnergy + world.second.thermalEnergy +
          secondKinetic world.second.momentum + world.reservoirEnergy =
        (world.first.structuralEnergy -
            (world.first.structuralEnergy - newStructuralEnergy)) +
          (world.first.thermalEnergy +
            (world.first.structuralEnergy - newStructuralEnergy)) +
          world.first.storedEnergy + firstKinetic world.first.momentum +
          world.second.structuralEnergy + world.second.storedEnergy +
          world.second.thermalEnergy + secondKinetic world.second.momentum +
          world.reservoirEnergy := by ring
    _ = (world.first.structuralEnergy + world.first.thermalEnergy) +
          world.first.storedEnergy + firstKinetic world.first.momentum +
          world.second.structuralEnergy + world.second.storedEnergy +
          world.second.thermalEnergy + secondKinetic world.second.momentum +
          world.reservoirEnergy := by rw [converted]
    _ = world.first.structuralEnergy + world.first.storedEnergy +
          world.first.thermalEnergy + firstKinetic world.first.momentum +
          world.second.structuralEnergy + world.second.storedEnergy +
          world.second.thermalEnergy + secondKinetic world.second.momentum +
          world.reservoirEnergy := by ring

theorem boundaryMaterialTransfer_preserves_material
    (world : WorldLite) (amount : ℚ) :
    (boundaryMaterialTransfer world amount).materialTotal = world.materialTotal := by
  have exchanged := worldReservoirExchange_preserves_energy
    world.first.material world.reservoirMaterial amount
  simp only [WorldLite.materialTotal, boundaryMaterialTransfer]
  calc
    world.first.material + amount + world.second.material +
          (world.reservoirMaterial - amount) =
        (world.first.material + amount) + (world.reservoirMaterial - amount) +
          world.second.material := by ring
    _ = (world.first.material + world.reservoirMaterial) +
          world.second.material := by rw [exchanged]
    _ = world.first.material + world.second.material + world.reservoirMaterial := by ring

theorem boundaryEnergyTransfer_preserves_energy
    (world : WorldLite) (amount : ℚ)
    (firstKinetic secondKinetic : Vec3 → ℚ) :
    (boundaryEnergyTransfer world amount).energyTotal firstKinetic secondKinetic =
      world.energyTotal firstKinetic secondKinetic := by
  have exchanged := worldReservoirExchange_preserves_energy
    world.first.thermalEnergy world.reservoirEnergy amount
  simp only [WorldLite.energyTotal, boundaryEnergyTransfer]
  calc
    world.first.structuralEnergy + world.first.storedEnergy +
          (world.first.thermalEnergy + amount) + firstKinetic world.first.momentum +
          world.second.structuralEnergy + world.second.storedEnergy +
          world.second.thermalEnergy + secondKinetic world.second.momentum +
          (world.reservoirEnergy - amount) =
        (world.first.thermalEnergy + amount) + (world.reservoirEnergy - amount) +
          world.first.structuralEnergy + world.first.storedEnergy +
          firstKinetic world.first.momentum + world.second.structuralEnergy +
          world.second.storedEnergy + world.second.thermalEnergy +
          secondKinetic world.second.momentum := by ring
    _ = (world.first.thermalEnergy + world.reservoirEnergy) +
          world.first.structuralEnergy + world.first.storedEnergy +
          firstKinetic world.first.momentum + world.second.structuralEnergy +
          world.second.storedEnergy + world.second.thermalEnergy +
          secondKinetic world.second.momentum := by rw [exchanged]
    _ = world.first.structuralEnergy + world.first.storedEnergy +
          world.first.thermalEnergy + firstKinetic world.first.momentum +
          world.second.structuralEnergy + world.second.storedEnergy +
          world.second.thermalEnergy + secondKinetic world.second.momentum +
          world.reservoirEnergy := by ring

theorem actuatedDissipativePairImpulse_preserves_momentum
    (world : WorldLite) (impulse : Vec3)
    (firstKinetic secondKinetic : Vec3 → ℚ) :
    (actuatedDissipativePairImpulse world impulse firstKinetic secondKinetic).momentumTotal =
      world.momentumTotal := by
  have exchanged := equalOppositeImpulse_preserves_momentum
    world.first.momentum world.second.momentum impulse
  simp only [actuatedDissipativePairImpulse]
  split <;> simp only [WorldLite.momentumTotal] <;> rw [exchanged]

theorem actuatedDissipativePairImpulse_preserves_energy
    (world : WorldLite) (impulse : Vec3)
    (firstKinetic secondKinetic : Vec3 → ℚ) :
    (actuatedDissipativePairImpulse world impulse firstKinetic secondKinetic).energyTotal
        firstKinetic secondKinetic =
      world.energyTotal firstKinetic secondKinetic := by
  simp only [actuatedDissipativePairImpulse]
  split <;> simp only [WorldLite.energyTotal] <;> ring

/-- The exact defect hidden by a linear-momentum-only point-pair contract. -/
theorem pairImpulse_orbitalAngular_delta
    (firstPosition secondPosition firstMomentum secondMomentum impulse : Vec3) :
    (orbitalAngularMomentum firstPosition (firstMomentum + impulse) +
        orbitalAngularMomentum secondPosition (secondMomentum - impulse)) -
      (orbitalAngularMomentum firstPosition firstMomentum +
        orbitalAngularMomentum secondPosition secondMomentum) =
      cross (firstPosition - secondPosition) impulse := by
  funext component
  fin_cases component <;>
    simp [orbitalAngularMomentum, cross] <;>
    ring

theorem centralActuatedDissipativePairImpulse_preserves_angularMomentum
    (world : WorldLite) (impulse : Vec3)
    (firstKinetic secondKinetic : Vec3 → ℚ)
    (central : CentralPairImpulse world.first.position world.second.position impulse) :
    (actuatedDissipativePairImpulse world impulse firstKinetic secondKinetic).angularMomentumTotal =
      world.angularMomentumTotal := by
  have delta := pairImpulse_orbitalAngular_delta
    world.first.position world.second.position
    world.first.momentum world.second.momentum impulse
  rw [central] at delta
  have orbitalEqual :
      orbitalAngularMomentum world.first.position (world.first.momentum + impulse) +
          orbitalAngularMomentum world.second.position (world.second.momentum - impulse) =
        orbitalAngularMomentum world.first.position world.first.momentum +
          orbitalAngularMomentum world.second.position world.second.momentum := by
    exact sub_eq_zero.mp delta
  simp only [actuatedDissipativePairImpulse]
  split <;> simp only [WorldLite.angularMomentumTotal] <;>
    exact congrArg (fun total => total + world.reservoirAngularMomentum) orbitalEqual

theorem boundaryPointImpulse_preserves_momentum
    (world : WorldLite) (impulse : Vec3) (firstKinetic : Vec3 → ℚ) :
    (boundaryPointImpulse world impulse firstKinetic).momentumTotal =
      world.momentumTotal := by
  simp [WorldLite.momentumTotal, boundaryPointImpulse]
  abel

theorem boundaryPointImpulse_preserves_angularMomentum
    (world : WorldLite) (impulse : Vec3) (firstKinetic : Vec3 → ℚ) :
    (boundaryPointImpulse world impulse firstKinetic).angularMomentumTotal =
      world.angularMomentumTotal := by
  funext component
  fin_cases component <;>
    simp [WorldLite.angularMomentumTotal, boundaryPointImpulse,
      orbitalAngularMomentum, cross] <;>
    ring

theorem boundaryPointImpulse_preserves_energy
    (world : WorldLite) (impulse : Vec3)
    (firstKinetic secondKinetic : Vec3 → ℚ) :
    (boundaryPointImpulse world impulse firstKinetic).energyTotal
        firstKinetic secondKinetic =
      world.energyTotal firstKinetic secondKinetic := by
  simp [WorldLite.energyTotal, boundaryPointImpulse]
  ring

end MLSFormal
