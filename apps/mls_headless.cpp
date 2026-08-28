#include "mls/chemistry.hpp"
#include "mls/world.hpp"

#include <cstddef>
#include <cstdint>
#include <iostream>
#include <utility>
#include <vector>

namespace {

[[nodiscard]] mls::CompoundGraph atom(mls::ElementId element) {
    return mls::CompoundGraph(std::vector<mls::ElementId>{element}, {});
}

[[nodiscard]] mls::MaterialSeed material_seed(
    mls::Position3 position,
    mls::CompoundId compound) {
    return mls::MaterialSeed{
        .position = position,
        .momentum = {},
        .composition = mls::CompoundMixture{{compound, 1}},
        .stored_energy = mls::Energy::from_raw(1'000),
        .thermal_energy = mls::Energy::from_raw(1'000),
    };
}

[[nodiscard]] bool cell_has_both(
    const mls::SparseVoxelGrid& grid, mls::ElementId first, mls::ElementId second) {
    for (const auto& [coordinate, cell] : grid.cells()) {
        static_cast<void>(coordinate);
        if (cell.totals.has_value() &&
            cell.totals->elements.amount(first) > 0 &&
            cell.totals->elements.amount(second) > 0) {
            return true;
        }
    }
    return false;
}

} // namespace

int main() {
    using namespace mls;

    const ElementId a{0};
    const ElementId b{1};

    ElementCatalog elements;
    elements.define(
        a,
        ElementProperties{
            Mass::from_raw(10), HeatCapacity::from_raw(1), Energy::from_raw(100)});
    elements.define(
        b,
        ElementProperties{
            Mass::from_raw(10), HeatCapacity::from_raw(1), Energy::from_raw(100)});
    elements.define_bond_energy(a, b, 1, Energy::from_raw(20));

    CompoundRegistry compounds;
    const auto a_compound = compounds.intern(atom(a));
    const auto b_compound = compounds.intern(atom(b));
    const auto ab_compound = compounds.intern(CompoundGraph(
        std::vector<ElementId>{a, b}, std::vector<Bond>{{0, 1, 1}}));
    const ReactionDefinition association(
        std::vector<StoichiometricTerm>{{a_compound, 1}, {b_compound, 1}},
        std::vector<StoichiometricTerm>{{ab_compound, 1}},
        Energy::from_raw(5));

    World world(
        std::move(elements),
        std::move(compounds),
        WorldConfig{
            .voxel_edge = Length::from_raw(1),
            .kinetic_energy_scale_denominator = 1,
            .packet_history_limit = 16,
            .audit_after_each_operation = true,
        });
    const auto packet_a = world.introduce_material_from_boundary(material_seed(
        Position3{Length::from_raw(0), Length::from_raw(0), Length::from_raw(0)},
        a_compound));
    const auto packet_b = world.introduce_material_from_boundary(material_seed(
        Position3{Length::from_raw(2), Length::from_raw(0), Length::from_raw(0)},
        b_compound));

    const auto fine_reactable_before_transport = cell_has_both(world.grid(), a, b);
    const auto aggregated = world.totals();
    const auto lossy_aggregate_looks_reactable =
        aggregated.elements.amount(a) > 0 && aggregated.elements.amount(b) > 0;

    world.apply_point_impulse_from_boundary(
        packet_a,
        Momentum3{
            Momentum::from_raw(10), Momentum::from_raw(0), Momentum::from_raw(0)});
    world.apply_point_impulse_from_boundary(
        packet_b,
        Momentum3{
            Momentum::from_raw(-10), Momentum::from_raw(0), Momentum::from_raw(0)});
    world.step();

    const auto report = world.audit();
    const auto fine_reactable_after_transport = cell_has_both(world.grid(), a, b);
    const auto state_hash = world.physical_state_hash();

    std::cout << "{\n"
              << "  \"schema\": \"mls.headless-audit.v0\",\n"
              << "  \"tick\": " << world.tick() << ",\n"
              << "  \"packet_count\": " << world.packets().alive_count() << ",\n"
              << "  \"occupied_voxels\": " << world.grid().cells().size() << ",\n"
              << "  \"reaction_definition_balanced\": "
              << (association.is_balanced(world.compound_registry()) ? "true" : "false") << ",\n"
              << "  \"fine_reactable_before_transport\": "
              << (fine_reactable_before_transport ? "true" : "false") << ",\n"
              << "  \"lossy_aggregate_looks_reactable\": "
              << (lossy_aggregate_looks_reactable ? "true" : "false") << ",\n"
              << "  \"fine_reactable_after_physical_transport\": "
              << (fine_reactable_after_transport ? "true" : "false") << ",\n"
              << "  \"conservation_ok\": " << (report.ok() ? "true" : "false") << ",\n"
              << "  \"physical_state_hash_fnv1a64\": " << state_hash << "\n"
              << "}\n";

    return report.ok() && association.is_balanced(world.compound_registry()) ? 0 : 1;
}
