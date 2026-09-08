#include "mls/authoritative_mechanics_kernel_parity_lab.hpp"
#include "mls/checkpoint.hpp"
#include "mls/world.hpp"
#include <algorithm>
#include <bit>
#include <fstream>
#include <functional>
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
template <class F> void rejects(F f) {
  bool failed = false;
  try {
    f();
  } catch (const std::exception &) {
    failed = true;
  }
  check(failed, "required rejection missing");
}
Bytes read(const std::string &path) {
  std::ifstream f(path, std::ios::binary);
  check(bool(f), "input missing");
  return Bytes(std::istreambuf_iterator<char>(f), {});
}
void write(const std::string &path, const Bytes &b) {
  std::ofstream f(path, std::ios::binary);
  f.write(reinterpret_cast<const char *>(b.data()),
          static_cast<std::streamsize>(b.size()));
  check(bool(f), "write failed");
}
void write(const std::string &path, const std::string &s) {
  write(path, Bytes(s.begin(), s.end()));
}
Bytes unhex(const std::string &s) {
  Bytes b;
  check(s.size() % 2 == 0, "odd hex");
  for (std::size_t i = 0; i < s.size(); i += 2)
    b.push_back(
        static_cast<std::uint8_t>(std::stoul(s.substr(i, 2), nullptr, 16)));
  return b;
}
std::uint64_t u64(const Bytes &b, std::size_t p) {
  check(p + 8 <= b.size(), "short bytes");
  std::uint64_t n = 0;
  for (unsigned k = 0; k < 8; ++k)
    n |= static_cast<std::uint64_t>(b[p + k]) << (8 * k);
  return n;
}
void put(Bytes &b, std::uint64_t n) {
  for (unsigned k = 0; k < 8; ++k)
    b.push_back(static_cast<std::uint8_t>(n >> (8 * k)));
}
std::uint64_t hash(const Bytes &b) {
  std::uint64_t h = 14695981039346656037ULL;
  for (auto c : b)
    h = (h ^ c) * 1099511628211ULL;
  return h;
}
std::vector<mls::MaterialPhaseSeed>
seeds(const mls::ResearchMechanicsInput &input, mls::CompoundId compound) {
  auto wire = unhex(input.wire);
  std::vector<mls::MaterialPhaseSeed> out;
  for (std::size_t j = 0; j < u64(wire, 44); ++j) {
    const auto id = u64(wire, 52 + 118 * j);
    const auto mass = std::bit_cast<mls::Scalar>(u64(wire, 60 + 118 * j));
    check(id < (std::numeric_limits<std::uint64_t>::max() - 10000) / 7,
          "test ID bound");
    out.push_back({id, 10000 + 7 * (u64(wire, 44) - j),
                   mls::CompoundMixture{{compound, mass}},
                   mls::Energy::from_raw(100 + static_cast<mls::Scalar>(j)),
                   mls::Energy::from_raw(200 + static_cast<mls::Scalar>(j))});
  }
  return out;
}
struct Fixture {
  mls::World world;
  mls::CompoundId compound;
};
Fixture empty(const mls::ResearchMechanicsInput &input, bool enabled = true,
              mls::Scalar radius = 281474976710656LL) {
  mls::ElementCatalog elements;
  mls::ElementId e{1};
  elements.define(e, {mls::Mass::from_raw(1), mls::HeatCapacity::from_raw(2),
                      mls::Energy::from_raw(3)});
  mls::CompoundRegistry registry;
  const auto compound = registry.intern(mls::CompoundGraph({e}, {}));
  mls::WorldConfig config;
  config.material_phase_enabled = enabled;
  config.physical_timestep = mls::Time::from_raw(input.dt);
  config.interaction_radius = mls::Length::from_raw(radius);
  return {mls::World(elements, registry, config), compound};
}
mls::World make(const mls::ResearchMechanicsInput &input,
                bool reversed = false) {
  auto f = empty(input);
  auto s = seeds(input, f.compound);
  if (reversed)
    std::reverse(s.begin(), s.end());
  f.world.attach_material_phase(input, s);
  return f.world;
}
void ownership(const mls::World &world) {
  const auto s = world.material_phase_mechanics();
  const auto wire = unhex(s.wire);
  const auto binding = world.material_phase_binding();
  const auto material = world.packets().material_phase_packets();
  check(material.size() == binding.size() &&
            world.packets().alive_count() == material.size() &&
            world.packets().slot_count() == material.size(),
        "one material inventory");
  for (std::size_t j = 0; j < binding.size(); ++j) {
    const auto &link = binding[j];
    auto p = world.packets().material_phase_packet(link.material);
    check(p.mechanics_id == link.mechanics_id &&
              link.material.id.value != link.mechanics_id &&
              world.packets().contains(link.material),
          "explicit persistent binding");
    check(u64(wire, 52 + 118 * j) == p.mechanics_id &&
              std::bit_cast<mls::Scalar>(u64(wire, 60 + 118 * j)) ==
                  p.mass.raw(),
          "owned mass identity");
    check(std::equal(p.phase.begin(), p.phase.end(),
                     wire.begin() + static_cast<std::ptrdiff_t>(68 + 118 * j)),
          "owned phase payload mismatch");
    check(p.mass == mls::mass_of(p.composition, world.compound_registry(),
                                 world.element_catalog()),
          "composition mass mismatch");
  }
  check(world.material_phase_audit(), "exact material ledger");
}
void neutral(mls::World &world) {
  const auto prior = world.material_phase_mechanics();
  auto links = world.material_phase_binding();
  const auto total = world.material_phase_totals();
  const bool odd = world.tick() % 2 != 0;
  auto a = links.front().material, b = links.back().material;
  world.transfer_heat(odd ? a : b, odd ? b : a, mls::Energy::from_raw(1));
  world.convert_energy(
      a, odd ? mls::EnergyChannel::stored : mls::EnergyChannel::thermal,
      odd ? mls::EnergyChannel::thermal : mls::EnergyChannel::stored,
      mls::Energy::from_raw(1));
  auto after = world.material_phase_mechanics();
  check(prior.wire == after.wire && prior.events == after.events,
        "neutral operation changed mechanics");
  auto t = world.material_phase_totals();
  check(t.elements == total.elements && t.mass == total.mass &&
            t.structural == total.structural &&
            t.material_energy() == total.material_energy(),
        "neutral material accounting");
  ownership(world);
}
void advance(mls::World &world, int count, std::ostream &out,
             const std::string &checkpoint, bool coexist) {
  auto initial = world.material_phase_mechanics();
  const auto ids = world.material_phase_binding();
  out << "S " << initial.step << ' ' << initial.wire << " -\n";
  for (int k = 0; k < count; ++k) {
    const auto before = world.material_phase_checkpoint();
    const auto tick = world.tick();
    const auto time = world.physical_time();
    try {
      world.step();
    } catch (const mls::ResearchMechanicsRejection &e) {
      check(world.material_phase_checkpoint() == before &&
                world.tick() == tick && world.physical_time() == time,
            "non-atomic unified failure");
      out << e.record();
      return;
    }
    ownership(world);
    auto s = world.material_phase_mechanics();
    check(world.tick() == tick + 1 &&
              s.time == time.raw() + world.config().physical_timestep.raw() &&
              ids == world.material_phase_binding(),
          "clock/binding step");
    const auto witness = "S " + std::to_string(s.step) + " " + s.wire + " ";
    check(s.events.find(witness) != std::string::npos,
          "state commit differs from stored material");
    if (coexist)
      neutral(world);
    out << s.events;
    if (!checkpoint.empty() && k + 1 == std::max(1, count / 2 - 1))
      write(checkpoint, world.material_phase_checkpoint());
  }
}
Bytes mutate_records(
    const Bytes &original,
    const std::function<void(std::vector<std::string> &)> &mutation) {
  const std::string magic = "MLS-MATERIAL-PHASE-v1\n";
  std::size_t at = magic.size();
  std::vector<Bytes> fields;
  for (int k = 0; k < 4; ++k) {
    const auto n = u64(original, at);
    at += 8;
    fields.emplace_back(original.begin() + static_cast<std::ptrdiff_t>(at),
                        original.begin() + static_cast<std::ptrdiff_t>(at + n));
    at += static_cast<std::size_t>(n);
  }
  std::istringstream in(std::string(fields[1].begin(), fields[1].end()));
  std::vector<std::string> words;
  std::string word;
  while (in >> word)
    words.push_back(word);
  mutation(words);
  std::string record;
  for (const auto &s : words)
    record += s + ' ';
  fields[1] = Bytes(record.begin(), record.end());
  Bytes out(magic.begin(), magic.end());
  for (const auto &f : fields) {
    put(out, f.size());
    out.insert(out.end(), f.begin(), f.end());
  }
  put(out, hash(out));
  return out;
}
void contracts(const mls::ResearchMechanicsInput &input,
               const std::string &output) {
  auto world = make(input);
  ownership(world);
  const auto initial = world.material_phase_checkpoint();
  check(make(input, true).material_phase_checkpoint() == initial,
        "seed order changed canonical state");
  check(mls::World::restore_material_phase_checkpoint(initial)
                .material_phase_checkpoint() == initial,
        "checkpoint roundtrip");
  auto no = empty(input, false);
  rejects([&] {
    no.world.attach_material_phase(input, seeds(input, no.compound));
  });
  auto unattached = empty(input);
  rejects([&] { unattached.world.step(); });
  auto bad = empty(input);
  auto badseeds = seeds(input, bad.compound);
  badseeds[0].composition.add(bad.compound, 1);
  rejects([&] { bad.world.attach_material_phase(input, badseeds); });
  check(bad.world.packets().alive_count() == 0, "failed import mutated matter");
  auto ids = world.material_phase_binding();
  const auto a = ids.front().material, b = ids.back().material;
  rejects([&] { static_cast<void>(world.packets().snapshot(a)); });
  rejects([&] { static_cast<void>(world.packets().snapshots()); });
  rejects([&] { static_cast<void>(world.grid()); });
  rejects([&] { static_cast<void>(world.ledger()); });
  rejects([&] { static_cast<void>(world.totals()); });
  rejects([&] { static_cast<void>(world.audit()); });
  rejects(
      [&] { static_cast<void>(mls::serialize_canonical_checkpoint(world)); });
  rejects([&] { world.establish_current_state_as_baseline(); });
  rejects([&] { world.attach_research_mechanics(input); });
  rejects([&] { world.remove_material_to_boundary(a); });
  rejects(
      [&] { static_cast<void>(world.introduce_material_from_boundary({})); });
  rejects([&] { world.apply_point_impulse_from_boundary(a, {}); });
  const auto statehash = world.physical_state_hash();
  auto view = world.packets().material_phase_packet(a);
  view.phase[8] ^= 1;
  view.thermal_energy = mls::Energy{};
  auto observable = world.material_phase_mechanics();
  observable.wire.clear();
  observable.events = "wrong";
  check(world.physical_state_hash() == statehash &&
            world.material_phase_checkpoint() == initial,
        "observer feedback");
  auto stale = a;
  ++stale.generation;
  rejects([&] { world.transfer_heat(stale, b, mls::Energy::from_raw(1)); });
  rejects([&] {
    world.transfer_heat(a, {mls::PacketId{999999999}, 1},
                        mls::Energy::from_raw(1));
  });
  rejects([&] { world.transfer_heat(a, b, mls::Energy::from_raw(-1)); });
  rejects([&] {
    world.convert_energy(a, mls::EnergyChannel::stored,
                         mls::EnergyChannel::thermal,
                         mls::Energy::from_raw(999999999));
  });
  rejects([&] { world.step(std::numeric_limits<mls::Tick>::max()); });
  world.step(0);
  check(world.material_phase_checkpoint() == initial,
        "rejection/zero step mutation");
  auto corrupt = initial;
  corrupt.back() ^= 1;
  rejects([&] {
    static_cast<void>(mls::World::restore_material_phase_checkpoint(corrupt));
  });
  corrupt = initial;
  corrupt.pop_back();
  rejects([&] {
    static_cast<void>(mls::World::restore_material_phase_checkpoint(corrupt));
  });
  for (auto which : {7U, 9U, 17U}) {
    auto mutated = mutate_records(initial, [which](auto &tokens) {
      tokens.at(which) =
          which == 17 ? "00"
                      : std::to_string(std::stoull(tokens.at(which)) + 1);
    });
    rejects([&] {
      static_cast<void>(mls::World::restore_material_phase_checkpoint(mutated));
    });
  }
  auto binding_bad = mutate_records(initial, [](auto &t) {
    auto start = 7 + 12 * std::stoull(t.at(5));
    std::swap(t.at(start + 1), t.at(start + 4));
  });
  rejects([&] {
    static_cast<void>(
        mls::World::restore_material_phase_checkpoint(binding_bad));
  });
  std::ostringstream expected;
  std::istringstream request(mls::research_kernel_request(input, 1));
  check(mls::kernel_parity::run(request, expected) == 0,
        "isolated control run");
  std::ostringstream actual;
  advance(world, 1, actual, "", false);
  check(actual.str() == expected.str(), "single step kernel parity");
  if (expected.str().find("REJECT ") != std::string::npos) {
    check(world.material_phase_checkpoint() == initial, "atomic rejection");
    write(output, "{\"status\":\"PASS\",\"atomic_rejection\":true}\n");
    return;
  }
  auto copy = world;
  auto center = world.material_phase_mechanics();
  neutral(world);
  check(copy.material_phase_mechanics().wire ==
            world.material_phase_mechanics().wire,
        "coexistence phase");
  std::ostringstream baseline, coexist;
  advance(copy, 1, baseline, "", false);
  advance(world, 1, coexist, "", true);
  check(baseline.str() == coexist.str(),
        "neutral material changed future mechanics");
  auto narrow = empty(input, true, 1);
  narrow.world.attach_material_phase(input, seeds(input, narrow.compound));
  rejects([&] { narrow.world.transfer_heat(a, b, mls::Energy::from_raw(1)); });
  write(output, "{\"status\":\"PASS\",\"single_authority\":true,\"explicit_"
                "binding\":true,\"exact_material_ledger\":true,\"neutral_"
                "coexistence\":true,\"checkpoint_mutations\":6}\n");
}
} // namespace
int main(int argc, char **argv) {
  try {
#ifdef _WIN32
    const auto job = CreateJobObjectW(nullptr, nullptr);
    check(job != nullptr, "job allocation");
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION info{};
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY;
    info.ProcessMemoryLimit = std::size_t{2} * 1024 * 1024 * 1024;
    check(SetInformationJobObject(job, JobObjectExtendedLimitInformation, &info,
                                  sizeof(info)) &&
              AssignProcessToJobObject(job, GetCurrentProcess()),
          "process limit");
#else
    rlimit lim{rlim_t{2} * 1024 * 1024 * 1024, rlim_t{2} * 1024 * 1024 * 1024};
    check(setrlimit(RLIMIT_AS, &lim) == 0, "process limit");
#endif
    check(argc >= 3 && std::string(argv[1]) == "--research-material-phase",
          "explicit material research enable required");
    const std::string mode = argv[2];
    if (mode == "run" || mode == "neutral") {
      check(argc == 6, "run arguments");
      std::ifstream in(argv[3]);
      auto input = mls::read_research_mechanics_input(in);
      auto world = make(input);
      std::ostringstream out;
      advance(world, input.count, out, argv[5], mode == "neutral");
      write(argv[4], out.str());
      write(std::string(argv[4]) + ".final", world.material_phase_checkpoint());
    } else if (mode == "resume" || mode == "resume-neutral") {
      check(argc == 6, "resume arguments");
      auto world = mls::World::restore_material_phase_checkpoint(read(argv[3]));
      int count = std::stoi(argv[4]);
      check(count >= 0, "resume count");
      std::ostringstream out;
      advance(world, count, out, "", mode == "resume-neutral");
      write(argv[5], out.str());
      write(std::string(argv[5]) + ".final", world.material_phase_checkpoint());
    } else if (mode == "contracts") {
      check(argc == 5, "contract arguments");
      std::ifstream in(argv[3]);
      contracts(mls::read_research_mechanics_input(in), argv[4]);
    } else
      throw std::invalid_argument("unknown mode");
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "MATERIAL_PHASE_FAILURE " << e.what() << '\n';
    return 2;
  }
}
