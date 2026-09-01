import MLSFormal.TransitionModel
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

/-!
# Exact authoritative mechanics bridge identities

These statements concern only exact rational units and exact equal/opposite
central impulses.  They do not prove binary64 rounding, an error bound, a
force-work approximation, or an admissible time evolution.
-/

def mechanicsMomentumQuantum (mass length time : ℚ) : ℚ :=
  mass * length / time

def mechanicsEnergyQuantum (mass length time : ℚ) : ℚ :=
  mass * length ^ 2 / time ^ 2

def mechanicsForceQuantum (mass length time : ℚ) : ℚ :=
  mass * length / time ^ 2

theorem mechanicsEnergyQuantum_eq_momentum_mul_velocity
    (mass length time : ℚ) (timeNonzero : time ≠ 0) :
    mechanicsEnergyQuantum mass length time =
      mechanicsMomentumQuantum mass length time * (length / time) := by
  unfold mechanicsEnergyQuantum mechanicsMomentumQuantum
  field_simp [timeNonzero]

theorem mechanicsForceQuantum_eq_energy_div_length
    (mass length time : ℚ)
    (lengthNonzero : length ≠ 0)
    (timeNonzero : time ≠ 0) :
    mechanicsForceQuantum mass length time =
      mechanicsEnergyQuantum mass length time / length := by
  unfold mechanicsForceQuantum mechanicsEnergyQuantum
  field_simp [lengthNonzero, timeNonzero]

theorem refinedMomentumQuantum_identity
    (mass length time refinement : ℚ)
    (timeNonzero : time ≠ 0)
    (refinementNonzero : refinement ≠ 0) :
    mechanicsMomentumQuantum (mass / refinement) (length / refinement) time =
      mechanicsMomentumQuantum mass length time / refinement ^ 2 := by
  unfold mechanicsMomentumQuantum
  field_simp [timeNonzero, refinementNonzero]

theorem refinedEnergyQuantum_identity
    (mass length time refinement : ℚ)
    (timeNonzero : time ≠ 0)
    (refinementNonzero : refinement ≠ 0) :
    mechanicsEnergyQuantum (mass / refinement) (length / refinement) time =
      mechanicsEnergyQuantum mass length time / refinement ^ 3 := by
  unfold mechanicsEnergyQuantum
  field_simp [timeNonzero, refinementNonzero]

def mechanicsVecScale (scale : ℚ) (vector : Vec3) : Vec3 :=
  fun axis => scale * vector axis

theorem exactQuantizedPairImpulse_preserves_momentum
    (firstMomentum secondMomentum impulse : Vec3) :
    (firstMomentum + impulse) + (secondMomentum - impulse) =
      firstMomentum + secondMomentum := by
  funext axis
  simp

theorem centralPrimitiveQuantizedImpulse_zero_couple
    (offset : Vec3) (multiple : ℚ) :
    cross offset (mechanicsVecScale multiple offset) = 0 := by
  funext axis
  fin_cases axis <;>
    simp [cross, mechanicsVecScale] <;>
    ring

theorem centralPrimitiveQuantizedPair_preserves_orbitalAngularMomentum
    (firstPosition secondPosition firstMomentum secondMomentum : Vec3)
    (multiple : ℚ) :
    let offset := firstPosition - secondPosition
    let impulse := mechanicsVecScale multiple offset
    orbitalAngularMomentum firstPosition (firstMomentum + impulse) +
        orbitalAngularMomentum secondPosition (secondMomentum - impulse) =
      orbitalAngularMomentum firstPosition firstMomentum +
        orbitalAngularMomentum secondPosition secondMomentum := by
  dsimp
  have delta := pairImpulse_orbitalAngular_delta
    firstPosition secondPosition firstMomentum secondMomentum
      (mechanicsVecScale multiple (firstPosition - secondPosition))
  rw [centralPrimitiveQuantizedImpulse_zero_couple] at delta
  exact sub_eq_zero.mp delta

theorem explicitRemainderStep_balance
    (available rounded : ℚ) :
    rounded + (available - rounded) = available := by
  ring

theorem explicitRemainderAccumulation_balance
    (target applied remainder : ℚ)
    (remainderDefinition : remainder = target - applied) :
    applied + remainder = target := by
  rw [remainderDefinition]
  ring

end MLSFormal
