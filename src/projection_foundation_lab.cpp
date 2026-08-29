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
    if (values.size() != system.active_nodes().size()) {
        throw std::invalid_argument("consistent mass vector has the wrong dimension");
    }
    std::vector<double> result(values.size(), 0.0);
    for (std::size_t row = 0; row < system.consistent_mass_rows().size(); ++row) {
        long double sum = 0.0L;
        for (const auto& [column, coefficient] : system.consistent_mass_rows()[row]) {
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
    bool resolved{true};
    std::string method{};
};

struct JacobiEigenResult final {
    std::vector<double> eigenvalues{};
    bool converged{false};
    double final_relative_off_diagonal{std::numeric_limits<double>::infinity()};
};

[[nodiscard]] JacobiEigenResult jacobi_eigenvalues(
    std::vector<double> matrix, std::size_t maximum_sweeps);

[[nodiscard]] SpectralDiagnostic dense_cholesky_diagnostic(
    const ProjectionSystem& system,
    bool jacobi_scaled,
    double relative_pivot_min,
    std::size_t jacobi_maximum_sweeps) {
    const auto count = system.active_nodes().size();
    std::vector<double> matrix(count * count, 0.0);
    for (std::size_t row = 0; row < count; ++row) {
        for (const auto& [column, coefficient] : system.consistent_mass_rows()[row]) {
            auto value = coefficient;
            if (jacobi_scaled) {
                value /= std::sqrt(
                    system.lumped_mass_kg()[row] * system.lumped_mass_kg()[column]);
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
    auto factor = matrix;
    std::size_t pivot_rank = 0;
    for (std::size_t row = 0; row < count; ++row) {
        for (std::size_t column = 0; column <= row; ++column) {
            long double value = factor[row * count + column];
            for (std::size_t inner = 0; inner < column; ++inner) {
                value -= static_cast<long double>(factor[row * count + inner]) *
                    static_cast<long double>(factor[column * count + inner]);
            }
            if (row == column) {
                const auto pivot = static_cast<double>(value);
                if (!std::isfinite(pivot) || !(pivot > relative_pivot_min * diagonal_scale)) {
                    break;
                }
                factor[row * count + column] = std::sqrt(pivot);
                pivot_rank = row + 1U;
            } else {
                factor[row * count + column] =
                    static_cast<double>(value) / factor[column * count + column];
            }
        }
        if (pivot_rank != row + 1U) {
            break;
        }
    }
    const auto eigen_result = jacobi_eigenvalues(
        std::move(matrix), jacobi_maximum_sweeps);
    SpectralDiagnostic result{};
    result.method = jacobi_scaled
        ? "dense Cholesky rank pivots plus symmetric Jacobi spectrum of D^-1/2 M D^-1/2"
        : "dense Cholesky rank pivots plus symmetric Jacobi spectrum of M";
    result.resolved = eigen_result.converged;
    if (!result.resolved) {
        result.rank = 0;
        result.smallest = std::numeric_limits<double>::quiet_NaN();
        result.largest = std::numeric_limits<double>::quiet_NaN();
        result.condition = std::numeric_limits<double>::infinity();
        result.method += "; Jacobi off-diagonal convergence unresolved";
        return result;
    }
    result.smallest = eigen_result.eigenvalues.front();
    result.largest = eigen_result.eigenvalues.back();
    const auto spectral_threshold = relative_pivot_min *
        std::max(std::abs(result.largest), std::numeric_limits<double>::min());
    const auto spectral_rank = static_cast<std::size_t>(std::ranges::count_if(
        eigen_result.eigenvalues, [spectral_threshold](double value) {
            return std::isfinite(value) && value > spectral_threshold;
        }));
    result.rank = std::min(pivot_rank, spectral_rank);
    result.condition = result.smallest > 0.0
        ? result.largest / result.smallest
        : std::numeric_limits<double>::infinity();
    result.estimated = false;
    return result;
}

[[nodiscard]] JacobiEigenResult jacobi_eigenvalues(
    std::vector<double> matrix, std::size_t maximum_sweeps) {
    const auto count = static_cast<std::size_t>(
        std::sqrt(static_cast<double>(matrix.size())));
    if (count * count != matrix.size()) {
        throw std::logic_error("Jacobi diagnostic matrix is not square");
    }
    const auto tolerance = 64.0 * std::numeric_limits<double>::epsilon();
    for (std::size_t sweep = 0; sweep < maximum_sweeps; ++sweep) {
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
        const auto matrix_scale =
            std::max(maximum_diagonal, std::numeric_limits<double>::min());
        if (maximum_off_diagonal <= tolerance * matrix_scale) {
            break;
        }
        for (std::size_t row = 0; row < count; ++row) {
            for (std::size_t column = row + 1U; column < count; ++column) {
                const auto off = matrix[row * count + column];
                if (std::abs(off) <= tolerance * matrix_scale) {
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
    JacobiEigenResult result{};
    result.eigenvalues.resize(count, 0.0);
    for (std::size_t index = 0; index < count; ++index) {
        result.eigenvalues[index] = matrix[index * count + index];
    }
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
    result.final_relative_off_diagonal = maximum_off_diagonal /
        std::max(maximum_diagonal, std::numeric_limits<double>::min());
    result.converged =
        result.final_relative_off_diagonal <= 64.0 * std::numeric_limits<double>::epsilon();
    std::ranges::sort(result.eigenvalues);
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
    const auto eigen_result = jacobi_eigenvalues(std::move(tridiagonal), 128U);
    SpectralDiagnostic result{};
    result.resolved = eigen_result.converged;
    result.rank = dimension;
    result.smallest = result.resolved
        ? eigen_result.eigenvalues.front()
        : std::numeric_limits<double>::quiet_NaN();
    result.largest = result.resolved
        ? eigen_result.eigenvalues.back()
        : std::numeric_limits<double>::quiet_NaN();
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
        preconditioned[index] = residual[index] / system.lumped_mass_kg()[index];
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
            preconditioned[index] = residual[index] / system.lumped_mass_kg()[index];
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
    std::vector<Vec3d> result(system.active_nodes().size());
    for (std::size_t index = 0; index < result.size(); ++index) {
        result[index] = system.consistent_rhs_kg_m_per_s()[index] /
            system.lumped_mass_kg()[index];
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
    std::vector<Vec3d> result(system.active_nodes().size());
    for (std::uint32_t level = 1; level <= order; ++level) {
        for (std::size_t index = 0; index < result.size(); ++index) {
            result[index] += increment[index];
        }
        if (level <= order) {
            const auto mass_increment = apply_consistent_mass(system, increment);
            std::vector<Vec3d> next(increment.size());
            for (std::size_t index = 0; index < next.size(); ++index) {
                next[index] = increment[index] -
                    mass_increment[index] / system.lumped_mass_kg()[index];
            }
            increment = std::move(next);
        }
    }
    const auto mass_result = apply_consistent_mass(system, result);
    std::vector<Vec3d> residual(result.size());
    std::vector<Vec3d> identity_difference(result.size());
    for (std::size_t index = 0; index < result.size(); ++index) {
        residual[index] = system.consistent_rhs_kg_m_per_s()[index] - mass_result[index];
        identity_difference[index] = residual[index] -
            system.lumped_mass_kg()[index] * increment[index];
    }
    residual_identity_normalized = normalized_grid_norm(
        identity_difference, system.consistent_rhs_kg_m_per_s());
    return result;
}

void record_consistent_system_residual(
    const ProjectionSystem& system,
    std::span<const Vec3d> grid_velocity,
    ProjectionDiagnostics& diagnostics) {
    const auto applied = apply_consistent_mass(system, grid_velocity);
    for (std::size_t component = 0; component < 3U; ++component) {
        std::vector<double> residual(applied.size(), 0.0);
        std::vector<double> rhs(applied.size(), 0.0);
        for (std::size_t index = 0; index < applied.size(); ++index) {
            residual[index] = scalar_component(
                applied[index] - system.consistent_rhs_kg_m_per_s()[index], component);
            rhs[index] = scalar_component(
                system.consistent_rhs_kg_m_per_s()[index], component);
        }
        diagnostics.solve_residual_applicable[component] = true;
        diagnostics.absolute_solve_residual[component] = vector_norm(residual);
        diagnostics.normalized_solve_residual[component] =
            diagnostics.absolute_solve_residual[component] /
            std::max(1.0, vector_norm(rhs));
    }
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
    case ProjectionStatus::numerical_overflow:
        return "numerical_overflow";
    }
    return "unknown";
}

ProjectionSystem build_projection_system(
    std::span<const CenterParticle> particles,
    const TransferConfig& config) {
    validate_config(config);
    ProjectionSystem result{};
    result.config_ = config;
    result.particles_ = canonical_centers(particles);
    result.assembly_diagnostics_.particle_count = result.particles_.size();
    result.assembly_diagnostics_.exact_mass_quanta_before = exact_mass(result.particles_);
    result.assembly_diagnostics_.exact_mass_quanta_after =
        result.assembly_diagnostics_.exact_mass_quanta_before;
    if (result.particles_.empty()) {
        result.assembly_diagnostics_.numerical_rank_method = "empty";
        result.assembly_diagnostics_.termination_reason = "empty center state";
        return result;
    }

    struct LocalEntry final {
        GridIndex index{};
        double weight{0.0};
        Vec3d node_position_m{};
    };
    std::vector<std::vector<LocalEntry>> local_stencils;
    local_stencils.reserve(result.particles_.size());
    std::map<GridIndex, Vec3d> ordered_nodes;
    for (const auto& particle : result.particles_) {
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
        result.assembly_diagnostics_.shape_entry_count += local.size();
        local_stencils.push_back(std::move(local));
    }
    std::map<GridIndex, std::size_t> node_lookup;
    for (const auto& [index, position] : ordered_nodes) {
        node_lookup.emplace(index, result.active_nodes_.size());
        result.active_nodes_.push_back(index);
        result.active_node_positions_m_.push_back(position);
    }
    const auto node_count = result.active_nodes_.size();
    result.assembly_diagnostics_.active_node_count = node_count;
    result.assembly_diagnostics_.structural_rank_upper_bound =
        std::min(result.particles_.size(), node_count);
    result.assembly_diagnostics_.node_order_digest = node_digest(result.active_nodes_);
    result.lumped_mass_kg_.assign(node_count, 0.0);
    result.consistent_mass_rows_.resize(node_count);
    result.consistent_rhs_kg_m_per_s_.assign(node_count, {});
    result.particle_stencils_.reserve(result.particles_.size());
    result.particle_mass_kg_.reserve(result.particles_.size());

    for (std::size_t particle_index = 0;
         particle_index < result.particles_.size(); ++particle_index) {
        const auto& particle = result.particles_[particle_index];
        const auto mass = particle_mass_kg(particle, config);
        result.particle_mass_kg_.push_back(mass);
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
            result.lumped_mass_kg_[node] += weighted_mass;
            result.consistent_rhs_kg_m_per_s_[node] +=
                weighted_mass * particle.velocity_m_per_s;
        }
        result.assembly_diagnostics_.partition_unity_max_residual = std::max(
            result.assembly_diagnostics_.partition_unity_max_residual,
            std::abs(static_cast<double>(partition_sum - 1.0L)));
        result.assembly_diagnostics_.linear_reproduction_max_residual_m = std::max(
            result.assembly_diagnostics_.linear_reproduction_max_residual_m,
            norm(reproduced - particle.position_m));
        for (const auto& row_entry : stencil) {
            auto& row = result.consistent_mass_rows_[row_entry.node_index];
            for (const auto& column_entry : stencil) {
                auto& coefficient = row[column_entry.node_index];
                coefficient += mass * row_entry.weight * column_entry.weight;
                if (!std::isfinite(coefficient)) {
                    throw std::overflow_error("consistent mass assembly overflow");
                }
            }
        }
        result.particle_stencils_.push_back(std::move(stencil));
    }

    long double grid_mass = 0.0L;
    long double particle_mass = 0.0L;
    double maximum_matrix_entry = 0.0;
    double maximum_symmetry_difference = 0.0;
    double maximum_row_sum_difference = 0.0;
    for (std::size_t row = 0; row < node_count; ++row) {
        if (!(result.lumped_mass_kg_[row] > 0.0) ||
            !std::isfinite(result.lumped_mass_kg_[row])) {
            throw std::runtime_error("projection active node has invalid lumped mass");
        }
        grid_mass += result.lumped_mass_kg_[row];
        long double row_sum = 0.0L;
        for (const auto& [column, coefficient] : result.consistent_mass_rows_[row]) {
            if (coefficient != 0.0) {
                ++result.assembly_diagnostics_.matrix_nonzero_count;
            }
            maximum_matrix_entry = std::max(maximum_matrix_entry, std::abs(coefficient));
            row_sum += coefficient;
            const auto opposite = result.consistent_mass_rows_[column].find(row);
            if (opposite == result.consistent_mass_rows_[column].end()) {
                maximum_symmetry_difference = std::numeric_limits<double>::infinity();
            } else {
                maximum_symmetry_difference = std::max(
                    maximum_symmetry_difference,
                    std::abs(coefficient - opposite->second));
            }
        }
        maximum_row_sum_difference = std::max(
            maximum_row_sum_difference,
            std::abs(static_cast<double>(row_sum) - result.lumped_mass_kg_[row]));
    }
    for (const auto mass : result.particle_mass_kg_) {
        particle_mass += mass;
    }
    result.assembly_diagnostics_.matrix_symmetry_relative_residual =
        maximum_symmetry_difference / std::max(1.0, maximum_matrix_entry);
    result.assembly_diagnostics_.row_sum_relative_residual =
        maximum_row_sum_difference /
        std::max(1.0, *std::ranges::max_element(result.lumped_mass_kg_));
    result.assembly_diagnostics_.grid_mass_relative_error = symmetric_relative(
        static_cast<double>(grid_mass), static_cast<double>(particle_mass));
    result.assembly_diagnostics_.termination_reason = "assembled";
    return result;
}

std::vector<Vec3d> apply_consistent_mass(
    const ProjectionSystem& system,
    std::span<const Vec3d> grid_values) {
    if (grid_values.size() != system.active_nodes().size()) {
        throw std::invalid_argument("consistent mass vector has the wrong dimension");
    }
    std::vector<Vec3d> result(grid_values.size());
    for (std::size_t row = 0; row < system.consistent_mass_rows().size(); ++row) {
        Vec3d value{};
        for (const auto& [column, coefficient] : system.consistent_mass_rows()[row]) {
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
    if (grid_velocity_m_per_s.size() != system.active_nodes().size()) {
        throw std::invalid_argument("grid reconstruction vector has the wrong dimension");
    }
    std::vector<CenterParticle> result = system.particles();
    for (std::size_t particle = 0; particle < result.size(); ++particle) {
        Vec3d velocity{};
        for (const auto& entry : system.particle_stencils()[particle]) {
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
        policy.dense_jacobi_max_sweeps == 0U ||
        !std::isfinite(policy.dense_relative_pivot_min) ||
        !std::isfinite(policy.raw_condition_max) ||
        !std::isfinite(policy.preconditioned_condition_max) ||
        !std::isfinite(policy.normalized_residual_max)) {
        throw std::invalid_argument("projection solve policy is invalid");
    }
    ProjectionResult result{};
    result.candidate = candidate;
    result.diagnostics = system.assembly_diagnostics();
    result.particles = system.particles();
    if (system.particles().empty()) {
        result.status = ProjectionStatus::empty;
        result.diagnostics.termination_reason = "empty center state";
        return result;
    }

    try {
    result.center_kinetic_before_j = center_kinetic(system.particles(), system.config());
    result.center_kinetic_before_applicable = true;

    if (candidate == ProjectionCandidate::lumped_pic) {
        result.grid_velocity_m_per_s = lumped_velocity(system);
        result.status = ProjectionStatus::solved;
        result.diagnostics.termination_reason = "lumped direct solve";
    } else if (candidate != ProjectionCandidate::full_consistent) {
        result.grid_velocity_m_per_s = fmpm_velocity(
            system, fmpm_order(candidate), result.fmpm_residual_identity_normalized);
        result.fmpm_residual_identity_applicable = true;
        result.status = ProjectionStatus::solved;
        result.diagnostics.termination_reason = "revised 2026 FMPM recurrence";
    } else {
        const auto node_count = system.active_nodes().size();
        if (result.diagnostics.structural_rank_upper_bound < node_count) {
            result.status = ProjectionStatus::structurally_rank_deficient;
            result.diagnostics.numerical_rank_estimate =
                result.diagnostics.structural_rank_upper_bound;
            result.diagnostics.numerical_rank_method = "rank(M)<=min(P,n)";
            result.diagnostics.rank_certified = true;
            result.diagnostics.numerical_rank_is_estimated = false;
            result.diagnostics.termination_reason =
                "active nodes exceed the particle rank upper bound";
            return result;
        }

        SpectralDiagnostic raw{};
        SpectralDiagnostic preconditioned{};
        if (node_count <= policy.dense_diagnostic_max_nodes) {
            raw = dense_cholesky_diagnostic(
                system,
                false,
                policy.dense_relative_pivot_min,
                policy.dense_jacobi_max_sweeps);
            preconditioned = dense_cholesky_diagnostic(
                system,
                true,
                policy.dense_relative_pivot_min,
                policy.dense_jacobi_max_sweeps);
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
                            std::sqrt(system.lumped_mass_kg()[index]);
                    }
                    auto applied = apply_scalar_mass(system, scaled);
                    for (std::size_t index = 0; index < values.size(); ++index) {
                        applied[index] /= std::sqrt(system.lumped_mass_kg()[index]);
                    }
                    return applied;
                },
                "deterministic Lanczos Ritz estimate of D^-1/2 M D^-1/2");
        }
        const auto rank_is_estimated = raw.estimated || preconditioned.estimated;
        result.diagnostics.numerical_rank_estimate = rank_is_estimated
            ? 0U
            : std::min(raw.rank, preconditioned.rank);
        result.diagnostics.numerical_rank_method = raw.method + "; " + preconditioned.method;
        result.diagnostics.numerical_rank_is_estimated = rank_is_estimated;
        result.diagnostics.rank_certified = !rank_is_estimated;
        result.diagnostics.condition_estimated = true;
        result.diagnostics.smallest_spectral_or_pivot_value = raw.smallest;
        result.diagnostics.largest_spectral_or_pivot_value = raw.largest;
        result.diagnostics.raw_condition_estimate = raw.condition;
        result.diagnostics.preconditioned_condition_estimate = preconditioned.condition;
        if (!raw.resolved || !preconditioned.resolved) {
            result.status = ProjectionStatus::breakdown;
            result.diagnostics.termination_reason =
                "symmetric eigen/condition diagnostic did not converge; rank and condition unresolved";
            return result;
        }
        if (!rank_is_estimated &&
            (raw.rank < node_count || preconditioned.rank < node_count ||
             !(raw.smallest > 0.0) || !(preconditioned.smallest > 0.0))) {
            result.status = ProjectionStatus::numerically_rank_deficient;
            result.diagnostics.termination_reason = "rank diagnostic failed";
            return result;
        }
        if (!(raw.smallest > 0.0) || !(preconditioned.smallest > 0.0) ||
            !std::isfinite(raw.condition) || !std::isfinite(preconditioned.condition) ||
            raw.condition > policy.raw_condition_max ||
            preconditioned.condition > policy.preconditioned_condition_max) {
            result.status = ProjectionStatus::ill_conditioned;
            result.diagnostics.termination_reason = rank_is_estimated
                ? "estimated Ritz condition evidence failed or exceeded threshold; rank unknown"
                : "condition threshold exceeded";
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
                    system.consistent_rhs_kg_m_per_s()[index], component);
            }
            const auto solved = solve_pcg(
                system, rhs, iteration_limit, policy.normalized_residual_max);
            result.diagnostics.component_iterations[component] = solved.iterations;
            result.diagnostics.solve_residual_applicable[component] = true;
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
        result.status = ProjectionStatus::solved;
        result.diagnostics.termination_reason = "unregularized PCG solved";
    }

    record_consistent_system_residual(
        system, result.grid_velocity_m_per_s, result.diagnostics);
    if (candidate == ProjectionCandidate::full_consistent) {
        for (const auto residual : result.diagnostics.normalized_solve_residual) {
            if (!(residual <= policy.normalized_residual_max)) {
                result.status = ProjectionStatus::residual_failed;
                result.grid_velocity_m_per_s.clear();
                result.diagnostics.termination_reason =
                    "recomputed full-system residual exceeds threshold";
                return result;
            }
        }
    }
    result.particles = reconstruct_centers(system, result.grid_velocity_m_per_s);
    result.diagnostics.exact_mass_quanta_after = exact_mass(result.particles);
    result.center_kinetic_after_j = center_kinetic(result.particles, system.config());
    result.center_kinetic_after_applicable = true;
    long double grid_energy = 0.0L;
    for (std::size_t index = 0; index < result.grid_velocity_m_per_s.size(); ++index) {
        grid_energy += 0.5L * static_cast<long double>(
            dot(result.grid_velocity_m_per_s[index],
                system.consistent_rhs_kg_m_per_s()[index]));
    }
    result.consistent_grid_quadratic_energy_j = static_cast<double>(grid_energy);
    if (!std::isfinite(result.consistent_grid_quadratic_energy_j)) {
        throw std::overflow_error("consistent grid energy diagnostic overflow");
    }
    result.consistent_grid_quadratic_energy_applicable = true;
    result.numerical_projection_energy_residual_j =
        result.center_kinetic_after_j - result.center_kinetic_before_j;
    if (!std::isfinite(result.numerical_projection_energy_residual_j)) {
        throw std::overflow_error("projection energy residual overflow");
    }
    result.numerical_projection_energy_residual_applicable = true;
    return result;
    } catch (const std::overflow_error& error) {
        result.status = ProjectionStatus::numerical_overflow;
        result.particles = system.particles();
        result.grid_velocity_m_per_s.clear();
        result.diagnostics.exact_mass_quanta_after =
            result.diagnostics.exact_mass_quanta_before;
        result.diagnostics.solve_residual_applicable = {};
        result.diagnostics.absolute_solve_residual.fill(
            std::numeric_limits<double>::quiet_NaN());
        result.diagnostics.normalized_solve_residual.fill(
            std::numeric_limits<double>::quiet_NaN());
        result.diagnostics.termination_reason =
            std::string("numerical overflow: ") + error.what();
        result.center_kinetic_before_applicable = false;
        result.center_kinetic_after_applicable = false;
        result.consistent_grid_quadratic_energy_applicable = false;
        result.consistent_grid_quadratic_energy_j =
            std::numeric_limits<double>::quiet_NaN();
        result.numerical_projection_energy_residual_applicable = false;
        result.numerical_projection_energy_residual_j =
            std::numeric_limits<double>::quiet_NaN();
        result.fmpm_residual_identity_applicable = false;
        result.fmpm_residual_identity_normalized =
            std::numeric_limits<double>::quiet_NaN();
        return result;
    }
}

ProjectionResult project_centers(
    std::span<const CenterParticle> particles,
    const TransferConfig& config,
    ProjectionCandidate candidate,
    const ProjectionSolvePolicy& policy) {
    validate_config(config);
    // Validate exact input contracts before classifying any later binary64
    // failure as a numerical-overflow result.
    const auto canonical = canonical_centers(particles);
    const auto total_mass = exact_mass(canonical);
    try {
        auto result = project_centers(
            build_projection_system(canonical, config), candidate, policy);
        if (!successful(result.status)) {
            result.particles.assign(particles.begin(), particles.end());
        }
        return result;
    } catch (const std::overflow_error& error) {
        ProjectionResult result{};
        result.candidate = candidate;
        result.status = ProjectionStatus::numerical_overflow;
        result.particles.assign(particles.begin(), particles.end());
        result.diagnostics.particle_count = particles.size();
        result.diagnostics.exact_mass_quanta_before = total_mass;
        result.diagnostics.exact_mass_quanta_after = total_mass;
        result.diagnostics.termination_reason =
            std::string("numerical overflow while assembling projection: ") + error.what();
        return result;
    }
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
    result.projection = project_centers(
        state.particles, state.config, candidate, policy);
    if (!successful(result.projection.status)) {
        return result;
    }
    const auto canonical_before = canonical_centers(state.particles);
    if (timestep_quanta >
        std::numeric_limits<std::uint64_t>::max() - state.elapsed_time_quanta) {
        result.projection.status = ProjectionStatus::numerical_overflow;
        result.projection.particles.assign(state.particles.begin(), state.particles.end());
        result.projection.grid_velocity_m_per_s.clear();
        result.projection.diagnostics.termination_reason =
            "numerical overflow: exact projection clock overflow";
        return result;
    }
    result.state.particles = result.projection.particles;
    for (std::size_t index = 0; index < result.state.particles.size(); ++index) {
        const auto displacement = 0.5 * timestep_s *
            (canonical_before[index].velocity_m_per_s +
             result.projection.particles[index].velocity_m_per_s);
        result.state.particles[index].position_m += displacement;
        result.state.particles[index].velocity_m_per_s =
            result.projection.particles[index].velocity_m_per_s;
        if (!finite(result.state.particles[index].position_m)) {
            result.state = state;
            result.projection.status = ProjectionStatus::numerical_overflow;
            result.projection.particles.assign(state.particles.begin(), state.particles.end());
            result.projection.grid_velocity_m_per_s.clear();
            result.projection.diagnostics.termination_reason =
                "numerical overflow: projection trapezoid position overflow";
            return result;
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
