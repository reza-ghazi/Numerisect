/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * numerisect-squfof - Shanks' square forms factorization.
 *
 * WHY THIS PROGRAM EXISTS
 * -----------------------
 * Numerisect is a user interface over existing number-theory libraries, and a
 * computation is only implemented here when no installed library provides it.
 * SQUFOF is that case: the installed YAFU build has no `squfof` function, PARI/GP
 * exposes none, Msieve implements only QS/NFS, and GMP-ECM implements only
 * ECM/P-1/P+1. So this file supplies it, in optimized C, per the project policy.
 *
 * METHOD
 * ------
 * Shanks' algorithm walks the principal cycle of binary quadratic forms of
 * discriminant 4kN, looking for a form whose leading coefficient is a perfect
 * square. Squaring the ambiguous form found there and running the cycle backwards
 * yields a proper factor. The implementation races a standard multiplier list so
 * that a discriminant with a short cycle is found quickly.
 *
 * The inner loop runs entirely in 64-bit registers with 128-bit intermediate
 * products, which is what makes SQUFOF fast. That bounds useful inputs at roughly
 * 2^62: above that, k*N overflows the multiplier-scaled discriminant and the
 * method stops being competitive with SIQS anyway. Larger inputs are rejected with
 * an explicit message rather than silently mis-answering; the caller is expected to
 * route those to YAFU/Msieve/CADO.
 *
 * GMP is used for input parsing and for the size check only. It is deliberately
 * absent from the inner loop.
 *
 * OUTPUT
 * ------
 * Tagged lines, matching the convention used by numerisect_zeta.c:
 *   N:<n>                   the input
 *   MULTIPLIER:<k>          multiplier that succeeded
 *   QUEUE_LIMIT:<n>         perfect-square queue capacity
 *   ITERATIONS:<n>          forward iterations consumed
 *   FACTOR:<f>|<cofactor>   the proper factor and its cofactor
 *   STATUS:<found|exhausted|rejected>
 *   DONE:<0|1>              completion marker; absence means the run failed
 *
 * STATUS=exhausted is an inconclusive result, not a claim that N is prime.
 *
 * Build (the Python side does this automatically):
 *   cc -O3 -std=c11 numerisect_squfof.c -o numerisect-squfof -lgmp -lm
 */

#include <gmp.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

/* Standard SQUFOF multiplier list, ordered so that small, highly composite
 * multipliers (which tend to give short cycles) are tried first. */
static const uint32_t MULTIPLIERS[] = {
    1,   3,   5,   7,   11,  3 * 5, 3 * 7, 3 * 11, 5 * 7, 5 * 11, 7 * 11,
    3 * 5 * 7, 3 * 5 * 11, 3 * 7 * 11, 5 * 7 * 11, 3 * 5 * 7 * 11};
static const size_t MULTIPLIER_COUNT = sizeof(MULTIPLIERS) / sizeof(MULTIPLIERS[0]);

/* Largest input the 64-bit cycle can handle once scaled by the largest
 * multiplier. 2^62 keeps 4*k*N inside 128-bit intermediates with room to spare. */
static const uint64_t MAX_INPUT = (uint64_t)1 << 62;

#define QUEUE_CAPACITY 64

static uint64_t isqrt64(uint64_t n) {
  if (n == 0) return 0;
  uint64_t root = (uint64_t)__builtin_sqrt((double)n);
  /* Correct the floating-point estimate; at most a couple of steps. */
  while (root > 0 && root > n / root) root--;
  while ((root + 1) <= n / (root + 1)) root++;
  return root;
}

static bool is_square64(uint64_t n, uint64_t *root_out) {
  /* Cheap residue filter before the expensive square root: only 12 of the 64
   * residues mod 64 are quadratic residues. */
  static const bool residue64[64] = {
      [0] = true,  [1] = true,  [4] = true,  [9] = true,  [16] = true, [17] = true,
      [25] = true, [33] = true, [36] = true, [41] = true, [49] = true, [57] = true};
  if (!residue64[n & 63]) return false;
  uint64_t root = isqrt64(n);
  if (root * root != n) return false;
  if (root_out) *root_out = root;
  return true;
}

static uint64_t gcd64(uint64_t a, uint64_t b) {
  while (b) {
    uint64_t t = a % b;
    a = b;
    b = t;
  }
  return a;
}

/* One SQUFOF pass for a single multiplier.
 *
 * Returns a proper factor of n, or 0 if this multiplier's cycle was exhausted
 * within `max_iterations`. `iterations_out` receives the forward step count. */
static uint64_t squfof_once(uint64_t n, uint32_t multiplier, uint64_t max_iterations,
                            uint64_t *iterations_out) {
  const unsigned __int128 scaled = (unsigned __int128)n * multiplier;
  if (scaled >> 64) return 0; /* k*n must stay in 64 bits */
  const uint64_t d = (uint64_t)scaled;

  const uint64_t s = isqrt64(d);
  if (s * s == d) {
    /* k*n is a perfect square; gcd(n, s) splits n unless the square is trivial. */
    uint64_t g = gcd64(n, s);
    return (g > 1 && g < n) ? g : 0;
  }

  /* Forward cycle. Queue holds the small square Q values already seen, which is
   * how spurious ambiguous forms are rejected (Gower and Wagstaff). */
  uint64_t queue[QUEUE_CAPACITY];
  size_t queue_size = 0;

  uint64_t p_prev = s;
  uint64_t q_prev = 1;
  uint64_t q = d - s * s;
  if (q == 0) return 0;

  const uint64_t bound = 2 * isqrt64(2 * s);
  uint64_t i = 0;
  uint64_t p = 0, q_next = 0, root = 0;

  for (i = 1; i <= max_iterations; i++) {
    const uint64_t b = (s + p_prev) / q;
    p = b * q - p_prev;
    /* q_next = q_prev + b*(p_prev - p); the difference can be negative, so it is
     * computed in signed 128-bit space and folded back. */
    const __int128 delta = (__int128)b * ((__int128)p_prev - (__int128)p);
    const __int128 candidate = (__int128)q_prev + delta;
    if (candidate <= 0) return 0;
    q_next = (uint64_t)candidate;

    if ((i & 1) == 0 && is_square64(q, &root)) {
      /* Reject square Q values that already appeared in the queue: those come
       * from a form that squares back into the cycle rather than an ambiguous one. */
      bool seen = false;
      for (size_t j = 0; j < queue_size; j++) {
        if (queue[j] == root) {
          seen = true;
          break;
        }
      }
      if (!seen) break;
    }
    if (q <= bound && queue_size < QUEUE_CAPACITY) queue[queue_size++] = q;

    q_prev = q;
    q = q_next;
    p_prev = p;
  }
  if (iterations_out) *iterations_out = i;
  if (i > max_iterations) return 0;
  if (!is_square64(q, &root) || root == 0) return 0;

  /* Reverse cycle from the ambiguous form. */
  uint64_t rp_prev = p;
  uint64_t rq_prev = root;
  {
    const uint64_t b = (s - rp_prev) / rq_prev;
    rp_prev = b * rq_prev + rp_prev;
  }
  const unsigned __int128 pp = (unsigned __int128)rp_prev * rp_prev;
  if (pp > (unsigned __int128)d) return 0;
  uint64_t rq = (uint64_t)(((unsigned __int128)d - pp) / rq_prev);
  uint64_t rq_pp = root;

  for (uint64_t j = 0; j < max_iterations; j++) {
    const uint64_t b = (s + rp_prev) / rq;
    const uint64_t rp = b * rq - rp_prev;
    if (rp == rp_prev) break; /* the cycle has folded: rp is the half-period point */
    const __int128 delta = (__int128)b * ((__int128)rp_prev - (__int128)rp);
    const __int128 candidate = (__int128)rq_pp + delta;
    if (candidate <= 0) return 0;
    rq_pp = rq;
    rq = (uint64_t)candidate;
    rp_prev = rp;
  }

  const uint64_t factor = gcd64(n, rp_prev);
  return (factor > 1 && factor < n) ? factor : 0;
}

static void usage(void) {
  fprintf(stderr,
          "usage: numerisect-squfof <decimal integer> [max-iterations]\n"
          "  Shanks' square forms factorization for odd composites below 2^62.\n");
}

int main(int argc, char **argv) {
  if (argc < 2 || argc > 3) {
    usage();
    return 2;
  }

  mpz_t n_big;
  mpz_init(n_big);
  if (mpz_set_str(n_big, argv[1], 10) != 0 || mpz_sgn(n_big) <= 0) {
    fprintf(stderr, "numerisect-squfof: '%s' is not a positive decimal integer\n", argv[1]);
    mpz_clear(n_big);
    return 2;
  }

  uint64_t max_iterations = 4000000;
  if (argc == 3) {
    char *end = NULL;
    unsigned long long requested = strtoull(argv[2], &end, 10);
    if (end == argv[2] || *end != '\0' || requested < 1000 || requested > 200000000ULL) {
      fprintf(stderr, "numerisect-squfof: max-iterations must be between 1000 and 200000000\n");
      mpz_clear(n_big);
      return 2;
    }
    max_iterations = (uint64_t)requested;
  }

  gmp_printf("N:%Zd\n", n_big);

  if (mpz_cmp_ui(n_big, MAX_INPUT) >= 0) {
    printf("STATUS:rejected\n");
    printf("REASON:SQUFOF here is limited to inputs below 2^62; route larger inputs to SIQS or NFS\n");
    printf("DONE:0\n");
    mpz_clear(n_big);
    return 0;
  }

  const uint64_t n = (uint64_t)mpz_get_ui(n_big);
  mpz_clear(n_big);

  if (n % 2 == 0) {
    printf("MULTIPLIER:1\n");
    printf("ITERATIONS:0\n");
    printf("FACTOR:2|%" PRIu64 "\n", n / 2);
    printf("STATUS:found\n");
    printf("DONE:1\n");
    return 0;
  }

  uint64_t root = 0;
  if (is_square64(n, &root)) {
    printf("MULTIPLIER:1\n");
    printf("ITERATIONS:0\n");
    printf("FACTOR:%" PRIu64 "|%" PRIu64 "\n", root, root);
    printf("STATUS:found\n");
    printf("DONE:1\n");
    return 0;
  }

  printf("QUEUE_LIMIT:%d\n", QUEUE_CAPACITY);

  uint64_t total_iterations = 0;
  for (size_t m = 0; m < MULTIPLIER_COUNT; m++) {
    uint64_t iterations = 0;
    const uint64_t factor = squfof_once(n, MULTIPLIERS[m], max_iterations, &iterations);
    total_iterations += iterations;
    if (factor > 1 && factor < n && n % factor == 0) {
      printf("MULTIPLIER:%u\n", MULTIPLIERS[m]);
      printf("ITERATIONS:%" PRIu64 "\n", total_iterations);
      printf("FACTOR:%" PRIu64 "|%" PRIu64 "\n", factor, n / factor);
      printf("STATUS:found\n");
      printf("DONE:1\n");
      return 0;
    }
  }

  printf("ITERATIONS:%" PRIu64 "\n", total_iterations);
  printf("STATUS:exhausted\n");
  printf("REASON:no multiplier produced a proper factor within the iteration limit\n");
  printf("DONE:1\n");
  return 0;
}
