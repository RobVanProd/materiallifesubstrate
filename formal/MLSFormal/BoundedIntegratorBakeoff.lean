import MLSFormal.RelationCoordinateDefectTailCertification
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring
import Mathlib.LinearAlgebra.BilinearForm.Basic

set_option autoImplicit false
namespace MLSFormal

/-- Exact radial identity; length-square and positive-denominator hypotheses
are mathematical obligations, not assertions about rounded Path B. -/
theorem bakeoff_radial_chain
    (ax ay az bx byy bz l0 l1 rest : ℝ)
    (h0 : l0^2 = ax^2+ay^2+az^2)
    (h1 : l1^2 = bx^2+byy^2+bz^2) (positive : 0 < l0+l1) :
    ((ax+bx)*(bx-ax)+(ay+byy)*(byy-ay)+(az+bz)*(bz-az))/(l0+l1) =
      (l1-rest)-(l0-rest) := by
  apply (div_eq_iff (ne_of_gt positive)).mpr
  nlinarith

/-- Equal radii and unchanged endpoints need no small-increment division. -/
theorem bakeoff_equal_radius (a b l : ℝ) (same : a = b) (_positive : 0 < l) :
    (a+b)*(b-a)/(l+l) = 0 := by
  rw [same]
  simp

/-- A symmetric bilinear form includes every frozen symmetric quadratic H.
This is its discrete chain rule, not a premise assuming energy conservation. -/
theorem bakeoff_quadratic_chain {V : Type*} [AddCommGroup V] [Module ℝ V]
    (B : V →ₗ[ℝ] V →ₗ[ℝ] ℝ) (symm : ∀ x y, B x y = B y x) (x y : V) :
    B ((1/2 : ℝ) • (x+y)) (y-x) = (B y y-B x x)/2 := by
  simp only [map_smul, map_add, map_sub, LinearMap.smul_apply,
    LinearMap.add_apply, smul_eq_mul]
  rw [symm x y]
  ring

theorem bakeoff_kinetic_chain (p v m : ℝ) (_nonzero : m ≠ 0) :
    (v^2-p^2)/(2*m) = ((p+v)/(2*m))*(v-p) := by
  field_simp
  ring

/-- One-coordinate work cancellation from the actual exact step equations.
Summing this identity over packets/axes cancels quadratic kinetic and DG work. -/
theorem bakeoff_step_work (x y p v m h force : ℝ) (mass : m ≠ 0)
    (drift : y-x = h*(p+v)/(2*m)) (kick : v-p = h*force) :
    (v^2-p^2)/(2*m) = force*(y-x) := by
  rw [bakeoff_kinetic_chain p v m mass, kick, drift]
  ring

/-- Chain-compatible potential work plus the proved kinetic work identity
implies energy cancellation; these hypotheses are separately audited. -/
theorem bakeoff_energy_composition {I : Type*} [Fintype I]
    (k0 k1 force dx : I → ℝ) (u0 u1 : ℝ)
    (kinetic : ∀ i, k1 i-k0 i = force i*dx i)
    (chain : u1-u0 = -(∑ i, force i*dx i)) :
    (∑ i, k1 i)+u1 = (∑ i, k0 i)+u0 := by
  have work : (∑ i, k1 i)-(∑ i, k0 i) = ∑ i, force i*dx i := by
    rw [← Finset.sum_sub_distrib]
    exact Finset.sum_congr rfl (fun i _ => kinetic i)
  linarith

theorem bakeoff_pair_momentum (pi pj impulse : ℝ) :
    (pi+impulse)+(pj-impulse) = pi+pj := by ring

/-- Each cyclic component of midpoint relation torque vanishes. -/
theorem bakeoff_midpoint_centrality (rx ry alpha : ℝ) :
    rx*(alpha*ry)-ry*(alpha*rx) = 0 := by ring

/-- Discrete angular product rule. The first term is midpoint central torque;
the second vanishes for momentum-midpoint drift. Apply cyclically. -/
theorem bakeoff_angular_product (x y p q xn yn pn qn : ℝ) :
    (xn*qn-yn*pn)-(x*q-y*p) =
    ((xn+x)/2*(qn-q)-(yn+y)/2*(pn-p)) +
    ((xn-x)*(qn+q)/2-(yn-y)*(pn+p)/2) := by ring

theorem bakeoff_midpoint_drift_torque (p q pn qn h m : ℝ) :
    (h*(p+pn)/(2*m))*(qn+q)/2 -
      (h*(q+qn)/(2*m))*(pn+p)/2 = 0 := by ring

theorem bakeoff_time_exchange (a b l0 l1 : ℝ) :
    (a+b)/(l0+l1) = (b+a)/(l1+l0) := by ring

/-- The affine equation is exact; no finite-precision Picard map is assumed
linear. Gaussian elimination targets this equation only. -/
theorem bakeoff_exact_fixed_cell {V : Type*} [AddCommGroup V]
    (A : V →+ V) (b z : V) : z = A z+b ↔ z-A z = b := by
  constructor
  · intro h
    exact sub_eq_iff_eq_add.mpr (by simpa [add_comm] using h)
  · intro h
    simpa [add_comm] using (sub_eq_iff_eq_add.mp h)

theorem bakeoff_root_rounding {V Bits : Type*} (round : V → Bits)
    (root : V) (box : Set V) (output : Bits)
    (inside : root ∈ box) (cell : ∀ z ∈ box, round z = output) :
    round root = output := cell root inside

/-- Exact scalar quadratic completion for an interior chord minimum. -/
theorem bakeoff_chord_completion (aa ad dd t : ℝ) (nonzero : dd ≠ 0) :
    aa+2*t*ad+t^2*dd = aa-ad^2/dd+dd*(t+ad/dd)^2 := by
  field_simp
  ring

theorem bakeoff_atomic_rejection {S : Type*} (prior : S) :
    (fun (_proposal : S) => prior) prior = prior := rfl

end MLSFormal
