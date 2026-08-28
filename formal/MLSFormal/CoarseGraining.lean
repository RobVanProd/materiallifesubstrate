import Mathlib.Data.Nat.Basic

set_option autoImplicit false

namespace MLSFormal

/-- Two reactant inventories within one local reaction volume. -/
structure ReactionCell where
  amountA : Nat
  amountB : Nat
deriving DecidableEq, Repr

/-- Maximum extent of a one-to-one local `A + B` reaction. -/
def localReactionCapacity (cell : ReactionCell) : Nat :=
  min cell.amountA cell.amountB

/-- Naive extensive aggregation of two fine reaction cells. -/
def aggregateReactionCells (left right : ReactionCell) : ReactionCell where
  amountA := left.amountA + right.amountA
  amountB := left.amountB + right.amountB

def separatedA : ReactionCell := { amountA := 1, amountB := 0 }
def separatedB : ReactionCell := { amountA := 0, amountB := 1 }

/-- Naive aggregation exactly preserves each reactant total. -/
theorem aggregation_preserves_reactantTotals :
    aggregateReactionCells separatedA separatedB =
      { amountA := 1, amountB := 1 } := by
  rfl

/-- Separated fine cells cannot react locally, while their coarse sum can. -/
theorem conservativeAggregation_canInventReaction :
    localReactionCapacity separatedA + localReactionCapacity separatedB = 0 ∧
      localReactionCapacity (aggregateReactionCells separatedA separatedB) = 1 := by
  decide

end MLSFormal
