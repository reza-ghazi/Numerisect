/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * numerisect-mfactor-cuda - GPU Mersenne trial factoring over q = 2kd + 1.
 *
 * WHAT THIS ADDS OVER THE CPU HELPER
 * ----------------------------------
 * numerisect_mfactor.c sieves the k range and tests survivors with a 64-bit modular
 * exponentiation across every core. This program does the same work on the device.
 *
 * It is an OPTIONAL accelerator. It computes nothing the CPU helper cannot, produces the
 * same tagged output, and Numerisect never requires a GPU.
 *
 * WHY THE SIEVE RUNS ON THE DEVICE
 * --------------------------------
 * The first version of this program sieved on the host, gathered the survivors, and
 * copied them across. Benchmarked against the C helper it was SLOWER, and parallelising
 * the host sieve only narrowed the gap. The arithmetic was never the problem: roughly
 * thirty 64-bit Montgomery squarings per candidate is not enough work to pay for moving
 * that candidate over PCIe, while the CPU helper tests each survivor in place in the same
 * loop that found it.
 *
 * So nothing is transferred any more. The segment bitmap is allocated, marked and
 * consumed entirely on the device. Only the small prime table, once, and the handful of
 * hits at the end ever cross the bus.
 *
 * MONTGOMERY ARITHMETIC AND THE 2^63 LIMIT
 * ----------------------------------------
 * REDC requires q < 2^63. Candidates at or above that are counted as DEFERRED and never
 * reported as tested, because an untested range must not read as an absence of factors.
 * Send those to the CPU helper, which handles them with GMP.
 *
 * OUTPUT
 * ------
 *   ORDER  K_START  K_END  SIEVE_BOUND  DEVICE
 *   FACTOR:<q>|<k>       one per divisor found, ascending in k
 *   CANDIDATES:<n>       survivors actually tested on the device
 *   DEFERRED:<n>         survivors at or above 2^63, not tested here
 *   COUNT:<n>            divisors found
 *   STATUS:complete|deferred-wide|hit-limit
 *   DONE:1               completion marker; absence means the run failed
 *
 * A hit is a DIVISOR of 2^order - 1, not a proven prime factor. The caller confirms
 * primality; PARI/GP does that in Numerisect.
 *
 * Build (the Python side does this automatically, and skips it without nvcc):
 *   nvcc -O3 -arch=native numerisect_mfactor_cuda.cu -o numerisect-mfactor-cuda
 */

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <utility>
#include <vector>

#include "numerisect_mfactor_kernel.cu"

#define SEGMENT (1u << 26)
#define MAX_HITS 4096
#define BLOCK 256

static std::vector<unsigned int> odd_primes(unsigned long bound) {
  std::vector<char> composite(bound + 1, 0);
  for (unsigned long i = 3; i * i <= bound; i += 2)
    if (!composite[i])
      for (unsigned long j = i * i; j <= bound; j += 2 * i) composite[j] = 1;
  std::vector<unsigned int> primes;
  for (unsigned long i = 3; i <= bound; i += 2)
    if (!composite[i]) primes.push_back((unsigned int)i);
  return primes;
}

static bool ok(cudaError_t status, const char *what) {
  if (status == cudaSuccess) return true;
  fprintf(stderr, "numerisect-mfactor-cuda: %s: %s\n", what, cudaGetErrorString(status));
  return false;
}

int main(int argc, char **argv) {
  if (argc < 4 || argc > 5) {
    fprintf(stderr,
            "usage: numerisect-mfactor-cuda <order> <k-start> <k-end> [sieve-bound]\n");
    return 2;
  }
  const numerisect_u64 order = strtoull(argv[1], nullptr, 10);
  const numerisect_u64 k_start = strtoull(argv[2], nullptr, 10);
  const numerisect_u64 k_end = strtoull(argv[3], nullptr, 10);
  const unsigned long sieve_bound = argc >= 5 ? strtoul(argv[4], nullptr, 10) : 1000000UL;
  if (order < 3 || order % 2 == 0 || k_start < 1 || k_end < k_start ||
      sieve_bound < 3 || sieve_bound > 50000000UL) {
    fprintf(stderr, "numerisect-mfactor-cuda: invalid order, k range or sieve bound\n");
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
  printf("SIEVE_BOUND:%lu\n", sieve_bound);
  printf("DEVICE:%s\n", prop.name);

  const std::vector<unsigned int> primes = odd_primes(sieve_bound);
  const numerisect_u64 montgomery_k = ((1ULL << 63) - 1) / (2 * order);

  unsigned char *d_dead = nullptr;
  unsigned int *d_primes = nullptr, *d_residues = nullptr, *d_hit_count = nullptr;
  numerisect_u64 *d_hits = nullptr;
  unsigned long long *d_deferred = nullptr, *d_tested = nullptr;
  if (!ok(cudaMalloc(&d_dead, SEGMENT), "allocate the segment") ||
      !ok(cudaMalloc(&d_primes, primes.size() * sizeof(unsigned int)), "allocate primes") ||
      !ok(cudaMalloc(&d_residues, primes.size() * sizeof(unsigned int)), "allocate residues") ||
      !ok(cudaMalloc(&d_hits, MAX_HITS * 2 * sizeof(numerisect_u64)), "allocate hits") ||
      !ok(cudaMalloc(&d_hit_count, sizeof(unsigned int)), "allocate the hit counter") ||
      !ok(cudaMalloc(&d_deferred, sizeof(unsigned long long)), "allocate the deferred counter") ||
      !ok(cudaMalloc(&d_tested, sizeof(unsigned long long)), "allocate the tested counter"))
    return 1;

  /* The prime table crosses once. Nothing else large ever does. */
  if (!ok(cudaMemcpy(d_primes, primes.data(), primes.size() * sizeof(unsigned int),
                     cudaMemcpyHostToDevice), "upload primes"))
    return 1;
  if (!ok(cudaMemset(d_hit_count, 0, sizeof(unsigned int)), "clear the hit counter") ||
      !ok(cudaMemset(d_deferred, 0, sizeof(unsigned long long)), "clear deferred") ||
      !ok(cudaMemset(d_tested, 0, sizeof(unsigned long long)), "clear tested"))
    return 1;

  /* The residue for each prime is computed once, not once per chunk. */
  const unsigned int residue_blocks =
      (unsigned int)((primes.size() + BLOCK - 1) / BLOCK);
  numerisect_residue_kernel<<<residue_blocks, BLOCK>>>(
      d_primes, (unsigned int)primes.size(), order, d_residues);
  if (!ok(cudaDeviceSynchronize(), "compute sieve residues")) return 1;

  /* Chunking spreads a small prime's work across many threads instead of one. */
  const numerisect_u64 chunk = 1u << 16;
  const numerisect_u64 chunk_count = (SEGMENT + chunk - 1) / chunk;
  const unsigned int sieve_blocks = 4096;
  const unsigned int scan_blocks = 4096;

  for (numerisect_u64 base = k_start; base <= k_end; base += SEGMENT) {
    const numerisect_u64 length =
        std::min<numerisect_u64>(SEGMENT, k_end - base + 1);
    if (!ok(cudaMemset(d_dead, 0, length), "clear the segment")) return 1;
    numerisect_sieve_kernel<<<sieve_blocks, BLOCK>>>(
        d_dead, base, length, order, d_primes, d_residues,
        (unsigned int)primes.size(), chunk, chunk_count, montgomery_k);
    numerisect_scan_kernel<<<scan_blocks, BLOCK>>>(
        d_dead, base, length, order, montgomery_k, d_hits, d_hit_count, MAX_HITS,
        d_deferred, d_tested);
    if (!ok(cudaDeviceSynchronize(), "run the segment")) return 1;
  }

  unsigned int found = 0;
  unsigned long long deferred = 0, tested = 0;
  cudaMemcpy(&found, d_hit_count, sizeof found, cudaMemcpyDeviceToHost);
  cudaMemcpy(&deferred, d_deferred, sizeof deferred, cudaMemcpyDeviceToHost);
  cudaMemcpy(&tested, d_tested, sizeof tested, cudaMemcpyDeviceToHost);

  const unsigned int take = std::min<unsigned int>(found, MAX_HITS);
  std::vector<numerisect_u64> host(2 * (take ? take : 1));
  if (take)
    cudaMemcpy(host.data(), d_hits, 2 * take * sizeof(numerisect_u64),
               cudaMemcpyDeviceToHost);

  std::vector<std::pair<numerisect_u64, numerisect_u64>> hits;
  for (unsigned int i = 0; i < take; i++)
    hits.emplace_back(host[2 * i + 1], host[2 * i]);   /* (k, q), sorted by k */
  std::sort(hits.begin(), hits.end());
  for (const auto &hit : hits)
    printf("FACTOR:%llu|%llu\n", (unsigned long long)hit.second,
           (unsigned long long)hit.first);

  printf("CANDIDATES:%llu\n", tested);
  printf("DEFERRED:%llu\n", deferred);
  printf("COUNT:%u\n", found);
  printf("STATUS:%s\n",
         found > MAX_HITS ? "hit-limit" : (deferred ? "deferred-wide" : "complete"));
  printf("DONE:1\n");

  cudaFree(d_dead);
  cudaFree(d_primes);
  cudaFree(d_residues);
  cudaFree(d_hits);
  cudaFree(d_hit_count);
  cudaFree(d_deferred);
  cudaFree(d_tested);
  return 0;
}
