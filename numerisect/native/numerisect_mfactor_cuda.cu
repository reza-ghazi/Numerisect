/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * numerisect-mfactor-cuda - GPU Mersenne trial factoring over q = 2kd + 1.
 *
 * WHAT THIS ADDS OVER THE CPU HELPER
 * ----------------------------------
 * numerisect_mfactor.c already sieves the k range and tests survivors with a 64-bit
 * modular exponentiation across every core. The test itself is the remaining cost, and
 * it is perfectly independent per candidate, which is what a GPU is for. This program
 * keeps the sieve on the host and moves the exponentiations to the device.
 *
 * It is an OPTIONAL accelerator. It computes nothing the CPU helper cannot, produces
 * the same tagged output, and is only used when a CUDA device is present and the
 * candidates are in range. Numerisect never requires a GPU.
 *
 * MONTGOMERY ARITHMETIC, AND THE 2^63 LIMIT
 * -----------------------------------------
 * A 128-bit division per multiply would waste the device. Montgomery multiplication
 * replaces it with two 64-bit multiplies and a shift, at the cost of working in the
 * Montgomery domain. The usual REDC bound applies: the intermediate sum must not
 * overflow 64 bits, which requires q < 2^63.
 *
 * Candidates at or above 2^63 are NOT tested here. They are reported back so the caller
 * can run them on the CPU helper, which handles them with GMP. Silently skipping them
 * would turn an untested range into an apparent absence of factors, which is the one
 * outcome this project refuses to produce.
 *
 * OUTPUT
 * ------
 * Identical to the CPU helper, plus:
 *   DEVICE:<name>        the CUDA device used
 *   DEFERRED:<n>         candidates at or above 2^63, not tested here
 *
 * Build (the Python side does this automatically, and skips it when nvcc is absent):
 *   nvcc -O3 -arch=native numerisect_mfactor_cuda.cu -o numerisect-mfactor-cuda
 */

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <utility>
#include <vector>

#define SEGMENT (1u << 26)
#define MAX_HITS 4096
#define BLOCK 256

#include "numerisect_mfactor_kernel.cu"

static uint64_t modinv_host(uint64_t a, uint64_t prime) {
  uint64_t result = 1, base = a % prime, e = prime - 2;
  while (e) {
    if (e & 1) result = (uint64_t)((__uint128_t)result * base % prime);
    base = (uint64_t)((__uint128_t)base * base % prime);
    e >>= 1;
  }
  return result;
}

static std::vector<uint32_t> odd_primes(uint64_t bound) {
  std::vector<char> composite(bound + 1, 0);
  for (uint64_t i = 3; i * i <= bound; i += 2)
    if (!composite[i])
      for (uint64_t j = i * i; j <= bound; j += 2 * i) composite[j] = 1;
  std::vector<uint32_t> primes;
  for (uint64_t i = 3; i <= bound; i += 2)
    if (!composite[i]) primes.push_back((uint32_t)i);
  return primes;
}

int main(int argc, char **argv) {
  if (argc < 4 || argc > 5) {
    fprintf(stderr,
            "usage: numerisect-mfactor-cuda <order> <k-start> <k-end> [sieve-bound]\n");
    return 2;
  }
  const uint64_t order = strtoull(argv[1], nullptr, 10);
  const uint64_t k_start = strtoull(argv[2], nullptr, 10);
  const uint64_t k_end = strtoull(argv[3], nullptr, 10);
  const uint64_t sieve_bound = argc >= 5 ? strtoull(argv[4], nullptr, 10) : 1000000ULL;
  if (order < 3 || order % 2 == 0 || k_start < 1 || k_end < k_start) {
    fprintf(stderr, "numerisect-mfactor-cuda: invalid order or k range\n");
    return 2;
  }

  int devices = 0;
  if (cudaGetDeviceCount(&devices) != cudaSuccess || devices == 0) {
    fprintf(stderr, "numerisect-mfactor-cuda: no CUDA device available\n");
    return 3;
  }
  cudaDeviceProp prop{};
  cudaGetDeviceProperties(&prop, 0);

  printf("ORDER:%llu\n", (unsigned long long)order);
  printf("K_START:%llu\n", (unsigned long long)k_start);
  printf("K_END:%llu\n", (unsigned long long)k_end);
  printf("SIEVE_BOUND:%llu\n", (unsigned long long)sieve_bound);
  printf("DEVICE:%s\n", prop.name);

  const std::vector<uint32_t> primes = odd_primes(sieve_bound);
  /* Montgomery needs q < 2^63; beyond that the caller must use the CPU helper. */
  const uint64_t montgomery_k = ((1ULL << 63) - 1) / (2 * order);

  std::vector<unsigned char> dead(SEGMENT);
  std::vector<uint64_t> survivors;
  uint64_t candidates = 0, deferred = 0, found_total = 0;
  std::vector<std::pair<uint64_t, uint64_t>> all_hits;

  uint64_t *d_ks = nullptr, *d_hits = nullptr;
  uint32_t *d_count = nullptr;
  cudaMalloc(&d_ks, (size_t)SEGMENT * sizeof(uint64_t));
  cudaMalloc(&d_hits, (size_t)MAX_HITS * 2 * sizeof(uint64_t));
  cudaMalloc(&d_count, sizeof(uint32_t));

  for (uint64_t base = k_start; base <= k_end; base += SEGMENT) {
    const uint64_t length = (k_end - base + 1) < SEGMENT ? (k_end - base + 1) : SEGMENT;
    std::memset(dead.data(), 0, length);
    for (uint32_t r : primes) {
      const uint64_t a = (2 % r) * (order % r) % r;
      if (a == 0) continue;
      const uint64_t k0 = (r - modinv_host(a, r)) % r;
      uint64_t first = k0 >= (base % r) ? k0 - (base % r) : k0 + r - (base % r);
      for (uint64_t j = first; j < length; j += r) {
        const uint64_t k = base + j;
        if (k <= montgomery_k && 2 * k * order + 1 == r) continue;
        dead[j] = 1;
      }
    }
    survivors.clear();
    for (uint64_t j = 0; j < length; j++) {
      if (dead[j]) continue;
      const uint64_t k = base + j;
      if (k > montgomery_k) { deferred++; continue; }
      const uint64_t q = 2 * k * order + 1;
      const uint64_t residue = q & 7ULL;
      if (residue != 1 && residue != 7) continue;
      survivors.push_back(k);
    }
    if (survivors.empty()) continue;
    candidates += survivors.size();

    cudaMemcpy(d_ks, survivors.data(), survivors.size() * sizeof(uint64_t),
               cudaMemcpyHostToDevice);
    cudaMemset(d_count, 0, sizeof(uint32_t));
    const uint32_t blocks = (uint32_t)((survivors.size() + BLOCK - 1) / BLOCK);
    numerisect_mfactor_kernel<<<blocks, BLOCK>>>(d_ks, (uint32_t)survivors.size(), order, d_hits,
                                   d_count, MAX_HITS);
    if (cudaDeviceSynchronize() != cudaSuccess) {
      fprintf(stderr, "numerisect-mfactor-cuda: kernel failed\n");
      return 1;
    }
    uint32_t count = 0;
    cudaMemcpy(&count, d_count, sizeof(uint32_t), cudaMemcpyDeviceToHost);
    if (count) {
      const uint32_t take = count < MAX_HITS ? count : MAX_HITS;
      std::vector<uint64_t> host(2 * take);
      cudaMemcpy(host.data(), d_hits, 2 * take * sizeof(uint64_t),
                 cudaMemcpyDeviceToHost);
      for (uint32_t i = 0; i < take; i++)
        all_hits.emplace_back(host[2 * i + 1], host[2 * i]);
      found_total += count;
    }
  }

  std::sort(all_hits.begin(), all_hits.end());
  for (const auto &hit : all_hits)
    printf("FACTOR:%llu|%llu\n", (unsigned long long)hit.second,
           (unsigned long long)hit.first);

  printf("CANDIDATES:%llu\n", (unsigned long long)candidates);
  printf("DEFERRED:%llu\n", (unsigned long long)deferred);
  printf("COUNT:%llu\n", (unsigned long long)found_total);
  printf("STATUS:%s\n", deferred ? "deferred-wide" : "complete");
  printf("DONE:1\n");

  cudaFree(d_ks);
  cudaFree(d_hits);
  cudaFree(d_count);
  return 0;
}
