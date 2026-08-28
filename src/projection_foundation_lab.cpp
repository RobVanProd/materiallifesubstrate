#include "mls/projection_foundation_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstring>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <tuple>
#include <type_traits>
#include <utility>

namespace mls::experimental::projection_foundation {
namespace {

constexpr std::array<std::uint8_t, 8> checkpoint_magic{
    'M', 'L', 'S', 'P', 'R', 'O', 'J', '1'};
constexpr std::uint64_t fnv_offset = UINT64_C(14695981039346656037);
constexpr std::uint64_t fnv_prime = UINT64_C(1099511628211);

[[nodiscard]] bool finite(Vec3d value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z);
}

void validate_config(const TransferConfig& config) {
    if (!(config.grid_spacing_m > 0.0) || !std::isfinite(config.grid_spacing_m)) {
        throw std::invalid_argument("projection grid spacing must be finite and positive");
    }
    if (!(config.kg_per_mass_quantum > 0.0) ||
        !std::isfinite(config.kg_per_mass_quantum)) {
        throw std::invalid_argument("projection mass quantum scale must be finite and positive");
    }
    if (!finite(config.grid_origin_m)) {
        throw std::invalid_argument("projection grid origin must be finite");
    }
}

[[nodiscard]] std::vector<CenterParticle> canonical_centers(
    std::span<const CenterParticle> particles) {
    std::vector<CenterParticle> result(particles.begin(), particles.end());
    std::ranges::sort(result, {}, &CenterParticle::id);
    std::int64_t total_mass = 0;
    bool have_previous = false;
    std::uint64_t previous_id = 0;
    for (const auto& particle : result) {
        if (particle.mass_quanta <= 0) {
            throw std::invalid_argument("projection center mass must be positive");
        }
        if (!finite(particle.position_m) || !finite(particle.velocity_m_per_s)) {
            throw std::invalid_argument("projection center state must be finite");
        }
        if (have_previous && particle.id == previous_id) {
            throw std::invalid_argument("projection center IDs must be unique");
        }
        have_previous = true;
        previous_id = particle.id;
        if (particle.mass_quanta > std::numeric_limits<std::int64_t>::max() - total_mass) {
            throw std::overflow_error("exact projection mass overflow");
        }
        total_mass += particle.mass_quanta;
    }
    return result;
}

[[nodiscard]] std::int64_t exact_mass(std::span<const CenterParticle> particles) {
    std::int64_t total = 0;
    for (const auto& particle : particles) {
        if (particle.mass_quanta > std::numeric_limits<std::int64_t>::max() - total) {
            throw std::overflow_error("exact projection mass overflow");
        }
        total += particle.mass_quanta;
    }
    return total;
}

[[nodiscard]] double particle_mass_kg(
    const CenterParticle& particle, const TransferConfig& config) {
    const auto mass = static_cast<double>(particle.mass_quanta) * config.kg_per_mass_quantum;
    if (!(mass > 0.0) || !std::isfinite(mass)) {
        throw std::overflow_error("projection center mass conversion overflow");
    }
    return mass;
}

[[nodiscard]] double scalar_component(Vec3d value, std::size_t component) noexcept {
    switch (component) {
    case 0:
        return value.x;
    case 1:
        return value.y;
    default:
        return value.z;
    }
}

void set_scalar_component(Vec3d& value, std::size_t component, double scalar) noexcept {
    switch (component) {
    case 0:
        value.x = scalar;
        break;
    case 1:
        value.y = scalar;
        break;
    default:
        value.z = scalar;
        break;
    }
}

[[nodiscard]] double vector_norm(std::span<const double> values) noexcept {
    long double squared = 0.0L;
    for (const auto value : values) {
        squared += static_cast<long double>(value) * static_cast<long double>(value);
    }
    return std::sqrt(static_cast<double>(squared));
}

[[nodiscard]] double scalar_dot(
    std::span<const double> lhs, std::span<const double> rhs) noexcept {
    long double result = 0.0L;
    for (std::size_t index = 0; index < lhs.size(); ++index) {
        result += static_cast<long double>(lhs[index]) *
            static_cast<long double>(rhs[index]);
    }
    return static_cast<double>(result);
}

[[nodiscard]] std::vector<double> apply_scalar_mass(
    const ProjectionSystem& system, std::span<const double> values) {
    if (values.size() != system.active_nodes.size()) {
        throw std::invalid_argument("consistent mass vector has the wrong dimension");
    }
    std::vector<double> result(values.size(), 0.0);
    for (std::size_t row = 0; row < system.consistent_mass_rows.size(); ++row) {
        long double sum = 0.0L;
        for (const auto& [column, coefficient] : system.consistent_mass_rows[row]) {
            sum += static_cast<long double>(coefficient) *
                static_cast<long double>(values[column]);
        }
        result[row] = static_cast<double>(sum);
        if (!std::isfinite(result[row])) {
            throw std::overflow_error("consistent mass application overflow");
        }
    }
    return result;
}

[[nodiscard]] std::uint64_t fnv_byte(std::uint64_t hash, std::uint8_t byte) noexcept {
    return (hash ^ byte) * fnv_prime;
}

template <typename Integer>
[[nodiscard]] std::uint64_t fnv_integer(std::uint64_t hash, Integer value) noexcept {
    using Unsigned = std::make_unsigned_t<Integer>;
    auto bits = static_cast<Unsigned>(value);
    for (std::size_t index = 0; index < sizeof(Unsigned); ++index) {
        hash = fnv_byte(hash, static_cast<std::uint8_t>(bits & Unsigned{0xff}));
        bits >>= 8U;
    }
    return hash;
}

[[nodiscard]] std::uint64_t node_digest(std::span<const GridIndex> nodes) noexcept {
    auto hash = fnv_integer(fnv_offset, static_cast<std::uint64_t>(nodes.size()));
    for (const auto& node : nodes) {
        hash = fnv_integer(hash, node.x);
        hash = fnv_integer(hash, node.y);
        hash = fnv_integer(hash, node.z);
    }
    return hash;
}

[[nodiscard]] double symmetric_relative(double lhs, double rhs) noexcept {
    return std::abs(lhs - rhs) / std::max({1.0, std::abs(lhs), std::abs(rhs)});
}

[[nodiscard]] double center_kinetic(
    std::span<const CenterParticle> particles, const TransferConfig& config) {
    long double energy = 0.0L;
    for (const auto& particle : particles) {
        const auto mass = particle_mass_kg(particle, config);
        energy += 0.5L * static_cast<long double>(mass) *
            static_cast<long double>(dot(particle.velocity_m_per_s,
                                         particle.velocity_m_per_s));
    }
    const auto result = static_cast<double>(energy);
    if (!std::isfinite(result)) {
        throw std::overflow_error("projection kinetic diagnostic overflow");
    }
    return result;
}

struct SpectralDiagnostic final {
    std::size_t rank{0};
    double smallest{0.0};
    double largest{0.0};
    double condition{std::numeric_limits<double>::infinity()};
    bool estimated{false};
    std::string method{};
};

[[nodiscard]] SpectralDiagnostic dense_cholesky_diagnostic(
    const ProjectionSystem& system, bool jacobi_scaled, double relative_pivot_min) {
    const auto count = system.active_nodes.size();
    std::vector<double> matrix(count * count, 0.0);
    for (std::size_t row = 0; row < count; ++row) {
        for (const auto& [column, coefficient] : system.consistent_mass_rows[row]) {
            auto value = coefficient;
            if (jacobi_scaled) {
                value /= std::sqrt(
                    system.lumped_mass_kg[row] * system.lumped_mass_kg[column]);
            }
            matrix[row * count + column] = value;
        }
    }
    const auto diagonal_scale = [&]() {
        double result = 0.0;
        for (std::size_t index = 0; index < count; ++index) {
            result = std::max(result, std::abs(matrix[index * count + index]));
        }
        return result;
    }();
    SpectralDiagnostic result{};
    result.method = jacobi_scaled ? "dense Cholesky pivots of D^-1/2 M D^-1/2"
                                  : "dense Cholesky pivots of M";
    result.smallest = std::numeric_limits<double>::infinity();
    for (std::size_t row = 0; row < count; ++row) {
        for (std::size_t column = 0; column <= row; ++column) {
            long double value = matrix[row * count + column];
            for (std::size_t inner = 0; inner < column; ++inner) {
                value -= static_cast<long double>(matrix[row * count + inner]) *
                    static_cast<long double>(matrix[column * count + inner]);
            }
            if (row == column) {
                const auto pivot = static_cast<double>(value);
                result.smallest = std::min(result.smallest, pivot);
                result.largest = std::max(result.largest, pivot);
                if (!std::isfinite(pivot) || !(pivot > relative_pivot_min * diagonal_scale)) {
                    result.rank = row;
                    result.condition = std::numeric_limits<double>::infinity();
                    return result;
                }
                matrix[row * count + column] = std::sqrt(pivot);
                result.rank = row + 1U;
            } else {
                matrix[row * count + column] =
                    static_cast<double>(value) / matrix[column * count + column];
            }
        }
    }
    result.condition = result.largest / result.smallest;
    return result;
}

[[nodiscard]] std::vector<double> jacobi_eigenvalues(std::vector<double> matrix) {
    const auto count = static_cast<std::size_t>(
        std::sqrt(static_cast<double>(matrix.size())));
    if (count * count != matrix.size()) {
        throw std::logic_error("Jacobi diagnostic matrix is not square");
    }
    const auto tolerance = 64.0 * std::numeric_limits<double>::epsilon();
    for (std::size_t sweep = 0; sweep < 64U; ++sweep) {
        double maximum_off_diagonal = 0.0;
        double maximum_diagonal = 0.0;
        for (std::size_t row = 0; row < count; ++row) {
            maximum_diagonal = std::max(
                maximum_diagonal, std::abs(matrix[row * count + row]));
            for (std::size_t column = row + 1U; column < count; ++column) {
                maximum_off_diagonal = std::max(
                    maximum_off_diagonal, std::abs(matrix[row * count + column]));
            }
        }
        if (maximum_off_diagonal <= tolerance * std::max(1.0, maximum_diagonal)) {
            break;
        }
        for (std::size_t row = 0; row < count; ++row) {
            for (std::size_t column = row + 1U; column < count; ++column) {
                const auto off = matrix[row * count + column];
                if (std::abs(off) <= tolerance * std::max(1.0, maximum_diagonal)) {
                    continue;
                }
                const auto diagonal_row = matrix[row * count + row];
                const auto diagonal_column = matrix[column * count + column];
                const auto angle = 0.5 * std::atan2(
                    2.0 * off, diagonal_column - diagonal_row);
                const auto cosine = std::cos(angle);
                const auto sine = std::sin(angle);
                for (std::size_t index = 0; index < count; ++index) {
                    if (index == row || index == column) {
                        continue;
                    }
                    const auto left = matrix[index * count + row];
                    const auto right = matrix[index * count + column];
                    const auto new_left = cosine * left - sine * right;
                    const auto new_right = sine * left + cosine * right;
                    matrix[index * count + row] = new_left;
                    matrix[row * count + index] = new_left;
                    matrix[index * count + column] = new_right;
                    matrix[column * count + index] = new_right;
                }
                matrix[row * count + row] = cosine * cosine * diagonal_row -
                    2.0 * sine * cosine * off + sine * sine * diagonal_column;
                matrix[column * count + column] = sine * sine * diagonal_row +
                    2.0 * sine * cosine * off + cosine * cosine * diagonal_column;
                matrix[row * count + column] = 0.0;
                matrix[column * count + row] = 0.0;
            }
        }
    }
    std::vector<double> result(count, 0.0);
    for (std::size_t index = 0; index < count; ++index) {
        result[index] = matrix[index * count + index];
    }
    std::ranges::sort(result);
    return result;
}

template <typename Apply>
[[nodiscard]] SpectralDiagnostic lanczos_diagnostic(
    std::size_t dimension, std::size_t maximum_steps, Apply&& apply,
    std::string method) {
    const auto steps = std::min(dimension, maximum_steps);
    std::vector<std::vector<double>> basis;
    basis.reserve(steps);
    std::vector<double> vector(dimension, 0.0);
    for (std::size_t index = 0; index < dimension; ++index) {
        const auto centered = static_cast<std::int64_t>(index % 17U) - 8;
        vector[index] = static_cast<double>(centered) +
            (index % 2U == 0U ? 0.25 : -0.125);
    }
    const auto initial_norm = vector_norm(vector);
    for (auto& value : vector) {
        value /= initial_norm;
    }
    std::vector<double> alpha;
    std::vector<double> beta;
    alpha.reserve(steps);
    beta.reserve(steps > 0U ? steps - 1U : 0U);
    double previous_beta = 0.0;
    std::vector<double> previous(dimension, 0.0);
    for (std::size_t iteration = 0; iteration < steps; ++iteration) {
        basis.push_back(vector);
        auto work = apply(vector);
        if (iteration > 0U) {
            for (std::size_t index = 0; index < dimension; ++index) {
                work[index] -= previous_beta * previous[index];
            }
        }
        const auto diagonal = scalar_dot(vector, work);
        alpha.push_back(diagonal);
        for (std::size_t index = 0; index < dimension; ++index) {
            work[index] -= diagonal * vector[index];
        }
        // Full deterministic reorthogonalization keeps the small diagnostic
        // tridiagonal meaningful even for clustered eigenvalues.
        for (const auto& direction : basis) {
            const auto projection = scalar_dot(direction, work);
            for (std::size_t index = 0; index < dimension; ++index) {
                work[index] -= projection * direction[index];
            }
        }
        const auto next_beta = vector_norm(work);
        if (iteration + 1U == steps ||
            next_beta <= 128.0 * std::numeric_limits<double>::epsilon()) {
            break;
        }
        beta.push_back(next_beta);
        previous = vector;
        previous_beta = next_beta;
        for (std::size_t index = 0; index < dimension; ++index) {
            vector[index] = work[index] / next_beta;
        }
    }
    const auto count = alpha.size();
    std::vector<double> tridiagonal(count * count, 0.0);
    for (std::size_t index = 0; index < count; ++index) {
        tridiagonal[index * count + index] = alpha[index];
        if (index + 1U < count) {
            tridiagonal[index * count + index + 1U] = beta[index];
            tridiagonal[(index + 1U) * count + index] = beta[index];
        }
    }
    const auto eigenvalues = jacobi_eigenvalues(std::move(tridiagonal));
    SpectralDiagnostic result{};
    result.rank = dimension;
    result.smallest = eigenvalues.front();
    result.largest = eigenvalues.back();
    result.condition = result.smallest > 0.0
        ? result.largest / result.smallest
        : std::numeric_limits<double>::infinity();
    // Every Lanczos/Ritz report is an estimate, including the unusual case in
    // which the configured step cap reaches the vector-space dimension. It is
    // never presented as a certified rank or condition number.
    result.estimated = true;
    result.method = std::move(method);
    return result;
}

struct PcgResult final {
    ProjectionStatus status{ProjectionStatus::breakdown};
    std::vector<double> solution{};
    std::size_t iterations{0};
    double absolute_residual{std::numeric_limits<double>::infinity()};
    double normalized_residual{std::numeric_limits<double>::infinity()};
};

[[nodiscard]] PcgResult solve_pcg(
    const ProjectionSystem& system,
    std::span<const double> rhs,
    std::size_t iteration_limit,
    double normalized_residual_max) {
    const auto count = rhs.size();
    PcgResult result{};
    result.solution.assign(count, 0.0);
    std::vector<double> residual(rhs.begin(), rhs.end());
    const auto rhs_norm = vector_norm(rhs);
    const auto denominator = std::max(1.0, rhs_norm);
    result.absolute_residual = rhs_norm;
    result.normalized_residual = rhs_norm / denominator;
    if (result.normalized_residual <= normalized_residual_max) {
        result.status = ProjectionStatus::solved;
        return result;
    }
    std::vector<double> preconditioned(count, 0.0);
    for (std::size_t index = 0; index < count; ++index) {
        preconditioned[index] = residual[index] / system.lumped_mass_kg[index];
    }
    auto direction = preconditioned;
    auto residual_dot_preconditioned = scalar_dot(residual, preconditioned);
    if (!(residual_dot_preconditioned > 0.0) ||
        !std::isfinite(residual_dot_preconditioned)) {
        result.status = ProjectionStatus::breakdown;
        return result;
    }
    for (std::size_t iteration = 0; iteration < iteration_limit; ++iteration) {
        const auto matrix_direction = apply_scalar_mass(system, direction);
        const auto curvature = scalar_dot(direction, matrix_direction);
        if (!(curvature > 0.0) || !std::isfinite(curvature)) {
            result.status = ProjectionStatus::breakdown;
            result.iterations = iteration;
            return result;
        }
        const auto alpha = residual_dot_preconditioned / curvature;
        if (!std::isfinite(alpha)) {
            result.status = ProjectionStatus::breakdown;
            result.iterations = iteration;
            return result;
        }
        for (std::size_t index = 0; index < count; ++index) {
            result.solution[index] += alpha * direction[index];
            residual[index] -= alpha * matrix_direction[index];
        }
        result.iterations = iteration + 1U;
        result.absolute_residual = vector_norm(residual);
        result.normalized_residual = result.absolute_residual / denominator;
        if (!std::isfinite(result.normalized_residual)) {
            result.status = ProjectionStatus::breakdown;
            return result;
        }
        if (result.normalized_residual <= normalized_residual_max) {
            result.status = ProjectionStatus::solved;
            return result;
        }
        for (std::size_t index = 0; index < count; ++index) {
            preconditioned[index] = residual[index] / system.lumped_mass_kg[index];
        }
        const auto next_dot = scalar_dot(residual, preconditioned);
        if (!(next_dot > 0.0) || !std::isfinite(next_dot)) {
            result.status = ProjectionStatus::breakdown;
            return result;
        }
        const auto beta_value = next_dot / residual_dot_preconditioned;
        for (std::size_t index = 0; index < count; ++index) {
            direction[index] = preconditioned[index] + beta_value * direction[index];
        }
        residual_dot_preconditioned = next_dot;
    }
    result.status = ProjectionStatus::iteration_limit;
    return result;
}

[[nodiscard]] std::vector<Vec3d> lumped_velocity(const ProjectionSystem& system) {
    std::vector<Vec3d> result(system.active_nodes.size());
    for (std::size_t index = 0; index < result.size(); ++index) {
        result[index] = system.consistent_rhs_kg_m_per_s[index] /
            system.lumped_mass_kg[index];
        if (!finite(result[index])) {
            throw std::overflow_error("lumped projection produced a nonfinite velocity");
        }
    }
    return result;
}

[[nodiscard]] double normalized_grid_norm(
    std::span<const Vec3d> values, std::span<const Vec3d> reference) noexcept {
    long double numerator = 0.0L;
    long double denominator = 0.0L;
    for (std::size_t index = 0; index < values.size(); ++index) {
        numerator += static_cast<long double>(dot(values[index], values[index]));
        denominator += static_cast<long double>(dot(reference[index], reference[index]));
    }
    return std::sqrt(static_cast<double>(numerator)) /
        std::max(1.0, std::sqrt(static_cast<double>(denominator)));
}

[[nodiscard]] std::vector<Vec3d> fmpm_velocity(
    const ProjectionSystem& system, std::uint32_t order,
    double& residual_identity_normalized) {
    auto increment = lumped_velocity(system);
    std::vector<Vec3d> result(system.active_nodes.size());
    for (std::uint32_t level = 1; level <= order; ++level) {
        for (std::size_t index = 0; index < result.size(); ++index) {
            result[index] += increment[index];
        }
        if (level <= order) {
            const auto mass_increment = apply_consistent_mass(system, increment);
            std::vector<Vec3d> next(increment.size());
            for (std::size_t index = 0; index < next.size(); ++index) {
                next[index] = increment[index] -
                    mass_increment[index] / system.lumped_mass_kg[index];
            }
            increment = std::move(next);
        }
    }
    const auto mass_result = apply_consistent_mass(system, result);
    std::vector<Vec3d> residual(result.size());
    std::vector<Vec3d> identity_difference(result.size());
    for (std::size_t index = 0; index < result.size(); ++index) {
        residual[index] = system.consistent_rhs_kg_m_per_s[index] - mass_result[index];
        identity_difference[index] = residual[index] -
            system.lumped_mass_kg[index] * increment[index];
    }
    residual_identity_normalized = normalized_grid_norm(
        identity_difference, system.consistent_rhs_kg_m_per_s);
    return result;
}

[[nodiscard]] std::uint32_t fmpm_order(ProjectionCandidate candidate) {
    switch (candidate) {
    case ProjectionCandidate::fmpm_1:
        return 1;
    case ProjectionCandidate::fmpm_2:
        return 2;
    case ProjectionCandidate::fmpm_3:
        return 3;
    case ProjectionCandidate::fmpm_4:
        return 4;
    default:
        throw std::invalid_argument("candidate is not an FMPM order");
    }
}

[[nodiscard]] bool successful(ProjectionStatus status) noexcept {
    return status == ProjectionStatus::solved;
}

class Writer final {
public:
    void byte(std::uint8_t value) { bytes_.push_back(value); }

    template <typename Integer>
    void integer(Integer value) {
        using Unsigned = std::make_unsigned_t<Integer>;
        auto bits = static_cast<Unsigned>(value);
        for (std::size_t index = 0; index < sizeof(Unsigned); ++index) {
            byte(static_cast<std::uint8_t>(bits & Unsigned{0xff}));
            bits >>= 8U;
        }
    }

    void real(double value) {
        // Canonicalize the two IEEE zero encodings. Decode then rejects a
        // negative-zero payload through the byte-for-byte canonicality gate.
        integer(std::bit_cast<std::uint64_t>(value == 0.0 ? 0.0 : value));
    }

    [[nodiscard]] const std::vector<std::uint8_t>& bytes() const noexcept { return bytes_; }
    [[nodiscard]] std::vector<std::uint8_t> finish() && { return std::move(bytes_); }

private:
    std::vector<std::uint8_t> bytes_{};
};

[[nodiscard]] std::uint64_t checksum(std::span<const std::uint8_t> bytes) noexcept {
    auto hash = fnv_offset;
    for (const auto byte : bytes) {
        hash = fnv_byte(hash, byte);
    }
    return hash;
}

class Reader final {
public:
    explicit Reader(std::span<const std::uint8_t> bytes) : bytes_(bytes) {}

    [[nodiscard]] std::uint8_t byte() {
        if (offset_ >= bytes_.size()) {
            throw std::invalid_argument("projection checkpoint is truncated");
        }
        return bytes_[offset_++];
    }

    template <typename Integer>
    [[nodiscard]] Integer integer() {
        using Unsigned = std::make_unsigned_t<Integer>;
        Unsigned result = 0;
        for (std::size_t index = 0; index < sizeof(Unsigned); ++index) {
            result |= static_cast<Unsigned>(byte()) << (8U * index);
        }
        return static_cast<Integer>(result);
    }

    [[nodiscard]] double real() { return std::bit_cast<double>(integer<std::uint64_t>()); }
    [[nodiscard]] std::size_t offset() const noexcept { return offset_; }

private:
    std::span<const std::uint8_t> bytes_{};
    std::size_t offset_{0};
};

void validate_state(const ProjectionLabState& state) {
    validate_config(state.config);
    if (state.physical_time_scale.seconds_per_time_quantum_numerator == 0U ||
        state.physical_time_scale.seconds_per_time_quantum_denominator == 0U) {
        throw std::invalid_argument("projection checkpoint time scale must be positive");
    }
    static_cast<void>(canonical_centers(state.particles));
}

} // namespace

std::string_view candidate_name(ProjectionCandidate candidate) noexcept {
    switch (candidate) {
    case ProjectionCandidate::lumped_pic:
        return "lumped_PIC";
    case ProjectionCandidate::full_consistent:
        return "full_consistent";
    case ProjectionCandidate::fmpm_1:
        return "FMPM_1";
    case ProjectionCandidate::fmpm_2:
        return "FMPM_2";
    case ProjectionCandidate::fmpm_3:
        return "FMPM_3";
    case ProjectionCandidate::fmpm_4:
        return "FMPM_4";
    }
    return "unknown";
}

std::string_view status_name(ProjectionStatus status) noexcept {
    switch (status) {
    case ProjectionStatus::solved:
        return "solved";
    case ProjectionStatus::empty:
        return "empty";
    case ProjectionStatus::structurally_rank_deficient:
        return "structurally_rank_deficient";
    case ProjectionStatus::numerically_rank_deficient:
        return "numerically_rank_deficient";
    case ProjectionStatus::ill_conditioned:
        return "ill_conditioned";
    case ProjectionStatus::breakdown:
        return "breakdown";
    case ProjectionStatus::iteration_limit:
        return "iteration_limit";
    case ProjectionStatus::residual_failed:
        return "residual_failed";
    }
    return "unknown";
}

ProjectionSystem build_projection_system(
    std::span<const CenterParticle> particles,
    const TransferConfig& config) {
    validate_config(config);
    ProjectionSystem result{};
    result.config = config;
    result.particles = canonical_centers(particles);
    result.assembly_diagnostics.particle_count = result.particles.size();
    result.assembly_diagnostics.exact_mass_quanta_before = exact_mass(result.particles);
    result.assembly_diagnostics.exact_mass_quanta_after =
        result.assembly_diagnostics.exact_mass_quanta_before;
    if (result.particles.empty()) {
        result.assembly_diagnostics.numerical_rank_method = "empty";
        result.assembly_diagnostics.termination_reason = "empty center state";
        return result;
    }

    struct LocalEntry final {
        GridIndex index{};
        double weight{0.0};
        Vec3d node_position_m{};
    };
    std::vector<std::vector<LocalEntry>> local_stencils;
    local_stencils.reserve(result.particles.size());
    std::map<GridIndex, Vec3d> ordered_nodes;
    for (const auto& particle : result.particles) {
        std::vector<LocalEntry> local;
        for (const auto& sample : quadratic_bspline_samples(particle.position_m, config)) {
            if (!std::isfinite(sample.weight) || sample.weight < 0.0) {
                throw std::runtime_error("projection basis produced an invalid weight");
            }
            if (sample.weight == 0.0) {
                continue;
            }
            local.push_back({sample.index, sample.weight, sample.node_position_m});
            const auto [position, inserted] =
                ordered_nodes.emplace(sample.index, sample.node_position_m);
            if (!inserted && position->second != sample.node_position_m) {
                throw std::runtime_error("projection grid node position is inconsistent");
            }
        }
        if (local.empty()) {
            throw std::runtime_error("projection center has empty basis support");
        }
        result.assembly_diagnostics.shape_entry_count += local.size();
        local_stencils.push_back(std::move(local));
    }
    std::map<GridIndex, std::size_t> node_lookup;
    for (const auto& [index, position] : ordered_nodes) {
        node_lookup.emplace(index, result.active_nodes.size());
        result.active_nodes.push_back(index);
        result.active_node_positions_m.push_back(position);
    }
    const auto node_count = result.active_nodes.size();
    result.assembly_diagnostics.active_node_count = node_count;
    result.assembly_diagnostics.structural_rank_upper_bound =
        std::min(result.particles.size(), node_count);
    result.assembly_diagnostics.node_order_digest = node_digest(result.active_nodes);
    result.lumped_mass_kg.assign(node_count, 0.0);
    result.consistent_mass_rows.resize(node_count);
    result.consistent_rhs_kg_m_per_s.assign(node_count, {});
    result.particle_stencils.reserve(result.particles.size());
    result.particle_mass_kg.reserve(result.particles.size());

    for (std::size_t particle_index = 0;
         particle_index < result.particles.size(); ++particle_index) {
        const auto& particle = result.particles[particle_index];
        const auto mass = particle_mass_kg(particle, config);
        result.particle_mass_kg.push_back(mass);
        std::vector<ProjectionStencilEntry> stencil;
        stencil.reserve(local_stencils[particle_index].size());
        long double partition_sum = 0.0L;
        Vec3d reproduced{};
        for (const auto& local : local_stencils[particle_index]) {
            const auto found = node_lookup.find(local.index);
            if (found == node_lookup.end()) {
                throw std::logic_error("projection active-node lookup failed");
            }
            const auto node = found->second;
            stencil.push_back({node, local.weight});
            partition_sum += local.weight;
            reproduced += local.weight * local.node_position_m;
            const auto weighted_mass = mass * local.weight;
            result.lumped_mass_kg[node] += weighted_mass;
            result.consistent_rhs_kg_m_per_s[node] +=
                weighted_mass * particle.velocity_m_per_s;
        }
        result.assembly_diagnostics.partition_unity_max_residual = std::max(
            result.assembly_diagnostics.partition_unity_max_residual,
            std::abs(static_cast<double>(partition_sum - 1.0L)));
        result.assembly_diagnostics.linear_reproduction_max_residual_m = std::max(
            result.assembly_diagnostics.linear_reproduction_max_residual_m,
            norm(reproduced - particle.position_m));
        for (const auto& row_entry : stencil) {
            auto& row = result.consistent_mass_rows[row_entry.node_index];
            for (const auto& column_entry : stencil) {
                auto& coefficient = row[column_entry.node_index];
                coefficient += mass * row_entry.weight * column_entry.weight;
                if (!std::isfinite(coefficient)) {
                    throw std::overflow_error("consistent mass assembly overflow");
                }
            }
        }
        result.particle_stencils.push_back(std::move(stencil));
    }

    long double grid_mass = 0.0L;
    long double particle_mass = 0.0L;
    double maximum_matrix_entry = 0.0;
    double maximum_symmetry_difference = 0.0;
    double maximum_row_sum_difference = 0.0;
    for (std::size_t row = 0; row < node_count; ++row) {
        if (!(result.lumped_mass_kg[row] > 0.0) ||
            !std::isfinite(result.lumped_mass_kg[row])) {
            throw std::runtime_error("projection active node has invalid lumped mass");
        }
        grid_mass += result.lumped_mass_kg[row];
        long double row_sum = 0.0L;
        for (const auto& [column, coefficient] : result.consistent_mass_rows[row]) {
            if (coefficient != 0.0) {
                ++result.assembly_diagnostics.matrix_nonzero_count;
            }
            maximum_matrix_entry = std::max(maximum_matrix_entry, std::abs(coefficient));
            row_sum += coefficient;
            const auto opposite = result.consistent_mass_rows[column].find(row);
            if (opposite == result.consistent_mass_rows[column].end()) {
                maximum_symmetry_difference = std::numeric_limits<double>::infinity();
            } else {
                maximum_symmetry_difference = std::max(
                    maximum_symmetry_difference,
                    std::abs(coefficient - opposite->second));
            }
        }
        maximum_row_sum_difference = std::max(
            maximum_row_sum_difference,
            std::abs(static_cast<double>(row_sum) - result.lumped_mass_kg[row]));
    }
    for (const auto mass : result.particle_mass_kg) {
        particle_mass += mass;
    }
    result.assembly_diagnostics.matrix_symmetry_relative_residual =
        maximum_symmetry_difference / std::max(1.0, maximum_matrix_entry);
    result.assembly_diagnostics.row_sum_relative_residual =
        maximum_row_sum_difference /
        std::max(1.0, *std::ranges::max_element(result.lumped_mass_kg));
    result.assembly_diagnostics.grid_mass_relative_error = symmetric_relative(
        static_cast<double>(grid_mass), static_cast<double>(particle_mass));
    result.assembly_diagnostics.termination_reason = "assembled";
    return result;
}

std::vector<Vec3d> apply_consistent_mass(
    const ProjectionSystem& system,
    std::span<const Vec3d> grid_values) {
    if (grid_values.size() != system.active_nodes.size()) {
        throw std::invalid_argument("consistent mass vector has the wrong dimension");
    }
    std::vector<Vec3d> result(grid_values.size());
    for (std::size_t row = 0; row < system.consistent_mass_rows.size(); ++row) {
        Vec3d value{};
        for (const auto& [column, coefficient] : system.consistent_mass_rows[row]) {
            value += coefficient * grid_values[column];
        }
        if (!finite(value)) {
            throw std::overflow_error("consistent mass application overflow");
        }
        result[row] = value;
    }
    return result;
}

std::vector<CenterParticle> reconstruct_centers(
    const ProjectionSystem& system,
    std::span<const Vec3d> grid_velocity_m_per_s) {
    if (grid_velocity_m_per_s.size() != system.active_nodes.size()) {
        throw std::invalid_argument("grid reconstruction vector has the wrong dimension");
    }
    std::vector<CenterParticle> result = system.particles;
    for (std::size_t particle = 0; particle < result.size(); ++particle) {
        Vec3d velocity{};
        for (const auto& entry : system.particle_stencils[particle]) {
            if (!finite(grid_velocity_m_per_s[entry.node_index])) {
                throw std::invalid_argument("grid reconstruction input must be finite");
            }
            velocity += entry.weight * grid_velocity_m_per_s[entry.node_index];
        }
        if (!finite(velocity)) {
            throw std::overflow_error("particle reconstruction overflow");
        }
        result[particle].velocity_m_per_s = velocity;
    }
    return result;
}

ProjectionResult project_centers(
    const ProjectionSystem& system,
    ProjectionCandidate candidate,
    const ProjectionSolvePolicy& policy) {
    if (!(policy.dense_relative_pivot_min > 0.0) ||
        !(policy.raw_condition_max > 0.0) ||
        !(policy.preconditioned_condition_max > 0.0) ||
        !(policy.normalized_residual_max > 0.0) ||
        policy.lanczos_max_steps == 0U ||
        !std::isfinite(policy.dense_relative_pivot_min) ||
        !std::isfinite(policy.raw_condition_max) ||
        !std::isfinite(policy.preconditioned_condition_max) ||
        !std::isfinite(policy.normalized_residual_max)) {
        throw std::invalid_argument("projection solve policy is invalid");
    }
    ProjectionResult result{};
    result.candidate = candidate;
    result.diagnostics = system.assembly_diagnostics;
    result.particles = system.particles;
    result.center_kinetic_before_j = center_kinetic(system.particles, system.config);
    if (system.particles.empty()) {
        result.status = ProjectionStatus::empty;
        result.diagnostics.termination_reason = "empty center state";
        return result;
    }

    if (candidate == ProjectionCandidate::lumped_pic) {
        result.grid_velocity_m_per_s = lumped_velocity(system);
        result.status = ProjectionStatus::solved;
        result.diagnostics.termination_reason = "lumped direct solve";
    } else if (candidate != ProjectionCandidate::full_consistent) {
        result.grid_velocity_m_per_s = fmpm_velocity(
            system, fmpm_order(candidate), result.fmpm_residual_identity_normalized);
        result.status = ProjectionStatus::solved;
        result.diagnostics.termination_reason = "revised 2026 FMPM recurrence";
    } else {
        const auto node_count = system.active_nodes.size();
        if (result.diagnostics.structural_rank_upper_bound < node_count) {
            result.status = ProjectionStatus::structurally_rank_deficient;
            result.diagnostics.numerical_rank_estimate =
                result.diagnostics.structural_rank_upper_bound;
            result.diagnostics.numerical_rank_method = "rank(M)<=min(P,n)";
            result.diagnostics.termination_reason =
                "active nodes exceed the particle rank upper bound";
            return result;
        }

        SpectralDiagnostic raw{};
        SpectralDiagnostic preconditioned{};
        if (node_count <= policy.dense_diagnostic_max_nodes) {
            raw = dense_cholesky_diagnostic(
                system, false, policy.dense_relative_pivot_min);
            preconditioned = dense_cholesky_diagnostic(
                system, true, policy.dense_relative_pivot_min);
        } else {
            raw = lanczos_diagnostic(
                node_count,
                policy.lanczos_max_steps,
                [&system](std::span<const double> values) {
                    return apply_scalar_mass(system, values);
                },
                "deterministic Lanczos Ritz estimate of M");
            preconditioned = lanczos_diagnostic(
                node_count,
                policy.lanczos_max_steps,
                [&system](std::span<const double> values) {
                    std::vector<double> scaled(values.size());
                    for (std::size_t index = 0; index < values.size(); ++index) {
                        scaled[index] = values[index] /
                            std::sqrt(system.lumped_mass_kg[index]);
                    }
                    auto applied = apply_scalar_mass(system, scaled);
                    for (std::size_t index = 0; index < values.size(); ++index) {
                        applied[index] /= std::sqrt(system.lumped_mass_kg[index]);
                    }
                    return applied;
                },
                "deterministic Lanczos Ritz estimate of D^-1/2 M D^-1/2");
        }
        result.diagnostics.numerical_rank_estimate =
            std::min(raw.rank, preconditioned.rank);
        result.diagnostics.numerical_rank_method = raw.method + "; " + preconditioned.method;
        result.diagnostics.numerical_rank_is_estimated = raw.estimated || preconditioned.estimated;
        result.diagnostics.smallest_spectral_or_pivot_value = raw.smallest;
        result.diagnostics.largest_spectral_or_pivot_value = raw.largest;
        result.diagnostics.raw_condition_estimate = raw.condition;
        result.diagnostics.preconditioned_condition_estimate = preconditioned.condition;
        if (raw.rank < node_count || preconditioned.rank < node_count ||
            !(raw.smallest > 0.0) || !(preconditioned.smallest > 0.0)) {
            result.status = ProjectionStatus::numerically_rank_deficient;
            result.diagnostics.termination_reason = "rank diagnostic failed";
            return result;
        }
        if (!std::isfinite(raw.condition) || !std::isfinite(preconditioned.condition) ||
            raw.condition > policy.raw_condition_max ||
            preconditioned.condition > policy.preconditioned_condition_max) {
            result.status = ProjectionStatus::ill_conditioned;
            result.diagnostics.termination_reason = "condition threshold exceeded";
            return result;
        }

        result.grid_velocity_m_per_s.assign(node_count, {});
        const auto iteration_limit = policy.iteration_limit_override == 0U
            ? std::min<std::size_t>(4U * node_count, 10'000U)
            : policy.iteration_limit_override;
        for (std::size_t component = 0; component < 3U; ++component) {
            std::vector<double> rhs(node_count, 0.0);
            for (std::size_t index = 0; index < node_count; ++index) {
                rhs[index] = scalar_component(
                    system.consistent_rhs_kg_m_per_s[index], component);
            }
            const auto solved = solve_pcg(
                system, rhs, iteration_limit, policy.normalized_residual_max);
            result.diagnostics.component_iterations[component] = solved.iterations;
            result.diagnostics.absolute_solve_residual[component] = solved.absolute_residual;
            result.diagnostics.normalized_solve_residual[component] =
                solved.normalized_residual;
            if (solved.status != ProjectionStatus::solved) {
                result.status = solved.status;
                result.grid_velocity_m_per_s.clear();
                result.diagnostics.termination_reason =
                    solved.status == ProjectionStatus::iteration_limit
                    ? "PCG iteration limit"
                    : "PCG curvature/preconditioner breakdown";
                return result;
            }
            for (std::size_t index = 0; index < node_count; ++index) {
                set_scalar_component(
                    result.grid_velocity_m_per_s[index], component, solved.solution[index]);
            }
        }
        const auto applied = apply_consistent_mass(system, result.grid_velocity_m_per_s);
        for (std::size_t component = 0; component < 3U; ++component) {
            std::vector<double> residual(node_count, 0.0);
            std::vector<double> rhs(node_count, 0.0);
            for (std::size_t index = 0; index < node_count; ++index) {
                residual[index] = scalar_component(
                    applied[index] - system.consistent_rhs_kg_m_per_s[index], component);
                rhs[index] = scalar_component(
                    system.consistent_rhs_kg_m_per_s[index], component);
            }
            result.diagnostics.absolute_solve_residual[component] = vector_norm(residual);
            result.diagnostics.normalized_solve_residual[component] =
                result.diagnostics.absolute_solve_residual[component] /
                std::max(1.0, vector_norm(rhs));
            if (!(result.diagnostics.normalized_solve_residual[component] <=
                  policy.normalized_residual_max)) {
                result.status = ProjectionStatus::residual_failed;
                result.grid_velocity_m_per_s.clear();
                result.diagnostics.termination_reason =
                    "recomputed full-system residual exceeds threshold";
                return result;
            }
        }
        result.status = ProjectionStatus::solved;
        result.diagnostics.termination_reason = "unregularized PCG solved";
    }

    result.particles = reconstruct_centers(system, result.grid_velocity_m_per_s);
    result.diagnostics.exact_mass_quanta_after = exact_mass(result.particles);
    result.center_kinetic_after_j = center_kinetic(result.particles, system.config);
    const auto mass_velocity = apply_consistent_mass(system, result.grid_velocity_m_per_s);
    long double grid_energy = 0.0L;
    for (std::size_t index = 0; index < result.grid_velocity_m_per_s.size(); ++index) {
        grid_energy += 0.5L * static_cast<long double>(
            dot(result.grid_velocity_m_per_s[index], mass_velocity[index]));
    }
    result.consistent_grid_quadratic_energy_j = static_cast<double>(grid_energy);
    result.numerical_projection_energy_residual_j =
        result.center_kinetic_after_j - result.center_kinetic_before_j;
    return result;
}

ProjectionResult project_centers(
    std::span<const CenterParticle> particles,
    const TransferConfig& config,
    ProjectionCandidate candidate,
    const ProjectionSolvePolicy& policy) {
    return project_centers(build_projection_system(particles, config), candidate, policy);
}

ProjectionStep trapezoid_projection_step(
    const ProjectionLabState& state,
    ProjectionCandidate candidate,
    std::uint64_t timestep_quanta,
    double timestep_s,
    const ProjectionSolvePolicy& policy) {
    validate_state(state);
    if (timestep_quanta == 0U || !(timestep_s > 0.0) || !std::isfinite(timestep_s)) {
        throw std::invalid_argument("projection timestep must be finite and positive");
    }
    const auto expected_timestep =
        (static_cast<double>(timestep_quanta) *
         static_cast<double>(state.physical_time_scale.seconds_per_time_quantum_numerator)) /
        static_cast<double>(state.physical_time_scale.seconds_per_time_quantum_denominator);
    const auto agreement_tolerance = 4.0 * std::numeric_limits<double>::epsilon() *
        std::max({1.0, timestep_s, expected_timestep});
    if (std::abs(timestep_s - expected_timestep) > agreement_tolerance) {
        throw std::invalid_argument(
            "binary64 timestep disagrees with the declared exact physical clock");
    }
    ProjectionStep result{};
    result.state = state;
    result.state.particles = canonical_centers(state.particles);
    const auto system = build_projection_system(result.state.particles, state.config);
    result.projection = project_centers(system, candidate, policy);
    if (!successful(result.projection.status)) {
        return result;
    }
    if (timestep_quanta >
        std::numeric_limits<std::uint64_t>::max() - state.elapsed_time_quanta) {
        throw std::overflow_error("exact projection clock overflow");
    }
    for (std::size_t index = 0; index < result.state.particles.size(); ++index) {
        const auto displacement = 0.5 * timestep_s *
            (result.state.particles[index].velocity_m_per_s +
             result.projection.particles[index].velocity_m_per_s);
        result.state.particles[index].position_m += displacement;
        result.state.particles[index].velocity_m_per_s =
            result.projection.particles[index].velocity_m_per_s;
        if (!finite(result.state.particles[index].position_m)) {
            throw std::overflow_error("projection trapezoid position overflow");
        }
    }
    result.state.elapsed_time_quanta += timestep_quanta;
    return result;
}

std::vector<std::uint8_t> serialize_projection_checkpoint(
    const ProjectionLabState& state) {
    validate_state(state);
    const auto particles = canonical_centers(state.particles);
    Writer writer;
    for (const auto byte : checkpoint_magic) {
        writer.byte(byte);
    }
    writer.integer(projection_checkpoint_format_version);
    writer.real(state.config.grid_spacing_m);
    writer.real(state.config.grid_origin_m.x);
    writer.real(state.config.grid_origin_m.y);
    writer.real(state.config.grid_origin_m.z);
    writer.real(state.config.kg_per_mass_quantum);
    writer.integer(state.physical_time_scale.seconds_per_time_quantum_numerator);
    writer.integer(state.physical_time_scale.seconds_per_time_quantum_denominator);
    writer.integer(state.elapsed_time_quanta);
    writer.integer(static_cast<std::uint64_t>(particles.size()));
    for (const auto& particle : particles) {
        writer.integer(particle.id);
        writer.integer(particle.mass_quanta);
        writer.real(particle.position_m.x);
        writer.real(particle.position_m.y);
        writer.real(particle.position_m.z);
        writer.real(particle.velocity_m_per_s.x);
        writer.real(particle.velocity_m_per_s.y);
        writer.real(particle.velocity_m_per_s.z);
    }
    const auto image_checksum = checksum(writer.bytes());
    writer.integer(image_checksum);
    return std::move(writer).finish();
}

ProjectionLabState deserialize_projection_checkpoint(
    std::span<const std::uint8_t> checkpoint) {
    constexpr auto fixed_payload_bytes = checkpoint_magic.size() +
        sizeof(std::uint32_t) + 5U * sizeof(std::uint64_t) +
        4U * sizeof(std::uint64_t);
    if (checkpoint.size() < fixed_payload_bytes + sizeof(std::uint64_t)) {
        throw std::invalid_argument("projection checkpoint is truncated");
    }
    const auto payload_size = checkpoint.size() - sizeof(std::uint64_t);
    Reader checksum_reader(checkpoint.subspan(payload_size));
    const auto stored_checksum = checksum_reader.integer<std::uint64_t>();
    if (stored_checksum != checksum(checkpoint.first(payload_size))) {
        throw std::invalid_argument("projection checkpoint checksum mismatch");
    }
    Reader reader(checkpoint.first(payload_size));
    for (const auto expected : checkpoint_magic) {
        if (reader.byte() != expected) {
            throw std::invalid_argument("projection checkpoint magic is invalid");
        }
    }
    if (reader.integer<std::uint32_t>() != projection_checkpoint_format_version) {
        throw std::invalid_argument("projection checkpoint version is unsupported");
    }
    ProjectionLabState result{};
    result.config.grid_spacing_m = reader.real();
    result.config.grid_origin_m = {reader.real(), reader.real(), reader.real()};
    result.config.kg_per_mass_quantum = reader.real();
    result.physical_time_scale.seconds_per_time_quantum_numerator =
        reader.integer<std::uint64_t>();
    result.physical_time_scale.seconds_per_time_quantum_denominator =
        reader.integer<std::uint64_t>();
    result.elapsed_time_quanta = reader.integer<std::uint64_t>();
    const auto count_u64 = reader.integer<std::uint64_t>();
    constexpr auto particle_bytes = 2U * sizeof(std::uint64_t) + 6U * sizeof(double);
    if (count_u64 > static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max()) ||
        count_u64 > static_cast<std::uint64_t>((payload_size - reader.offset()) /
                                               particle_bytes)) {
        throw std::invalid_argument("projection checkpoint particle count is invalid");
    }
    const auto count = static_cast<std::size_t>(count_u64);
    result.particles.reserve(count);
    for (std::size_t index = 0; index < count; ++index) {
        CenterParticle particle{};
        particle.id = reader.integer<std::uint64_t>();
        particle.mass_quanta = reader.integer<std::int64_t>();
        particle.position_m = {reader.real(), reader.real(), reader.real()};
        particle.velocity_m_per_s = {reader.real(), reader.real(), reader.real()};
        if (!result.particles.empty() && result.particles.back().id >= particle.id) {
            throw std::invalid_argument(
                "projection checkpoint centers are not in canonical ID order");
        }
        result.particles.push_back(particle);
    }
    if (reader.offset() != payload_size) {
        throw std::invalid_argument("projection checkpoint contains trailing payload bytes");
    }
    validate_state(result);
    if (serialize_projection_checkpoint(result) !=
        std::vector<std::uint8_t>(checkpoint.begin(), checkpoint.end())) {
        throw std::invalid_argument("projection checkpoint encoding is noncanonical");
    }
    return result;
}

} // namespace mls::experimental::projection_foundation
