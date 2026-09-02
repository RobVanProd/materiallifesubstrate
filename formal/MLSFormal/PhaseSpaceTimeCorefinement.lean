import MLSFormal.TimeIntegrationFoundation
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.LinearCombination
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

/-!
# Integer phase-space co-refinement constraints

These theorems state exact algebraic facts about integer vectors and coherent
unit quanta. They do not prove finite-width safety, floating-point accuracy,
trajectory convergence, or an integrator property.
-/

theorem integerParallelToBezoutPrimitive
    (dx dy dz ux uy uz a b c : ℤ)
    (parallelXY : dx * uy = dy * ux)
    (parallelXZ : dx * uz = dz * ux)
    (parallelYZ : dy * uz = dz * uy)
    (bezout : a * ux + b * uy + c * uz = 1) :
    ∃ k : ℤ, dx = k * ux ∧ dy = k * uy ∧ dz = k * uz := by
  let k := a * dx + b * dy + c * dz
  refine ⟨k, ?_, ?_, ?_⟩
  · calc
      dx = dx * (a * ux + b * uy + c * uz) := by rw [bezout]; ring
      _ = k * ux := by
        dsimp [k]
        linear_combination b * parallelXY + c * parallelXZ
  · calc
      dy = dy * (a * ux + b * uy + c * uz) := by rw [bezout]; ring
      _ = k * uy := by
        dsimp [k]
        linear_combination -a * parallelXY + c * parallelYZ
  · calc
      dz = dz * (a * ux + b * uy + c * uz) := by rw [bezout]; ring
      _ = k * uz := by
        dsimp [k]
        linear_combination -a * parallelXZ - b * parallelYZ

theorem integerCrossZeroDrift_isPrimitiveMultiple
    (dx dy dz px py pz g ux uy uz a b c : ℤ)
    (gNonzero : g ≠ 0)
    (pxFactor : px = g * ux)
    (pyFactor : py = g * uy)
    (pzFactor : pz = g * uz)
    (crossXY : dx * py = dy * px)
    (crossXZ : dx * pz = dz * px)
    (crossYZ : dy * pz = dz * py)
    (primitiveBezout : a * ux + b * uy + c * uz = 1) :
    ∃ k : ℤ, dx = k * ux ∧ dy = k * uy ∧ dz = k * uz := by
  have parallelXY : dx * uy = dy * ux := by
    have scaled : g * (dx * uy - dy * ux) = 0 := by
      calc
        g * (dx * uy - dy * ux) = dx * (g * uy) - dy * (g * ux) := by ring
        _ = dx * py - dy * px := by rw [← pyFactor, ← pxFactor]
        _ = 0 := sub_eq_zero.mpr crossXY
    exact sub_eq_zero.mp ((mul_eq_zero.mp scaled).resolve_left gNonzero)
  have parallelXZ : dx * uz = dz * ux := by
    have scaled : g * (dx * uz - dz * ux) = 0 := by
      calc
        g * (dx * uz - dz * ux) = dx * (g * uz) - dz * (g * ux) := by ring
        _ = dx * pz - dz * px := by rw [← pzFactor, ← pxFactor]
        _ = 0 := sub_eq_zero.mpr crossXZ
    exact sub_eq_zero.mp ((mul_eq_zero.mp scaled).resolve_left gNonzero)
  have parallelYZ : dy * uz = dz * uy := by
    have scaled : g * (dy * uz - dz * uy) = 0 := by
      calc
        g * (dy * uz - dz * uy) = dy * (g * uz) - dz * (g * uy) := by ring
        _ = dy * pz - dz * py := by rw [← pzFactor, ← pyFactor]
        _ = 0 := sub_eq_zero.mpr crossYZ
    exact sub_eq_zero.mp ((mul_eq_zero.mp scaled).resolve_left gNonzero)
  exact integerParallelToBezoutPrimitive
    dx dy dz ux uy uz a b c parallelXY parallelXZ parallelYZ
    primitiveBezout

theorem nonzeroPrimitiveMultiple_minimumSquaredDisplacement
    (dx dy dz ux uy uz k : ℤ)
    (dxFactor : dx = k * ux)
    (dyFactor : dy = k * uy)
    (dzFactor : dz = k * uz)
    (displacementNonzero : dx ≠ 0 ∨ dy ≠ 0 ∨ dz ≠ 0) :
    ux * ux + uy * uy + uz * uz ≤ dx * dx + dy * dy + dz * dz := by
  have kNonzero : k ≠ 0 := by
    intro kZero
    have dxZero : dx = 0 := by rw [dxFactor, kZero]; ring
    have dyZero : dy = 0 := by rw [dyFactor, kZero]; ring
    have dzZero : dz = 0 := by rw [dzFactor, kZero]; ring
    rcases displacementNonzero with dxNonzero | dyNonzero | dzNonzero
    · exact dxNonzero dxZero
    · exact dyNonzero dyZero
    · exact dzNonzero dzZero
  have kCases : k ≤ -1 ∨ 1 ≤ k := by omega
  have kSquared : 1 ≤ k * k := by
    rcases kCases with negative | positive <;> nlinarith
  have primitiveSquaredNonnegative :
      0 ≤ ux * ux + uy * uy + uz * uz := by
    nlinarith [sq_nonneg ux, sq_nonneg uy, sq_nonneg uz]
  have productNonnegative :
      0 ≤ (k * k - 1) * (ux * ux + uy * uy + uz * uz) :=
    mul_nonneg (sub_nonneg.mpr kSquared) primitiveSquaredNonnegative
  calc
    ux * ux + uy * uy + uz * uz ≤
        (k * ux) * (k * ux) + (k * uy) * (k * uy) +
          (k * uz) * (k * uz) := by
      nlinarith
    _ = dx * dx + dy * dy + dz * dz := by
      rw [dxFactor, dyFactor, dzFactor]

theorem gcdOneMinimumPhysicalDriftIdentity
    (lengthQuantum massQuantum timeQuantum rawMomentumNorm
      physicalMomentumNorm : ℚ)
    (massNonzero : massQuantum ≠ 0)
    (timeNonzero : timeQuantum ≠ 0)
    (physicalMomentum :
      physicalMomentumNorm =
        (massQuantum * lengthQuantum / timeQuantum) * rawMomentumNorm) :
    lengthQuantum * rawMomentumNorm =
      physicalMomentumNorm * timeQuantum / massQuantum := by
  rw [physicalMomentum]
  field_simp [massNonzero, timeNonzero]

theorem orderMatchedRawBallisticFactor
    (lengthQuantum massQuantum timeQuantum momentumQuantum : ℚ)
    (lengthNonzero : lengthQuantum ≠ 0)
    (massNonzero : massQuantum ≠ 0)
    (timeNonzero : timeQuantum ≠ 0)
    (momentumDerived :
      momentumQuantum = massQuantum * lengthQuantum / timeQuantum) :
    momentumQuantum * timeQuantum /
        (massQuantum * lengthQuantum) = 1 := by
  rw [momentumDerived]
  field_simp [lengthNonzero, massNonzero, timeNonzero]

end MLSFormal
