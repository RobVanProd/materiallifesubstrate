#include "mls/checkpoint.hpp"
#include "mls/world.hpp"
#ifdef MLS_RESEARCH_MATERIAL_PHASE
#include "mls/authoritative_mechanics_kernel_parity_lab.hpp"
#include <algorithm>
#include <bit>
#include <boost/multiprecision/cpp_int.hpp>
#include <boost/rational.hpp>
#include <limits>
#include <set>
#include <sstream>

namespace mls {
namespace {
using Bytes = std::vector<std::uint8_t>;
using I = boost::multiprecision::cpp_int;
using Q = boost::rational<I>;
constexpr std::size_t limit = 16U * 1024U * 1024U;
const std::string magic = "MLS-MATERIAL-PHASE-v1\n";
void need(bool value, const char *message) {
  if (!value)
    throw std::invalid_argument(message);
}
Bytes unhex(const std::string &s) {
  need(s.size() % 2 == 0 && s.size() <= limit, "phase hex size");
  auto digit = [](char c) -> unsigned {
    if (c >= '0' && c <= '9')
      return static_cast<unsigned>(c - '0');
    if (c >= 'a' && c <= 'f')
      return static_cast<unsigned>(c - 'a' + 10);
    throw std::invalid_argument("noncanonical phase hex");
  };
  Bytes b;
  for (std::size_t n = 0; n < s.size(); n += 2)
    b.push_back(static_cast<std::uint8_t>(16 * digit(s[n]) + digit(s[n + 1])));
  return b;
}
std::string hex(std::span<const std::uint8_t> b) {
  const char *digits = "0123456789abcdef";
  std::string s;
  for (auto c : b) {
    s += digits[c >> 4];
    s += digits[c & 15];
  }
  return s;
}
std::uint64_t get64(std::span<const std::uint8_t> b, std::size_t pos) {
  need(pos <= b.size() && b.size() - pos >= 8, "truncated material bytes");
  std::uint64_t n = 0;
  for (unsigned k = 0; k < 8; ++k)
    n |= static_cast<std::uint64_t>(b[pos + k]) << (8 * k);
  return n;
}
void put64(Bytes &b, std::uint64_t n) {
  for (unsigned k = 0; k < 8; ++k)
    b.push_back(static_cast<std::uint8_t>(n >> (8 * k)));
}
std::uint64_t checksum(std::span<const std::uint8_t> b) {
  std::uint64_t h = 14695981039346656037ULL;
  for (auto x : b)
    h = (h ^ x) * 1099511628211ULL;
  return h;
}
void field(Bytes &b, std::span<const std::uint8_t> v) {
  need(v.size() <= limit, "field limit");
  put64(b, v.size());
  b.insert(b.end(), v.begin(), v.end());
}
void field(Bytes &b, const std::string &s) {
  field(b,
        std::span(reinterpret_cast<const std::uint8_t *>(s.data()), s.size()));
}
Bytes next(std::span<const std::uint8_t> b, std::size_t &p) {
  auto n = get64(b, p);
  p += 8;
  need(n <= limit && p <= b.size() && n <= b.size() - p, "field bounds");
  Bytes r(b.begin() + static_cast<std::ptrdiff_t>(p),
          b.begin() + static_cast<std::ptrdiff_t>(p + n));
  p += static_cast<std::size_t>(n);
  return r;
}
std::string text(const Bytes &b) { return std::string(b.begin(), b.end()); }
struct WirePacket {
  std::uint64_t id{};
  Scalar mass{};
  std::array<std::uint8_t, 102> phase{};
};
std::vector<WirePacket> split(const std::string &wire) {
  const auto b = unhex(wire);
  need(b.size() >= 52, "short phase wire");
  const auto n = get64(b, 44);
  need(n > 0 && n <= 16 && b.size() == 52 + 118 * n, "phase count");
  std::vector<WirePacket> packets;
  for (std::size_t j = 0; j < n; ++j) {
    WirePacket p;
    p.id = get64(b, 52 + 118 * j);
    p.mass = std::bit_cast<Scalar>(get64(b, 60 + 118 * j));
    std::copy_n(b.begin() + static_cast<std::ptrdiff_t>(68 + 118 * j), 102,
                p.phase.begin());
    packets.push_back(p);
  }
  return packets;
}
std::string wire_header(Scalar time, std::size_t count) {
  const std::string m("MLS-BOUNDED-BINARY-PHASE-v1\0", 28);
  Bytes b(m.begin(), m.end());
  for (const unsigned n : {1U, 96U, 49154U, 16383U}) {
    b.push_back(static_cast<std::uint8_t>(n));
    b.push_back(static_cast<std::uint8_t>(n >> 8));
  }
  put64(b, static_cast<std::uint64_t>(time));
  put64(b, count);
  return hex(b);
}
Q component(const MaterialPhasePacket &p, std::size_t k) {
  const auto at = 17 * k;
  I n = 0;
  for (std::size_t j = 5; j < 17; ++j) {
    n <<= 8;
    n += p.phase[at + j];
  }
  int e = static_cast<int>(p.phase[at + 3]) +
          256 * static_cast<int>(p.phase[at + 4]);
  if (e >= 32768)
    e -= 65536;
  e -= 95;
  Q q(n);
  if (e >= 0)
    q *= Q(I(1) << e);
  else
    q /= Q(I(1) << (-e));
  return p.phase[at] ? -q : q;
}
void canonical_input(const ResearchMechanicsInput &r) {
  std::istringstream in(research_kernel_request(r, 0));
  auto parsed = read_research_mechanics_input(in);
  need(parsed.wire == r.wire && parsed.model == r.model,
       "noncanonical model/phase import");
}
void encode_totals(std::ostream &s, const MaterialOnlyTotals &t) {
  s << t.mass.raw() << ' ' << t.structural.raw() << ' ' << t.stored.raw() << ' '
    << t.thermal.raw() << ' ' << t.elements.amounts().size() << ' ';
  for (const auto &[id, n] : t.elements.amounts())
    s << id.value << ' ' << n << ' ';
  s << '\n';
}
MaterialOnlyTotals decode_totals(std::istream &s) {
  Scalar mass, structural, stored, thermal;
  std::size_t count;
  need(bool(s >> mass >> structural >> stored >> thermal >> count) &&
           count <= 65536,
       "material ledger syntax");
  MaterialOnlyTotals t;
  t.mass = Mass::from_raw(mass);
  t.structural = Energy::from_raw(structural);
  t.stored = Energy::from_raw(stored);
  t.thermal = Energy::from_raw(thermal);
  for (std::size_t j = 0; j < count; ++j) {
    unsigned id;
    Scalar n;
    need(bool(s >> id >> n) && id <= 65535 && n > 0,
         "material inventory syntax");
    t.elements.add(ElementId{static_cast<std::uint16_t>(id)}, n);
  }
  return t;
}
} // namespace

std::vector<MaterialPhasePacket> PacketStore::material_phase_packets() const {
  std::vector<MaterialPhasePacket> out;
  for (const auto &[id, p] : material_phase_) {
    static_cast<void>(id);
    out.push_back(p);
  }
  return out;
}
MaterialPhasePacket
PacketStore::material_phase_packet(PacketHandle handle) const {
  auto found = material_phase_.find(handle.id);
  need(found != material_phase_.end() && found->second.handle == handle,
       "stale/unknown B96 material handle");
  return found->second;
}
MaterialOnlyTotals World::material_phase_totals() const {
  need(material_phase_.has_value(), "no unified material");
  MaterialOnlyTotals t;
  for (const auto &[id, p] : packets_.material_phase_) {
    static_cast<void>(id);
    t.elements.add_inventory(p.elements);
    t.mass += p.mass;
    t.structural += p.structural_energy;
    t.stored += p.stored_energy;
    t.thermal += p.thermal_energy;
  }
  return t;
}
bool World::material_phase_audit() const {
  const auto t = material_phase_totals();
  const auto &b = material_phase_->baseline;
  return t.elements == b.elements && t.mass == b.mass &&
         t.structural == b.structural &&
         t.material_energy() == b.material_energy();
}
void World::validate_material_phase() const {
  need(config_.material_phase_enabled && material_phase_ &&
           !research_mechanics_,
       "single phase authority required");
  const auto &c = *material_phase_;
  need(c.schedule.wire.empty(), "duplicate phase authority");
  need(packets_.ids_.empty() &&
           packets_.alive_count_ == packets_.material_phase_.size(),
       "legacy phase slots forbidden for unified matter");
  need(c.binding.size() == packets_.material_phase_.size() &&
           !c.binding.empty() && c.binding.size() <= 16,
       "binding coverage");
  need(config_.physical_time_scale == PhysicalTimeScale{1, 1000000000} &&
           config_.physical_timestep.raw() == c.schedule.dt &&
           c.schedule.start >= 0 &&
           tick_ == static_cast<Tick>(c.schedule.start) &&
           physical_time_.raw() ==
               detail::checked_multiply(c.schedule.start, c.schedule.dt),
       "unified clock contract");
  std::set<PacketId> used;
  std::uint64_t prior = 0;
  for (const auto &link : c.binding) {
    auto it = packets_.material_phase_.find(link.material.id);
    need(link.mechanics_id > prior && it != packets_.material_phase_.end() &&
             used.insert(link.material.id).second,
         "corrupted binding");
    prior = link.mechanics_id;
    const auto &p = it->second;
    need(p.handle == link.material && p.handle.generation == 1 &&
             p.mechanics_id == link.mechanics_id && p.handle.id.value > 0 &&
             p.handle.id.value < packets_.next_id_.value,
         "stale/swapped binding");
    need(!p.composition.empty() && p.mass.raw() > 0 &&
             p.mass == mass_of(p.composition, compounds_, elements_) &&
             p.elements == inventory_of(p.composition, compounds_) &&
             p.heat_capacity ==
                 heat_capacity_of(p.composition, compounds_, elements_) &&
             p.structural_energy ==
                 structural_energy_of(p.composition, compounds_, elements_),
         "World-derived material mass/inventory mismatch");
    need(p.thermal_energy.raw() >= 0 && p.stored_energy.raw() >= 0,
         "negative material energy");
  }
  need(material_phase_audit(), "material ledger mismatch");
}
ResearchMechanicsInput World::material_phase_request() const {
  validate_material_phase();
  auto r = material_phase_->schedule;
  r.count = 0;
  r.wire = wire_header(physical_time_.raw(), material_phase_->binding.size());
  for (const auto &link : material_phase_->binding) {
    const auto &p = packets_.material_phase_.at(link.material.id);
    Bytes b;
    put64(b, link.mechanics_id);
    put64(b, static_cast<std::uint64_t>(p.mass.raw()));
    b.insert(b.end(), p.phase.begin(), p.phase.end());
    r.wire += hex(b);
  }
  return r;
}
void World::attach_material_phase(const ResearchMechanicsInput &input,
                                  std::vector<MaterialPhaseSeed> seeds) {
  need(config_.material_phase_enabled && !config_.research_mechanics_enabled &&
           !material_phase_ && !research_mechanics_ &&
           packets_.alive_count() == 0 && packets_.slot_count() == 0,
       "unified fixed-inventory initialization only");
  canonical_input(input);
  const auto wire = split(input.wire);
  need(seeds.size() == wire.size(), "material seed coverage");
  std::sort(seeds.begin(), seeds.end(), [](const auto &a, const auto &b) {
    return a.mechanics_id < b.mechanics_id;
  });
  auto staged = *this;
  MaterialPhaseContext c;
  c.schedule = input;
  c.schedule.wire.clear();
  c.schedule.count = 0;
  std::set<PacketId> ids;
  for (std::size_t j = 0; j < wire.size(); ++j) {
    const auto &seed = seeds[j];
    const auto &raw = wire[j];
    need(seed.mechanics_id == raw.id &&
             seed.material_id >= packets_.next_id_.value &&
             seed.material_id < std::numeric_limits<std::uint64_t>::max() &&
             ids.insert(PacketId{seed.material_id}).second,
         "explicit material identity binding");
    MaterialPhasePacket p;
    p.handle = {PacketId{seed.material_id}, 1};
    p.mechanics_id = raw.id;
    p.composition = seed.composition;
    p.elements = inventory_of(p.composition, compounds_);
    p.mass = mass_of(p.composition, compounds_, elements_);
    p.heat_capacity = heat_capacity_of(p.composition, compounds_, elements_);
    p.structural_energy =
        structural_energy_of(p.composition, compounds_, elements_);
    need(p.mass.raw() == raw.mass, "World/kernel mass mismatch");
    p.stored_energy = seed.stored_energy;
    p.thermal_energy = seed.thermal_energy;
    p.phase = raw.phase;
    staged.packets_.material_phase_.emplace(p.handle.id, p);
    c.binding.push_back({raw.id, p.handle});
    staged.packets_.next_id_.value =
        std::max(staged.packets_.next_id_.value, seed.material_id + 1);
  }
  staged.packets_.alive_count_ = wire.size();
  staged.tick_ = static_cast<Tick>(input.start);
  staged.physical_time_ =
      Time::from_raw(detail::checked_multiply(input.start, input.dt));
  staged.material_phase_ = std::move(c);
  staged.material_phase_->baseline = staged.material_phase_totals();
  staged.validate_material_phase();
  need(staged.material_phase_request().wire == input.wire,
       "material import changed phase");
  *this = std::move(staged);
}
ResearchMechanicsSnapshot World::material_phase_mechanics() const {
  const auto r = material_phase_request();
  ResearchMechanicsSnapshot s{
      r.wire, material_phase_->last_events, {}, physical_time_.raw(), r.start};
  for (const auto &link : material_phase_->binding)
    s.ids.push_back(link.mechanics_id);
  return s;
}
std::vector<MaterialPhaseBinding> World::material_phase_binding() const {
  validate_material_phase();
  return material_phase_->binding;
}
void World::step_material_phase(Tick count) {
  validate_material_phase();
  need(tick_ <= static_cast<Tick>(std::numeric_limits<int>::max()) &&
           count <= static_cast<Tick>(std::numeric_limits<int>::max()) - tick_,
       "step overflow");
  static_cast<void>(detail::checked_multiply(static_cast<Scalar>(tick_ + count),
                                             config_.physical_timestep.raw()));
  if (count == 0)
    return;
  auto staged = *this;
  std::string events;
  for (Tick n = 0; n < count; ++n) {
    const auto r = staged.material_phase_request();
    std::istringstream in(research_kernel_request(r, 1));
    std::ostringstream out;
    need(kernel_parity::run(in, out) == 0, "kernel protocol failure");
    const auto stream = out.str();
    const auto prefix = "S " + std::to_string(r.start) + " " + r.wire + " -\n";
    need(stream.starts_with(prefix), "kernel initial state mismatch");
    const auto body = stream.substr(prefix.size());
    if (body.starts_with("REJECT ") ||
        body.find("\nREJECT ") != std::string::npos)
      throw ResearchMechanicsRejection(body);
    std::istringstream rows(body);
    std::string line, wire;
    int commits = 0;
    while (std::getline(rows, line)) {
      need(!line.empty() &&
               std::string("GTES").find(line[0]) != std::string::npos,
           "unknown kernel event");
      if (line.starts_with("S ")) {
        std::istringstream row(line);
        std::string kind, digest;
        int step;
        need(bool(row >> kind >> step >> wire >> digest) &&
                 step == r.start + 1 && digest.size() == 64,
             "kernel commit identity");
        ++commits;
      }
    }
    need(commits == 1, "kernel commit count");
    const auto packets = split(wire);
    need(packets.size() == staged.material_phase_->binding.size(),
         "kernel inventory change");
    for (std::size_t j = 0; j < packets.size(); ++j) {
      const auto &link = staged.material_phase_->binding[j];
      auto &material = staged.packets_.material_phase_.at(link.material.id);
      need(packets[j].id == link.mechanics_id &&
               packets[j].mass == material.mass.raw(),
           "kernel identity/mass change");
      material.phase = packets[j].phase;
    }
    ++staged.material_phase_->schedule.start;
    ++staged.tick_;
    staged.physical_time_ += config_.physical_timestep;
    need(staged.material_phase_request().wire == wire,
         "stored unified phase differs from commit");
    events += body;
    need(events.size() <= limit, "observer limit");
  }
  staged.material_phase_->last_events = std::move(events);
  *this = std::move(staged);
}
void World::transfer_material_phase_heat(PacketHandle from, PacketHandle to,
                                         Energy amount) {
  validate_material_phase();
  const auto a = packets_.material_phase_packet(from),
             b = packets_.material_phase_packet(to);
  need(amount.raw() >= 0 && amount <= a.thermal_energy, "invalid heat amount");
  Q squared(0);
  for (std::size_t k = 0; k < 3; ++k) {
    const auto d = component(a, k) - component(b, k);
    squared += d * d;
  }
  const Q radius(config_.interaction_radius.raw());
  need(squared <= radius * radius, "B96 material support");
  if (from == to)
    return;
  auto staged = *this;
  staged.packets_.material_phase_.at(from.id).thermal_energy -= amount;
  staged.packets_.material_phase_.at(to.id).thermal_energy += amount;
  staged.validate_material_phase();
  *this = std::move(staged);
}
void World::convert_material_phase_energy(PacketHandle handle,
                                          EnergyChannel from, EnergyChannel to,
                                          Energy amount) {
  validate_material_phase();
  static_cast<void>(packets_.material_phase_packet(handle));
  need(amount.raw() >= 0, "negative conversion");
  need((from == EnergyChannel::stored || from == EnergyChannel::thermal) &&
           (to == EnergyChannel::stored || to == EnergyChannel::thermal),
       "energy channel");
  auto staged = *this;
  auto &p = staged.packets_.material_phase_.at(handle.id);
  auto &source =
      from == EnergyChannel::stored ? p.stored_energy : p.thermal_energy;
  auto &target =
      to == EnergyChannel::stored ? p.stored_energy : p.thermal_energy;
  need(amount <= source, "insufficient material energy");
  if (from != to) {
    source -= amount;
    target += amount;
  }
  staged.validate_material_phase();
  *this = std::move(staged);
}
std::vector<std::uint8_t> World::material_phase_checkpoint() const {
  validate_material_phase();
  auto legacy = *this;
  legacy.material_phase_.reset();
  legacy.config_.material_phase_enabled = false;
  legacy.packets_.material_phase_.clear();
  legacy.packets_.alive_count_ = 0;
  const auto base = serialize_canonical_checkpoint(legacy);
  const auto &c = *material_phase_;
  const auto &r = c.schedule;
  std::ostringstream records;
  records << r.trajectory << ' ' << r.path << ' ' << r.level << ' ' << r.dt
          << ' ' << r.start << '\n';
  records << packets_.material_phase_.size() << '\n';
  for (const auto &[id, p] : packets_.material_phase_) {
    records << id.value << ' ' << p.handle.generation << ' ' << p.mechanics_id
            << ' ' << p.mass.raw() << ' ' << p.heat_capacity.raw() << ' '
            << p.structural_energy.raw() << ' ' << p.stored_energy.raw() << ' '
            << p.thermal_energy.raw() << ' ' << p.composition.amounts().size()
            << ' ';
    for (const auto &[compound, n] : p.composition.amounts())
      records << compound.value << ' ' << n << ' ';
    records << hex(p.phase) << '\n';
  }
  records << c.binding.size() << '\n';
  for (const auto &b : c.binding)
    records << b.mechanics_id << ' ' << b.material.id.value << ' '
            << b.material.generation << '\n';
  encode_totals(records, c.baseline);
  Bytes out(magic.begin(), magic.end());
  field(out, base);
  field(out, records.str());
  field(out, r.model);
  field(out, c.last_events);
  need(out.size() + 8 <= limit, "material checkpoint limit");
  put64(out, checksum(out));
  return out;
}
World World::restore_material_phase_checkpoint(
    std::span<const std::uint8_t> bytes) {
  need(bytes.size() >= magic.size() + 40 && bytes.size() <= limit &&
           std::equal(magic.begin(), magic.end(), bytes.begin()),
       "material checkpoint header");
  need(get64(bytes, bytes.size() - 8) ==
           checksum(bytes.first(bytes.size() - 8)),
       "material checksum");
  const auto payload = bytes.first(bytes.size() - 8);
  std::size_t pos = magic.size();
  const auto base = next(payload, pos), records = next(payload, pos),
             model = next(payload, pos), events = next(payload, pos);
  need(pos == payload.size(), "checkpoint trailing bytes");
  auto result = deserialize_canonical_checkpoint(base);
  need(result.packets_.slot_count() == 0 && result.packets_.alive_count() == 0,
       "duplicate legacy phase authority");
  result.config_.material_phase_enabled = true;
  MaterialPhaseContext c;
  std::istringstream in(text(records));
  auto &r = c.schedule;
  need(bool(in >> r.trajectory >> r.path >> r.level >> r.dt >> r.start),
       "schedule syntax");
  r.model = text(model);
  r.count = 0;
  r.wire.clear();
  c.last_events = text(events);
  std::size_t n;
  need(bool(in >> n) && n > 0 && n <= 16, "material record count");
  for (std::size_t j = 0; j < n; ++j) {
    MaterialPhasePacket p;
    Scalar mass, heat, structural, stored, thermal;
    std::size_t count;
    std::string phase;
    need(bool(in >> p.handle.id.value >> p.handle.generation >>
              p.mechanics_id >> mass >> heat >> structural >> stored >>
              thermal >> count) &&
             count > 0 && count <= 64,
         "material record syntax");
    for (std::size_t k = 0; k < count; ++k) {
      std::uint64_t id;
      Scalar amount;
      need(bool(in >> id >> amount) && amount > 0, "composition syntax");
      p.composition.add(CompoundId{id}, amount);
    }
    need(bool(in >> phase), "missing material phase");
    const auto raw = unhex(phase);
    need(raw.size() == 102, "phase payload size");
    std::copy(raw.begin(), raw.end(), p.phase.begin());
    p.mass = Mass::from_raw(mass);
    p.heat_capacity = HeatCapacity::from_raw(heat);
    p.structural_energy = Energy::from_raw(structural);
    p.stored_energy = Energy::from_raw(stored);
    p.thermal_energy = Energy::from_raw(thermal);
    p.elements = inventory_of(p.composition, result.compounds_);
    need(result.packets_.material_phase_.emplace(p.handle.id, p).second,
         "duplicate material ID");
  }
  std::size_t count;
  need(bool(in >> count) && count == n, "binding count");
  for (std::size_t j = 0; j < count; ++j) {
    MaterialPhaseBinding b;
    need(bool(in >> b.mechanics_id >> b.material.id.value >>
              b.material.generation),
         "binding syntax");
    c.binding.push_back(b);
  }
  c.baseline = decode_totals(in);
  std::string extra;
  need(!(in >> extra), "record trailing tokens");
  result.packets_.alive_count_ = n;
  result.material_phase_ = std::move(c);
  result.validate_material_phase();
  canonical_input(result.material_phase_request());
  need(result.material_phase_checkpoint() == Bytes(bytes.begin(), bytes.end()),
       "noncanonical material checkpoint");
  return result;
}
std::uint64_t World::material_phase_hash() const {
  auto copy = *this;
  copy.material_phase_->last_events.clear();
  return checksum(copy.material_phase_checkpoint());
}
} // namespace mls
#endif
