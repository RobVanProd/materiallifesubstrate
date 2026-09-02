import MLSFormal.AuthoritativeMechanicsStateBridge
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

/-!
# Exact authoritative drift bridge identities

These theorems concern exact rational, force-free drift only.  They do not
prove a nearest-even error bound, binary64 behavior, safe timestep, or dynamics.
-/

def forceFreeDriftMomentum (momentum : Vec3) : Vec3 := momentum

def forceFreeDriftPosition
    (position momentum : Vec3) (mass timestep : ℚ) : Vec3 :=
  position + mechanicsVecScale (timestep / mass) momentum

theorem forceFreeDriftMomentum_unchanged (momentum : Vec3) :
    forceFreeDriftMomentum momentum = momentum := by
  rfl

theorem scalarMomentumDisplacement_preserves_orbitalAngularMomentum
    (position momentum : Vec3) (scale : ℚ) :
    orbitalAngularMomentum
        (position + mechanicsVecScale scale momentum) momentum =
      orbitalAngularMomentum position momentum := by
  funext axis
  fin_cases axis <;>
    simp [orbitalAngularMomentum, cross, mechanicsVecScale] <;>
    ring

theorem forceFreeDrift_preserves_orbitalAngularMomentum
    (position momentum : Vec3) (mass timestep : ℚ) :
    orbitalAngularMomentum
        (forceFreeDriftPosition position momentum mass timestep)
        (forceFreeDriftMomentum momentum) =
      orbitalAngularMomentum position momentum := by
  exact scalarMomentumDisplacement_preserves_orbitalAngularMomentum
    position momentum (timestep / mass)

theorem primitiveDirectionalQuantization_zero_orbitalDelta
    (primitive : Vec3) (momentumMultiple displacementMultiple : ℚ) :
    cross
        (mechanicsVecScale displacementMultiple primitive)
        (mechanicsVecScale momentumMultiple primitive) = 0 := by
  funext axis
  fin_cases axis <;>
    simp [cross, mechanicsVecScale] <;>
    ring

theorem primitiveDirectionalDrift_preserves_orbitalAngularMomentum
    (position primitive : Vec3)
    (momentumMultiple displacementMultiple : ℚ) :
    orbitalAngularMomentum
        (position + mechanicsVecScale displacementMultiple primitive)
        (mechanicsVecScale momentumMultiple primitive) =
      orbitalAngularMomentum position
        (mechanicsVecScale momentumMultiple primitive) := by
  funext axis
  fin_cases axis <;>
    simp [orbitalAngularMomentum, cross, mechanicsVecScale] <;>
    ring

theorem coherentRefinedDriftRawIdentity
    (momentum mass timestep refinement : ℚ)
    (massNonzero : mass ≠ 0)
    (refinementNonzero : refinement ≠ 0) :
    (refinement ^ 2 * momentum * timestep) / (refinement * mass) =
      refinement * (momentum * timestep / mass) := by
  field_simp [massNonzero, refinementNonzero]

end MLSFormal
