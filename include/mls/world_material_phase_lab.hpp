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
struct MaterialPhaseContext {
  ResearchMechanicsInput schedule; // wire must remain empty: no duplicate phase
  std::vector<MaterialPhaseBinding> binding;
  MaterialOnlyTotals baseline;
  std::string last_events; // noncausal, never used for mechanics reconstruction
};
} // namespace mls
#endif
