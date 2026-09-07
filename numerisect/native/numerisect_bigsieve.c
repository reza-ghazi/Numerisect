/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * numerisect-bigsieve - segmented prime enumeration above 2^64.
 *
 * WHY THIS PROGRAM EXISTS
 * -----------------------
 * Numerisect uses an existing library wherever one serves. For enumerating primes
 * in an interval, that library is primesieve, and it is excellent. But primesieve
 * is strictly a 64-bit tool:
 *
 *     $ primesieve 18446744073709551617 -d 1000 --count
 *     Error: 64-bit unsigned integer overflow detected in string to integer
 *     conversion of '18446744073709551617'
 *
 * Above 2^64 the only remaining option in the installed set is PARI's forprime,
 * which is single-threaded and markedly slower as the interval moves up. Measured
 * on this machine over a 10^6-wide window:
 *
 *     near 10^12    7 ms      (inside primesieve's range anyway)
 *     near 10^30  922 ms      (~130x slower, and one core)
 *
 * So there is a real gap: multithreaded prime enumeration in an arbitrary-precision
 * interval. This program fills it with GMP and OpenMP.
 *
 * METHOD
 * ------
 * A window [start, start+length) is presieved by every prime up to a small bound B,
 * which removes the overwhelming majority of candidates cheaply: sieving to 10^6
 * eliminates about 92% of odd numbers. Each survivor is then subjected to a
 * Baillie-PSW test via GMP, optionally reinforced with extra Miller-Rabin rounds.
 *
 * Both phases are parallel. The window is split into contiguous chunks, one per
 * thread, so no two threads ever write the same byte during presieving, and the
 * survivor tests are distributed dynamically because their cost varies.
 *
 * PROVEN VERSUS PROBABLE
 * ----------------------
 * Above 2^64 this program reports PROBABLE primes. GMP's mpz_probab_prime_p is
 * Baillie-PSW plus Miller-Rabin rounds; it is not a proof. No BPSW pseudoprime is
 * known, but none is proven not to exist. Numerisect labels these results as
 * probable and offers PARI's isprime separately for a proof. The program never
 * calls a result proven.
 *
 * OUTPUT
 * ------
 * Tagged lines, matching the convention of the other helpers:
 *   START:<n>  LENGTH:<n>  SMALL_PRIME_BOUND:<n>  THREADS:<n>  ROUNDS:<n>
 *   PRIME:<n>            one per probable prime, ascending
 *   CANDIDATES:<n>       survivors of the presieve
 *   COUNT:<n>            probable primes found
 *   STATUS:probable|exact
 *   DONE:1               completion marker; absence means the run failed
 *
 * STATUS is "exact" only when the whole window lies below 2^64, where the same
 * BPSW test is deterministic; otherwise it is "probable".
 *
 * Build (the Python side does this automatically):
 *   cc -O3 -std=c11 -fopenmp numerisect_bigsieve.c -o numerisect-bigsieve -lgmp -lm
 */

#include <gmp.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _OPENMP
#include <omp.h>
#endif

/* Windows are capped so a request cannot exhaust memory: one byte per odd number. */
#define MAX_LENGTH 100000000UL
#define MAX_SMALL_PRIME_BOUND 100000000UL
#define DEFAULT_SMALL_PRIME_BOUND 1000000UL
#define MAX_ROUNDS 64

/* Below this the BPSW implementation in GMP is deterministic in practice and the
 * caller may treat results as exact; above it they are probable primes. */
static const char *TWO_TO_64 = "18446744073709551616";

/* Simple sieve of Eratosthenes for the presieve primes themselves. */
static uint32_t *small_primes(uint64_t bound, size_t *count_out) {
  if (bound < 2) {
    *count_out = 0;
    return NULL;
  }
  unsigned char *composite = calloc(bound + 1, 1);
  if (!composite) return NULL;
  for (uint64_t i = 2; i * i <= bound; i++) {
    if (composite[i]) continue;
    for (uint64_t j = i * i; j <= bound; j += i) composite[j] = 1;
  }
  size_t count = 0;
  for (uint64_t i = 2; i <= bound; i++) {
    if (!composite[i]) count++;
  }
  uint32_t *primes = malloc(count * sizeof(uint32_t));
  if (!primes) {
    free(composite);
    return NULL;
  }
  size_t index = 0;
  for (uint64_t i = 2; i <= bound; i++) {
    if (!composite[i]) primes[index++] = (uint32_t)i;
  }
  free(composite);
  *count_out = count;
  return primes;
}

static void usage(void) {
  fprintf(stderr,
          "usage: numerisect-bigsieve <start> <length> [small-prime-bound] "
          "[threads] [extra-mr-rounds]\n"
          "  Segmented probable-prime enumeration for intervals of any size.\n");
}

int main(int argc, char **argv) {
  if (argc < 3 || argc > 6) {
    usage();
    return 2;
  }

  mpz_t start, limit, candidate, ceiling;
  mpz_inits(start, limit, candidate, ceiling, NULL);
  if (mpz_set_str(start, argv[1], 10) != 0 || mpz_sgn(start) < 0) {
    fprintf(stderr, "numerisect-bigsieve: start must be a non-negative integer\n");
    return 2;
  }

  char *end = NULL;
  unsigned long length = strtoul(argv[2], &end, 10);
  if (end == argv[2] || *end != '\0' || length == 0 || length > MAX_LENGTH) {
    fprintf(stderr, "numerisect-bigsieve: length must be between 1 and %lu\n", MAX_LENGTH);
    return 2;
  }

  unsigned long bound = DEFAULT_SMALL_PRIME_BOUND;
  if (argc >= 4) {
    bound = strtoul(argv[3], &end, 10);
    if (*end != '\0' || bound < 100 || bound > MAX_SMALL_PRIME_BOUND) {
      fprintf(stderr, "numerisect-bigsieve: small-prime bound must be 100..%lu\n",
              MAX_SMALL_PRIME_BOUND);
      return 2;
    }
  }

  int threads = 0;
  if (argc >= 5) {
    threads = (int)strtol(argv[4], &end, 10);
    if (*end != '\0' || threads < 1 || threads > 1024) {
      fprintf(stderr, "numerisect-bigsieve: threads must be between 1 and 1024\n");
      return 2;
    }
  }

  int rounds = 0;
  if (argc >= 6) {
    rounds = (int)strtol(argv[5], &end, 10);
    if (*end != '\0' || rounds < 0 || rounds > MAX_ROUNDS) {
      fprintf(stderr, "numerisect-bigsieve: extra rounds must be 0..%d\n", MAX_ROUNDS);
      return 2;
    }
  }

#ifdef _OPENMP
  if (threads > 0) omp_set_num_threads(threads);
  threads = omp_get_max_threads();
#else
  threads = 1;
#endif

  mpz_add_ui(limit, start, length);
  mpz_set_str(ceiling, TWO_TO_64, 10);
  const bool exact = mpz_cmp(limit, ceiling) <= 0;

  gmp_printf("START:%Zd\n", start);
  printf("LENGTH:%lu\n", length);
  printf("SMALL_PRIME_BOUND:%lu\n", bound);
  printf("THREADS:%d\n", threads);
  printf("ROUNDS:%d\n", rounds);

  size_t prime_count = 0;
  uint32_t *primes = small_primes(bound, &prime_count);
  if (!primes) {
    fprintf(stderr, "numerisect-bigsieve: could not build the presieve table\n");
    return 1;
  }

  unsigned char *composite = calloc(length, 1);
  if (!composite) {
    fprintf(stderr, "numerisect-bigsieve: could not allocate the window\n");
    free(primes);
    return 1;
  }

  /* Presieve. The window is split into contiguous chunks so two threads never
   * touch the same byte; each thread applies every small prime to its own chunk. */
#pragma omp parallel
  {
    int id = 0, total = 1;
#ifdef _OPENMP
    id = omp_get_thread_num();
    total = omp_get_num_threads();
#endif
    const unsigned long chunk = (length + total - 1) / total;
    const unsigned long from = (unsigned long)id * chunk;
    unsigned long to = from + chunk;
    if (to > length) to = length;

    if (from < to) {
      for (size_t i = 0; i < prime_count; i++) {
        const uint32_t p = primes[i];
        /* First index in [from, to) that is a multiple of p. */
        const unsigned long residue = mpz_fdiv_ui(start, p);
        unsigned long first = (p - residue) % p;
        if (first < from) {
          const unsigned long gap = from - first;
          first += ((gap + p - 1) / p) * p;
        }
        /* If p itself lies in the window its own position must survive, and that
         * position is not generally the first multiple. Compute it once: when
         * start <= p the start fits in an unsigned long because p does. */
        long protected_index = -1;
        if (mpz_cmp_ui(start, p) <= 0) {
          const unsigned long low = mpz_get_ui(start);
          if (p >= low && (unsigned long)(p - low) < length) {
            protected_index = (long)(p - low);
          }
        }
        for (unsigned long j = first; j < to; j += p) {
          if (protected_index >= 0 && j == (unsigned long)protected_index) continue;
          composite[j] = 1;
        }
      }
    }
  }
  free(primes);

  /* Collect survivors, then test them in parallel. */
  unsigned long *survivors = malloc(length * sizeof(unsigned long));
  if (!survivors) {
    fprintf(stderr, "numerisect-bigsieve: could not allocate the candidate list\n");
    free(composite);
    return 1;
  }
  unsigned long candidates = 0;
  for (unsigned long i = 0; i < length; i++) {
    if (!composite[i]) survivors[candidates++] = i;
  }
  free(composite);
  printf("CANDIDATES:%lu\n", candidates);

  unsigned char *is_prime = calloc(candidates ? candidates : 1, 1);
  if (!is_prime) {
    fprintf(stderr, "numerisect-bigsieve: could not allocate the result list\n");
    free(survivors);
    return 1;
  }

  const int reps = 25 + rounds;
#pragma omp parallel
  {
    mpz_t local;
    mpz_init(local);
#pragma omp for schedule(dynamic, 64)
    for (long long k = 0; k < (long long)candidates; k++) {
      mpz_add_ui(local, start, survivors[k]);
      if (mpz_cmp_ui(local, 2) < 0) continue;
      /* GMP: 0 composite, 1 probably prime, 2 definitely prime. */
      is_prime[k] = mpz_probab_prime_p(local, reps) > 0 ? 1 : 0;
    }
    mpz_clear(local);
  }

  unsigned long found = 0;
  for (unsigned long k = 0; k < candidates; k++) {
    if (!is_prime[k]) continue;
    mpz_add_ui(candidate, start, survivors[k]);
    gmp_printf("PRIME:%Zd\n", candidate);
    found++;
  }

  printf("COUNT:%lu\n", found);
  printf("STATUS:%s\n", exact ? "exact" : "probable");
  printf("DONE:1\n");

  free(is_prime);
  free(survivors);
  mpz_clears(start, limit, candidate, ceiling, NULL);
  return 0;
}
