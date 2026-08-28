import MLSFormal.TransitionModel
import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.BigOperators.Pi
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Fintype.BigOperators
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.Ring

set_option autoImplicit false

namespace MLSFormal

open scoped BigOperators

/-!
This module is a finite, exact-rational reference model for the Time + Transfer
lab.  It defines particle-to-grid and grid-to-particle maps directly.  It does
not model forces, constitutive response, or a time integrator.
-/

/-- A three-by-three rational matrix, used only as an affine velocity map. -/
abbrev Mat3 := Fin 3 → Fin 3 → ℚ

/-- Explicit rational scaling, avoiding any hidden norm or floating operation. -/
def vscale (scale : ℚ) (vector : Vec3) : Vec3 :=
  fun component => scale * vector component

/-- The authoritative particle data needed by the finite transfer model. -/
structure TransferParticle where
  mass : ℚ
  position : Vec3
  velocity : Vec3
  affine : Mat3

/-- Apply an affine velocity matrix to a displacement. -/
def matVec (matrix : Mat3) (vector : Vec3) : Vec3 :=
  fun row => ∑ column : Fin 3, matrix row column * vector column

/-- Displacement from a particle to a grid sample. -/
def displacement
    {Particle Grid : Type*}
    (particles : Particle → TransferParticle)
    (gridPosition : Grid → Vec3)
    (particle : Particle) (grid : Grid) : Vec3 :=
  gridPosition grid - (particles particle).position

/-- An affine field evaluated at a physical position. -/
def affineVelocityField (offset : Vec3) (gradient : Mat3) (position : Vec3) : Vec3 :=
  offset + matVec gradient position

/-- Exact PIC particle-to-grid mass. -/
def p2gMass
    {Particle Grid : Type*} [Fintype Particle]
    (particles : Particle → TransferParticle)
    (weight : Particle → Grid → ℚ)
    (grid : Grid) : ℚ :=
  ∑ particle : Particle, weight particle grid * (particles particle).mass

/-- Exact PIC particle-to-grid momentum. -/
def p2gPICMomentum
    {Particle Grid : Type*} [Fintype Particle]
    (particles : Particle → TransferParticle)
    (weight : Particle → Grid → ℚ)
    (grid : Grid) : Vec3 :=
  fun component =>
    ∑ particle : Particle,
      weight particle grid * (particles particle).mass *
        (particles particle).velocity component

/--
Exact APIC particle-to-grid momentum.  The affine term is part of the
definition; no conservation property is supplied as an input premise.
-/
def p2gAPICMomentum
    {Particle Grid : Type*} [Fintype Particle]
    (particles : Particle → TransferParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (grid : Grid) : Vec3 :=
  fun component =>
    ∑ particle : Particle,
      weight particle grid * (particles particle).mass *
        ((particles particle).velocity component +
          matVec (particles particle).affine
            (displacement particles gridPosition particle grid) component)

/-- PIC grid-to-particle velocity interpolation. -/
def g2pPICVelocity
    {Particle Grid : Type*} [Fintype Grid]
    (weight : Particle → Grid → ℚ)
    (gridVelocity : Grid → Vec3)
    (particle : Particle) : Vec3 :=
  fun component =>
    ∑ grid : Grid, weight particle grid * gridVelocity grid component

/-- Result of APIC grid-to-particle reconstruction. -/
structure APICReconstruction where
  velocity : Vec3
  affine : Mat3

/--
APIC grid-to-particle reconstruction using an explicit dual displacement.  In
an implementation the dual is normally derived from the inverse particle
second-moment matrix.  Keeping it explicit exposes the exact reproduction
assumption instead of hiding an inverse-existence or conditioning premise.
-/
def g2pAPIC
    {Particle Grid : Type*} [Fintype Grid]
    (weight : Particle → Grid → ℚ)
    (dualDisplacement : Particle → Grid → Vec3)
    (gridVelocity : Grid → Vec3)
    (particle : Particle) : APICReconstruction :=
  let interpolated := g2pPICVelocity weight gridVelocity particle
  { velocity := interpolated
    affine := fun row column =>
      ∑ grid : Grid,
        weight particle grid *
          (gridVelocity grid row - interpolated row) *
          dualDisplacement particle grid column }

/--
Preconditions on a finite transfer stencil.  Partition of unity and vanishing
first moment are dimensioned geometric facts about the actual sample positions.
The final field states the dual-basis identity needed to reproduce an affine
gradient in `g2pAPIC`.
-/
structure KernelAssumptions
    {Particle Grid : Type*} [Fintype Grid]
    (particles : Particle → TransferParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (dualDisplacement : Particle → Grid → Vec3) : Prop where
  partitionUnity : ∀ particle, ∑ grid : Grid, weight particle grid = 1
  firstMoment : ∀ particle,
    ∑ grid : Grid,
      vscale (weight particle grid)
        (displacement particles gridPosition particle grid) = 0
  dualFirstMoment : ∀ particle sourceAxis recoveredAxis,
    ∑ grid : Grid,
      weight particle grid *
        displacement particles gridPosition particle grid sourceAxis *
        dualDisplacement particle grid recoveredAxis =
      if sourceAxis = recoveredAxis then 1 else 0

/-- Total particle mass. -/
def particleMassTotal
    {Particle : Type*} [Fintype Particle]
    (particles : Particle → TransferParticle) : ℚ :=
  ∑ particle : Particle, (particles particle).mass

/-- Total particle linear momentum. -/
def particleMomentumTotal
    {Particle : Type*} [Fintype Particle]
    (particles : Particle → TransferParticle) : Vec3 :=
  fun component =>
    ∑ particle : Particle,
      (particles particle).mass * (particles particle).velocity component

/-- Total grid orbital angular momentum for a supplied node momentum field. -/
def gridAngularMomentum
    {Grid : Type*} [Fintype Grid]
    (gridPosition : Grid → Vec3)
    (gridMomentum : Grid → Vec3) : Vec3 :=
  fun component =>
    ∑ grid : Grid, cross (gridPosition grid) (gridMomentum grid) component

/--
The APIC particle affine contribution to angular momentum for this exact finite
stencil.  This is the discrete internal angular term transferred by the affine
velocity contribution; it is not assumed to be conserved.
-/
def particleAffineAngularContribution
    {Particle Grid : Type*} [Fintype Grid]
    (particles : Particle → TransferParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (particle : Particle) : Vec3 :=
  fun component =>
    ∑ grid : Grid,
      cross (displacement particles gridPosition particle grid)
        (vscale (weight particle grid * (particles particle).mass)
          (matVec (particles particle).affine
            (displacement particles gridPosition particle grid))) component

/-- Particle orbital plus explicitly represented APIC affine angular momentum. -/
def particleAPICAngularMomentum
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → TransferParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ) : Vec3 :=
  fun component =>
    ∑ particle : Particle,
      (cross (particles particle).position
          (vscale (particles particle).mass (particles particle).velocity) +
        particleAffineAngularContribution particles gridPosition weight particle) component

private theorem matVec_zero (matrix : Mat3) : matVec matrix 0 = 0 := by
  funext component
  simp [matVec]

private theorem matVec_add (matrix : Mat3) (left right : Vec3) :
    matVec matrix (left + right) = matVec matrix left + matVec matrix right := by
  funext component
  simp [matVec, mul_add, Finset.sum_add_distrib]

private theorem matVec_smul (matrix : Mat3) (scale : ℚ) (vector : Vec3) :
    matVec matrix (vscale scale vector) = vscale scale (matVec matrix vector) := by
  funext component
  change (∑ column : Fin 3, matrix component column *
      (scale * vector column)) =
    scale * (∑ column : Fin 3, matrix component column * vector column)
  rw [Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro column _
  ring

private theorem cross_add_left (left right vector : Vec3) :
    cross (left + right) vector = cross left vector + cross right vector := by
  funext component
  fin_cases component <;> simp [cross] <;> ring

private theorem cross_add_right (vector left right : Vec3) :
    cross vector (left + right) = cross vector left + cross vector right := by
  funext component
  fin_cases component <;> simp [cross] <;> ring

private theorem cross_smul_left (scale : ℚ) (left right : Vec3) :
    cross (vscale scale left) right = vscale scale (cross left right) := by
  funext component
  fin_cases component <;> simp [cross, vscale] <;> ring

private theorem cross_smul_right (scale : ℚ) (left right : Vec3) :
    cross left (vscale scale right) = vscale scale (cross left right) := by
  funext component
  fin_cases component <;> simp [cross, vscale] <;> ring

private theorem finset_sum_cross_fixed_left
    {Index : Type*} [DecidableEq Index] (indices : Finset Index)
    (left : Vec3) (right : Index → Vec3) :
    (∑ index ∈ indices, cross left (right index)) =
      cross left (∑ index ∈ indices, right index) := by
  induction indices using Finset.induction_on with
  | empty =>
      funext component
      fin_cases component <;> simp [cross]
  | @insert index rest absent inductionHypothesis =>
      simp only [Finset.sum_insert absent]
      rw [cross_add_right, inductionHypothesis]

private theorem sum_cross_fixed_left
    {Index : Type*} [Fintype Index] (left : Vec3) (right : Index → Vec3) :
    (∑ index : Index, cross left (right index)) =
      cross left (∑ index : Index, right index) := by
  classical
  exact finset_sum_cross_fixed_left Finset.univ left right

private theorem finset_sum_cross_fixed_right
    {Index : Type*} [DecidableEq Index] (indices : Finset Index)
    (left : Index → Vec3) (right : Vec3) :
    (∑ index ∈ indices, cross (left index) right) =
      cross (∑ index ∈ indices, left index) right := by
  induction indices using Finset.induction_on with
  | empty =>
      funext component
      fin_cases component <;> simp [cross]
  | @insert index rest absent inductionHypothesis =>
      simp only [Finset.sum_insert absent]
      rw [cross_add_left, inductionHypothesis]

private theorem sum_cross_fixed_right
    {Index : Type*} [Fintype Index] (left : Index → Vec3) (right : Vec3) :
    (∑ index : Index, cross (left index) right) =
      cross (∑ index : Index, left index) right := by
  classical
  exact finset_sum_cross_fixed_right Finset.univ left right

private theorem weighted_fixed_sum
    {Index : Type*} [Fintype Index]
    (weight : Index → ℚ) (scale : ℚ) (vector : Vec3) :
    (∑ index : Index, vscale (weight index * scale) vector) =
      vscale ((∑ index : Index, weight index) * scale) vector := by
  funext component
  simp only [Finset.sum_apply, vscale]
  change (∑ index : Index, (weight index * scale) * vector component) =
    ((∑ index : Index, weight index) * scale) * vector component
  have scaledWeights :
      (∑ index : Index, weight index * scale) =
        (∑ index : Index, weight index) * scale := by
    exact (Finset.sum_mul (Finset.univ : Finset Index) weight scale).symm
  have scaledVectors :
      (∑ index : Index, (weight index * scale) * vector component) =
        (∑ index : Index, weight index * scale) * vector component := by
    exact (Finset.sum_mul (Finset.univ : Finset Index)
      (fun index => weight index * scale) (vector component)).symm
  rw [scaledVectors, scaledWeights]

private theorem scale_weighted_sum
    {Index : Type*} [Fintype Index]
    (weight : Index → ℚ) (scale : ℚ) (vector : Index → Vec3) :
    (∑ index : Index, vscale (weight index * scale) (vector index)) =
      vscale scale (∑ index : Index, vscale (weight index) (vector index)) := by
  funext component
  simp only [Finset.sum_apply, vscale]
  change (∑ index : Index, (weight index * scale) * vector index component) =
    scale * (∑ index : Index, weight index * vector index component)
  rw [Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro index _
  ring

private theorem finset_weighted_matVec_sum
    {Index : Type*} [DecidableEq Index] (indices : Finset Index)
    (weight : Index → ℚ) (matrix : Mat3) (vector : Index → Vec3) :
    (∑ index ∈ indices,
      vscale (weight index) (matVec matrix (vector index))) =
      matVec matrix
        (∑ index ∈ indices, vscale (weight index) (vector index)) := by
  induction indices using Finset.induction_on with
  | empty =>
      funext component
      simp [matVec]
  | @insert index rest absent inductionHypothesis =>
      simp only [Finset.sum_insert absent]
      rw [matVec_add, matVec_smul, inductionHypothesis]

private theorem weighted_matVec_sum
    {Index : Type*} [Fintype Index]
    (weight : Index → ℚ) (matrix : Mat3) (vector : Index → Vec3) :
    (∑ index : Index, vscale (weight index) (matVec matrix (vector index))) =
      matVec matrix
        (∑ index : Index, vscale (weight index) (vector index)) := by
  classical
  exact finset_weighted_matVec_sum Finset.univ weight matrix vector

/-- Partition of unity makes the shared PIC/APIC P2G mass map exact. -/
theorem p2gMass_preserves_mass
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → TransferParticle)
    (weight : Particle → Grid → ℚ)
    (partitionUnity : ∀ particle, ∑ grid : Grid, weight particle grid = 1) :
    (∑ grid : Grid, p2gMass particles weight grid) =
      particleMassTotal particles := by
  simp only [p2gMass, particleMassTotal]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro particle _
  have massFactor :
      (∑ grid : Grid, weight particle grid * (particles particle).mass) =
        (∑ grid : Grid, weight particle grid) * (particles particle).mass := by
    symm
    exact Finset.sum_mul (Finset.univ : Finset Grid)
      (weight particle) (particles particle).mass
  rw [massFactor, partitionUnity]
  ring

/-- PIC P2G preserves exact linear momentum under partition of unity. -/
theorem p2gPIC_preserves_linearMomentum
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → TransferParticle)
    (weight : Particle → Grid → ℚ)
    (partitionUnity : ∀ particle, ∑ grid : Grid, weight particle grid = 1) :
    (∑ grid : Grid, p2gPICMomentum particles weight grid) =
      particleMomentumTotal particles := by
  funext component
  simp only [Finset.sum_apply, p2gPICMomentum, particleMomentumTotal]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro particle _
  have massFactor :
      (∑ grid : Grid, weight particle grid * (particles particle).mass) =
        (∑ grid : Grid, weight particle grid) * (particles particle).mass := by
    symm
    exact Finset.sum_mul (Finset.univ : Finset Grid)
      (weight particle) (particles particle).mass
  have momentumFactor :
      (∑ grid : Grid,
        weight particle grid * (particles particle).mass *
          (particles particle).velocity component) =
        (∑ grid : Grid,
          weight particle grid * (particles particle).mass) *
            (particles particle).velocity component := by
    symm
    exact Finset.sum_mul (Finset.univ : Finset Grid)
      (fun grid => weight particle grid * (particles particle).mass)
      ((particles particle).velocity component)
  rw [momentumFactor, massFactor, partitionUnity]
  ring

/--
First-moment exactness makes the affine part of APIC P2G carry zero net linear
momentum, so APIC preserves total linear momentum.
-/
theorem p2gAPIC_preserves_linearMomentum
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → TransferParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (partitionUnity : ∀ particle, ∑ grid : Grid, weight particle grid = 1)
    (firstMoment : ∀ particle,
      ∑ grid : Grid,
        vscale (weight particle grid)
          (displacement particles gridPosition particle grid) = 0) :
    (∑ grid : Grid, p2gAPICMomentum particles gridPosition weight grid) =
      particleMomentumTotal particles := by
  funext component
  simp only [Finset.sum_apply, p2gAPICMomentum, particleMomentumTotal]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro particle _
  have affineZero :
      ∑ grid : Grid,
          vscale (weight particle grid)
            (matVec (particles particle).affine
              (displacement particles gridPosition particle grid)) = 0 := by
    rw [weighted_matVec_sum, firstMoment particle, matVec_zero]
  have affineComponentZero := congrFun affineZero component
  simp only [Finset.sum_apply, vscale, Pi.zero_apply] at affineComponentZero
  change
    (∑ grid : Grid,
      weight particle grid *
        matVec (particles particle).affine
          (displacement particles gridPosition particle grid) component) = 0
    at affineComponentZero
  have velocityPart :
      (∑ grid : Grid,
        weight particle grid * (particles particle).mass *
          (particles particle).velocity component) =
        (particles particle).mass * (particles particle).velocity component := by
    calc
      _ = ((∑ grid : Grid, weight particle grid) *
          (particles particle).mass) *
            (particles particle).velocity component := by
        rw [Finset.sum_mul, Finset.sum_mul]
      _ = _ := by rw [partitionUnity particle]; ring
  have affinePart :
      (∑ grid : Grid,
        weight particle grid * (particles particle).mass *
          matVec (particles particle).affine
            (displacement particles gridPosition particle grid) component) = 0 := by
    calc
      _ = (particles particle).mass *
          (∑ grid : Grid,
            weight particle grid *
              matVec (particles particle).affine
                (displacement particles gridPosition particle grid) component) := by
        rw [Finset.mul_sum]
        apply Finset.sum_congr rfl
        intro grid _
        ring
      _ = 0 := by rw [affineComponentZero]; ring
  simp_rw [mul_add]
  rw [Finset.sum_add_distrib, velocityPart, affinePart]
  simp

/-- PIC G2P exactly reproduces a constant velocity field. -/
theorem g2pPIC_reproduces_constant
    {Particle Grid : Type*} [Fintype Grid]
    (weight : Particle → Grid → ℚ)
    (partitionUnity : ∀ particle, ∑ grid : Grid, weight particle grid = 1)
    (constantVelocity : Vec3) (particle : Particle) :
    g2pPICVelocity weight (fun _ => constantVelocity) particle = constantVelocity := by
  funext component
  simp only [g2pPICVelocity]
  rw [← Finset.sum_mul, partitionUnity]
  simp

/-- Partition of unity plus first moment makes PIC reproduce affine velocity. -/
theorem g2pPIC_reproduces_affineVelocity
    {Particle Grid : Type*} [Fintype Grid]
    (particles : Particle → TransferParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (partitionUnity : ∀ particle, ∑ grid : Grid, weight particle grid = 1)
    (firstMoment : ∀ particle,
      ∑ grid : Grid,
        vscale (weight particle grid)
          (displacement particles gridPosition particle grid) = 0)
    (offset : Vec3) (gradient : Mat3) (particle : Particle) :
    g2pPICVelocity weight (affineVelocityField offset gradient ∘ gridPosition) particle =
      affineVelocityField offset gradient (particles particle).position := by
  have positionDecomposition : ∀ grid,
      gridPosition grid = (particles particle).position +
        displacement particles gridPosition particle grid := by
    intro grid
    funext component
    simp [displacement]
  have affineMeanZero :
      ∑ grid : Grid,
          vscale (weight particle grid)
            (matVec gradient
              (displacement particles gridPosition particle grid)) = 0 := by
    rw [weighted_matVec_sum, firstMoment particle, matVec_zero]
  funext component
  have affineComponentZero := congrFun affineMeanZero component
  simp only [Finset.sum_apply, vscale, Pi.zero_apply] at affineComponentZero
  change
    (∑ grid : Grid,
      weight particle grid *
        matVec gradient
          (displacement particles gridPosition particle grid) component) = 0
    at affineComponentZero
  simp only [g2pPICVelocity, Function.comp_apply, affineVelocityField]
  simp_rw [positionDecomposition, matVec_add]
  simp only [Pi.add_apply]
  simp_rw [mul_add]
  rw [Finset.sum_add_distrib]
  rw [Finset.sum_add_distrib]
  have offsetPart :
      (∑ grid : Grid, weight particle grid * offset component) =
        offset component := by
    rw [← Finset.sum_mul, partitionUnity]
    simp
  have constantPart :
      (∑ grid : Grid,
        weight particle grid *
          matVec gradient (particles particle).position component) =
        matVec gradient (particles particle).position component := by
    rw [← Finset.sum_mul, partitionUnity]
    simp
  rw [offsetPart, constantPart, affineComponentZero]
  ring

/--
With the explicit dual first-moment identity, APIC G2P reproduces both the
velocity and gradient of any affine field.
-/
theorem g2pAPIC_reproduces_affine
    {Particle Grid : Type*} [Fintype Grid]
    (particles : Particle → TransferParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (dualDisplacement : Particle → Grid → Vec3)
    (assumptions : KernelAssumptions particles gridPosition weight dualDisplacement)
    (offset : Vec3) (gradient : Mat3) (particle : Particle) :
    let reconstructed :=
      g2pAPIC weight dualDisplacement
        (affineVelocityField offset gradient ∘ gridPosition) particle
    reconstructed.velocity =
        affineVelocityField offset gradient (particles particle).position ∧
      reconstructed.affine = gradient := by
  dsimp only
  have velocityExact := g2pPIC_reproduces_affineVelocity
    particles gridPosition weight assumptions.partitionUnity assumptions.firstMoment
    offset gradient particle
  constructor
  · exact velocityExact
  · funext row column
    simp only [g2pAPIC]
    rw [velocityExact]
    have positionDecomposition : ∀ grid,
        gridPosition grid = (particles particle).position +
          displacement particles gridPosition particle grid := by
      intro grid
      funext component
      simp [displacement]
    simp only [Function.comp_apply, affineVelocityField]
    simp_rw [positionDecomposition, matVec_add]
    simp only [Pi.add_apply]
    ring_nf
    simp only [matVec]
    simp_rw [Finset.mul_sum]
    simp_rw [Finset.sum_mul]
    rw [Finset.sum_comm]
    calc
      (∑ sourceAxis : Fin 3,
        ∑ grid : Grid,
          weight particle grid *
              (gradient row sourceAxis *
                displacement particles gridPosition particle grid sourceAxis) *
            dualDisplacement particle grid column) =
        ∑ sourceAxis : Fin 3,
          gradient row sourceAxis *
            (∑ grid : Grid,
              weight particle grid *
                displacement particles gridPosition particle grid sourceAxis *
                dualDisplacement particle grid column) := by
          apply Finset.sum_congr rfl
          intro sourceAxis _
          rw [Finset.mul_sum]
          apply Finset.sum_congr rfl
          intro grid _
          ring
      _ = ∑ sourceAxis : Fin 3,
          gradient row sourceAxis *
            (if sourceAxis = column then 1 else 0) := by
          apply Finset.sum_congr rfl
          intro sourceAxis _
          rw [assumptions.dualFirstMoment particle sourceAxis column]
      _ = gradient row column := by simp

/--
APIC P2G preserves orbital-plus-affine angular momentum under partition of
unity and first-moment exactness.  The conclusion is derived from the concrete
P2G definition and the explicit affine angular contribution above.
-/
theorem p2gAPIC_preserves_angularMomentum
    {Particle Grid : Type*} [Fintype Particle] [Fintype Grid]
    (particles : Particle → TransferParticle)
    (gridPosition : Grid → Vec3)
    (weight : Particle → Grid → ℚ)
    (partitionUnity : ∀ particle, ∑ grid : Grid, weight particle grid = 1)
    (firstMoment : ∀ particle,
      ∑ grid : Grid,
        vscale (weight particle grid)
          (displacement particles gridPosition particle grid) = 0) :
    gridAngularMomentum gridPosition
        (p2gAPICMomentum particles gridPosition weight) =
      particleAPICAngularMomentum particles gridPosition weight := by
  funext component
  change
    (∑ grid : Grid,
      cross (gridPosition grid)
        (p2gAPICMomentum particles gridPosition weight grid) component) =
    ∑ particle : Particle,
      (cross (particles particle).position
          (vscale (particles particle).mass (particles particle).velocity) +
        particleAffineAngularContribution particles gridPosition weight particle)
        component
  have p2gAsVectorSum : ∀ grid,
      p2gAPICMomentum particles gridPosition weight grid =
        ∑ particle : Particle,
          vscale (weight particle grid * (particles particle).mass)
            ((particles particle).velocity +
              matVec (particles particle).affine
                (displacement particles gridPosition particle grid)) := by
    intro grid
    funext coordinate
    simp only [p2gAPICMomentum, Finset.sum_apply, vscale, Pi.add_apply]
  simp_rw [p2gAsVectorSum]
  simp_rw [← sum_cross_fixed_left]
  simp only [Finset.sum_apply]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro particle _
  let d : Grid → Vec3 :=
    fun grid => displacement particles gridPosition particle grid
  let affineVelocity : Grid → Vec3 :=
    fun grid => matVec (particles particle).affine (d grid)
  have positionDecomposition : ∀ grid,
      gridPosition grid = (particles particle).position + d grid := by
    intro grid
    funext component
    simp [d, displacement]
  have weightedDisplacementZero :
      ∑ grid : Grid,
          vscale (weight particle grid * (particles particle).mass) (d grid) = 0 := by
    rw [scale_weighted_sum, firstMoment particle]
    funext coordinate
    simp [vscale]
  have weightedAffineZero :
      ∑ grid : Grid,
          vscale (weight particle grid * (particles particle).mass)
            (affineVelocity grid) = 0 := by
    rw [scale_weighted_sum]
    change vscale (particles particle).mass
      (∑ grid : Grid,
        vscale (weight particle grid)
          (matVec (particles particle).affine (d grid))) = 0
    rw [weighted_matVec_sum]
    change vscale (particles particle).mass
      (matVec (particles particle).affine
        (∑ grid : Grid,
          vscale (weight particle grid)
            (displacement particles gridPosition particle grid))) = 0
    rw [firstMoment particle, matVec_zero]
    funext coordinate
    simp [vscale]
  have weightedVelocity :
      ∑ grid : Grid,
          vscale (weight particle grid * (particles particle).mass)
            (particles particle).velocity =
        vscale (particles particle).mass (particles particle).velocity := by
    rw [weighted_fixed_sum, partitionUnity]
    simp
  have angularVector :
      (∑ grid : Grid,
        cross (gridPosition grid)
          (vscale (weight particle grid * (particles particle).mass)
            ((particles particle).velocity + affineVelocity grid))) =
        cross (particles particle).position
            (vscale (particles particle).mass (particles particle).velocity) +
          ∑ grid : Grid,
            cross (d grid)
              (vscale (weight particle grid * (particles particle).mass)
                (affineVelocity grid)) := by
    simp_rw [positionDecomposition, cross_add_left]
    have vscaleAdd : ∀ grid,
        vscale (weight particle grid * (particles particle).mass)
            ((particles particle).velocity + affineVelocity grid) =
          vscale (weight particle grid * (particles particle).mass)
              (particles particle).velocity +
            vscale (weight particle grid * (particles particle).mass)
              (affineVelocity grid) := by
      intro grid
      funext coordinate
      simp [vscale]
      ring
    simp_rw [vscaleAdd, cross_add_right]
    simp_rw [Finset.sum_add_distrib]
    have fixedVelocityCross :
        (∑ grid : Grid,
          cross (d grid)
            (vscale (weight particle grid * (particles particle).mass)
              (particles particle).velocity)) = 0 := by
      simp_rw [cross_smul_right, ← cross_smul_left]
      rw [sum_cross_fixed_right, weightedDisplacementZero]
      funext coordinate
      fin_cases coordinate <;> simp [cross]
    have fixedPositionVelocity :
        (∑ grid : Grid,
          cross (particles particle).position
            (vscale (weight particle grid * (particles particle).mass)
              (particles particle).velocity)) =
          cross (particles particle).position
            (vscale (particles particle).mass (particles particle).velocity) := by
      rw [sum_cross_fixed_left, weightedVelocity]
    have fixedPositionAffine :
        (∑ grid : Grid,
          cross (particles particle).position
            (vscale (weight particle grid * (particles particle).mass)
              (affineVelocity grid))) = 0 := by
      rw [sum_cross_fixed_left, weightedAffineZero]
      funext coordinate
      fin_cases coordinate <;> simp [cross]
    rw [fixedPositionVelocity, fixedPositionAffine, fixedVelocityCross]
    abel
  simpa [particleAffineAngularContribution, d, affineVelocity,
    Finset.sum_apply] using congrFun angularVector component

end MLSFormal
