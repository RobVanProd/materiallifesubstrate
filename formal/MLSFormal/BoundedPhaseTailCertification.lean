import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.NormNum

set_option autoImplicit false
namespace MLSFormal

/-- A per-stage inclusion invariant gives inclusion along the whole trajectory.
The hypothesis must cover the actual step map, including its rounded force. -/
theorem boundedTail_trajectory_enclosure {α : Type*} (z : ℕ → α)
    (step : ℕ → α → α) (box : ℕ → Set α)
    (initial : z 0 ∈ box 0)
    (recurrence : ∀ n, z (n + 1) = step n (z n))
    (preserves : ∀ n x, x ∈ box n → step n x ∈ box (n + 1)) :
    ∀ n, z n ∈ box n := by
  intro n
  induction n with
  | zero => exact initial
  | succ n ih => rw [recurrence]; exact preserves n (z n) ih

/-- Verifier rounding needs an upper allowance, not an inward witness. -/
theorem boundedTail_outward_slack (error propagated witness slack : ℝ)
    (he : |error| ≤ propagated) (hw : propagated ≤ witness + slack) :
    |error| ≤ witness + slack := le_trans he hw

/-- The absolute weighted error is bounded by the weighted sample envelopes.
For least squares use weights (t_i - mean t) / sum (t_i - mean t)^2. -/
theorem boundedTail_slope_sample_envelope {ι : Type*} (s : Finset ι)
    (weight error bound : ι → ℝ)
    (h : ∀ i ∈ s, |error i| ≤ bound i) :
    |∑ i ∈ s, weight i * error i| ≤ ∑ i ∈ s, |weight i| * bound i := by
  calc
    |∑ i ∈ s, weight i * error i| ≤ ∑ i ∈ s, |weight i * error i| :=
      Finset.abs_sum_le_sum_abs _ _
    _ ≤ ∑ i ∈ s, |weight i| * bound i := by
      apply Finset.sum_le_sum
      intro i hi
      rw [abs_mul]
      exact mul_le_mul_of_nonneg_left (h i hi) (abs_nonneg _)

/-- Exact quotient/remainder identities behind the 1/201 control. -/
theorem boundedTail_one_over_201_remainders :
    (2 ^ 199 : ℕ) % 201 = 2 ∧ (2 ^ 263 : ℕ) % 201 = 101 := by
  norm_num [pow_succ]

/-- The realized nearest errors miss the factor-four rule despite each
being at most half its respective grid spacing. No MPFR theorem is claimed. -/
theorem boundedTail_one_over_201_error_bounds :
    (2 : ℚ) / (201 * 2^199) ≤ 1 / (2 * 2^199) ∧
    (100 : ℚ) / (201 * 2^263) ≤ 1 / (2 * 2^263) ∧
    (100 : ℚ) / (201 * 2^263) >
      4 / 2^64 * (2 / (201 * 2^199)) := by
  norm_num [pow_succ]

end MLSFormal
