import MLSFormal.MechanicalObservability

set_option autoImplicit false

namespace MLSFormal

open scoped BigOperators Matrix

/-!
# Kelvin-coordinate covariance audit

This module isolates the coordinate law audited after the Mechanical
Observability Lab.  A raw corrected symmetric-gradient matrix maps packet
velocity coordinates to orthonormal Kelvin coordinates.  Under the spatial
similarity `x' = s Q x + t`, its required coordinate law is

`R' = (1 / s) K R Uᵀ`,

where `U` is the orthogonal block rotation of packet velocities and `K` is the
orthogonal Kelvin representation of `S ↦ Q S Qᵀ`.  Translation does not enter
a derivative operator.  The definitions below make that law executable and
the assumptions explicit; no invertibility or covariance fact is introduced
as an axiom.

The final exact counterexample concerns coordinate diagnostics only.  It shows
that normalizing each scalar Kelvin row independently can change the raw
singular spectrum even when the unnormalized operators differ only by an
orthogonal output rotation.  It does not change the sealed observability run
and it promotes no mechanical representation.
-/

/-- A finite spatial similarity, including the dimensioned scale and the
translation which correctly drops out of the derivative transformation. -/
structure KelvinSpatialSimilarity (Axis : Type*) where
  scale : ℚ
  rotation : Matrix Axis Axis ℚ
  translation : Axis → ℚ

/-- Two-sided orthogonality, stated explicitly for finite rational matrices. -/
def KelvinOrthogonal
    {Index : Type*} [Fintype Index] [DecidableEq Index]
    (matrix : Matrix Index Index ℚ) : Prop :=
  matrix.transpose * matrix = 1 ∧ matrix * matrix.transpose = 1

/-- Input Gram matrix; its eigenvalues are squared singular values. -/
def rawInputGram
    {Output Input : Type*} [Fintype Output]
    (raw : Matrix Output Input ℚ) : Matrix Input Input ℚ :=
  raw.transpose * raw

/-- Output Gram matrix; its nonzero spectrum is the same squared-singular-value
spectrum as `rawInputGram`. -/
def rawOutputGram
    {Output Input : Type*} [Fintype Input]
    (raw : Matrix Output Input ℚ) : Matrix Output Output ℚ :=
  raw * raw.transpose

/--
The raw corrected symmetric-gradient operator after a spatial similarity.
`inputRotation` is the packet-velocity block action of `Q`; `kelvinRotation`
is the orthogonal six-coordinate action induced by `S ↦ Q S Qᵀ`.
-/
def transformedRawCorrectedSymmetricGradient
    {Output Input Axis : Type*}
    [Fintype Output] [Fintype Input]
    (similarity : KelvinSpatialSimilarity Axis)
    (kelvinRotation : Matrix Output Output ℚ)
    (inputRotation : Matrix Input Input ℚ)
    (raw : Matrix Output Input ℚ) : Matrix Output Input ℚ :=
  similarity.scale⁻¹ •
    (kelvinRotation * raw * inputRotation.transpose)

/-- Translation cannot alter the raw derivative operator. -/
theorem transformedRawCorrectedSymmetricGradient_translation_independent
    {Output Input Axis : Type*}
    [Fintype Output] [Fintype Input]
    (scale : ℚ) (rotation : Matrix Axis Axis ℚ)
    (translation₁ translation₂ : Axis → ℚ)
    (kelvinRotation : Matrix Output Output ℚ)
    (inputRotation : Matrix Input Input ℚ)
    (raw : Matrix Output Input ℚ) :
    transformedRawCorrectedSymmetricGradient
        ⟨scale, rotation, translation₁⟩ kelvinRotation inputRotation raw =
      transformedRawCorrectedSymmetricGradient
        ⟨scale, rotation, translation₂⟩ kelvinRotation inputRotation raw := by
  rfl

/-- The explicit `1/s`, Kelvin-output, and packet-input transformation law. -/
theorem transformedRawCorrectedSymmetricGradient_mul_inputRotation
    {Output Input Axis : Type*}
    [Fintype Output] [Fintype Input]
    [DecidableEq Input]
    (similarity : KelvinSpatialSimilarity Axis)
    (kelvinRotation : Matrix Output Output ℚ)
    (inputRotation : Matrix Input Input ℚ)
    (raw : Matrix Output Input ℚ)
    (inputOrthogonal : KelvinOrthogonal inputRotation) :
    transformedRawCorrectedSymmetricGradient similarity kelvinRotation
        inputRotation raw * inputRotation =
      similarity.scale⁻¹ • (kelvinRotation * raw) := by
  rcases inputOrthogonal with ⟨inputTransposeMul, _inputMulTranspose⟩
  simp only [transformedRawCorrectedSymmetricGradient, Matrix.smul_mul,
    Matrix.mul_assoc, inputTransposeMul, Matrix.mul_one]

/-- After removing the physical `1/s` factor, the raw input Gram is related by
orthogonal similarity.  This is the algebraic singular-spectrum covariance
contract used by the numerical audit. -/
theorem transformedRawCorrectedSymmetricGradient_descaled_gram
    {Output Input Axis : Type*}
    [Fintype Output] [Fintype Input]
    [DecidableEq Output] [DecidableEq Input]
    (similarity : KelvinSpatialSimilarity Axis)
    (kelvinRotation : Matrix Output Output ℚ)
    (inputRotation : Matrix Input Input ℚ)
    (raw : Matrix Output Input ℚ)
    (scaleNonzero : similarity.scale ≠ 0)
    (kelvinOrthogonal : KelvinOrthogonal kelvinRotation) :
    rawInputGram
        (similarity.scale • transformedRawCorrectedSymmetricGradient similarity
          kelvinRotation inputRotation raw) =
      inputRotation * rawInputGram raw * inputRotation.transpose := by
  rcases kelvinOrthogonal with ⟨kelvinTransposeMul, _kelvinMulTranspose⟩
  have scaleCancel : similarity.scale * similarity.scale⁻¹ = 1 := by
    exact mul_inv_cancel₀ scaleNonzero
  simp only [transformedRawCorrectedSymmetricGradient, smul_smul, scaleCancel,
    one_smul, rawInputGram, Matrix.transpose_mul, Matrix.transpose_transpose,
    Matrix.mul_assoc]
  rw [← Matrix.mul_assoc kelvinRotation.transpose kelvinRotation,
    kelvinTransposeMul, Matrix.one_mul]

/-- Orthogonal conjugation recovers the original input Gram.  Therefore the
descaled raw operator has the same complete squared-singular-value spectrum. -/
theorem transformedRawCorrectedSymmetricGradient_raw_spectrum_covariant
    {Output Input Axis : Type*}
    [Fintype Output] [Fintype Input]
    [DecidableEq Output] [DecidableEq Input]
    (similarity : KelvinSpatialSimilarity Axis)
    (kelvinRotation : Matrix Output Output ℚ)
    (inputRotation : Matrix Input Input ℚ)
    (raw : Matrix Output Input ℚ)
    (scaleNonzero : similarity.scale ≠ 0)
    (kelvinOrthogonal : KelvinOrthogonal kelvinRotation)
    (inputOrthogonal : KelvinOrthogonal inputRotation) :
    inputRotation.transpose *
          rawInputGram
            (similarity.scale • transformedRawCorrectedSymmetricGradient
              similarity kelvinRotation inputRotation raw) *
        inputRotation =
      rawInputGram raw := by
  rw [transformedRawCorrectedSymmetricGradient_descaled_gram similarity
    kelvinRotation inputRotation raw scaleNonzero kelvinOrthogonal]
  rcases inputOrthogonal with ⟨inputTransposeMul, _inputMulTranspose⟩
  calc
    inputRotation.transpose *
          (inputRotation * rawInputGram raw * inputRotation.transpose) *
        inputRotation =
        (inputRotation.transpose * inputRotation) * rawInputGram raw *
          (inputRotation.transpose * inputRotation) := by
      simp only [Matrix.mul_assoc]
    _ = rawInputGram raw := by
      rw [inputTransposeMul, Matrix.one_mul, Matrix.mul_one]

/-- A single scalar applied to the complete Kelvin block is rotationally
invariant.  This is diagnostic-only; it is not a production normalization. -/
def diagnosticKelvinBlockScale
    {Output Input : Type*}
    (blockScale : ℚ) (raw : Matrix Output Input ℚ) : Matrix Output Input ℚ :=
  blockScale • raw

/-- A block scalar commutes with the complete raw covariance transformation. -/
theorem diagnosticKelvinBlockScale_covariant
    {Output Input Axis : Type*}
    [Fintype Output] [Fintype Input]
    (similarity : KelvinSpatialSimilarity Axis)
    (kelvinRotation : Matrix Output Output ℚ)
    (inputRotation : Matrix Input Input ℚ)
    (blockScale : ℚ)
    (raw : Matrix Output Input ℚ) :
    diagnosticKelvinBlockScale blockScale
        (transformedRawCorrectedSymmetricGradient similarity kelvinRotation
          inputRotation raw) =
      transformedRawCorrectedSymmetricGradient similarity kelvinRotation
        inputRotation (diagnosticKelvinBlockScale blockScale raw) := by
  ext output input
  simp [diagnosticKelvinBlockScale,
    transformedRawCorrectedSymmetricGradient, Matrix.mul_apply]
  ring

/-! ## Exact scalar-row-normalization counterexample -/

/-- Two raw Kelvin-style scalar rows over three input coordinates. -/
def kelvinRowNormalizationRaw : Matrix (Fin 2) (Fin 3) ℚ :=
  !![-7, 0, 0;
     -4, -3, 0]

/-- An exact nontrivial orthogonal mixing of the two output coordinates. -/
def kelvinRowMixing : Matrix (Fin 2) (Fin 2) ℚ :=
  !![3 / 5, -4 / 5;
     4 / 5,  3 / 5]

/-- The independently unit-normalized rows before output-coordinate mixing. -/
def kelvinRowsNormalizedBeforeMixing : Matrix (Fin 2) (Fin 3) ℚ :=
  !![-1, 0, 0;
     -4 / 5, -3 / 5, 0]

/-- The independently unit-normalized rows after the exact output mixing. -/
def kelvinRowsNormalizedAfterMixing : Matrix (Fin 2) (Fin 3) ℚ :=
  !![-5 / 13, 12 / 13, 0;
     -40 / 41, -9 / 41, 0]

/-- Exact squared Euclidean norm of one scalar output row. -/
def rationalRowSquaredNorm
    {Rows Columns : Type*} [Fintype Columns]
    (matrix : Matrix Rows Columns ℚ) (row : Rows) : ℚ :=
  ∑ column, matrix row column * matrix row column

/-- Independent scalar-row rescaling, the diagnostic operation under audit. -/
def scalarRowScale
    {Rows Columns : Type*}
    (scale : Rows → ℚ) (matrix : Matrix Rows Columns ℚ) :
    Matrix Rows Columns ℚ :=
  fun row column ↦ scale row * matrix row column

/-- Explicit determinant of a two-row output Gram. -/
def twoByTwoGramDeterminant (gram : Matrix (Fin 2) (Fin 2) ℚ) : ℚ :=
  gram 0 0 * gram 1 1 - gram 0 1 * gram 1 0

/-- The output mixing in the counterexample is exactly orthogonal. -/
theorem kelvinRowMixing_orthogonal : KelvinOrthogonal kelvinRowMixing := by
  constructor
  all_goals ext row column
  all_goals fin_cases row
  all_goals fin_cases column
  all_goals
    norm_num [kelvinRowMixing, Matrix.mul_apply, Fin.sum_univ_succ]

/-- Raw orthogonal output mixing preserves the input Gram exactly. -/
theorem kelvinRowNormalizationCounterexample_raw_gram_covariant :
    rawInputGram (kelvinRowMixing * kelvinRowNormalizationRaw) =
      rawInputGram kelvinRowNormalizationRaw := by
  ext row column
  all_goals fin_cases row
  all_goals fin_cases column
  all_goals
    norm_num [rawInputGram, kelvinRowMixing, kelvinRowNormalizationRaw,
      Matrix.mul_apply, Fin.sum_univ_succ]

/-- The displayed unit-row matrices are exactly the independent Euclidean row
normalizations before and after mixing; no floating approximation is hidden. -/
theorem kelvinRowNormalizationCounterexample_exact_normalizations :
    scalarRowScale ![1 / 7, 1 / 5] kelvinRowNormalizationRaw =
        kelvinRowsNormalizedBeforeMixing ∧
      scalarRowScale ![5 / 13, 5 / 41]
          (kelvinRowMixing * kelvinRowNormalizationRaw) =
        kelvinRowsNormalizedAfterMixing := by
  constructor
  · ext row column
    all_goals fin_cases row
    all_goals fin_cases column
    all_goals
      norm_num [scalarRowScale, kelvinRowNormalizationRaw,
        kelvinRowsNormalizedBeforeMixing]
  · ext row column
    all_goals fin_cases row
    all_goals fin_cases column
    all_goals
      norm_num [scalarRowScale, kelvinRowMixing, kelvinRowNormalizationRaw,
        kelvinRowsNormalizedAfterMixing, Matrix.mul_apply, Fin.sum_univ_succ]

/-- Both rows are exactly unit length before independent normalization. -/
theorem kelvinRowsNormalizedBeforeMixing_unit_rows :
    ∀ row : Fin 2,
      rationalRowSquaredNorm kelvinRowsNormalizedBeforeMixing row = 1 := by
  intro row
  fin_cases row <;>
    norm_num [rationalRowSquaredNorm, kelvinRowsNormalizedBeforeMixing,
      Fin.sum_univ_succ]

/-- Both rows are exactly unit length after independent normalization. -/
theorem kelvinRowsNormalizedAfterMixing_unit_rows :
    ∀ row : Fin 2,
      rationalRowSquaredNorm kelvinRowsNormalizedAfterMixing row = 1 := by
  intro row
  fin_cases row <;>
    norm_num [rationalRowSquaredNorm, kelvinRowsNormalizedAfterMixing,
      Fin.sum_univ_succ]

/--
The two independently normalized matrices have different output-Gram
determinants.  These determinants are products of the two nonzero squared
singular values, so their raw singular spectra cannot agree.
-/
theorem scalarRowNormalization_destroys_raw_spectrum_covariance :
    twoByTwoGramDeterminant
        (rawOutputGram kelvinRowsNormalizedBeforeMixing) ≠
      twoByTwoGramDeterminant
        (rawOutputGram kelvinRowsNormalizedAfterMixing) := by
  norm_num [rawOutputGram, kelvinRowsNormalizedBeforeMixing,
    kelvinRowsNormalizedAfterMixing, twoByTwoGramDeterminant,
    Matrix.mul_apply, Fin.sum_univ_succ]

end MLSFormal
