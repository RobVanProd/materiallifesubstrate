import Mathlib.Data.Rat.Defs
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

def reynolds (velocity length viscosity : ℚ) : ℚ :=
  velocity * length / viscosity

def froudeSquared (velocity gravity length : ℚ) : ℚ :=
  velocity * velocity / (gravity * length)

def peclet (velocity length diffusivity : ℚ) : ℚ :=
  velocity * length / diffusivity

def damkohlerFirstOrder (reactionRate length velocity : ℚ) : ℚ :=
  reactionRate * length / velocity

/-- Scaling space by `alpha` and time by `beta` preserves Reynolds number. -/
theorem reynolds_scale_invariant
    (alpha beta velocity length viscosity : ℚ)
    (alpha_nonzero : alpha ≠ 0)
    (beta_nonzero : beta ≠ 0)
    (viscosity_nonzero : viscosity ≠ 0) :
    reynolds ((alpha / beta) * velocity) (alpha * length)
        (((alpha * alpha) / beta) * viscosity) =
      reynolds velocity length viscosity := by
  unfold reynolds
  field_simp [alpha_nonzero, beta_nonzero, viscosity_nonzero]

/-- The same transform, with acceleration scaled by `alpha / beta^2`, preserves `Fr^2`. -/
theorem froudeSquared_scale_invariant
    (alpha beta velocity gravity length : ℚ)
    (alpha_nonzero : alpha ≠ 0)
    (beta_nonzero : beta ≠ 0)
    (gravity_nonzero : gravity ≠ 0)
    (length_nonzero : length ≠ 0) :
    froudeSquared ((alpha / beta) * velocity)
        ((alpha / (beta * beta)) * gravity) (alpha * length) =
      froudeSquared velocity gravity length := by
  unfold froudeSquared
  field_simp [alpha_nonzero, beta_nonzero, gravity_nonzero, length_nonzero]

/-- Scaling diffusivity by `alpha^2 / beta` preserves Peclet number. -/
theorem peclet_scale_invariant
    (alpha beta velocity length diffusivity : ℚ)
    (alpha_nonzero : alpha ≠ 0)
    (beta_nonzero : beta ≠ 0)
    (diffusivity_nonzero : diffusivity ≠ 0) :
    peclet ((alpha / beta) * velocity) (alpha * length)
        (((alpha * alpha) / beta) * diffusivity) =
      peclet velocity length diffusivity := by
  unfold peclet
  field_simp [alpha_nonzero, beta_nonzero, diffusivity_nonzero]

/-- With a first-order/effective rate scaled by `1 / beta`, Damkohler is preserved. -/
theorem damkohlerFirstOrder_scale_invariant
    (alpha beta reactionRate length velocity : ℚ)
    (alpha_nonzero : alpha ≠ 0)
    (beta_nonzero : beta ≠ 0)
    (velocity_nonzero : velocity ≠ 0) :
    damkohlerFirstOrder (reactionRate / beta) (alpha * length)
        ((alpha / beta) * velocity) =
      damkohlerFirstOrder reactionRate length velocity := by
  unfold damkohlerFirstOrder
  field_simp [alpha_nonzero, beta_nonzero, velocity_nonzero]

end MLSFormal
