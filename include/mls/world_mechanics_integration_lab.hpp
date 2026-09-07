#pragma once
#ifdef MLS_RESEARCH_WORLD_MECHANICS
#include <cstdint>
#include <iosfwd>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace mls {
// Research import protocol, not a production material/World API. No expected
// next state, force, or observer value is accepted by a transition.
struct ResearchMechanicsInput {
  std::string trajectory, path, wire, model;
  int level{}, count{}, start{};
  std::int64_t dt{};
};
struct ResearchMechanicsContext {
  ResearchMechanicsInput request;
  std::string last_events; // noncausal, last committed World call only
};
struct ResearchMechanicsSnapshot {
  std::string wire, events;
  std::vector<std::uint64_t> ids;
  std::int64_t time{};
  int step{};
};
class ResearchMechanicsRejection final : public std::runtime_error {
public:
  explicit ResearchMechanicsRejection(std::string record)
      : std::runtime_error("research mechanics rejected staged transition"),
        record_(std::move(record)) {}
  [[nodiscard]] std::string record() const { return record_; }

private:
  std::string record_;
};
[[nodiscard]] ResearchMechanicsInput
read_research_mechanics_input(std::istream &);
[[nodiscard]] std::string
research_kernel_request(const ResearchMechanicsInput &, int count);
} // namespace mls
#endif
