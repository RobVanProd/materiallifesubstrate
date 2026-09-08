#pragma once
#ifdef MLS_RESEARCH_MATERIAL_PHASE
#include "mls/packet_store.hpp"
#include "mls/world_mechanics_integration_lab.hpp"
#include <string>
#include <vector>
namespace mls {
struct MaterialPhaseSeed {
  std::uint64_t mechanics_id{}, material_id{};
  CompoundMixture composition{};
  Energy stored_energy{}, thermal_energy{};
};
struct MaterialPhaseBinding {
  std::uint64_t mechanics_id{};
  PacketHandle material{};
  [[nodiscard]] bool operator==(const MaterialPhaseBinding &) const = default;
};
struct MaterialOnlyTotals {
  ElementInventory elements{};
  Mass mass{};
  Energy structural{}, stored{}, thermal{};
  [[nodiscard]] Energy material_energy() const {
    return structural + stored + thermal;
  }
  [[nodiscard]] bool operator==(const MaterialOnlyTotals &) const = default;
};
// Preserve World's no-throw commit contract on MSVC too: an optional context
// must not contain a map whose move constructor may allocate a sentinel node.
struct MaterialPhaseBaseline {
  std::vector<std::pair<ElementId, ElementCount>> elements;
  Mass mass{};
  Energy structural{}, stored{}, thermal{};
};
struct MaterialPhaseContext {
  ResearchMechanicsInput schedule; // wire must remain empty: no duplicate phase
  std::vector<MaterialPhaseBinding> binding;
  MaterialPhaseBaseline baseline;
  std::string last_events; // noncausal, never used for mechanics reconstruction
};
} // namespace mls
#endif
