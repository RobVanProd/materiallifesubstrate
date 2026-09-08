#include "mls/authoritative_mechanics_kernel_parity_lab.hpp"
#include "mls/checkpoint.hpp"
#include "mls/world.hpp"

#ifdef MLS_RESEARCH_WORLD_MECHANICS
#include <algorithm>
#include <bit>
#include <charconv>
#include <limits>
#include <sstream>
#include <string_view>
#include <utility>

namespace mls {
namespace {
using Bytes = std::vector<std::uint8_t>;
constexpr std::string_view magic = "MLS-WORLD-B96-RESEARCH-v1\n";
constexpr std::size_t checkpoint_limit = 16U * 1024U * 1024U;
void need(bool ok, const char *why) {
  if (!ok)
    throw std::invalid_argument(why);
}
std::uint64_t integer(std::string_view s) {
  std::uint64_t value{};
  auto [p, ec] = std::from_chars(s.data(), s.data() + s.size(), value);
  need(ec == std::errc{} && p == s.data() + s.size(),
       "invalid unsigned protocol integer");
  return value;
}
Bytes unhex(std::string_view s) {
  need(s.size() % 2 == 0, "odd wire length");
  Bytes b;
  b.reserve(s.size() / 2);
  auto digit = [](char c) -> unsigned {
    if (c >= '0' && c <= '9')
      return static_cast<unsigned>(c - '0');
    if (c >= 'a' && c <= 'f')
      return static_cast<unsigned>(c - 'a' + 10);
    throw std::invalid_argument("noncanonical lowercase hex");
  };
  for (std::size_t i = 0; i < s.size(); i += 2)
    b.push_back(static_cast<std::uint8_t>(16 * digit(s[i]) + digit(s[i + 1])));
  return b;
}
std::uint64_t read64(std::span<const std::uint8_t> b, std::size_t at) {
  need(at <= b.size() && b.size() - at >= 8, "truncated research bytes");
  std::uint64_t n{};
  for (unsigned k = 0; k < 8; ++k)
    n |= static_cast<std::uint64_t>(b[at + k]) << (8 * k);
  return n;
}
void put64(Bytes &b, std::uint64_t n) {
  for (unsigned k = 0; k < 8; ++k)
    b.push_back(static_cast<std::uint8_t>(n >> (8 * k)));
}
struct WireInfo {
  std::int64_t time{};
  std::vector<std::pair<std::uint64_t, std::uint64_t>> identity;
};
WireInfo wire_info(const std::string &wire) {
  const auto b = unhex(wire);
  need(b.size() >= 52, "short mechanics wire");
  auto count = read64(b, 44);
  need(count > 0 && count <= 16 && b.size() == 52 + 118 * count,
       "unregistered mechanics packet count");
  WireInfo out;
  out.time = std::bit_cast<std::int64_t>(read64(b, 36));
  for (std::size_t i = 0; i < count; ++i)
    out.identity.emplace_back(read64(b, 52 + 118 * i), read64(b, 60 + 118 * i));
  return out;
}
std::string initial_line(const ResearchMechanicsInput &r) {
  return "S " + std::to_string(r.start) + " " + r.wire + " -\n";
}
std::string normalize_model(std::istream &in) {
  std::vector<std::string> words;
  std::string word;
  while (in >> word) {
    need(word.size() <= 65536 && words.size() < 8192, "model evidence limit");
    auto pos = word[0] == '-' ? 1U : 0U;
    need(pos < word.size(), "empty model integer");
    need(std::all_of(word.begin() + pos, word.end(),
                     [](char c) { return c >= '0' && c <= '9'; }),
         "model integer syntax");
    need(word[pos] != '0' || word.size() == 1, "noncanonical model integer");
    words.push_back(word);
  }
  need(!words.empty(), "missing model");
  auto nr = integer(words.front());
  need(nr > 0 && nr <= 64 && words.size() == 1 + nr * 10 + nr * nr,
       "model shape");
  std::string result;
  for (const auto &w : words) {
    result += w;
    result += ' ';
  }
  result.back() = '\n';
  return result;
}
void validate_input(const ResearchMechanicsInput &r) {
  need(r.dt > 0 && r.dt % 2 == 0 && r.start >= 0 && r.count >= 0 &&
           r.count <= std::numeric_limits<int>::max() - r.start,
       "invalid research schedule");
  need(r.level >= 0 && r.level < 5 && (r.path == "KDK" || r.path == "CONTROL"),
       "unregistered research profile");
  need(!r.trajectory.empty() && r.trajectory.size() <= 128 &&
           r.trajectory.find_first_of(" \t\r\n") == std::string::npos,
       "trajectory identity");
  const auto info = wire_info(r.wire);
  need(info.time == detail::checked_multiply(r.start, r.dt),
       "mechanics clock/step mismatch");
  std::istringstream model(r.model);
  need(normalize_model(model) == r.model, "noncanonical model wire");
  std::istringstream in(research_kernel_request(r, 0));
  std::ostringstream out;
  need(kernel_parity::run(in, out) == 0 && out.str() == initial_line(r),
       "kernel rejected research import");
}
std::uint64_t checksum(std::span<const std::uint8_t> bytes) {
  std::uint64_t h = 14695981039346656037ULL;
  for (auto b : bytes)
    h = (h ^ b) * 1099511628211ULL;
  return h;
}
void field(Bytes &out, std::span<const std::uint8_t> b) {
  need(b.size() <= checkpoint_limit, "checkpoint field limit");
  put64(out, b.size());
  out.insert(out.end(), b.begin(), b.end());
}
void field(Bytes &out, const std::string &s) {
  field(out,
        std::span(reinterpret_cast<const std::uint8_t *>(s.data()), s.size()));
}
std::span<const std::uint8_t> next_field(std::span<const std::uint8_t> bytes,
                                         std::size_t &pos) {
  const auto n = read64(bytes, pos);
  pos += 8;
  need(n <= checkpoint_limit && pos <= bytes.size() && n <= bytes.size() - pos,
       "truncated checkpoint field");
  auto result = bytes.subspan(pos, static_cast<std::size_t>(n));
  pos += static_cast<std::size_t>(n);
  return result;
}
std::string string_of(std::span<const std::uint8_t> b) {
  return std::string(reinterpret_cast<const char *>(b.data()), b.size());
}
} // namespace

ResearchMechanicsInput read_research_mechanics_input(std::istream &in) {
  ResearchMechanicsInput r;
  std::string mode;
  in >> mode >> r.trajectory >> r.level >> r.dt >> r.count >> r.start >>
      r.path >> r.wire;
  need(bool(in) && mode == "run", "research run protocol");
  r.model = normalize_model(in);
  validate_input(r);
  return r;
}
std::string research_kernel_request(const ResearchMechanicsInput &r,
                                    int count) {
  std::ostringstream out;
  out << "run " << r.trajectory << ' ' << r.level << ' ' << r.dt << ' ' << count
      << ' ' << r.start << ' ' << r.path << '\n'
      << r.wire << '\n'
      << r.model;
  return out.str();
}
void World::attach_research_mechanics(const ResearchMechanicsInput &input) {
#ifdef MLS_RESEARCH_MATERIAL_PHASE
  need(!config_.material_phase_enabled, "material phase owns the only mechanics state");
#endif
  need(config_.research_mechanics_enabled, "research runtime enable required");
  need(!research_mechanics_, "research mechanics already attached");
  need(config_.physical_timestep.raw() == input.dt &&
           config_.physical_time_scale == PhysicalTimeScale{1, 1'000'000'000},
       "World/kernel clock unit mismatch");
  validate_input(input);
  const auto time = wire_info(input.wire).time;
  need((tick_ == 0 && physical_time_.raw() == 0) ||
           (tick_ == static_cast<Tick>(input.start) &&
            physical_time_.raw() == time),
       "World import clock mismatch");
  auto staged = *this;
  staged.research_mechanics_ = ResearchMechanicsContext{input, {}};
  staged.research_mechanics_->request.count = 0;
  staged.tick_ = static_cast<Tick>(input.start);
  staged.physical_time_ = Time::from_raw(time);
  *this = std::move(staged);
}
ResearchMechanicsSnapshot World::research_mechanics() const {
  need(research_mechanics_.has_value(), "no research mechanics attached");
  const auto &r = research_mechanics_->request;
  const auto info = wire_info(r.wire);
  ResearchMechanicsSnapshot s{
      r.wire, research_mechanics_->last_events, {}, info.time, r.start};
  for (const auto &id : info.identity)
    s.ids.push_back(id.first);
  return s; // A copy; no mutable phase or observer alias is exposed.
}
void World::step_research_mechanics(Tick count) {
  need(research_mechanics_.has_value(),
       "enabled research World has no mechanics state");
  need(tick_ <= static_cast<Tick>(std::numeric_limits<int>::max()) &&
           count <= static_cast<Tick>(std::numeric_limits<int>::max()) - tick_,
       "research step index overflow");
  const auto final_time = detail::checked_multiply(
      static_cast<Scalar>(tick_ + count), config_.physical_timestep.raw());
  if (count == 0)
    return;
  auto staged = *this;
  std::string committed;
  for (Tick i = 0; i < count; ++i) {
    auto &r = staged.research_mechanics_->request;
    const auto prior = wire_info(r.wire);
    std::istringstream input(research_kernel_request(r, 1));
    std::ostringstream output;
    const auto rc = kernel_parity::run(input, output);
    const auto record = output.str();
    const auto prefix = initial_line(r);
    need(rc == 0 && record.starts_with(prefix),
         "kernel protocol/error failure");
    const auto body = record.substr(prefix.size());
    if (body.starts_with("REJECT ") ||
        body.find("\nREJECT ") != std::string::npos)
      throw ResearchMechanicsRejection(body);
    std::istringstream lines(body);
    std::string line, wire;
    int states = 0;
    while (std::getline(lines, line)) {
      need(!line.empty() &&
               std::string("GTES").find(line[0]) != std::string::npos,
           "unexpected kernel record");
      if (line.starts_with("S ")) {
        std::istringstream row(line);
        std::string kind, digest;
        int step{};
        row >> kind >> step >> wire >> digest;
        need(bool(row) && step == r.start + 1 && digest.size() == 64,
             "kernel commit identity");
        ++states;
      }
    }
    need(states == 1, "kernel must commit exactly one step");
    const auto next = wire_info(wire);
    need(next.identity == prior.identity,
         "kernel changed packet identity/mass");
    const auto next_time = detail::checked_add(prior.time, r.dt);
    need(next.time == next_time, "kernel clock delta mismatch");
    r.wire = wire;
    ++r.start;
    staged.tick_ += 1;
    staged.physical_time_ = Time::from_raw(next_time);
    committed += body;
    need(committed.size() <= checkpoint_limit, "research event buffer limit");
  }
  need(staged.physical_time_.raw() == final_time,
       "World/kernel clock diverged");
  staged.research_mechanics_->last_events = std::move(committed);
  *this =
      std::move(staged); // The only commit; rejection cannot advance clocks.
}
std::vector<std::uint8_t> World::research_unrelated_checkpoint() const {
  auto legacy = *this;
  legacy.research_mechanics_.reset();
  legacy.config_.research_mechanics_enabled = false;
  legacy.tick_ = 0;
  legacy.physical_time_ = Time{};
  return serialize_canonical_checkpoint(legacy);
}
std::vector<std::uint8_t> World::research_checkpoint() const {
  need(research_mechanics_.has_value() && config_.research_mechanics_enabled,
       "no research checkpoint state");
  const auto &r = research_mechanics_->request;
  need(tick_ == static_cast<Tick>(r.start) &&
           physical_time_.raw() == wire_info(r.wire).time,
       "checkpoint clock mismatch");
  auto legacy = *this;
  legacy.research_mechanics_.reset();
  legacy.config_.research_mechanics_enabled = false;
  const auto base = serialize_canonical_checkpoint(legacy);
  Bytes out(magic.begin(), magic.end());
  field(out, base);
  field(out, research_kernel_request(r, 0));
  field(out, research_mechanics_->last_events);
  need(out.size() + 8 <= checkpoint_limit, "research checkpoint size limit");
  put64(out, checksum(out));
  return out;
}
World World::restore_research_checkpoint(std::span<const std::uint8_t> bytes) {
  need(bytes.size() >= magic.size() + 32 && bytes.size() <= checkpoint_limit &&
           std::equal(magic.begin(), magic.end(), bytes.begin()),
       "research checkpoint magic/size");
  need(read64(bytes, bytes.size() - 8) ==
           checksum(bytes.first(bytes.size() - 8)),
       "research checkpoint checksum");
  const auto payload = bytes.first(bytes.size() - 8);
  std::size_t pos = magic.size();
  const auto base = next_field(payload, pos);
  const auto request = string_of(next_field(payload, pos));
  const auto events = string_of(next_field(payload, pos));
  need(pos == payload.size(), "research checkpoint trailing bytes");
  auto result = deserialize_canonical_checkpoint(base);
  result.config_.research_mechanics_enabled = true;
  std::istringstream input(request);
  const auto r = read_research_mechanics_input(input);
  need(r.count == 0 && result.tick_ == static_cast<Tick>(r.start) &&
           result.physical_time_.raw() == wire_info(r.wire).time,
       "research checkpoint schedule mismatch");
  result.attach_research_mechanics(r);
  result.research_mechanics_->last_events = events;
  need(result.research_checkpoint() == Bytes(bytes.begin(), bytes.end()),
       "noncanonical research checkpoint");
  return result;
}
} // namespace mls
#endif
