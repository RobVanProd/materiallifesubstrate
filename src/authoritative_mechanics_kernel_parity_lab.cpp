#include "mls/authoritative_mechanics_kernel_parity_lab.hpp"
#include <algorithm>
#include <bit>
#include <boost/multiprecision/cpp_int.hpp>
#include <boost/rational.hpp>
#include <cfenv>
#include <cmath>
#include <iomanip>
#include <istream>
#include <limits>
#include <map>
#include <ostream>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace mls::kernel_parity {
namespace {
using I = boost::multiprecision::cpp_int;
using Q = boost::rational<I>;
using V = std::array<Q, 3>;
using Bytes = std::vector<std::uint8_t>;
void need(bool b, const char *s) {
  if (!b)
    throw std::runtime_error(s);
}
I mag(I x) { return x < 0 ? -x : x; }
int width(const I &x) {
  return x == 0 ? 0 : static_cast<int>(boost::multiprecision::msb(mag(x))) + 1;
}
Q absq(Q x) { return x < Q(0) ? -x : x; }
Q pow2(int e) { return e >= 0 ? Q(I(1) << e) : Q(I(1), I(1) << -e); }
void le(Bytes &b, std::uint64_t v, int n) {
  for (int i = 0; i < n; ++i) {
    b.push_back(static_cast<std::uint8_t>(v & 255));
    v >>= 8;
  }
}
void str(Bytes &b, const std::string &s) {
  b.insert(b.end(), s.begin(), s.end());
}
void frame(Bytes &b, const std::string &s) {
  le(b, s.size(), 8);
  str(b, s);
}
std::string hex(const Bytes &b) {
  std::ostringstream s;
  s << std::hex << std::setfill('0');
  for (auto x : b)
    s << std::setw(2) << static_cast<unsigned>(x);
  return s.str();
}
Bytes unhex(const std::string &s) {
  need(s.size() % 2 == 0, "hex width");
  Bytes b;
  for (std::size_t i = 0; i < s.size(); i += 2) {
    auto t = s.substr(i, 2);
    std::size_t k = 0;
    auto v = std::stoul(t, &k, 16);
    need(k == 2, "hex digit");
    b.push_back(static_cast<std::uint8_t>(v));
  }
  return b;
}
// FIPS SHA-256, unsigned 32-bit modular arithmetic; checked against hashlib.
std::string hash(Bytes b) {
  static constexpr std::uint32_t k[] = {
      0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
      0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
      0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
      0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
      0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
      0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
      0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
      0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
      0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
  std::array<std::uint32_t, 8> h = {0x6a09e667, 0xbb67ae85, 0x3c6ef372,
                                    0xa54ff53a, 0x510e527f, 0x9b05688c,
                                    0x1f83d9ab, 0x5be0cd19};
  auto bits = static_cast<std::uint64_t>(b.size()) * 8;
  b.push_back(128);
  while (b.size() % 64 != 56)
    b.push_back(0);
  for (int j = 7; j >= 0; --j)
    b.push_back(static_cast<std::uint8_t>(bits >> (8 * j)));
  for (std::size_t off = 0; off < b.size(); off += 64) {
    std::array<std::uint32_t, 64> w{};
    for (int j = 0; j < 16; ++j)
      for (int a = 0; a < 4; ++a)
        w[j] = (w[j] << 8) | b[off + static_cast<std::size_t>(4 * j + a)];
    for (int j = 16; j < 64; ++j) {
      auto x = w[j - 15], y = w[j - 2];
      w[j] = w[j - 16] + (std::rotr(x, 7) ^ std::rotr(x, 18) ^ (x >> 3)) +
             w[j - 7] + (std::rotr(y, 17) ^ std::rotr(y, 19) ^ (y >> 10));
    }
    auto a = h[0], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7],
         bb = h[1];
    for (int j = 0; j < 64; ++j) {
      auto t1 = hh + (std::rotr(e, 6) ^ std::rotr(e, 11) ^ std::rotr(e, 25)) +
                ((e & f) ^ (~e & g)) + k[j] + w[j];
      auto t2 = (std::rotr(a, 2) ^ std::rotr(a, 13) ^ std::rotr(a, 22)) +
                ((a & bb) ^ (a & c) ^ (bb & c));
      hh = g;
      g = f;
      f = e;
      e = d + t1;
      d = c;
      c = bb;
      bb = a;
      a = t1 + t2;
    }
    h[0] += a;
    h[1] += bb;
    h[2] += c;
    h[3] += d;
    h[4] += e;
    h[5] += f;
    h[6] += g;
    h[7] += hh;
  }
  Bytes out;
  for (auto x : h)
    for (int j = 3; j >= 0; --j)
      out.push_back(static_cast<std::uint8_t>(x >> (8 * j)));
  return hex(out);
}
Q value(const B96 &b) {
  I s = 0;
  for (int i = 5; i < 17; ++i) {
    s <<= 8;
    s += b.wire[i];
  }
  int e = static_cast<int>(b.wire[3]) + 256 * static_cast<int>(b.wire[4]);
  if (e >= 32768)
    e -= 65536;
  return (b.wire[0] ? -Q(s) : Q(s)) * pow2(e - 95);
}
int log2q(const Q &x) {
  int e = width(x.numerator()) - width(x.denominator());
  if (x < pow2(e))
    --e;
  return e;
}
Q rounded(Q x, int bits) {
  if (x == Q(0))
    return x;
  bool neg = x < Q(0);
  x = absq(x);
  int e = log2q(x);
  Q y = x / pow2(e - bits + 1);
  I n = y.numerator() / y.denominator(), r = y.numerator() % y.denominator();
  if (2 * r > y.denominator() ||
      (2 * r == y.denominator() && static_cast<bool>(n & 1)))
    ++n;
  Q z = Q(n) * pow2(e - bits + 1);
  return neg ? -z : z;
}
B96 rn(Q x) {
  B96 b;
  b.wire[1] = 96;
  if (x == Q(0))
    return b;
  Q z = rounded(x, 96);
  int e = log2q(absq(z));
  need(e >= -16382, "phase_range_failure:underflow");
  need(e <= 16383, "phase_range_failure:overflow");
  b.wire[0] = z < Q(0) ? 1 : 0;
  auto u = static_cast<std::uint16_t>(e);
  b.wire[3] = static_cast<std::uint8_t>(u & 255);
  b.wire[4] = static_cast<std::uint8_t>(u >> 8);
  I n = (absq(z) / pow2(e - 95)).numerator();
  for (int i = 16; i >= 5; --i) {
    b.wire[i] = static_cast<std::uint8_t>((n & 255).convert_to<unsigned>());
    n >>= 8;
  }
  return b;
}
Q fromdouble(double x) {
  need(std::isfinite(x), "nonfinite binary64");
  auto b = std::bit_cast<std::uint64_t>(x);
  auto e = static_cast<int>((b >> 52) & 2047);
  I n = b & 0xfffffffffffffULL;
  if (e)
    n += I(1) << 52;
  Q q = Q(n) * pow2(e ? e - 1023 - 52 : -1074);
  return b >> 63 ? -q : q;
}
double todouble(Q x) {
  if (x == Q(0))
    return 0.;
  bool neg = x < Q(0);
  x = absq(x);
  int e = log2q(x);
  int quantum = std::max(e - 52, -1074);
  Q y = x / pow2(quantum);
  I n = y.numerator() / y.denominator(), r = y.numerator() % y.denominator();
  if (2 * r > y.denominator() ||
      (2 * r == y.denominator() && static_cast<bool>(n & 1)))
    ++n;
  double v = std::ldexp(n.convert_to<double>(), quantum);
  need(std::isfinite(v), "binary64 relative conversion failed");
  return neg ? -v : v;
}
V add(V a, V b) {
  for (int i = 0; i < 3; ++i)
    a[i] += b[i];
  return a;
}
V sub(V a, V b) {
  for (int i = 0; i < 3; ++i)
    a[i] -= b[i];
  return a;
}
V cross(V a, V b) {
  return {a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
          a[0] * b[1] - a[1] * b[0]};
}
V vec(const std::array<B96, 3> &v) {
  return {value(v[0]), value(v[1]), value(v[2])};
}
Q dot(V a, V b) {
  Q q;
  for (int i = 0; i < 3; ++i)
    q += a[i] * b[i];
  return q;
}
void unsigned_bytes(Bytes &b, I x) {
  need(x >= 0, "unsigned encoding");
  Bytes t;
  while (x != 0) {
    t.push_back(static_cast<std::uint8_t>((x & 255).convert_to<unsigned>()));
    x >>= 8;
  }
  le(b, t.size(), 8);
  b.insert(b.end(), t.rbegin(), t.rend());
}
void fraction(Bytes &b, Q x) {
  b.push_back(x < Q(0) ? 1 : 0);
  unsigned_bytes(b, mag(x.numerator()));
  unsigned_bytes(b, x.denominator());
}
std::string qhash(Q q) {
  Bytes b;
  fraction(b, q);
  return hash(b);
}
std::string vhash(V v) {
  Bytes b;
  for (auto q : v)
    fraction(b, q);
  return hash(b);
}
std::string dyadic(Q q) {
  if (q == Q(0))
    return "0";
  I n = mag(q.numerator());
  int t = static_cast<int>(boost::multiprecision::lsb(n));
  n >>= t;
  need((q.denominator() & (q.denominator() - 1)) == 0, "nondyadic observer");
  int e = t - width(q.denominator()) + 1;
  std::ostringstream s;
  if (q < Q(0))
    s << '-';
  s << "0x" << std::hex << n << '@' << std::dec << e;
  return s.str();
}
void validate(const State &s) {
  std::uint64_t prior = 0;
  for (auto &p : s.packets) {
    need(p.id > prior && p.mass > 0, "invalid packet ordering or mass");
    prior = p.id;
    for (int k = 0; k < 6; ++k) {
      auto &b = k < 3 ? p.x[k] : p.p[k - 3];
      need(b.wire[0] <= 1 && b.wire[1] == 96 && b.wire[2] == 0,
           "component profile");
      need(rn(value(b)).wire == b.wire, "noncanonical component");
      need(absq(value(b)) < pow2(k < 3 ? 48 : 40),
           "raw state evidence bound exceeded");
    }
  }
}
Bytes encode(const State &s) {
  validate(s);
  Bytes b;
  str(b, std::string("MLS-BOUNDED-BINARY-PHASE-v1\0", 28));
  le(b, 1, 2);
  le(b, 96, 2);
  le(b, static_cast<std::uint16_t>(-16382), 2);
  le(b, 16383, 2);
  le(b, static_cast<std::uint64_t>(s.time), 8);
  le(b, s.packets.size(), 8);
  for (auto &p : s.packets) {
    le(b, p.id, 8);
    le(b, static_cast<std::uint64_t>(p.mass), 8);
    for (auto &v : {p.x, p.p})
      for (auto &x : v)
        b.insert(b.end(), x.wire.begin(), x.wire.end());
  }
  return b;
}
State decode(const Bytes &b) {
  std::string magic("MLS-BOUNDED-BINARY-PHASE-v1\0", 28);
  need(b.size() >= magic.size() + 24 &&
           std::equal(magic.begin(), magic.end(), b.begin()),
       "state magic");
  std::size_t c = magic.size();
  auto read = [&](int n) {
    need(c + static_cast<std::size_t>(n) <= b.size(), "truncated wire");
    std::uint64_t v = 0;
    for (int k = 0; k < n; ++k)
      v |= static_cast<std::uint64_t>(b[c++]) << (8 * k);
    return v;
  };
  need(read(2) == 1 && read(2) == 96 &&
           read(2) == static_cast<std::uint16_t>(-16382) && read(2) == 16383,
       "state profile");
  State s;
  s.time = std::bit_cast<std::int64_t>(read(8));
  auto count = read(8);
  need(count < 100000 && b.size() == c + count * 118, "wire count");
  for (std::uint64_t i = 0; i < count; ++i) {
    Packet p;
    p.id = read(8);
    p.mass = std::bit_cast<std::int64_t>(read(8));
    for (auto *v : {&p.x, &p.p})
      for (auto &x : *v)
        for (auto &byte : x.wire)
          byte = static_cast<std::uint8_t>(read(1));
    s.packets.push_back(p);
  }
  need(encode(s) == b, "wire roundtrip");
  return s;
}
struct Relation {
  int index{};
  std::size_t i{}, j{};
  V reference{};
  double rest{};
};
struct Model {
  std::vector<Relation> relations;
  std::vector<std::vector<double>> h;
};
struct Geometry {
  V raw;
  std::array<double, 3> si{};
  double length{}, extension{}, g{};
};
using DD = std::pair<double, double>;
DD quick(double a, double b) {
  double s = a + b;
  return {s, b - (s - a)};
}
DD sum(double a, double b) {
  double s = a + b, v = s - a;
  return {s, (a - (s - v)) + (b - v)};
}
DD diff(double a, double b) {
  double s = a - b, v = a - s;
  return {s, (a - (s + v)) + (v - b)};
}
DD da(DD a, DD b) {
  double s = a.first + b.first, v = s - a.first,
         e = (a.first - (s - v)) + (b.first - v);
  e += a.second + b.second;
  return quick(s, e);
}
DD dm(DD a, DD b) {
  double p = a.first * b.first, e = std::fma(a.first, b.first, -p);
  e += a.first * b.second + a.second * b.first;
  e += a.second * b.second;
  return quick(p, e);
}
DD divide(DD n, DD d) {
  DD q = {n.first / d.first, 0.};
  for (int i = 0; i < 2; ++i) {
    auto p = dm(d, q);
    auto r = da(n, {-p.first, -p.second});
    q = da(q, {r.first / d.first, 0.});
  }
  return quick(q.first, q.second);
}
double norm(std::array<double, 3> a) {
  double s = std::max({std::abs(a[0]), std::abs(a[1]), std::abs(a[2])});
  if (s == 0.)
    return 0.;
  for (auto &x : a)
    x /= s;
  double q = a[0] * a[0];
  q += a[1] * a[1];
  q += a[2] * a[2];
  return s * std::sqrt(q);
}
V offset(const State &s, const Relation &r) {
  return sub(vec(s.packets[r.j].x), vec(s.packets[r.i].x));
}
// Exact aligned integer ledger, identical reserve semantics to Python.
struct Scratch {
  int observed = 0;
  static constexpr int limit = 4 * (96 + 16383 + 16382) + 64;
  void reserve(int w) {
    observed = std::max(observed, w);
    need(w <= limit, "domain_scratch_bound_exceeded");
  }
  I obs(I a) {
    reserve(width(a));
    return a;
  }
  I plus(I a, I b) {
    if (a == 0)
      return obs(b);
    if (b == 0)
      return obs(a);
    reserve(std::max(width(a), width(b)) + 1);
    return obs(a + b);
  }
  I minus(I a, I b) { return plus(a, -b); }
  I mul(I a, I b) {
    if (a == 0 || b == 0)
      return obs(0);
    reserve(width(a) + width(b));
    return obs(a * b);
  }
  I shift(I a, int n) {
    if (a == 0)
      return obs(0);
    reserve(width(a) + n);
    return obs(a << n);
  }
};
struct DomainInfo {
  bool safe{};
  std::string minimum;
  Q lhs{}, rhs{};
  int bits{};
};
struct DomainFailure : std::runtime_error {
  int relation;
  DomainInfo info;
  DomainFailure(int r, DomainInfo i)
      : std::runtime_error("chord_domain_failure"), relation(r),
        info(std::move(i)) {}
};
DomainInfo certificate(V a, V b, V ref) {
  Scratch sc;
  std::array<Q, 9> vals = {a[0], a[1],   a[2],   b[0],  b[1],
                           b[2], ref[0], ref[1], ref[2]};
  std::array<I, 9> ns{};
  std::array<int, 9> es{};
  int ce = 0;
  bool first = true;
  for (int i = 0; i < 9; ++i) {
    if (vals[i] == Q(0))
      continue;
    I n = mag(vals[i].numerator());
    int t = static_cast<int>(boost::multiprecision::lsb(n));
    need((vals[i].denominator() & (vals[i].denominator() - 1)) == 0,
         "nondyadic domain");
    ns[i] = vals[i].numerator() / (I(1) << t);
    es[i] = t - width(vals[i].denominator()) + 1;
    if (first || es[i] < ce)
      ce = es[i];
    first = false;
  }
  for (int i = 0; i < 9; ++i)
    ns[i] = ns[i] == 0 ? sc.obs(0) : sc.shift(ns[i], es[i] - ce);
  std::array<I, 3> d{};
  for (int i = 0; i < 3; ++i)
    d[i] = sc.minus(ns[i + 3], ns[i]);
  I aa = 0, dd = 0, ad = 0, rr = 0, bb = 0;
  for (int i = 0; i < 3; ++i) {
    aa = sc.plus(aa, sc.mul(ns[i], ns[i]));
    dd = sc.plus(dd, sc.mul(d[i], d[i]));
    ad = sc.plus(ad, sc.mul(ns[i], d[i]));
    rr = sc.plus(rr, sc.mul(ns[i + 6], ns[i + 6]));
  }
  need(rr > 0, "zero reference relation");
  if (dd == 0 || ad >= 0) {
    bool ok = sc.shift(aa, 48) >= rr;
    return {ok, "initial", Q(aa) * pow2(2 * ce), Q(rr) * pow2(2 * ce - 48),
            sc.observed};
  }
  if (ad <= -dd) {
    for (int i = 0; i < 3; ++i)
      bb = sc.plus(bb, sc.mul(ns[i + 3], ns[i + 3]));
    bool ok = sc.shift(bb, 48) >= rr;
    return {ok, "final", Q(bb) * pow2(2 * ce), Q(rr) * pow2(2 * ce - 48),
            sc.observed};
  }
  I area = sc.minus(sc.mul(aa, dd), sc.mul(ad, ad));
  I lhs = sc.shift(area, 48), rhs = sc.mul(rr, dd);
  return {lhs >= rhs, "interior", Q(area) * pow2(4 * ce),
          Q(rhs) * pow2(4 * ce - 48), sc.observed};
}
std::pair<std::vector<Geometry>, double> force(const Model &m, const State &s) {
  std::vector<Geometry> gs;
  Q lq = value(rn(Q(1, I(128000000000LL))));
  for (auto &r : m.relations) {
    Geometry g;
    auto raw = offset(s, r);
    for (int a = 0; a < 3; ++a)
      g.raw[a] = value(rn(raw[a]));
    need(certificate(raw, raw, r.reference).safe, "force_domain_failure");
    DD numerator = {0., 0.};
    std::array<double, 3> ref{};
    for (int a = 0; a < 3; ++a) {
      need(absq(g.raw[a]) < pow2(49), "raw_relation_evidence_bound_exceeded");
      g.si[a] = todouble(value(rn(g.raw[a] * lq)));
      ref[a] = todouble(r.reference[a] / Q(I(128000000000LL)));
    }
    g.length = norm(g.si);
    need(g.length > 0. && std::isfinite(g.length), "force_domain_failure");
    for (int a = 0; a < 3; ++a)
      numerator =
          da(numerator, dm(diff(g.si[a], ref[a]), sum(g.si[a], ref[a])));
    double den = g.length + r.rest;
    need(den > 0. && std::isfinite(den), "invalid Path-B denominator");
    g.extension = divide(numerator, {den, 0.}).first;
    need(std::isfinite(g.extension), "nonfinite extension");
    gs.push_back(g);
  }
  for (std::size_t i = 0; i < gs.size(); ++i) {
    double g = 0.;
    for (std::size_t j = 0; j < gs.size(); ++j)
      g += m.h[i][j] * gs[j].extension;
    need(std::isfinite(g), "nonfinite conjugate");
    gs[i].g = g;
  }
  double u = 0.;
  for (auto &g : gs)
    u += g.extension * g.g;
  need(std::isfinite(u), "nonfinite potential");
  return {gs, 0.5 * u};
}
using Row = std::vector<std::pair<std::string, std::string>>;
void vectors(Row &row, const std::string &prefix, V v) {
  for (int i = 0; i < 3; ++i)
    row.emplace_back(prefix + "_raw_" + std::string(1, "xyz"[i]) + "_dyadic",
                     dyadic(v[i]));
}
std::string event(const std::string &kind, const Row &row) {
  Bytes b;
  str(b, std::string("MLS-BOUNDED-OBSERVER-EVENT-v2\0", 30));
  frame(b, kind);
  le(b, row.size(), 8);
  for (auto &[k, v] : row) {
    frame(b, k);
    frame(b, v);
  }
  return hash(b);
}
Row identity(const std::string &trajectory, int level, int step) {
  return {{"trajectory_id", trajectory},
          {"precision", "96"},
          {"level", std::to_string(level)},
          {"step", std::to_string(step)}};
}
void invariant(std::vector<std::string> &ev, const State &s,
               const std::string &t, int level, int step,
               const std::string &stage) {
  auto row = identity(t, level, step);
  row.emplace_back("stage", stage);
  row.emplace_back("state_hash", hash(encode(s)));
  V p{}, l{};
  for (auto &packet : s.packets) {
    p = add(p, vec(packet.p));
    l = add(l, cross(vec(packet.x), vec(packet.p)));
  }
  vectors(row, "momentum", p);
  vectors(row, "angular", l);
  ev.push_back(event("invariant", row));
}
void kick(const Model &m, State &s, std::int64_t dt,
          std::vector<std::string> &ev, const std::string &t, int level,
          int step, const std::string &stage, std::ostream &trace) {
  auto gs = force(m, s).first;
  Q c = value(rn(Q(I(dt) * 67108864, I(1000000000) * 128000000000LL)));
  for (std::size_t k = 0; k < gs.size(); ++k) {
    auto &g = gs[k];
    auto &r = m.relations[k];
    auto &pi = s.packets[r.i];
    auto &pj = s.packets[r.j];
    Q coefficient = value(rn(c * fromdouble(g.g)));
    Q alpha = value(rn(coefficient / fromdouble(g.length)));
    V impulse, oldi = vec(pi.p), oldj = vec(pj.p);
    for (int a = 0; a < 3; ++a) {
      impulse[a] = value(rn(alpha * g.raw[a]));
      need(absq(impulse[a]) < pow2(40), "raw_impulse_evidence_bound_exceeded");
      pi.p[a] = rn(oldi[a] + impulse[a]);
      pj.p[a] = rn(oldj[a] - impulse[a]);
    }
    V di = sub(vec(pi.p), oldi), dj = sub(vec(pj.p), oldj), off = offset(s, r),
      negdj{};
    for (int a = 0; a < 3; ++a)
      negdj[a] = -dj[a];
    auto row = identity(t, level, step);
    row.emplace_back("stage", stage);
    for (auto kv : Row{{"relation_index", std::to_string(r.index)},
                       {"first_id", std::to_string(pi.id)},
                       {"second_id", std::to_string(pj.id)},
                       {"length_bits",
                        std::to_string(std::bit_cast<std::uint64_t>(g.length))},
                       {"conjugate_bits",
                        std::to_string(std::bit_cast<std::uint64_t>(g.g))},
                       {"causal_offset_raw_hash", vhash(g.raw)},
                       {"exact_stored_offset_raw_hash", vhash(off)},
                       {"ideal_impulse_raw_hash", vhash(impulse)},
                       {"first_actual_impulse_raw_hash", vhash(di)},
                       {"second_actual_impulse_raw_hash", vhash(dj)}})
      row.push_back(kv);
    vectors(row, "pair_momentum_residual", add(di, dj));
    vectors(row, "stored_impulse_centrality_residual", cross(off, impulse));
    vectors(row, "first_actual_centrality_residual", cross(off, di));
    vectors(row, "second_actual_centrality_residual", cross(off, negdj));
    vectors(row, "relation_angular_residual",
            add(cross(vec(pi.x), di), cross(vec(pj.x), dj)));
    ev.push_back(event("force_audit", row));
    trace << "G " << step << ' ' << stage << ' ' << r.index;
    for (auto x : g.si)
      trace << ' ' << std::bit_cast<std::uint64_t>(x);
    trace << ' ' << std::bit_cast<std::uint64_t>(g.length) << ' '
          << std::bit_cast<std::uint64_t>(g.extension) << ' '
          << std::bit_cast<std::uint64_t>(g.g) << '\n';
  }
  validate(s);
}
void drift(const Model &m, State &s, std::int64_t dt) {
  State old = s;
  for (auto &p : s.packets) {
    Q c = value(rn(Q(dt, p.mass)));
    for (int a = 0; a < 3; ++a)
      p.x[a] = rn(value(p.x[a]) + value(rn(c * value(p.p[a]))));
  }
  for (auto &r : m.relations) {
    auto info = certificate(offset(old, r), offset(s, r), r.reference);
    if (!info.safe)
      throw DomainFailure(r.index, info);
  }
  validate(s);
}
void energy(std::vector<std::string> &ev, const Model &m, const State &s,
            const std::string &t, int level, int step) {
  Q k;
  for (auto &p : s.packets)
    k += dot(vec(p.p), vec(p.p)) /
         Q(I(8589934592LL) * 2 * p.mass); // PQ^2/MQ = 2^-33
  double uf = force(m, s).second;
  Q u = fromdouble(uf), e = k + u;
  auto row = identity(t, level, step);
  row.emplace_back("state_hash", hash(encode(s)));
  row.emplace_back("potential_binary64_bits",
                   std::to_string(std::bit_cast<std::uint64_t>(uf)));
  for (auto pair : std::vector<std::pair<std::string, Q>>{
           {"kinetic", k}, {"potential", u}, {"mechanical", e}}) {
    row.emplace_back(pair.first + "_num",
                     pair.second.numerator().convert_to<std::string>());
    row.emplace_back(pair.first + "_den",
                     pair.second.denominator().convert_to<std::string>());
    row.emplace_back(pair.first + "_hash", qhash(pair.second));
  }
  ev.push_back(event("energy", row));
}
} // namespace
int run(std::istream &in, std::ostream &out) {
  try {
    need(std::numeric_limits<double>::is_iec559 &&
             std::fegetround() == FE_TONEAREST,
         "binary64 environment");
    std::string mode;
    in >> mode;
    if (mode == "chord") {
      V a{}, b{}, ref{};
      for (auto *v : {&a, &b, &ref})
        for (auto &x : *v) {
          std::string n, d;
          in >> n >> d;
          x = Q(I(n), I(d));
        }
      auto c = certificate(a, b, ref);
      out << c.safe << ' ' << c.minimum << ' ' << c.lhs.numerator() << ' '
          << c.lhs.denominator() << ' ' << c.rhs.numerator() << ' '
          << c.rhs.denominator() << ' ' << c.bits << ' ' << Scratch::limit
          << '\n';
      return 0;
    }
    if (mode == "round") {
      std::string a, b;
      while (in >> a >> b) {
        try {
          auto z = rn(Q(I(a), I(b)));
          out << hex(Bytes(z.wire.begin(), z.wire.end())) << '\n';
        } catch (const std::exception &e) {
          out << "ERROR " << e.what() << '\n';
        }
      }
      return 0;
    }
    need(mode == "run", "protocol mode");
    std::string wire, trajectory, path;
    int level = 0, count = 0, start = 0;
    std::int64_t dt = 0;
    in >> trajectory >> level >> dt >> count >> start >> path >> wire;
    State s = decode(unhex(wire));
    Model m;
    std::size_t nr = 0;
    in >> nr;
    need(nr < 100000, "relation count");
    for (std::size_t k = 0; k < nr; ++k) {
      Relation r;
      std::uint64_t first = 0, second = 0, bits = 0;
      in >> r.index >> first >> second >> bits;
      r.rest = std::bit_cast<double>(bits);
      auto locate = [&](std::uint64_t id) {
        for (std::size_t i = 0; i < s.packets.size(); ++i)
          if (s.packets[i].id == id)
            return i;
        throw std::runtime_error("unknown endpoint");
      };
      r.i = locate(first);
      r.j = locate(second);
      for (auto &x : r.reference) {
        std::string n, d;
        in >> n >> d;
        x = Q(I(n), I(d));
      }
      m.relations.push_back(r);
    }
    m.h.resize(nr, std::vector<double>(nr));
    for (auto &row : m.h)
      for (auto &x : row) {
        std::uint64_t b = 0;
        in >> b;
        x = std::bit_cast<double>(b);
      }
    need(bool(in), "truncated model");
    need(count >= 0 && start >= 0 &&
             count <= std::numeric_limits<int>::max() - start,
         "invalid step inventory");
    out << "S " << start << ' ' << hex(encode(s)) << " -\n";
    for (int n = 1; n <= count; ++n) {
      auto old = s;
      std::vector<std::string> ev;
      std::ostringstream stage;
      int step = start + n;
      try {
        if (path == "KDK")
          need(dt % 2 == 0, "nonintegral half step");
        need(path == "KDK" || path == "CONTROL", "unknown path");
        auto label = path == "KDK" ? "first_kick" : "full_kick";
        kick(m, s, path == "KDK" ? dt / 2 : dt, ev, trajectory, level, step,
             label, stage);
        invariant(ev, s, trajectory, level, step, label);
        stage << "T " << step << ' ' << label << ' ' << hex(encode(s)) << '\n';
        drift(m, s, dt);
        invariant(ev, s, trajectory, level, step, "drift");
        stage << "T " << step << " drift " << hex(encode(s)) << '\n';
        if (path == "KDK") {
          kick(m, s, dt / 2, ev, trajectory, level, step, "second_kick", stage);
          invariant(ev, s, trajectory, level, step, "second_kick");
          stage << "T " << step << " second_kick " << hex(encode(s)) << '\n';
        }
        I time = I(s.time) + dt;
        need(time >= std::numeric_limits<std::int64_t>::min() &&
                 time <= std::numeric_limits<std::int64_t>::max(),
             "time overflow");
        s.time = time.convert_to<std::int64_t>();
        validate(s);
        invariant(ev, s, trajectory, level, step, "committed");
        energy(ev, m, s, trajectory, level, step);
        Bytes digest;
        for (auto &e : ev) {
          auto b = unhex(e);
          digest.insert(digest.end(), b.begin(), b.end());
        }
        out << stage.str();
        for (auto &e : ev)
          out << "E " << step << ' ' << e << '\n';
        out << "S " << step << ' ' << hex(encode(s)) << ' ' << hash(digest)
            << '\n';
      } catch (const std::exception &e) {
        s = old;
        if (auto *d = dynamic_cast<const DomainFailure *>(&e)) {
          auto &c = d->info;
          out << "D " << d->relation << ' ' << c.minimum << ' '
              << c.lhs.numerator() << ' ' << c.lhs.denominator() << ' '
              << c.rhs.numerator() << ' ' << c.rhs.denominator() << ' '
              << c.bits << ' ' << Scratch::limit << '\n';
        }
        out << "REJECT " << step << ' ' << e.what() << ' ' << hex(encode(s))
            << '\n';
        return 0;
      }
    }
    return 0;
  } catch (const std::exception &e) {
    out << "ERROR " << e.what() << '\n';
    return 1;
  }
}
} // namespace mls::kernel_parity
