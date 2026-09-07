#include "mls/authoritative_mechanics_kernel_parity_lab.hpp"
#include "mls/checkpoint.hpp"
#include "mls/world.hpp"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <sstream>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <sys/resource.h>
#endif

namespace {
using Bytes = std::vector<std::uint8_t>;
void check(bool ok, const char *why) {
  if (!ok)
    throw std::runtime_error(why);
}
template <class F> void rejects(F action) {
  bool failed = false;
  try {
    action();
  } catch (const std::exception &) {
    failed = true;
  }
  check(failed, "expected rejection did not occur");
}
Bytes read_bytes(const std::string &path) {
  std::ifstream in(path, std::ios::binary);
  check(bool(in), "missing checkpoint");
  return Bytes(std::istreambuf_iterator<char>(in), {});
}
void write_bytes(const std::string &path, const Bytes &b) {
  std::ofstream out(path, std::ios::binary);
  out.write(reinterpret_cast<const char *>(b.data()),
            static_cast<std::streamsize>(b.size()));
  check(bool(out), "checkpoint output failed");
}
mls::World make_world(std::int64_t dt, bool enabled = true) {
  mls::ElementCatalog elements;
  const mls::ElementId e{1};
  elements.define(e, {mls::Mass::from_raw(4), mls::HeatCapacity::from_raw(2),
                      mls::Energy::from_raw(3)});
  mls::CompoundRegistry compounds;
  auto c = compounds.intern(mls::CompoundGraph({e}, {}));
  mls::WorldConfig config;
  config.physical_timestep = mls::Time::from_raw(dt);
  config.packet_history_limit = 8;
  config.research_mechanics_enabled = enabled;
  mls::World world(elements, compounds, config);
  mls::MaterialSeed seed;
  seed.position = {mls::Length::from_raw(5), mls::Length{}, mls::Length{}};
  seed.momentum = {mls::Momentum::from_raw(4), mls::Momentum{},
                   mls::Momentum{}};
  seed.composition = mls::CompoundMixture{{c, 1}};
  seed.stored_energy = mls::Energy::from_raw(100);
  seed.thermal_energy = mls::Energy::from_raw(50);
  static_cast<void>(world.introduce_material_from_boundary(seed));
  return world;
}
std::string history(const mls::World &w) {
  std::ostringstream out;
  for (const auto &p : w.packets().snapshots())
    for (const auto &e : w.packets().history(p.handle))
      out << e.tick << ' ' << static_cast<int>(e.kind) << ' '
          << e.related_packet.value << ' ' << e.position_after.x.raw() << ' '
          << e.position_after.y.raw() << ' ' << e.position_after.z.raw() << ' '
          << e.momentum_delta.x.raw() << ' ' << e.momentum_delta.y.raw() << ' '
          << e.momentum_delta.z.raw() << ' ' << e.thermal_delta.raw() << ' '
          << e.stored_delta.raw() << '\n';
  return out.str();
}
void same_unrelated(const mls::World &before, const mls::World &after) {
  check(before.research_unrelated_checkpoint() ==
            after.research_unrelated_checkpoint(),
        "unrelated checkpoint state changed");
  check(before.packets().snapshots() == after.packets().snapshots(),
        "legacy packet changed/double drift");
  check(history(before) == history(after), "legacy history changed");
  const auto &a = before.grid().cells();
  const auto &b = after.grid().cells();
  check(a.size() == b.size(), "grid size changed");
  auto j = b.begin();
  for (const auto &[key, cell] : a) {
    check(j != b.end() && j->first == key &&
              j->second.packets == cell.packets &&
              j->second.totals == cell.totals,
          "unrelated grid changed");
    ++j;
  }
}
std::string start_line(const mls::World &w) {
  const auto s = w.research_mechanics();
  return "S " + std::to_string(s.step) + " " + s.wire + " -\n";
}
void owned_state_matches_commit(const mls::ResearchMechanicsSnapshot &state) {
  std::istringstream events(state.events);
  std::string line;
  int matches = 0;
  while (std::getline(events, line)) {
    if (!line.starts_with("S "))
      continue;
    std::istringstream row(line);
    std::string kind, wire, digest;
    int step{};
    row >> kind >> step >> wire >> digest;
    if (step == state.step) {
      check(bool(row) && wire == state.wire,
            "World-owned phase differs from the committed kernel record");
      ++matches;
    }
  }
  check(matches == 1, "missing/duplicate World-owned state witness");
}
void advance(mls::World &w, int count, std::ostream &out,
             const std::string &checkpoint = {}) {
  const auto initial = w;
  const auto ids = w.research_mechanics().ids;
  out << start_line(w);
  for (int i = 0; i < count; ++i) {
    const auto before = w.research_checkpoint();
    const auto tick = w.tick();
    const auto time = w.physical_time();
    try {
      w.step();
    } catch (const mls::ResearchMechanicsRejection &e) {
      check(w.research_checkpoint() == before && w.tick() == tick &&
                w.physical_time() == time,
            "failed step mutated World/clock/events");
      same_unrelated(initial, w);
      out << e.record();
      return;
    }
    const auto s = w.research_mechanics();
    owned_state_matches_commit(s);
    check(w.tick() == tick + 1 &&
              w.physical_time().raw() ==
                  time.raw() + w.config().physical_timestep.raw(),
          "World clock advance");
    check(s.time == w.physical_time().raw() &&
              static_cast<mls::Tick>(s.step) == w.tick() && s.ids == ids,
          "mechanics clock/IDs");
    same_unrelated(initial, w);
    out << s.events;
    if (!checkpoint.empty() && i + 1 == std::max(1, count / 2))
      write_bytes(checkpoint, w.research_checkpoint());
  }
}
void contracts(const mls::ResearchMechanicsInput &r, std::ostream &out) {
  auto disabled = make_world(r.dt, false);
  const auto disabled_bytes = mls::serialize_canonical_checkpoint(disabled);
  rejects([&] { disabled.attach_research_mechanics(r); });
  check(mls::serialize_canonical_checkpoint(disabled) == disabled_bytes,
        "disabled attach mutated World");
  const auto old_position = disabled.packets().snapshots().front().position;
  disabled.step();
  check(disabled.packets().snapshots().front().position != old_position,
        "default legacy path stopped");
  auto w = make_world(r.dt);
  rejects([&] { w.step(); });
  w.attach_research_mechanics(r);
  rejects([&] { w.attach_research_mechanics(r); });
  rejects([&] { static_cast<void>(mls::serialize_canonical_checkpoint(w)); });
  rejects([&] { static_cast<void>(w.totals()); });
  rejects([&] { static_cast<void>(w.audit()); });
  auto checkpoint = w.research_checkpoint();
  const auto hash = w.physical_state_hash();
  w.step(0);
  check(w.research_checkpoint() == checkpoint, "zero step changed state");
  for (int i = 0; i < 5; ++i) {
    auto copy = w.research_mechanics();
    copy.wire.assign("not state");
    copy.events.assign("not feedback");
  }
  check(w.research_checkpoint() == checkpoint &&
            w.physical_state_hash() == hash,
        "observer copy feedback");
  auto restored = mls::World::restore_research_checkpoint(checkpoint);
  check(restored.research_checkpoint() == checkpoint &&
            restored.physical_state_hash() == hash,
        "complete checkpoint roundtrip");
  for (const auto at :
       {std::size_t{0}, checkpoint.size() / 2, checkpoint.size() - 1}) {
    auto broken = checkpoint;
    broken[at] ^= 1;
    rejects([&] {
      static_cast<void>(mls::World::restore_research_checkpoint(broken));
    });
  }
  auto truncated = checkpoint;
  truncated.pop_back();
  rejects([&] {
    static_cast<void>(mls::World::restore_research_checkpoint(truncated));
  });
  // Recompute the outer checksum: these exercise semantic validation, not
  // merely accidental-corruption detection.
  const auto prefix = "run " + r.trajectory + " " + std::to_string(r.level) +
                      " " + std::to_string(r.dt) + " 0 ";
  const auto found = std::search(checkpoint.begin(), checkpoint.end(),
                                 prefix.begin(), prefix.end());
  check(found != checkpoint.end(), "checkpoint request not found");
  const auto at = static_cast<std::size_t>(found - checkpoint.begin());
  for (auto offset : {at + prefix.size() - 2, at + prefix.size()}) {
    auto semantic = checkpoint;
    semantic[offset] = semantic[offset] == '1' ? '0' : '1';
    std::uint64_t h = 14695981039346656037ULL;
    for (std::size_t i = 0; i < semantic.size() - 8; ++i)
      h = (h ^ semantic[i]) * 1099511628211ULL;
    for (unsigned i = 0; i < 8; ++i)
      semantic[semantic.size() - 8 + i] =
          static_cast<std::uint8_t>(h >> (8 * i));
    rejects([&] {
      static_cast<void>(mls::World::restore_research_checkpoint(semantic));
    });
  }
  rejects([&] { w.step(std::numeric_limits<mls::Tick>::max()); });
  check(w.research_checkpoint() == checkpoint, "overflow advanced World");
  auto fork = w;
  std::ostringstream expected;
  std::istringstream kernel_input(mls::research_kernel_request(r, 1));
  check(mls::kernel_parity::run(kernel_input, expected) == 0,
        "isolated contract input error");
  std::ostringstream actual;
  advance(w, 1, actual);
  check(actual.str() == expected.str(),
        "World/isolated first-step semantic divergence");
  check(fork.research_checkpoint() == checkpoint,
        "World copy aliases phase state");
  if (actual.str().find("REJECT ") != std::string::npos) {
    check(w.research_checkpoint() == checkpoint, "rejection not atomic");
    std::ostringstream repeat;
    advance(w, 1, repeat);
    check(repeat.str() == actual.str(), "nondeterministic rejection");
    rejects([&] { w.step(2); });
    check(w.research_checkpoint() == checkpoint, "batch rejection committed");
    out << "{\"status\":\"PASS\",\"atomic_rejection\":true}\n";
    return;
  }
  check(w.physical_state_hash() != hash,
        "mechanics omitted from physical hash");
  fork.step();
  check(fork.research_checkpoint() == w.research_checkpoint(),
        "observer-frequency/copy continuation divergence");
  auto batched = restored;
  std::istringstream two_input(mls::research_kernel_request(r, 2));
  std::ostringstream two_expected;
  check(mls::kernel_parity::run(two_input, two_expected) == 0,
        "isolated two-step failure");
  const auto batch_before = batched.research_checkpoint();
  try {
    const auto header = start_line(batched);
    batched.step(2);
    owned_state_matches_commit(batched.research_mechanics());
    check(header + batched.research_mechanics().events == two_expected.str(),
          "batch double/omitted step");
    same_unrelated(restored, batched);
  } catch (const mls::ResearchMechanicsRejection &) {
    check(batched.research_checkpoint() == batch_before,
          "later batch rejection committed state");
    check(two_expected.str().find("REJECT ") != std::string::npos,
          "unexpected batch rejection");
  }
  out << "{\"status\":\"PASS\",\"atomic_rejection\":false}\n";
}
void backstop() {
#ifdef _WIN32
  HANDLE job = CreateJobObjectW(nullptr, nullptr);
  JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
  limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY;
  limits.ProcessMemoryLimit = static_cast<SIZE_T>(2ULL * 1024 * 1024 * 1024);
  check(job &&
            SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                    &limits, sizeof(limits)) &&
            AssignProcessToJobObject(job, GetCurrentProcess()),
        "resource backstop setup");
#else
  rlimit limits{2ULL * 1024 * 1024 * 1024, 2ULL * 1024 * 1024 * 1024};
  check(setrlimit(RLIMIT_AS, &limits) == 0, "resource backstop setup");
#endif
}
} // namespace
int main(int argc, char **argv) {
  try {
    check(argc >= 3 && std::string(argv[1]) == "--research-world-mechanics",
          "explicit research runtime flag required");
    backstop();
    const std::string mode = argv[2];
    if (mode == "resume") {
      check(argc == 6, "resume checkpoint count output");
      auto w = mls::World::restore_research_checkpoint(read_bytes(argv[3]));
      const int count = std::stoi(argv[4]);
      check(count >= 0, "negative resume count");
      std::ofstream out(argv[5], std::ios::binary);
      advance(w, count, out);
      check(bool(out), "output failure");
      return 0;
    }
    check((mode == "run" && argc == 6) || (mode == "contracts" && argc == 5),
          "run/contracts arguments");
    std::ifstream input(argv[3], std::ios::binary);
    auto r = mls::read_research_mechanics_input(input);
    std::ofstream out(argv[4], std::ios::binary);
    if (mode == "contracts")
      contracts(r, out);
    else {
      auto world = make_world(r.dt);
      world.attach_research_mechanics(r);
      advance(world, r.count, out, argv[5]);
    }
    check(bool(out), "output failure");
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "WORLD_INTEGRATION_FAILURE " << e.what() << '\n';
    return 1;
  }
}
