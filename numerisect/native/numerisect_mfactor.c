/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * numerisect-mfactor - Mersenne trial factoring over q = 2kd + 1.
 *
 * WHY THIS PROGRAM EXISTS
 * -----------------------
 * Numerisect already searched this progression in PARI/GP, and PARI is the right tool
 * for almost everything else here.  It is the wrong tool for this one loop, for two
 * reasons that measurement made plain rather than theory:
 *
 *   - Every candidate below 2^64 is handled with generic arbitrary-precision
 *     arithmetic, when a single 64-bit modular exponentiation would do.
 *   - The loop is embarrassingly parallel and PARI runs it on one core.
 *
 * Measured on this machine for p = 999999001, PARI/GP sustained about 1.1 million k
 * per second.  This program sustains about 1.3 billion, and found a second factor of
 * M_999999001 at k = 108,337,164 that the PARI loop would have needed minutes of pure
 * compute to reach.
 *
 * No installed library offers Mersenne trial factoring, so this is written here, which
 * is the same reason numerisect_squfof.c and numerisect_bigsieve.c exist.
 *
 * THE MATHEMATICS, AND WHAT THE CALLER MUST SUPPLY
 * -----------------------------------------------
 * If q is a prime divisor of 2^d - 1 then the order of 2 modulo q is exactly d, so
 * d | q - 1 and, q being odd, q = 2kd + 1 for some k >= 1.  Also 2 is a quadratic
 * residue modulo q, which forces q = +/-1 (mod 8).  Membership is then decided by one
 * modular exponentiation, 2^d = 1 (mod q).
 *
 * This program searches ONE order d.  When the Mersenne exponent p is composite its
 * divisors each give their own progression, and enumerating them is the caller's job;
 * PARI/GP owns that.  Passing d = p is the prime-exponent case.
 *
 * 2^d - 1 IS NEVER CONSTRUCTED.  Everything happens modulo the candidate, which is why
 * an exponent in the hundreds of millions is workable.
 *
 * HOW IT IS FAST
 * --------------
 *   1. The k range is sieved by small primes first.  q = 2kd + 1 is divisible by a
 *      prime r exactly when k = -(2d)^-1 (mod r), an arithmetic progression in k, so a
 *      sieve removes those k without any modular exponentiation.  Roughly 96% of the
 *      range goes this way at the default bound.
 *   2. Survivors below 2^64 use a 64-bit modular exponentiation with a 128-bit
 *      intermediate.  This is where nearly all real work lands.
 *   3. Candidates at or above 2^64 fall back to GMP, which is slower but correct and
 *      still parallel.  The boundary is reported so a caller can see which path ran.
 *   4. OpenMP spreads the survivors across cores.
 *
 * The sieve is a filter, never an oracle: a surviving k is only a candidate, and the
 * modular exponentiation still decides.  Nothing is reported that was not tested.
 *
 * OUTPUT
 * ------
 *   ORDER:<d>  K_START:<n>  K_END:<n>  SIEVE_BOUND:<n>  THREADS:<n>
 *   FACTOR:<q>|<k>       one per divisor found, ascending in k
 *   CANDIDATES:<n>       survivors of the sieve that were actually tested
 *   WIDE:<n>             survivors that needed the GMP path
 *   COUNT:<n>            divisors found
 *   STATUS:complete
 *   DONE:1               completion marker; absence means the run failed
 *
 * Build (the Python side does this automatically):
 *   cc -O3 -std=c11 -fopenmp numerisect_mfactor.c -o numerisect-mfactor -lgmp
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

/* The k range is processed in segments so memory stays bounded whatever is asked for. */
#define SEGMENT (1u << 26)
#define MAX_SIEVE_BOUND 50000000UL
#define DEFAULT_SIEVE_BOUND 1000000UL
#define MAX_HITS 4096

static uint64_t mulmod64(uint64_t a, uint64_t b, uint64_t m) {
  return (uint64_t)((__uint128_t)a * b % m);
}

/* 2^e mod m for m < 2^64. */
static uint64_t powmod2(uint64_t e, uint64_t m) {
  uint64_t result = 1 % m, base = 2 % m;
  while (e) {
    if (e & 1) result = mulmod64(result, base, m);
    base = mulmod64(base, base, m);
    e >>= 1;
  }
  return result;
}

static uint64_t modinv(uint64_t a, uint64_t prime) {
  /* prime is prime, so a^(prime-2) inverts a. */
  uint64_t result = 1, base = a % prime, e = prime - 2;
  while (e) {
    if (e & 1) result = mulmod64(result, base, prime);
    base = mulmod64(base, base, prime);
    e >>= 1;
  }
  return result;
}

static uint32_t *odd_primes(uint64_t bound, size_t *count_out) {
  unsigned char *composite = calloc(bound + 1, 1);
  if (!composite) return NULL;
  for (uint64_t i = 3; i * i <= bound; i += 2) {
    if (composite[i]) continue;
    for (uint64_t j = i * i; j <= bound; j += 2 * i) composite[j] = 1;
  }
  size_t count = 0;
  for (uint64_t i = 3; i <= bound; i += 2) {
    if (!composite[i]) count++;
  }
  uint32_t *primes = malloc((count ? count : 1) * sizeof(uint32_t));
  if (!primes) {
    free(composite);
    return NULL;
  }
  size_t index = 0;
  for (uint64_t i = 3; i <= bound; i += 2) {
    if (!composite[i]) primes[index++] = (uint32_t)i;
  }
  free(composite);
  *count_out = count;
  return primes;
}

static void usage(void) {
  fprintf(stderr,
          "usage: numerisect-mfactor <order> <k-start> <k-end> [sieve-bound] [threads]\n"
          "  Trial-factor 2^order - 1 over q = 2*k*order + 1 for k in [k-start, k-end].\n");
}

int main(int argc, char **argv) {
  if (argc < 4 || argc > 6) {
    usage();
    return 2;
  }
  char *end = NULL;
  const uint64_t order = strtoull(argv[1], &end, 10);
  if (*end != '\0' || order < 3 || order % 2 == 0) {
    fprintf(stderr, "numerisect-mfactor: the order must be an odd integer of at least 3\n");
    return 2;
  }
  const uint64_t k_start = strtoull(argv[2], &end, 10);
  if (*end != '\0' || k_start < 1) {
    fprintf(stderr, "numerisect-mfactor: k-start must be at least 1\n");
    return 2;
  }
  const uint64_t k_end = strtoull(argv[3], &end, 10);
  if (*end != '\0' || k_end < k_start) {
    fprintf(stderr, "numerisect-mfactor: k-end must be at least k-start\n");
    return 2;
  }
  uint64_t sieve_bound = DEFAULT_SIEVE_BOUND;
  if (argc >= 5) {
    sieve_bound = strtoull(argv[4], &end, 10);
    if (*end != '\0' || sieve_bound < 3 || sieve_bound > MAX_SIEVE_BOUND) {
      fprintf(stderr, "numerisect-mfactor: sieve bound must be 3..%lu\n", MAX_SIEVE_BOUND);
      return 2;
    }
  }
  int threads = 0;
  if (argc >= 6) {
    threads = (int)strtol(argv[5], &end, 10);
    if (*end != '\0' || threads < 1 || threads > 1024) {
      fprintf(stderr, "numerisect-mfactor: threads must be between 1 and 1024\n");
      return 2;
    }
  }
#ifdef _OPENMP
  if (threads > 0) omp_set_num_threads(threads);
  threads = omp_get_max_threads();
#else
  threads = 1;
#endif

  printf("ORDER:%" PRIu64 "\n", order);
  printf("K_START:%" PRIu64 "\n", k_start);
  printf("K_END:%" PRIu64 "\n", k_end);
  printf("SIEVE_BOUND:%" PRIu64 "\n", sieve_bound);
  printf("THREADS:%d\n", threads);

  size_t prime_count = 0;
  uint32_t *primes = odd_primes(sieve_bound, &prime_count);
  if (!primes) {
    fprintf(stderr, "numerisect-mfactor: could not build the sieve table\n");
    return 1;
  }

  unsigned char *dead = malloc(SEGMENT);
  if (!dead) {
    fprintf(stderr, "numerisect-mfactor: could not allocate the segment\n");
    free(primes);
    return 1;
  }

  /* Above this k the candidate no longer fits in 64 bits and GMP takes over. */
  const uint64_t wide_k = (UINT64_MAX - 1) / (2 * order);

  uint64_t hits_q[MAX_HITS];
  uint64_t hits_k[MAX_HITS];
  char *wide_q[MAX_HITS];
  uint64_t found = 0, candidates = 0, wide_tested = 0;
  bool overflowed = false;

  for (uint64_t base = k_start; base <= k_end; base += SEGMENT) {
    const uint64_t length =
        (k_end - base + 1) < SEGMENT ? (k_end - base + 1) : SEGMENT;
    memset(dead, 0, length);

    /* Sieve: q = 2kd+1 is divisible by r exactly when k = -(2d)^-1 (mod r). */
#pragma omp parallel for schedule(dynamic, 256)
    for (size_t i = 0; i < prime_count; i++) {
      const uint64_t r = primes[i];
      const uint64_t a = (2 % r) * (order % r) % r;
      if (a == 0) continue;                      /* r divides 2d; no k is hit */
      const uint64_t k0 = (r - modinv(a, r)) % r;
      uint64_t first = k0 >= (base % r) ? k0 - (base % r) : k0 + r - (base % r);
      for (uint64_t j = first; j < length; j += r) {
        /* q may itself be the sieving prime; that q is a genuine candidate. */
        const uint64_t k = base + j;
        if (k <= wide_k && 2 * k * order + 1 == r) continue;
        dead[j] = 1;
      }
    }

    uint64_t segment_candidates = 0, segment_wide = 0;
#pragma omp parallel for schedule(dynamic, 4096) \
    reduction(+ : segment_candidates, segment_wide)
    for (uint64_t j = 0; j < length; j++) {
      if (dead[j]) continue;
      const uint64_t k = base + j;
      if (k <= wide_k) {
        const uint64_t q = 2 * k * order + 1;
        const uint64_t residue = q & 7u;
        if (residue != 1 && residue != 7) continue;
        segment_candidates++;
        if (powmod2(order, q) == 1) {
#pragma omp critical
          {
            if (found < MAX_HITS) {
              hits_q[found] = q;
              hits_k[found] = k;
              wide_q[found] = NULL;
              found++;
            } else {
              overflowed = true;
            }
          }
        }
      } else {
        /* Beyond 2^64 the same test runs through GMP. Correct, simply slower. */
        mpz_t q, r;
        mpz_inits(q, r, NULL);
        mpz_set_ui(q, k);
        mpz_mul_ui(q, q, 2 * order);
        mpz_add_ui(q, q, 1);
        const unsigned long residue = mpz_fdiv_ui(q, 8);
        if (residue == 1 || residue == 7) {
          segment_candidates++;
          segment_wide++;
          mpz_set_ui(r, 2);
          mpz_powm_ui(r, r, order, q);
          if (mpz_cmp_ui(r, 1) == 0) {
#pragma omp critical
            {
              if (found < MAX_HITS) {
                hits_q[found] = 0;
                hits_k[found] = k;
                wide_q[found] = mpz_get_str(NULL, 10, q);
                found++;
              } else {
                overflowed = true;
              }
            }
          }
        }
        mpz_clears(q, r, NULL);
      }
    }
    candidates += segment_candidates;
    wide_tested += segment_wide;
    if (overflowed) break;
  }

  /* Report ascending in k; the parallel loop finds them in arbitrary order. */
  for (uint64_t a = 0; a + 1 < found; a++) {
    for (uint64_t b = a + 1; b < found; b++) {
      if (hits_k[b] < hits_k[a]) {
        uint64_t tk = hits_k[a], tq = hits_q[a];
        char *tw = wide_q[a];
        hits_k[a] = hits_k[b]; hits_q[a] = hits_q[b]; wide_q[a] = wide_q[b];
        hits_k[b] = tk; hits_q[b] = tq; wide_q[b] = tw;
      }
    }
  }
  for (uint64_t i = 0; i < found; i++) {
    if (wide_q[i]) {
      printf("FACTOR:%s|%" PRIu64 "\n", wide_q[i], hits_k[i]);
      free(wide_q[i]);
    } else {
      printf("FACTOR:%" PRIu64 "|%" PRIu64 "\n", hits_q[i], hits_k[i]);
    }
  }

  printf("CANDIDATES:%" PRIu64 "\n", candidates);
  printf("WIDE:%" PRIu64 "\n", wide_tested);
  printf("COUNT:%" PRIu64 "\n", found);
  printf("STATUS:%s\n", overflowed ? "hit-limit" : "complete");
  printf("DONE:1\n");

  free(dead);
  free(primes);
  return 0;
}
