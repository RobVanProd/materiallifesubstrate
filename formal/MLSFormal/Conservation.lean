import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Data.Rat.Defs
import Mathlib.Tactic.Abel
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

section ScalarTransfers

/-- Moving an amount between two scalar stores preserves their sum. -/
theorem pairTransfer_preserves_total (source target amount : ℚ) :
    (source - amount) + (target + amount) = source + target := by
  ring

/-- A bounded non-negative transfer leaves both scalar stores non-negative. -/
theorem pairTransfer_preserves_nonnegativity
    {source target amount : ℚ}
    (_source_nonnegative : 0 ≤ source)
    (target_nonnegative : 0 ≤ target)
    (amount_nonnegative : 0 ≤ amount)
    (amount_bounded : amount ≤ source) :
    0 ≤ source - amount ∧ 0 ≤ target + amount := by
  constructor <;> linarith

end ScalarTransfers

section Momentum

/-- Equal and opposite impulses preserve total momentum in any additive group. -/
theorem equalOppositeImpulse_preserves_momentum
    {V : Type*} [AddCommGroup V] (first second impulse : V) :
    (first + impulse) + (second - impulse) = first + second := by
  abel

end Momentum

section Energy

/-- A paired chemical-to-thermal conversion preserves their combined energy. -/
theorem chemicalThermalConversion_preserves_energy
    (chemical thermal converted : ℚ) :
    (chemical - converted) + (thermal + converted) = chemical + thermal := by
  ring

/-- Energy exchanged between the world and a reservoir closes jointly. -/
theorem worldReservoirExchange_preserves_energy
    (world reservoir exchanged : ℚ) :
    (world + exchanged) + (reservoir - exchanged) = world + reservoir := by
  ring

end Energy

section Aggregation

open scoped BigOperators

/-- Summing two disjoint regions preserves an extensive scalar total. -/
theorem disjointAggregation_preserves_total
    {Index : Type*} [DecidableEq Index]
    (value : Index → ℚ) (left right : Finset Index)
    (disjoint : Disjoint left right) :
    (∑ i ∈ left ∪ right, value i) =
      (∑ i ∈ left, value i) + (∑ i ∈ right, value i) := by
  rw [Finset.sum_union disjoint]

end Aggregation

end MLSFormal
