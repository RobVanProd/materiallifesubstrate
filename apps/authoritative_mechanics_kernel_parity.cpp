#include "mls/authoritative_mechanics_kernel_parity_lab.hpp"
#include <fstream>
#include <iostream>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <sys/resource.h>
#endif
int main(int argc, char **argv) {
  if (argc != 3) {
    std::cerr << "usage: kernel input output\n";
    return 2;
  }
  // The frozen 2 GiB backstop is per process, not an allocator-timing gate.
#ifdef _WIN32
  HANDLE job = CreateJobObjectW(nullptr, nullptr);
  JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
  limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY;
  limits.ProcessMemoryLimit = static_cast<SIZE_T>(2ULL * 1024 * 1024 * 1024);
  if (!job ||
      !SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits,
                               sizeof(limits)) ||
      !AssignProcessToJobObject(job, GetCurrentProcess())) {
    std::cerr << "resource_backstop_setup_failed\n";
    return 2;
  }
#else
  rlimit limits{2ULL * 1024 * 1024 * 1024, 2ULL * 1024 * 1024 * 1024};
  if (setrlimit(RLIMIT_AS, &limits) != 0) {
    std::cerr << "resource_backstop_setup_failed\n";
    return 2;
  }
#endif
  std::ifstream in(argv[1], std::ios::binary);
  std::ofstream out(argv[2], std::ios::binary);
  if (!in || !out)
    return 2;
  return mls::kernel_parity::run(in, out);
}
