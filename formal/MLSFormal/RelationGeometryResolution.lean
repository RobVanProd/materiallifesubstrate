import MLSFormal.ConservativeForceConsistency
import Mathlib.Analysis.SpecialFunctions.Sqrt
import Mathlib.Tactic.Positivity

set_option autoImplicit false

namespace MLSFormal

/-!
# Exact relation-geometry reformulation

This module proves only the real-arithmetic identity used by the Relation
Geometry Resolution Lab.  It makes no statement about binary64 rounding,
forward error, a selectable evaluator, or admissibility near coincidence.
-/

/-- Rationalizing a difference of nonnegative square roots preserves its
exact real value whenever the denominator is positive. -/
theorem sqrt_sub_eq_sub_div_add
    (a b : ℝ)
    (aNonnegative : 0 ≤ a)
    (bNonnegative : 0 ≤ b)
    (denominatorPositive : 0 < Real.sqrt a + Real.sqrt b) :
    Real.sqrt a - Real.sqrt b =
      (a - b) / (Real.sqrt a + Real.sqrt b) := by
  apply (eq_div_iff (ne_of_gt denominatorPositive)).2
  nlinarith [Real.sq_sqrt aNonnegative, Real.sq_sqrt bNonnegative]

/-- Squared Euclidean distance of two exact three-coordinate real points. -/
def relationSquaredDistance
    (first second : Fin 3 → ℝ) : ℝ :=
  ∑ axis : Fin 3, (second axis - first axis) ^ 2

theorem relationSquaredDistance_nonnegative
    (first second : Fin 3 → ℝ) :
    0 ≤ relationSquaredDistance first second := by
  unfold relationSquaredDistance
  positivity

/-- The relation extension formed from exact endpoint squared distances has
the same rationalized representation away from a zero denominator. -/
theorem relationExtension_eq_squaredDistanceDifference_div_lengthSum
    (referenceFirst referenceSecond currentFirst currentSecond : Fin 3 → ℝ)
    (denominatorPositive :
      0 < Real.sqrt (relationSquaredDistance currentFirst currentSecond) +
        Real.sqrt (relationSquaredDistance referenceFirst referenceSecond)) :
    Real.sqrt (relationSquaredDistance currentFirst currentSecond) -
        Real.sqrt (relationSquaredDistance referenceFirst referenceSecond) =
      (relationSquaredDistance currentFirst currentSecond -
          relationSquaredDistance referenceFirst referenceSecond) /
        (Real.sqrt (relationSquaredDistance currentFirst currentSecond) +
          Real.sqrt (relationSquaredDistance referenceFirst referenceSecond)) := by
  exact sqrt_sub_eq_sub_div_add
    (relationSquaredDistance currentFirst currentSecond)
    (relationSquaredDistance referenceFirst referenceSecond)
    (relationSquaredDistance_nonnegative currentFirst currentSecond)
    (relationSquaredDistance_nonnegative referenceFirst referenceSecond)
    denominatorPositive

end MLSFormal
