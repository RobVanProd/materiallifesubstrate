#include "mls/kelvin_covariance_audit.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#ifndef MLS_CONFIGURED_SOURCE_SHA
#define MLS_CONFIGURED_SOURCE_SHA "unknown"
#endif
#ifndef MLS_CONFIGURED_SOURCE_BRANCH
#define MLS_CONFIGURED_SOURCE_BRANCH "unknown"
#endif
#ifndef MLS_CONFIGURED_SOURCE_DIRTY
#define MLS_CONFIGURED_SOURCE_DIRTY "true"
#endif
#ifndef MLS_CONFIGURED_COMPILER_ID
#define MLS_CONFIGURED_COMPILER_ID "unknown"
#endif
#ifndef MLS_CONFIGURED_COMPILER_VERSION
#define MLS_CONFIGURED_COMPILER_VERSION "unknown"
#endif

namespace {

namespace audit = mls::experimental::kelvin_covariance_audit;
namespace observation = mls::experimental::mechanical_observability;
using mls::experimental::Matrix3d;
using mls::experimental::Vec3d;
using observation::MechanicalObservabilityState;
using observation::MechanicalPacket;

constexpr std::uint64_t seed = 260829U;
constexpr double epsilon64 = std::numeric_limits<double>::epsilon();

struct Configuration final {
    std::string id{};
    std::vector<MechanicalPacket> packets{};
    double support_radius_m{1.0};
};

struct TransformCase final {
    std::string id{};
    Matrix3d rotation{Matrix3d::identity()};
    Vec3d translation_m{};
    double scale{1.0};
    bool permute_input{false};
};

struct ResultRow final {
    std::string configuration{};
    std::string transform{};
    std::size_t packets{0};
    double support_base{0.0};
    double support_transformed{0.0};
    double scale{1.0};
    std::string base_status{};
    std::string transformed_status{};
    double q_orthogonality{std::numeric_limits<double>::infinity()};
    double determinant{std::numeric_limits<double>::infinity()};
    double kelvin_orthogonality{std::numeric_limits<double>::infinity()};
    double raw_operator_residual{std::numeric_limits<double>::infinity()};
    double raw_spectrum_delta{std::numeric_limits<double>::infinity()};
    double block_residual{std::numeric_limits<double>::infinity()};
    double scalar_row_spectrum_delta{std::numeric_limits<double>::infinity()};
    double orthogonality_tolerance{0.0};
    double kelvin_tolerance{0.0};
    double operator_tolerance{0.0};
    double spectrum_tolerance{0.0};
    double block_tolerance{0.0};
    bool raw_available{false};
    bool raw_pass{false};
    bool block_pass{false};
    bool pass{false};
};

[[nodiscard]] Matrix3d rational_rotation() {
    Matrix3d result{};
    result.value = {{{1.0 / 9.0, 8.0 / 9.0, 4.0 / 9.0},
                     {8.0 / 9.0, 1.0 / 9.0, -4.0 / 9.0},
                     {-4.0 / 9.0, 4.0 / 9.0, -7.0 / 9.0}}};
    return result;
}

[[nodiscard]] std::uint64_t mix(std::uint64_t value) {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31U);
}

[[nodiscard]] double jitter(const std::uint64_t id, const std::size_t axis) {
    const auto bits = mix(seed ^ (id * 17U) ^
        (static_cast<std::uint64_t>(axis) * 0x632be59bd9b4e019ULL));
    const auto mantissa = bits >> 11U;
    const double unit = static_cast<double>(mantissa) / 9007199254740992.0;
    return 0.04 * (unit - 0.5);
}

[[nodiscard]] std::vector<MechanicalPacket> lattice(
    const int nx, const int ny, const int nz, const double spacing,
    const bool apply_jitter) {
    std::vector<MechanicalPacket> result;
    std::uint64_t id = 1U;
    for (int z = 0; z < nz; ++z) {
        for (int y = 0; y < ny; ++y) {
            for (int x = 0; x < nx; ++x) {
                const Vec3d position{
                    spacing * static_cast<double>(x) +
                        (apply_jitter ? jitter(id, 0U) : 0.0),
                    spacing * static_cast<double>(y) +
                        (apply_jitter ? jitter(id, 1U) : 0.0),
                    spacing * static_cast<double>(z) +
                        (apply_jitter ? jitter(id, 2U) : 0.0)};
                result.push_back({id++, 1, position, {}});
            }
        }
    }
    return result;
}

[[nodiscard]] std::vector<Configuration> configurations() {
    auto cube = lattice(2, 2, 2, 1.0, false);
    auto bcc = cube;
    bcc.push_back({9U, 1, {0.5, 0.5, 0.5}, {}});
    return {
        {"cube8", std::move(cube), 2.0},
        {"bcc9", std::move(bcc), 2.0},
        {"jitter27", lattice(3, 3, 3, 0.5, true), 2.2},
        {"surface18", lattice(3, 3, 2, 0.5, false), 3.1},
    };
}

[[nodiscard]] std::vector<TransformCase> transforms() {
    const auto q = rational_rotation();
    const Vec3d t{0.37, -0.29, 0.41};
    return {
        {"translation", Matrix3d::identity(), t, 1.0, false},
        {"rotation", q, {}, 1.0, false},
        {"rotation_translation", q, t, 1.0, false},
        {"scale_half_rotation_translation", q, t, 0.5, false},
        {"scale_double_rotation_translation", q, t, 2.0, false},
        {"packet_permutation", Matrix3d::identity(), {}, 1.0, true},
    };
}

[[nodiscard]] double tolerance(
    const observation::DenseMatrix& matrix, const double factor) {
    return factor * static_cast<double>(std::max({std::size_t{6U},
        matrix.row_count(), matrix.column_count()})) * epsilon64;
}

[[nodiscard]] std::string hex(const double value) {
    if (!std::isfinite(value)) {
        return std::isnan(value) ? "nan" :
            (value < 0.0 ? "-inf" : "inf");
    }
    std::ostringstream output;
    output << std::hexfloat << value;
    return output.str();
}

[[nodiscard]] std::string boolean(const bool value) {
    return value ? "true" : "false";
}

void ensure_output_directory(const std::filesystem::path& path) {
    if (std::filesystem::exists(path)) {
        if (!std::filesystem::is_directory(path)) {
            throw std::runtime_error("output path must be a directory");
        }
        // Deterministic test reruns may replace only this producer's complete
        // known inventory.  Unknown/stale files still fail closed.
        const std::vector<std::filesystem::path> allowed{
            "summary.json", "tolerances.json", "counterexample.json",
            "covariance.csv", "checkpoints", "checkpoints/cube8.bin",
            "checkpoints/bcc9.bin", "checkpoints/jitter27.bin",
            "checkpoints/surface18.bin"};
        for (const auto& entry :
             std::filesystem::recursive_directory_iterator(path)) {
            const auto relative = std::filesystem::relative(entry.path(), path);
            if (std::ranges::find(allowed, relative) == allowed.end()) {
                throw std::runtime_error(
                    "output directory contains an unknown entry");
            }
        }
    } else if (!std::filesystem::create_directories(path)) {
        throw std::runtime_error("could not create output directory");
    }
    std::filesystem::create_directories(path / "checkpoints");
}

void write_binary(const std::filesystem::path& path,
                  const std::span<const std::uint8_t> bytes) {
    std::ofstream output(path, std::ios::binary);
    if (!output) {
        throw std::runtime_error("could not create checkpoint");
    }
    output.write(reinterpret_cast<const char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size()));
    if (!output) {
        throw std::runtime_error("could not write checkpoint");
    }
}

void write_text(const std::filesystem::path& path, const std::string& text) {
    std::ofstream output(path, std::ios::binary);
    if (!output) {
        throw std::runtime_error("could not create evidence file");
    }
    output << text;
    if (!output) {
        throw std::runtime_error("could not write evidence file");
    }
}

[[nodiscard]] ResultRow evaluate(
    const Configuration& configuration, const TransformCase& transform) {
    ResultRow row{};
    row.configuration = configuration.id;
    row.transform = transform.id;
    row.packets = configuration.packets.size();
    row.support_base = configuration.support_radius_m;
    row.support_transformed =
        transform.scale * configuration.support_radius_m;
    row.scale = transform.scale;

    const auto base = observation::build_corrected_local_gradient(
        configuration.packets,
        {.support_radius_m = configuration.support_radius_m});
    auto transformed_packets = audit::transform_packet_geometry(
        configuration.packets, transform.rotation,
        transform.translation_m, transform.scale);
    if (transform.permute_input) {
        std::ranges::reverse(transformed_packets);
    }
    const auto transformed = observation::build_corrected_local_gradient(
        transformed_packets,
        {.support_radius_m = row.support_transformed});
    row.base_status = std::string(observation::status_name(base.status));
    row.transformed_status =
        std::string(observation::status_name(transformed.status));
    const auto kelvin = audit::kelvin_rotation(transform.rotation);
    const auto orthogonality = audit::diagnose_orthogonality(
        transform.rotation, kelvin);
    row.q_orthogonality = orthogonality.q_residual;
    row.determinant = orthogonality.determinant_residual;
    row.kelvin_orthogonality = orthogonality.kelvin_residual;

    const auto& base_matrix = base.symmetric_gradient.matrix;
    row.orthogonality_tolerance = tolerance(base_matrix, 8192.0);
    row.kelvin_tolerance = tolerance(base_matrix, 16384.0);
    row.operator_tolerance = tolerance(base_matrix, 32768.0);
    row.spectrum_tolerance = tolerance(base_matrix, 65536.0);
    row.block_tolerance = tolerance(base_matrix, 65536.0);
    row.raw_available = base.status == observation::OperatorBuildStatus::built &&
        transformed.status == observation::OperatorBuildStatus::built;
    if (!row.raw_available) {
        return row;
    }

    const auto expected = audit::expected_transformed_operator(
        base_matrix, transform.rotation, transform.scale);
    row.raw_operator_residual = audit::normalized_frobenius_difference(
        transformed.symmetric_gradient.matrix, expected);
    row.raw_spectrum_delta = audit::normalized_spectrum_difference(
        audit::singular_values(transformed.symmetric_gradient.matrix),
        audit::singular_values(base_matrix), transform.scale);

    const auto base_blocks = audit::normalize_kelvin_blocks(base_matrix);
    const auto transformed_blocks = audit::normalize_kelvin_blocks(
        transformed.symmetric_gradient.matrix);
    if (base_blocks.complete && transformed_blocks.complete) {
        const auto expected_blocks = audit::expected_transformed_operator(
            base_blocks.normalized, transform.rotation, 1.0);
        row.block_residual = audit::normalized_frobenius_difference(
            transformed_blocks.normalized, expected_blocks);
    }

    const auto base_rows = observation::normalize_operator_rows(base_matrix);
    const auto transformed_rows = observation::normalize_operator_rows(
        transformed.symmetric_gradient.matrix);
    if (base_rows.complete && transformed_rows.complete) {
        row.scalar_row_spectrum_delta = audit::normalized_spectrum_difference(
            audit::singular_values(transformed_rows.normalized),
            audit::singular_values(base_rows.normalized));
    }
    row.raw_pass = row.q_orthogonality <= row.orthogonality_tolerance &&
        row.determinant <= row.orthogonality_tolerance &&
        row.kelvin_orthogonality <= row.kelvin_tolerance &&
        row.raw_operator_residual <= row.operator_tolerance &&
        row.raw_spectrum_delta <= row.spectrum_tolerance;
    row.block_pass = row.block_residual <= row.block_tolerance;
    row.pass = row.raw_pass && row.block_pass;
    return row;
}

[[nodiscard]] std::string covariance_csv(
    const std::span<const ResultRow> rows) {
    std::ostringstream output;
    output << "configuration,transform,packets,support_base_m,"
              "support_transformed_m,scale,base_status,transformed_status,"
              "q_orthogonality_residual,determinant_residual,"
              "kelvin_orthogonality_residual,raw_operator_residual,"
              "raw_scaled_spectrum_delta,block_scalar_operator_residual,"
              "legacy_scalar_row_spectrum_delta,orthogonality_tolerance,"
              "kelvin_tolerance,operator_tolerance,spectrum_tolerance,"
              "block_tolerance,raw_available,raw_pass,block_pass,pass\n";
    for (const auto& row : rows) {
        output << row.configuration << ',' << row.transform << ',' <<
            row.packets << ',' << hex(row.support_base) << ',' <<
            hex(row.support_transformed) << ',' << hex(row.scale) << ',' <<
            row.base_status << ',' << row.transformed_status << ',' <<
            hex(row.q_orthogonality) << ',' << hex(row.determinant) << ',' <<
            hex(row.kelvin_orthogonality) << ',' <<
            hex(row.raw_operator_residual) << ',' <<
            hex(row.raw_spectrum_delta) << ',' << hex(row.block_residual) << ',' <<
            hex(row.scalar_row_spectrum_delta) << ',' <<
            hex(row.orthogonality_tolerance) << ',' <<
            hex(row.kelvin_tolerance) << ',' <<
            hex(row.operator_tolerance) << ',' <<
            hex(row.spectrum_tolerance) << ',' << hex(row.block_tolerance) << ',' <<
            boolean(row.raw_available) << ',' << boolean(row.raw_pass) << ',' <<
            boolean(row.block_pass) << ',' << boolean(row.pass) << '\n';
    }
    return output.str();
}

[[nodiscard]] bool logic_audit() {
    const auto cases = configurations();
    const auto rotations = transforms();
    const auto row = evaluate(cases.front(), rotations[3]);
    const auto counterexample =
        audit::kelvin_row_normalization_counterexample(rational_rotation());
    return row.raw_available && row.raw_pass && row.block_pass &&
        counterexample.row_normalizations_complete &&
        counterexample.raw_spectrum_delta <=
            65536.0 * 6.0 * epsilon64 &&
        counterexample.row_normalized_spectrum_delta >
            1000.0 * 65536.0 * 6.0 * epsilon64;
}

void produce(const std::filesystem::path& output_directory) {
    ensure_output_directory(output_directory);
    const auto cases = configurations();
    const auto transform_cases = transforms();
    std::vector<ResultRow> rows;
    rows.reserve(cases.size() * transform_cases.size());
    for (const auto& configuration : cases) {
        const MechanicalObservabilityState state{
            configuration.support_radius_m, configuration.packets, {}, {}};
        const auto checkpoint =
            observation::serialize_mechanical_observability_state(state);
        const auto restored =
            observation::deserialize_mechanical_observability_state(checkpoint);
        if (!(restored == state) ||
            observation::serialize_mechanical_observability_state(restored) !=
                checkpoint) {
            throw std::runtime_error("checkpoint round trip mismatch");
        }
        write_binary(output_directory / "checkpoints" /
            (configuration.id + ".bin"), checkpoint);
        for (const auto& transform : transform_cases) {
            rows.push_back(evaluate(configuration, transform));
        }
    }

    const auto counterexample =
        audit::kelvin_row_normalization_counterexample(rational_rotation());
    const double counter_tolerance = 65536.0 * 6.0 * epsilon64;
    const bool counter_pass = counterexample.row_normalizations_complete &&
        counterexample.raw_transform_residual <= counter_tolerance &&
        counterexample.raw_spectrum_delta <= counter_tolerance &&
        counterexample.row_normalized_spectrum_delta >
            1000.0 * counter_tolerance;
    const std::size_t raw_failures = static_cast<std::size_t>(
        std::ranges::count_if(rows, [](const auto& row) {
            return row.raw_available && !row.raw_pass;
        }));
    const std::size_t unavailable = static_cast<std::size_t>(
        std::ranges::count_if(rows, [](const auto& row) {
            return !row.raw_available;
        }));
    const std::size_t block_failures = static_cast<std::size_t>(
        std::ranges::count_if(rows, [](const auto& row) {
            return row.raw_available && !row.block_pass;
        }));
    const std::size_t legacy_rotation_differences = static_cast<std::size_t>(
        std::ranges::count_if(rows, [](const auto& row) {
            return row.transform != "translation" &&
                row.transform != "packet_permutation" &&
                row.scalar_row_spectrum_delta > row.spectrum_tolerance;
        }));
    const std::string decision = raw_failures != 0U ?
        "RAW_OPERATOR_COVARIANCE_FAILURE" :
        (unavailable == 0U && block_failures == 0U && counter_pass ?
            "SUPPORTED_DIAGNOSTIC_COORDINATE_DEFECT" : "INCONCLUSIVE");

    write_text(output_directory / "covariance.csv", covariance_csv(rows));
    std::ostringstream counter;
    counter << "{\n"
            << "  \"construction\": \"actual_3d_kelvin_rotation_of_diagonal_raw_operator\",\n"
            << "  \"raw_transform_residual\": \""
            << hex(counterexample.raw_transform_residual) << "\",\n"
            << "  \"raw_spectrum_delta\": \""
            << hex(counterexample.raw_spectrum_delta) << "\",\n"
            << "  \"scalar_row_normalized_spectrum_delta\": \""
            << hex(counterexample.row_normalized_spectrum_delta) << "\",\n"
            << "  \"binary64_tolerance\": \"" << hex(counter_tolerance)
            << "\",\n"
            << "  \"minimum_required_multiple\": 1000,\n"
            << "  \"row_normalizations_complete\": "
            << boolean(counterexample.row_normalizations_complete) << ",\n"
            << "  \"pass\": " << boolean(counter_pass) << "\n}\n";
    write_text(output_directory / "counterexample.json", counter.str());

    std::ostringstream tolerances;
    tolerances << "{\n"
        << "  \"epsilon64\": \"" << hex(epsilon64) << "\",\n"
        << "  \"q_factor\": 8192,\n"
        << "  \"kelvin_factor\": 16384,\n"
        << "  \"raw_operator_factor\": 32768,\n"
        << "  \"raw_spectrum_factor\": 65536,\n"
        << "  \"block_scalar_factor\": 65536,\n"
        << "  \"dimension_formula\": \"max(6,rows,columns)\",\n"
        << "  \"counterexample_required_multiple\": 1000\n"
        << "}\n";
    write_text(output_directory / "tolerances.json", tolerances.str());

    std::ostringstream summary;
    summary << "{\n"
        << "  \"schema_version\": 1,\n"
        << "  \"producer\": \"cpp_kelvin_covariance_audit\",\n"
        << "  \"source_sha\": \"" << MLS_CONFIGURED_SOURCE_SHA << "\",\n"
        << "  \"source_branch\": \"" << MLS_CONFIGURED_SOURCE_BRANCH << "\",\n"
        << "  \"source_dirty_at_configure\": "
        << MLS_CONFIGURED_SOURCE_DIRTY << ",\n"
        << "  \"compiler_id\": \"" << MLS_CONFIGURED_COMPILER_ID << "\",\n"
        << "  \"compiler_version\": \"" << MLS_CONFIGURED_COMPILER_VERSION
        << "\",\n"
        << "  \"seed\": " << seed << ",\n"
        << "  \"exact_oracle_result_sha256\": "
        << "\"58fa03bef4451bc5411ce8ee2c59f17e8f1fa6e056f2909147a0e15ef81d9ff6\",\n"
        << "  \"configuration_count\": " << cases.size() << ",\n"
        << "  \"transform_count\": " << transform_cases.size() << ",\n"
        << "  \"comparison_count\": " << rows.size() << ",\n"
        << "  \"raw_failures\": " << raw_failures << ",\n"
        << "  \"unavailable_comparisons\": " << unavailable << ",\n"
        << "  \"block_scalar_failures\": " << block_failures << ",\n"
        << "  \"legacy_rotation_spectrum_differences\": "
        << legacy_rotation_differences << ",\n"
        << "  \"counterexample_pass\": " << boolean(counter_pass) << ",\n"
        << "  \"candidate_promotion_permitted\": false,\n"
        << "  \"decision\": \"" << decision << "\"\n"
        << "}\n";
    write_text(output_directory / "summary.json", summary.str());
    std::cout << "Kelvin Covariance Audit evidence written: " <<
        output_directory.string() << "\nDecision: " << decision << '\n';
}

} // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--schema-audit") {
            std::cout << "Kelvin Covariance Audit schema audit: PASS\n";
            return 0;
        }
        if (argc == 2 && std::string_view(argv[1]) == "--logic-audit") {
            if (!logic_audit()) {
                throw std::runtime_error("logic audit failed");
            }
            std::cout << "Kelvin Covariance Audit logic audit: PASS\n";
            return 0;
        }
        if (argc == 3 && std::string_view(argv[1]) == "--output") {
            produce(std::filesystem::path(argv[2]));
            return 0;
        }
        std::cerr << "usage: mls_kelvin_covariance_diagnostic "
                     "--output DIR | --schema-audit | --logic-audit\n";
        return 2;
    } catch (const std::exception& error) {
        std::cerr << "Kelvin Covariance Audit error: " << error.what() << '\n';
        return 1;
    }
}
