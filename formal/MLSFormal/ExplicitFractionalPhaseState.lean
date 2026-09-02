import MLSFormal.PhaseSpaceTimeCorefinement
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

/-!
# Reciprocal integer phase-lattice obstruction

These are exact integer/rational algebra statements. They do not prove a
floating-point force evaluation, time-integration order, or bounded rational
state complexity.
-/

/-- An exact-central integer impulse is a primitive multiple of the raw
relation direction under the same explicit Bezout witness used for drift. -/
theorem integerCrossZeroKick_isPrimitiveMultiple
    (jx jy jz rx ry rz g ux uy uz a b c : ℤ)
    (gNonzero : g ≠ 0)
    (rxFactor : rx = g * ux)
    (ryFactor : ry = g * uy)
    (rzFactor : rz = g * uz)
    (crossXY : jx * ry = jy * rx)
    (crossXZ : jx * rz = jz * rx)
    (crossYZ : jy * rz = jz * ry)
    (primitiveBezout : a * ux + b * uy + c * uz = 1) :
    ∃ k : ℤ, jx = k * ux ∧ jy = k * uy ∧ jz = k * uz := by
  exact integerCrossZeroDrift_isPrimitiveMultiple
    jx jy jz rx ry rz g ux uy uz a b c gNonzero
    rxFactor ryFactor rzFactor crossXY crossXZ crossYZ primitiveBezout

/-- The primitive-multiple theorem gives the same minimum nonzero squared
magnitude for exact-central integer kicks as for exact-L integer drifts. -/
theorem nonzeroPrimitiveKick_minimumSquaredImpulse
    (jx jy jz ux uy uz k : ℤ)
    (jxFactor : jx = k * ux)
    (jyFactor : jy = k * uy)
    (jzFactor : jz = k * uz)
    (impulseNonzero : jx ≠ 0 ∨ jy ≠ 0 ∨ jz ≠ 0) :
    ux * ux + uy * uy + uz * uz ≤ jx * jx + jy * jy + jz * jz := by
  exact nonzeroPrimitiveMultiple_minimumSquaredDisplacement
    jx jy jz ux uy uz k jxFactor jyFactor jzFactor impulseNonzero

/-- Rewriting the minimum exact-central kick in physical relation
coordinates. Squared norms avoid any square-root assumptions. -/
theorem minimumCentralKickSquared_physical
    (lengthQuantum momentumQuantum rawRelationSquared
      physicalRelationSquared relationGcdSquared minimumImpulseSquared : ℚ)
    (lengthNonzero : lengthQuantum ≠ 0)
    (gcdNonzero : relationGcdSquared ≠ 0)
    (physicalRelation :
      physicalRelationSquared = lengthQuantum ^ 2 * rawRelationSquared)
    (minimumImpulse :
      minimumImpulseSquared =
        momentumQuantum ^ 2 * rawRelationSquared / relationGcdSquared) :
    minimumImpulseSquared =
      (momentumQuantum / lengthQuantum) ^ 2 *
        physicalRelationSquared / relationGcdSquared := by
  rw [minimumImpulse, physicalRelation]
  field_simp [lengthNonzero, gcdNonzero]

/-- Rewriting the minimum exact-L drift in physical momentum coordinates. -/
theorem minimumDriftSquared_physical
    (lengthQuantum momentumQuantum rawMomentumSquared
      physicalMomentumSquared momentumGcdSquared minimumDriftSquared : ℚ)
    (momentumNonzero : momentumQuantum ≠ 0)
    (gcdNonzero : momentumGcdSquared ≠ 0)
    (physicalMomentum :
      physicalMomentumSquared = momentumQuantum ^ 2 * rawMomentumSquared)
    (minimumDrift :
      minimumDriftSquared =
        lengthQuantum ^ 2 * rawMomentumSquared / momentumGcdSquared) :
    minimumDriftSquared =
      (lengthQuantum / momentumQuantum) ^ 2 *
        physicalMomentumSquared / momentumGcdSquared := by
  rw [minimumDrift, physicalMomentum]
  field_simp [momentumNonzero, gcdNonzero]

/-- Multiplying the squared minimum kick and drift cancels both unit quanta.
The remaining obstruction depends only on physical squared norms and gcds. -/
theorem reciprocalKickDriftResolution_squared
    (lengthQuantum momentumQuantum physicalRelationSquared
      physicalMomentumSquared relationGcdSquared momentumGcdSquared
      minimumImpulseSquared minimumDriftSquared : ℚ)
    (lengthNonzero : lengthQuantum ≠ 0)
    (momentumNonzero : momentumQuantum ≠ 0)
    (relationGcdNonzero : relationGcdSquared ≠ 0)
    (momentumGcdNonzero : momentumGcdSquared ≠ 0)
    (minimumImpulse :
      minimumImpulseSquared =
        (momentumQuantum / lengthQuantum) ^ 2 *
          physicalRelationSquared / relationGcdSquared)
    (minimumDrift :
      minimumDriftSquared =
        (lengthQuantum / momentumQuantum) ^ 2 *
          physicalMomentumSquared / momentumGcdSquared) :
    minimumImpulseSquared * minimumDriftSquared =
      physicalRelationSquared * physicalMomentumSquared /
        (relationGcdSquared * momentumGcdSquared) := by
  rw [minimumImpulse, minimumDrift]
  field_simp [lengthNonzero, momentumNonzero,
    relationGcdNonzero, momentumGcdNonzero]

/-- Primitive raw relation and momentum vectors specialize both squared gcds
to one, leaving a unit-independent product. -/
theorem primitiveReciprocalKickDriftResolution_squared
    (lengthQuantum momentumQuantum physicalRelationSquared
      physicalMomentumSquared minimumImpulseSquared minimumDriftSquared : ℚ)
    (lengthNonzero : lengthQuantum ≠ 0)
    (momentumNonzero : momentumQuantum ≠ 0)
    (minimumImpulse :
      minimumImpulseSquared =
        (momentumQuantum / lengthQuantum) ^ 2 * physicalRelationSquared)
    (minimumDrift :
      minimumDriftSquared =
        (lengthQuantum / momentumQuantum) ^ 2 * physicalMomentumSquared) :
    minimumImpulseSquared * minimumDriftSquared =
      physicalRelationSquared * physicalMomentumSquared := by
  rw [minimumImpulse, minimumDrift]
  field_simp [lengthNonzero, momentumNonzero]

end MLSFormal
