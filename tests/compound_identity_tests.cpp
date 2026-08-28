#include "mls/chemistry.hpp"

#include "test_harness.hpp"

#include <cstddef>
#include <stdexcept>
#include <utility>
#include <vector>

MLS_TEST("hard-contract/compound_identity_is_invariant_under_site_renumbering") {
    const mls::ElementId a{2};
    const mls::ElementId b{7};
    const mls::ElementId c{11};

    const mls::CompoundGraph first(
        std::vector<mls::ElementId>{a, b, a, c},
        std::vector<mls::Bond>{{0, 1, 1}, {1, 2, 2}, {2, 3, 1}, {0, 3, 3}});
    // The same labeled graph under old->new site mapping 0->2, 1->0,
    // 2->3, 3->1, with deliberately shuffled/reversed bond encodings.
    const mls::CompoundGraph renumbered(
        std::vector<mls::ElementId>{b, c, a, a},
        std::vector<mls::Bond>{{1, 3, 1}, {3, 0, 2}, {1, 2, 3}, {0, 2, 1}});

    MLS_REQUIRE_EQ(first, renumbered);
    MLS_REQUIRE_EQ(first.structural_hash(), renumbered.structural_hash());

    mls::CompoundRegistry registry;
    const auto first_id = registry.intern(first);
    const auto second_id = registry.intern(renumbered);
    MLS_REQUIRE_EQ(first_id, second_id);
    MLS_REQUIRE_EQ(registry.compounds().size(), std::size_t{1});
}

MLS_TEST("hard-contract/compound_identity_rejects_disconnected_molecular_graph") {
    const mls::ElementId a{2};
    const mls::ElementId b{7};
    const mls::ElementId c{11};

    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::CompoundGraph(
            std::vector<mls::ElementId>{a, b, c},
            std::vector<mls::Bond>{{0, 1, 1}}));
}

MLS_TEST("hard-contract/compound_identity_rejects_parallel_bond_encodings") {
    const mls::ElementId a{2};
    const mls::ElementId b{7};

    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::CompoundGraph(
            std::vector<mls::ElementId>{a, b},
            std::vector<mls::Bond>{{0, 1, 1}, {1, 0, 2}}));
}

MLS_TEST("hard-contract/compound_canonicalization_has_an_explicit_size_bound") {
    const mls::ElementId a{2};
    std::vector<mls::ElementId> atoms(mls::max_compound_atom_sites + 1U, a);
    std::vector<mls::Bond> bonds;
    bonds.reserve(mls::max_compound_atom_sites);
    for (std::size_t site = 1; site < atoms.size(); ++site) {
        bonds.push_back(mls::Bond{
            static_cast<std::uint32_t>(site - 1U),
            static_cast<std::uint32_t>(site),
            1,
        });
    }

    MLS_REQUIRE_THROWS(
        std::length_error, mls::CompoundGraph(std::move(atoms), std::move(bonds)));
}
