import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

open scoped BigOperators

/-- Total inventory of one element across a finite set of compounds. -/
def elementInventory
    {Element Species : Type*} [Fintype Species]
    (composition : Element → Species → ℤ)
    (amount : Species → ℤ)
    (element : Element) : ℤ :=
  ∑ species, composition element species * amount species

/-- A reaction vector is balanced when its net count of every element is zero. -/
def StoichiometricallyBalanced
    {Element Species : Type*} [Fintype Species]
    (composition : Element → Species → ℤ)
    (reaction : Species → ℤ) : Prop :=
  ∀ element, ∑ species, composition element species * reaction species = 0

/-- `A * nu = 0` implies that every element inventory is unchanged by a reaction extent. -/
theorem balancedReaction_preserves_elements
    {Element Species : Type*} [Fintype Species]
    (composition : Element → Species → ℤ)
    (amount reaction : Species → ℤ)
    (extent : ℤ)
    (balanced : StoichiometricallyBalanced composition reaction)
    (element : Element) :
    elementInventory composition
        (fun species => amount species + extent * reaction species) element =
      elementInventory composition amount element := by
  classical
  unfold elementInventory
  simp_rw [mul_add]
  rw [Finset.sum_add_distrib]
  have scaledReaction :
      (∑ species, composition element species *
          (extent * reaction species)) =
        extent *
          (∑ species, composition element species * reaction species) := by
    rw [Finset.mul_sum]
    apply Finset.sum_congr rfl
    intro species _
    ring
  rw [scaledReaction, balanced element]
  ring

end MLSFormal
