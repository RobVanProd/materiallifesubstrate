#pragma once

#include <algorithm>
#include <cstdint>
#include <exception>
#include <functional>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace mls::test {

struct Case final {
    std::string_view name;
    void (*function)();
};

inline std::vector<Case>& registry() {
    static std::vector<Case> cases;
    return cases;
}

class Registrar final {
public:
    Registrar(std::string_view name, void (*function)()) {
        registry().push_back(Case{name, function});
    }
};

class Failure final : public std::runtime_error {
public:
    Failure(const char* file, int line, std::string message)
        : std::runtime_error(format(file, line, std::move(message))) {}

private:
    [[nodiscard]] static std::string format(const char* file, int line, std::string message) {
        std::ostringstream stream;
        stream << file << ':' << line << ": " << message;
        return stream.str();
    }
};

inline void require(bool condition, const char* expression, const char* file, int line) {
    if (!condition) {
        throw Failure(file, line, std::string("requirement failed: ") + expression);
    }
}

template <typename Left, typename Right>
void require_equal(
    const Left& left,
    const Right& right,
    const char* left_expression,
    const char* right_expression,
    const char* file,
    int line) {
    if (!(left == right)) {
        throw Failure(
            file,
            line,
            std::string("equality failed: ") + left_expression + " == " + right_expression);
    }
}

template <typename Exception, typename Function>
void require_throws(
    Function&& function,
    const char* expression,
    const char* exception_name,
    const char* file,
    int line) {
    try {
        std::invoke(std::forward<Function>(function));
    } catch (const Exception&) {
        return;
    } catch (const std::exception& error) {
        throw Failure(
            file,
            line,
            std::string("wrong exception for ") + expression + "; expected " + exception_name +
                ", received: " + error.what());
    } catch (...) {
        throw Failure(file, line, std::string("non-standard exception for ") + expression);
    }
    throw Failure(
        file,
        line,
        std::string("no exception for ") + expression + "; expected " + exception_name);
}

class SplitMix64 final {
public:
    explicit constexpr SplitMix64(std::uint64_t seed) noexcept : state_(seed) {}

    [[nodiscard]] constexpr std::uint64_t next() noexcept {
        state_ += UINT64_C(0x9e3779b97f4a7c15);
        auto value = state_;
        value = (value ^ (value >> 30U)) * UINT64_C(0xbf58476d1ce4e5b9);
        value = (value ^ (value >> 27U)) * UINT64_C(0x94d049bb133111eb);
        return value ^ (value >> 31U);
    }

    [[nodiscard]] std::uint64_t below(std::uint64_t stop) {
        if (stop == 0) {
            throw std::invalid_argument("SplitMix64 bound must be positive");
        }
        const auto threshold = (std::uint64_t{0} - stop) % stop;
        while (true) {
            const auto value = next();
            if (value >= threshold) {
                return value % stop;
            }
        }
    }

    [[nodiscard]] std::int64_t integer(std::int64_t low, std::int64_t high) {
        if (high < low) {
            throw std::invalid_argument("SplitMix64 interval is empty");
        }
        const auto width = static_cast<std::uint64_t>(high - low) + UINT64_C(1);
        return low + static_cast<std::int64_t>(below(width));
    }

private:
    std::uint64_t state_;
};

inline int run(int argc, char** argv) {
    std::string_view selected;
    bool list_only = false;
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument(argv[index]);
        if (argument == "--list") {
            list_only = true;
        } else if (argument == "--test" && index + 1 < argc) {
            selected = argv[++index];
        } else {
            std::cerr << "unknown or incomplete argument: " << argument << '\n';
            return 2;
        }
    }

    auto cases = registry();
    std::ranges::sort(cases, {}, &Case::name);
    if (list_only) {
        for (const auto& test_case : cases) {
            std::cout << test_case.name << '\n';
        }
        return 0;
    }

    std::size_t executed = 0;
    std::size_t failed = 0;
    for (const auto& test_case : cases) {
        if (!selected.empty() && selected != test_case.name) {
            continue;
        }
        ++executed;
        try {
            test_case.function();
            std::cout << "[PASS] " << test_case.name << '\n';
        } catch (const std::exception& error) {
            ++failed;
            std::cerr << "[FAIL] " << test_case.name << "\n  " << error.what() << '\n';
        } catch (...) {
            ++failed;
            std::cerr << "[FAIL] " << test_case.name << "\n  unknown exception\n";
        }
    }

    if (!selected.empty() && executed == 0) {
        std::cerr << "no test named " << selected << '\n';
        return 2;
    }
    std::cout << "MLS validation: " << (executed - failed) << '/' << executed << " passed\n";
    return failed == 0 ? 0 : 1;
}

} // namespace mls::test

#define MLS_TEST_CONCATENATE_IMPL(left, right) left##right
#define MLS_TEST_CONCATENATE(left, right) MLS_TEST_CONCATENATE_IMPL(left, right)
#define MLS_TEST(name)                                                                            \
    static void MLS_TEST_CONCATENATE(mls_test_function_, __LINE__)();                             \
    static const ::mls::test::Registrar MLS_TEST_CONCATENATE(mls_test_registrar_, __LINE__)(      \
        name, &MLS_TEST_CONCATENATE(mls_test_function_, __LINE__));                               \
    static void MLS_TEST_CONCATENATE(mls_test_function_, __LINE__)()

#define MLS_REQUIRE(expression)                                                                   \
    ::mls::test::require(static_cast<bool>(expression), #expression, __FILE__, __LINE__)

#define MLS_REQUIRE_EQ(left, right)                                                               \
    ::mls::test::require_equal((left), (right), #left, #right, __FILE__, __LINE__)

#define MLS_REQUIRE_THROWS(exception_type, expression)                                            \
    ::mls::test::require_throws<exception_type>(                                                  \
        [&]() { static_cast<void>(expression); }, #expression, #exception_type, __FILE__, __LINE__)
