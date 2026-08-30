#include "test_harness.hpp"

#include "mls/relational_observability_confirmation.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace {

namespace confirmation =
    mls::experimental::relational_observability_confirmation;
namespace observation = mls::experimental::mechanical_observability;
using observation::BondRelation;
using observation::MechanicalPacket;

[[nodiscard]] std::vector<MechanicalPacket> tetrahedron() {
    return {
        {1, 1, {0.0, 0.0, 0.0}, {}},
        {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}},
        {4, 1, {0.0, 0.0, 1.0}, {}},
    };
}

[[nodiscard]] std::vector<BondRelation> k4() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
}

} // namespace

MLS_TEST("relational confirmation raw K4 spectrum has exactly rigid kernel") {
    const auto result = confirmation::analyze_raw_central_rigidity(
        tetrahedron(), k4());
    MLS_REQUIRE_EQ(result.status, observation::RankStatus::analyzed);
    MLS_REQUIRE(result.row_norms_pass);
    MLS_REQUIRE(result.rank_paths_agree);
    MLS_REQUIRE_EQ(result.cpqr_rank, std::size_t{6});
    MLS_REQUIRE_EQ(result.svd_rank, std::size_t{6});
    MLS_REQUIRE_EQ(result.modular_rank_value, std::size_t{6});
    MLS_REQUIRE_EQ(result.nullity, std::size_t{6});
    MLS_REQUIRE_EQ(result.realized_rigid_rank, std::size_t{6});
    MLS_REQUIRE_EQ(result.nonrigid_nullity, std::size_t{0});
    MLS_REQUIRE(result.kernel_equals_rigid_subspace);
    MLS_REQUIRE_EQ(result.spectrum.size(), std::size_t{12});
    MLS_REQUIRE_EQ(result.null_modes.size(), std::size_t{6});
    MLS_REQUIRE_EQ(result.cpqr.nullspace_basis.row_count(), std::size_t{12});
    MLS_REQUIRE_EQ(result.cpqr.nullspace_basis.column_count(), std::size_t{6});
    MLS_REQUIRE(result.all_null_modes_accepted);
    MLS_REQUIRE(result.maximum_row_norm_relative_error <=
                result.row_norm_tolerance);
}

MLS_TEST("relational confirmation preserves resolved K4-minus-edge floppy mode") {
    auto relations = k4();
    relations.pop_back();
    const auto result = confirmation::analyze_raw_central_rigidity(
        tetrahedron(), relations);
    MLS_REQUIRE_EQ(result.status, observation::RankStatus::analyzed);
    MLS_REQUIRE_EQ(result.modular_rank_value, std::size_t{5});
    MLS_REQUIRE_EQ(result.nullity, std::size_t{7});
    MLS_REQUIRE_EQ(result.realized_rigid_rank, std::size_t{6});
    MLS_REQUIRE_EQ(result.nonrigid_nullity, std::size_t{1});
    MLS_REQUIRE(!result.kernel_equals_rigid_subspace);
    MLS_REQUIRE_EQ(result.spectrum.size(), std::size_t{12});
    MLS_REQUIRE_EQ(result.cpqr.nullspace_basis.row_count(), std::size_t{12});
    MLS_REQUIRE_EQ(result.cpqr.nullspace_basis.column_count(), std::size_t{7});
    MLS_REQUIRE(std::count_if(
        result.spectrum.begin(), result.spectrum.end(), [](const auto& entry) {
            return entry.classification ==
                confirmation::SingularClassification::resolved_zero;
        }) == 7);
}

MLS_TEST("relational confirmation exact rank and spectrum ignore packet labels") {
    const auto base_packets = tetrahedron();
    const auto base_relations = k4();
    auto renamed_packets = base_packets;
    const std::array<std::uint64_t, 4> labels{40, 10, 30, 20};
    for (std::size_t index = 0; index < renamed_packets.size(); ++index) {
        renamed_packets[index].id = labels[index];
    }
    std::vector<BondRelation> renamed_relations;
    for (const auto relation : base_relations) {
        auto first = labels[static_cast<std::size_t>(relation.first_id - 1U)];
        auto second = labels[static_cast<std::size_t>(relation.second_id - 1U)];
        if (second < first) {
            std::swap(first, second);
        }
        renamed_relations.push_back({first, second});
    }
    std::ranges::sort(renamed_relations, [](const auto& lhs, const auto& rhs) {
        return std::pair(lhs.first_id, lhs.second_id) <
            std::pair(rhs.first_id, rhs.second_id);
    });
    const auto base = confirmation::analyze_raw_central_rigidity(
        base_packets, base_relations);
    const auto renamed = confirmation::analyze_raw_central_rigidity(
        renamed_packets, renamed_relations);
    MLS_REQUIRE_EQ(base.modular_rank_value, renamed.modular_rank_value);
    MLS_REQUIRE_EQ(base.nonrigid_nullity, renamed.nonrigid_nullity);
    MLS_REQUIRE(confirmation::normalized_spectrum_difference(
                    renamed.spectrum, base.spectrum) < 2.0e-15);
}

MLS_TEST("relational confirmation exact modular rank handles dyadic jitter") {
    auto packets = tetrahedron();
    packets[0].position_m.x += std::ldexp(1.0, -30);
    packets[1].position_m.y -= std::ldexp(3.0, -31);
    packets[2].position_m.z += std::ldexp(5.0, -29);
    const auto modular = confirmation::three_prime_modular_rigidity_rank(
        packets, k4());
    MLS_REQUIRE(modular.unanimous);
    MLS_REQUIRE_EQ(modular.ranks.size(), std::size_t{3});
    MLS_REQUIRE_EQ(modular.rank, std::size_t{6});
}
