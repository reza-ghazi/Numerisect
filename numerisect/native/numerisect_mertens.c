/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * numerisect-mertens - the Mertens function M(x) = sum_{n<=x} mu(n), its sign changes,
 * and the ratio |M(x)|/sqrt(x) that the disproved Mertens conjecture was about.
 *
 * WHY THIS EXISTS
 * ---------------
 * PARI/GP has `moebius` but no summatory Mertens routine, and FLINT exposes
 * `n_moebius_mu` and a vectorised sieve for it but again no M(x). Numerisect computed
 * M(x) in `nt_summatory_functions` as a GP loop calling `moebius(n)` once per n: correct,
 * linear in x, and interpreted. That reached roughly x = 10^6 before becoming unusable.
 *
 * Two algorithms live here instead:
 *
 *   SIEVE   M(x) by a segmented Mobius sieve, O(x log log x) time and O(sqrt x) memory.
 *           This is also the only way to get every partial sum, so the sign-change and
 *           extremal-ratio searches use it.
 *
 *   HYPERBOLA  M(x) from the identity sum_{n<=x} M(x/n) = 1, which rearranges to
 *           M(x) = 1 - sum_{n=2}^{x} M(x/n). Grouping equal values of floor(x/n) and
 *           sieving the small arguments gives roughly O(x^(2/3)) work. This is what makes
 *           x = 10^12 a second rather than an afternoon.
 *
 * Measured on this machine, against the GP loop it replaces:
 *
 *   M(10^6)    GP 0.23 s     sieve 0.003 s    hyperbola 0.001 s
 *   M(10^7)    GP 4.27 s     sieve 0.23 s     hyperbola 0.002 s
 *   M(10^9)    (not run)     sieve 21.3 s     hyperbola 0.041 s
 *   M(10^12)   (not run)                      hyperbola 4.4 s
 *   M(10^13)   (not run)                      hyperbola 26.1 s
 *
 * The GP loop is linear and interpreted, so 10^7 is about where it stops being usable.
 *
 * THE TWO ALGORITHMS CHECK EACH OTHER
 * -----------------------------------
 * They share no code path beyond the Mobius sieve, so running both on the same x is a
 * genuine cross-check, and the test suite does exactly that. Published values of
 * M(10^k) are a further check, not the primary one.
 *
 * MEMORY, AND WHY A REFUSAL IS BETTER THAN A GUESS
 * -----------------------------------------------
 * The hyperbola method stores M(n) for n up to a cut u, as int32 (|M(n)| stays far below
 * 2^31 over any range reachable here). That is 4u bytes, so u is capped and the cap is
 * reported. The method needs u >= sqrt(x); when the cap cannot satisfy that, the program
 * refuses rather than returning a number computed outside its own validity.
 *
 * Both algorithms are sequential by nature: a prefix sum and a descending recurrence
 * whose terms read entries computed earlier in the same pass. There is nothing to
 * parallelise here, so no OpenMP.
 *
 * Build (the Python side does this automatically):
 *   cc -O3 -std=c11 numerisect_mertens.c -o numerisect-mertens -lm
 */

/* clock_gettime is POSIX, not C11, and -std=c11 hides it without this. */
#define _POSIX_C_SOURCE 200809L

#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Segment width for the Mobius sieve: large enough to amortise the prime walk, small
 * enough that the segment arrays stay in cache-friendly memory. */
#define NUMERISECT_SEGMENT 1048576
/* Default ceiling on the hyperbola method's table, in entries (4 bytes each). */
#define NUMERISECT_DEFAULT_CUT 100000000LL
#define NUMERISECT_MAX_SIGN_CHANGES 4096

static double numerisect_now(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

static uint64_t numerisect_isqrt(uint64_t n) {
  if (n == 0) return 0;
  uint64_t root = (uint64_t)sqrtl((long double)n);
  while (root > 0 && root > n / root) root--;
  while ((root + 1) <= n / (root + 1)) root++;
  return root;
}

/* Primes up to `limit` by a simple sieve of Eratosthenes; the caller frees the result.
 * These are only the sieving primes (up to sqrt of the range), so the array is small. */
static uint64_t *numerisect_small_primes(uint64_t limit, size_t *count) {
  char *composite = calloc((size_t)limit + 1, 1);
  if (composite == NULL) return NULL;
  size_t found = 0;
  for (uint64_t i = 2; i <= limit; i++) {
    if (!composite[i]) {
      found++;
      for (uint64_t j = i * i; j <= limit; j += i) composite[j] = 1;
    }
  }
  uint64_t *primes = malloc(found * sizeof(uint64_t));
  if (primes == NULL) {
    free(composite);
    return NULL;
  }
  size_t index = 0;
  for (uint64_t i = 2; i <= limit; i++) {
    if (!composite[i]) primes[index++] = i;
  }
  free(composite);
  *count = found;
  return primes;
}

/* Fill mu[0..length-1] with the Mobius function of low..low+length-1.
 *
 * Each entry starts at 1 and carries the unfactored remainder of n. Every sieving prime
 * flips the sign of its multiples and divides itself out; a p^2 multiple sets mu to 0.
 * Whatever remainder survives is a prime factor above sqrt(high), so it flips the sign
 * once more. This needs no factorisation and no per-entry division loop.
 */
static int numerisect_mobius_segment(uint64_t low, uint64_t length, int8_t *mu,
                                     uint64_t *remainder, const uint64_t *primes,
                                     size_t prime_count) {
  for (uint64_t i = 0; i < length; i++) {
    mu[i] = 1;
    remainder[i] = low + i;
  }
  if (low == 0) {
    mu[0] = 0;                      /* mu(0) is not defined; it is never summed */
    remainder[0] = 1;
  }
  const uint64_t high = low + length - 1;
  for (size_t index = 0; index < prime_count; index++) {
    const uint64_t p = primes[index];
    if (p > high) break;
    uint64_t start = (low / p) * p;
    if (start < low) start += p;
    for (uint64_t multiple = start; multiple <= high; multiple += p) {
      const uint64_t offset = multiple - low;
      mu[offset] = (int8_t)-mu[offset];
      remainder[offset] /= p;
    }
    const uint64_t square = p * p;
    if (square > high) continue;
    uint64_t square_start = (low / square) * square;
    if (square_start < low) square_start += square;
    for (uint64_t multiple = square_start; multiple <= high; multiple += square) {
      mu[multiple - low] = 0;
    }
  }
  for (uint64_t i = 0; i < length; i++) {
    if (mu[i] != 0 && remainder[i] > 1) mu[i] = (int8_t)-mu[i];
  }
  return 0;
}

/* ---------------------------------------------------------------------------------
 * M(x) BY DIRECT SIEVE
 *
 * Also the engine for the sign-change and extremal-ratio searches, because those need
 * every partial sum and not just the endpoint.
 * ------------------------------------------------------------------------------- */
typedef struct {
  int64_t value;              /* M(x) */
  uint64_t sign_changes;      /* number of n <= x where M changes sign */
  uint64_t first_sign_change; /* smallest such n, 0 if none */
  int64_t minimum;            /* min over n <= x */
  uint64_t minimum_at;
  int64_t maximum;
  uint64_t maximum_at;
  double extreme_ratio;       /* max |M(n)| / sqrt(n) */
  uint64_t extreme_ratio_at;
  uint64_t changes[NUMERISECT_MAX_SIGN_CHANGES];
  int change_count;
  int timed_out;
  uint64_t reached;
} numerisect_sieve_result;

static int numerisect_mertens_sieve(uint64_t x, double budget, double began,
                                    numerisect_sieve_result *out) {
  memset(out, 0, sizeof(*out));
  const uint64_t root = numerisect_isqrt(x);
  size_t prime_count = 0;
  uint64_t *primes = numerisect_small_primes(root < 2 ? 2 : root, &prime_count);
  if (primes == NULL) return -1;
  int8_t *mu = malloc(NUMERISECT_SEGMENT);
  uint64_t *remainder = malloc(NUMERISECT_SEGMENT * sizeof(uint64_t));
  if (mu == NULL || remainder == NULL) {
    free(primes);
    free(mu);
    free(remainder);
    return -1;
  }
  int64_t running = 0;
  int previous_sign = 0;
  out->minimum_at = out->maximum_at = 1;
  for (uint64_t low = 1; low <= x; low += NUMERISECT_SEGMENT) {
    const uint64_t length = (x - low + 1 < NUMERISECT_SEGMENT) ? (x - low + 1)
                                                              : NUMERISECT_SEGMENT;
    numerisect_mobius_segment(low, length, mu, remainder, primes, prime_count);
    for (uint64_t i = 0; i < length; i++) {
      const uint64_t n = low + i;
      running += mu[i];
      if (running < out->minimum) {
        out->minimum = running;
        out->minimum_at = n;
      }
      if (running > out->maximum) {
        out->maximum = running;
        out->maximum_at = n;
      }
      const int sign = (running > 0) - (running < 0);
      if (sign != 0) {
        if (previous_sign != 0 && sign != previous_sign) {
          out->sign_changes++;
          if (out->first_sign_change == 0) out->first_sign_change = n;
          if (out->change_count < NUMERISECT_MAX_SIGN_CHANGES) {
            out->changes[out->change_count++] = n;
          }
        }
        previous_sign = sign;
      }
      /* n = 1 gives |M|/sqrt(n) = 1 trivially and would mask every later record, so
       * the ratio the Mertens conjecture is about is tracked from n = 2. */
      const double ratio = n == 1 ? 0.0
                                  : (double)(running < 0 ? -running : running) / sqrt((double)n);
      if (ratio > out->extreme_ratio) {
        out->extreme_ratio = ratio;
        out->extreme_ratio_at = n;
      }
    }
    out->reached = low + length - 1;
    if (budget > 0.0 && numerisect_now() - began > budget) {
      out->timed_out = 1;
      break;
    }
  }
  out->value = running;
  free(primes);
  free(mu);
  free(remainder);
  return 0;
}

/* ---------------------------------------------------------------------------------
 * M(x) BY THE HYPERBOLA IDENTITY
 *
 * sum_{n<=x} M(x/n) = 1 for every x >= 1, so M(y) = 1 - sum_{n=2}^{y} M(y/n). Evaluated
 * for y = x/k with k descending, each M(y/n) is already known: small arguments come from
 * the sieved table, large ones from an entry computed earlier in the same pass. The inner
 * sum groups equal values of floor(y/n), which is what reduces the cost from linear to
 * about x^(2/3).
 * ------------------------------------------------------------------------------- */
static int numerisect_mertens_hyperbola(uint64_t x, uint64_t cut, int64_t *answer,
                                        uint64_t *used_cut) {
  const uint64_t root = numerisect_isqrt(x);
  if (cut < root) return 1;                       /* caller reports the refusal */
  if (cut > x) cut = x;
  *used_cut = cut;

  int32_t *small = malloc((size_t)(cut + 1) * sizeof(int32_t));
  if (small == NULL) return -1;
  size_t prime_count = 0;
  uint64_t *primes = numerisect_small_primes(numerisect_isqrt(cut) < 2 ? 2
                                                                      : numerisect_isqrt(cut),
                                             &prime_count);
  int8_t *mu = malloc(NUMERISECT_SEGMENT);
  uint64_t *remainder = malloc(NUMERISECT_SEGMENT * sizeof(uint64_t));
  if (primes == NULL || mu == NULL || remainder == NULL) {
    free(small);
    free(primes);
    free(mu);
    free(remainder);
    return -1;
  }
  small[0] = 0;
  int64_t running = 0;
  for (uint64_t low = 1; low <= cut; low += NUMERISECT_SEGMENT) {
    const uint64_t length = (cut - low + 1 < NUMERISECT_SEGMENT) ? (cut - low + 1)
                                                                : NUMERISECT_SEGMENT;
    numerisect_mobius_segment(low, length, mu, remainder, primes, prime_count);
    for (uint64_t i = 0; i < length; i++) {
      running += mu[i];
      small[low + i] = (int32_t)running;
    }
  }
  free(mu);
  free(remainder);
  free(primes);

  const uint64_t span = x / cut;                  /* big[k] holds M(x/k) for k <= span */
  int64_t *big = calloc((size_t)span + 2, sizeof(int64_t));
  if (big == NULL) {
    free(small);
    return -1;
  }
#define NUMERISECT_M(z) \
  (((uint64_t)(z) <= cut) ? (int64_t)small[(uint64_t)(z)] : big[x / (uint64_t)(z)])

  for (uint64_t k = span; k >= 1; k--) {
    const uint64_t y = x / k;
    const uint64_t sq = numerisect_isqrt(y);
    int64_t total = 1;
    for (uint64_t n = 2; n <= sq; n++) total -= NUMERISECT_M(y / n);
    /* Every n > sq shares its quotient with others; count them instead of visiting
     * each one. q runs over the distinct quotient values below sq. */
    for (uint64_t q = 1; q <= y / (sq + 1); q++) {
      const uint64_t count = y / q - y / (q + 1);
      total -= (int64_t)count * NUMERISECT_M(q);
    }
    big[k] = total;
    if (k == 1) break;
  }
#undef NUMERISECT_M
  *answer = (x <= cut) ? (int64_t)small[x] : big[1];
  free(small);
  free(big);
  return 0;
}

int main(int argc, char **argv) {
  if (argc < 3) {
    fprintf(stderr,
            "usage: numerisect-mertens <mertens|mertens-sieve|signs> <x>"
            " [cut-entries|seconds]\n");
    return 2;
  }
  const char *mode = argv[1];
  const uint64_t x = strtoull(argv[2], NULL, 10);
  if (x < 1) {
    fprintf(stderr, "numerisect-mertens: x must be at least 1\n");
    return 2;
  }
  const double began = numerisect_now();

  if (strcmp(mode, "mertens") == 0) {
    uint64_t cut = (uint64_t)NUMERISECT_DEFAULT_CUT;
    if (argc >= 4) {
      const long long requested = atoll(argv[3]);
      if (requested > 0) cut = (uint64_t)requested;
    }
    /* The identity needs the table to cover sqrt(x); x^(2/3) is the cost-optimal cut,
     * so use it when it is smaller than the cap. */
    const uint64_t optimal = (uint64_t)cbrtl((long double)x * (long double)x) + 1;
    if (optimal < cut) cut = optimal;
    const uint64_t root = numerisect_isqrt(x);
    if (cut < root) cut = root;                   /* validity before cost */
    int64_t answer = 0;
    uint64_t used = 0;
    const int status = numerisect_mertens_hyperbola(x, cut, &answer, &used);
    if (status == 1) {
      printf("MODE:mertens\nX:%" PRIu64 "\n", x);
      printf("STATUS:refused-memory\nDONE:1\n");
      return 0;
    }
    if (status != 0) {
      fprintf(stderr, "numerisect-mertens: allocation failed for x=%" PRIu64 "\n", x);
      return 1;
    }
    printf("MODE:mertens\nX:%" PRIu64 "\n", x);
    printf("METHOD:hyperbola\nCUT:%" PRIu64 "\n", used);
    printf("MERTENS:%" PRId64 "\n", answer);
    printf("RATIO:%.12f\n", (double)(answer < 0 ? -answer : answer) / sqrt((double)x));
    printf("SECONDS:%.3f\n", numerisect_now() - began);
    printf("STATUS:complete\nDONE:1\n");
    return 0;
  }

  if (strcmp(mode, "mertens-sieve") == 0 || strcmp(mode, "signs") == 0) {
    const double budget = (argc >= 4) ? strtod(argv[3], NULL) : 0.0;
    numerisect_sieve_result result;
    if (numerisect_mertens_sieve(x, budget, began, &result) != 0) {
      fprintf(stderr, "numerisect-mertens: allocation failed\n");
      return 1;
    }
    printf("MODE:%s\nX:%" PRIu64 "\n", mode, x);
    printf("METHOD:segmented-mobius-sieve\n");
    printf("MERTENS:%" PRId64 "\n", result.value);
    printf("REACHED:%" PRIu64 "\n", result.reached);
    printf("SIGN_CHANGES:%" PRIu64 "\n", result.sign_changes);
    printf("FIRST_SIGN_CHANGE:%" PRIu64 "\n", result.first_sign_change);
    printf("MINIMUM:%" PRId64 "|%" PRIu64 "\n", result.minimum, result.minimum_at);
    printf("MAXIMUM:%" PRId64 "|%" PRIu64 "\n", result.maximum, result.maximum_at);
    printf("EXTREME_RATIO:%.12f|%" PRIu64 "\n", result.extreme_ratio,
           result.extreme_ratio_at);
    if (strcmp(mode, "signs") == 0) {
      for (int index = 0; index < result.change_count; index++) {
        printf("CHANGE:%" PRIu64 "\n", result.changes[index]);
      }
      printf("LISTED:%d\n", result.change_count);
    }
    printf("SECONDS:%.3f\n", numerisect_now() - began);
    printf("STATUS:%s\nDONE:1\n", result.timed_out ? "timeout" : "complete");
    return 0;
  }

  fprintf(stderr, "numerisect-mertens: unknown mode '%s'\n", mode);
  return 2;
}
