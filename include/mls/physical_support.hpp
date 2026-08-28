#pragma once

#include "mls/quantity.hpp"

namespace mls {

// Exact spherical point support for the MLS-0 reference transitions. The
// radius is a dimensioned length; voxel coordinates never enter this decision.
// The implementation performs a portable checked 128-bit comparison without
// relying on compiler-specific integer extensions.
[[nodiscard]] bool within_spherical_support(
    const Position3& first, const Position3& second, Length interaction_radius);

} // namespace mls
