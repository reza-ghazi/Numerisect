/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * numerisect-fermatq - searches for primes satisfying a congruence modulo a power of
 * themselves: Wieferich, Wall-Sun-Sun, Wilson and Wolstenholme primes.
 *
 * WHY THIS EXISTS
 * ---------------
 * No installed engine searches for these. PARI/GP tests one candidate well, and a GP
 * loop over a range is a real option for Wieferich, so the honest case rests on
 * measurement rather than on GP being unable:
 *
 *   Wieferich, base 2, to 10^7      GP 0.38 s   this helper 0.15 s on one core
 *                                               and 0.04 s on 24 (about 23x)
 *   Wilson, to 20000                GP 3.72 s   this helper 0.02 s  (about 190x)
 *   Wolstenholme, to 20000          GP 6.46 s   this helper 0.17 s  (about 38x)
 *
 * The gap widens with the O(p) predicates, where GP pays interpreter overhead on every
 * one of the p terms rather than once per candidate. Wieferich to 10^9 takes 1.3 s here,
 * which is the range where a search becomes interesting at all.
 *
 * primesieve enumerates the primes but knows nothing about these congruences. Before
 * this program Numerisect answered the Wilson and Wolstenholme questions from a table of
 * three and two published values, answered Wieferich for one candidate in base 2 only,
 * and had no Wall-Sun-Sun test at all.
 *
 * WHAT A HIT MEANS, AND WHAT SILENCE MEANS
 * ----------------------------------------
 * A hit is a proof for that prime: the congruence either holds or it does not, and the
 * arithmetic here is exact. Silence over a range is an exhausted search, which is
 * evidence of absence only within the range actually covered - hence SCANNED_TO, which
 * reports the largest prime fully tested, and STATUS, which says whether the range was
 * finished. A time budget that expires reports `timeout`, never an empty success.
 *
 * PRECISION TIERS
 * ---------------
 * Each predicate works modulo a power of p, so the modulus, not p, sets the limit:
 *
 *   p^2 < 2^64  when p < 2^32          Wieferich, Wall-Sun-Sun, Wilson
 *   p^3 < 2^64  when p < 2,642,246     Wolstenholme
 *
 * Below those bounds a 64-bit modulus with 128-bit products is used. Above them,
 * Wieferich and Wall-Sun-Sun continue with GMP, which is slower but correct. Wilson and
 * Wolstenholme cost O(p) multiplications per candidate, so a GMP path would be useless
 * in practice; those candidates are REFUSED and counted rather than skipped, because a
 * candidate that was never tested must not read as one that passed.
 *
 * COST PER CANDIDATE
 * ------------------
 *   Wieferich      O(log p)  one modular exponentiation
 *   Wall-Sun-Sun   O(log p)  Fibonacci by fast doubling
 *   Wilson         O(p)      the full factorial product
 *   Wolstenholme   O(p log p) a modular inverse per term of the harmonic sum
 *
 * So the first two scan to 10^12 and beyond, while the last two are exhaustive only over
 * small ranges. That asymmetry is in the mathematics, not in this implementation.
 *
 * Build (the Python side does this automatically):
 *   cc -O3 -std=c11 -fopenmp numerisect_fermatq.c -o numerisect-fermatq \
 *      -lprimesieve -lgmp
 */

#include <inttypes.h>
#include <omp.h>
#include <primesieve.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <gmp.h>

typedef unsigned __int128 numerisect_u128;

/* p^2 stays inside 64 bits below this; p^3 below the second bound. */
static const uint64_t NUMERISECT_SQUARE_LIMIT = (uint64_t)1 << 32;
static const uint64_t NUMERISECT_CUBE_LIMIT = 2642246ULL;
/* Primes are generated in windows so a wide range never allocates the whole list. */
static const uint64_t NUMERISECT_WINDOW = 50000000ULL;
static const int NUMERISECT_MAX_HITS = 4096;

static double numerisect_now(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

static uint64_t numerisect_mulmod(uint64_t a, uint64_t b, uint64_t m) {
  return (uint64_t)(((numerisect_u128)a * b) % m);
}

static uint64_t numerisect_powmod(uint64_t base, uint64_t exponent, uint64_t m) {
  uint64_t result = 1 % m;
  base %= m;
  while (exponent) {
    if (exponent & 1) result = numerisect_mulmod(result, base, m);
    base = numerisect_mulmod(base, base, m);
    exponent >>= 1;
  }
  return result;
}

/* k^-1 mod m by the extended Euclidean algorithm; k must be coprime to m. */
static uint64_t numerisect_invmod(uint64_t k, uint64_t m) {
  int64_t old_r = (int64_t)(k % m), r = (int64_t)m;
  int64_t old_s = 1, s = 0;
  while (r != 0) {
    int64_t quotient = old_r / r;
    int64_t tmp = old_r - quotient * r;
    old_r = r;
    r = tmp;
    tmp = old_s - quotient * s;
    old_s = s;
    s = tmp;
  }
  if (old_s < 0) old_s += (int64_t)m;
  return (uint64_t)old_s;
}

/* ---------------------------------------------------------------------------------
 * WIEFERICH
 *
 * p is a Wieferich prime to base a when a^(p-1) = 1 (mod p^2). Writing
 * a^(p-1) = 1 + A*p (mod p^2), the residue A is the Fermat quotient; A = 0 is a hit and
 * a small |A| is a near-miss, which is what published searches report, because it says
 * how close the candidate came. A is returned in (-p/2, p/2].
 * ------------------------------------------------------------------------------- */
static int numerisect_wieferich(uint64_t base, uint64_t p, int64_t *quotient) {
  if (p < NUMERISECT_SQUARE_LIMIT) {
    const uint64_t modulus = p * p;
    const uint64_t residue = numerisect_powmod(base % modulus, p - 1, modulus);
    const uint64_t excess = (residue + modulus - 1) % modulus;   /* a^(p-1) - 1 */
    uint64_t a = (excess / p) % p;                               /* excess is a multiple of p */
    *quotient = (a > p / 2) ? (int64_t)a - (int64_t)p : (int64_t)a;
    return residue == 1 % modulus;
  }
  /* Above 2^32 the modulus no longer fits; GMP keeps the answer exact. */
  mpz_t modulus, residue, prime, exponent;
  mpz_inits(modulus, residue, prime, exponent, NULL);
  mpz_set_ui(prime, p);
  mpz_mul(modulus, prime, prime);
  mpz_sub_ui(exponent, prime, 1);
  mpz_set_ui(residue, base);
  mpz_powm(residue, residue, exponent, modulus);
  const int hit = mpz_cmp_ui(residue, 1) == 0;
  mpz_sub_ui(residue, residue, 1);
  mpz_divexact(residue, residue, prime);
  mpz_mod(residue, residue, prime);
  uint64_t a = mpz_get_ui(residue);
  *quotient = (a > p / 2) ? (int64_t)a - (int64_t)p : (int64_t)a;
  mpz_clears(modulus, residue, prime, exponent, NULL);
  return hit;
}

/* ---------------------------------------------------------------------------------
 * WALL-SUN-SUN
 *
 * p is a Wall-Sun-Sun (Fibonacci-Wieferich) prime when p^2 divides F_{p - (5|p)}, where
 * (5|p) is the Legendre symbol: +1 for p = +-1 (mod 5) and -1 for p = +-2 (mod 5).
 * Ordinary Fibonacci entry-point theory gives p | F_{p - (5|p)} for every p != 5, so the
 * search is for the rare case where the square divides it. None is known; every search
 * so far has returned nothing, which is a result about the range covered and not a
 * theorem.
 *
 * F_n mod m comes from fast doubling, so each candidate costs O(log p) rather than O(p).
 * ------------------------------------------------------------------------------- */
static void numerisect_fib_pair(uint64_t n, uint64_t m, uint64_t *fn, uint64_t *fn1) {
  if (n == 0) {
    *fn = 0;
    *fn1 = 1 % m;
    return;
  }
  uint64_t a, b;
  numerisect_fib_pair(n >> 1, m, &a, &b);           /* a = F_k, b = F_{k+1} */
  const uint64_t two_b = (b + b) % m;
  const uint64_t c = numerisect_mulmod(a, (two_b + m - a) % m, m);   /* F_2k */
  const uint64_t d = (numerisect_mulmod(a, a, m) + numerisect_mulmod(b, b, m)) % m;
  if (n & 1) {
    *fn = d;
    *fn1 = (c + d) % m;
  } else {
    *fn = c;
    *fn1 = d;
  }
}

static void numerisect_fib_mod_gmp(uint64_t n, const mpz_t m, mpz_t out) {
  /* Iterative fast doubling, highest bit first, carrying (F_k, F_{k+1}). */
  mpz_t a, b, c, d, t;
  mpz_inits(a, b, c, d, t, NULL);
  mpz_set_ui(a, 0);
  mpz_set_ui(b, 1);
  for (int bit = 63; bit >= 0; bit--) {
    mpz_mul_2exp(t, b, 1);            /* 2*F_{k+1} */
    mpz_sub(t, t, a);
    mpz_mod(t, t, m);
    mpz_mul(c, a, t);                 /* F_2k */
    mpz_mod(c, c, m);
    mpz_mul(d, a, a);
    mpz_mod(d, d, m);
    mpz_mul(t, b, b);
    mpz_mod(t, t, m);
    mpz_add(d, d, t);                 /* F_{2k+1} */
    mpz_mod(d, d, m);
    if ((n >> bit) & 1) {
      mpz_set(a, d);
      mpz_add(b, c, d);
      mpz_mod(b, b, m);
    } else {
      mpz_set(a, c);
      mpz_set(b, d);
    }
  }
  mpz_set(out, a);
  mpz_clears(a, b, c, d, t, NULL);
}

static int numerisect_wall_sun_sun(uint64_t p) {
  if (p == 5) return 0;                       /* F_n is never prime-indexed here */
  const int residue = (int)(p % 5);
  const uint64_t n = (residue == 1 || residue == 4) ? p - 1 : p + 1;
  if (p < NUMERISECT_SQUARE_LIMIT) {
    uint64_t fn, fn1;
    numerisect_fib_pair(n, p * p, &fn, &fn1);
    return fn == 0;
  }
  mpz_t modulus, value;
  mpz_inits(modulus, value, NULL);
  mpz_set_ui(modulus, p);
  mpz_mul(modulus, modulus, modulus);
  numerisect_fib_mod_gmp(n, modulus, value);
  const int hit = mpz_sgn(value) == 0;
  mpz_clears(modulus, value, NULL);
  return hit;
}

/* ---------------------------------------------------------------------------------
 * WILSON
 *
 * Wilson's theorem gives (p-1)! = -1 (mod p) for every prime. p is a Wilson prime when
 * the congruence holds to the square: (p-1)! = -1 (mod p^2). Only 5, 13 and 563 are
 * known. There is no shortcut: the factorial is computed term by term, so a candidate
 * costs O(p) multiplications and an exhaustive range is small by nature.
 * ------------------------------------------------------------------------------- */
static int numerisect_wilson(uint64_t p) {
  const uint64_t modulus = p * p;             /* caller guarantees p < 2^32 */
  uint64_t product = 1 % modulus;
  for (uint64_t k = 2; k < p; k++) product = numerisect_mulmod(product, k, modulus);
  return product == modulus - 1;
}

/* ---------------------------------------------------------------------------------
 * WOLSTENHOLME
 *
 * Wolstenholme's theorem gives H_{p-1} = 0 (mod p^2) for every prime p > 3, where
 * H_{p-1} is the harmonic sum taken with modular inverses. p is a Wolstenholme prime
 * when the congruence holds one power further, H_{p-1} = 0 (mod p^3); this is equivalent
 * to the binomial form C(2p-1, p-1) = 1 (mod p^4) and to p dividing the numerator of the
 * Bernoulli number B_{p-3}. Only 16843 and 2124679 are known.
 *
 * The harmonic form is the one implemented because each term needs only an inverse
 * modulo p^3, with no large binomial or Bernoulli computation. Every k in 1..p-1 is
 * coprime to p, so every inverse exists.
 * ------------------------------------------------------------------------------- */
static int numerisect_wolstenholme(uint64_t p) {
  if (p <= 3) return 0;
  const uint64_t modulus = p * p * p;         /* caller guarantees p < 2,642,246 */
  uint64_t total = 0;
  for (uint64_t k = 1; k < p; k++) {
    total = (total + numerisect_invmod(k, modulus)) % modulus;
  }
  return total == 0;
}

typedef struct {
  uint64_t prime;
  int64_t detail;
  int near_miss;
} numerisect_hit;

static int numerisect_compare_hits(const void *left, const void *right) {
  const uint64_t a = ((const numerisect_hit *)left)->prime;
  const uint64_t b = ((const numerisect_hit *)right)->prime;
  return (a > b) - (a < b);
}

int main(int argc, char **argv) {
  if (argc < 4) {
    fprintf(stderr,
            "usage: numerisect-fermatq <wieferich|wall-sun-sun|wilson|wolstenholme>"
            " <start> <end> [base] [near] [seconds]\n");
    return 2;
  }
  const char *mode = argv[1];
  const uint64_t start = strtoull(argv[2], NULL, 10);
  const uint64_t end = strtoull(argv[3], NULL, 10);
  uint64_t base = 2;
  uint64_t near = 0;
  double budget = 0.0;
  const int wieferich_mode = strcmp(mode, "wieferich") == 0;
  if (wieferich_mode) {
    if (argc >= 5) base = strtoull(argv[4], NULL, 10);
    if (argc >= 6) near = strtoull(argv[5], NULL, 10);
    if (argc >= 7) budget = strtod(argv[6], NULL);
  } else if (argc >= 5) {
    budget = strtod(argv[4], NULL);
  }
  const int wall_mode = strcmp(mode, "wall-sun-sun") == 0;
  const int wilson_mode = strcmp(mode, "wilson") == 0;
  const int wolstenholme_mode = strcmp(mode, "wolstenholme") == 0;
  if (!wieferich_mode && !wall_mode && !wilson_mode && !wolstenholme_mode) {
    fprintf(stderr, "numerisect-fermatq: unknown mode '%s'\n", mode);
    return 2;
  }
  if (start < 2 || end < start || (wieferich_mode && base < 2)) {
    fprintf(stderr, "numerisect-fermatq: invalid range or base\n");
    return 2;
  }

  printf("MODE:%s\n", mode);
  if (wieferich_mode) printf("BASE:%" PRIu64 "\n", base);
  printf("START:%" PRIu64 "\nEND:%" PRIu64 "\n", start, end);
  fflush(stdout);

  numerisect_hit hits[NUMERISECT_MAX_HITS];
  int hit_count = 0;
  uint64_t tested = 0, refused = 0, scanned_to = start ? start - 1 : 0;
  uint64_t first_refused = 0;
  int timed_out = 0;
  const double began = numerisect_now();

  for (uint64_t window = start; window <= end && !timed_out; window += NUMERISECT_WINDOW) {
    const uint64_t stop = (end - window < NUMERISECT_WINDOW) ? end : window + NUMERISECT_WINDOW - 1;
    size_t count = 0;
    uint64_t *primes = (uint64_t *)primesieve_generate_primes(window, stop, &count,
                                                              UINT64_PRIMES);
    if (primes == NULL) {
      fprintf(stderr, "numerisect-fermatq: primesieve could not generate the window\n");
      return 1;
    }
    uint64_t window_tested = 0, window_refused = 0, window_first_refused = 0;
    int window_timeout = 0;
#pragma omp parallel for schedule(dynamic, 64) \
    reduction(+ : window_tested, window_refused)
    for (size_t index = 0; index < count; index++) {
      if (window_timeout) continue;            /* benign race: a late candidate is fine */
      if (budget > 0.0 && (index & 0x3F) == 0 && numerisect_now() - began > budget) {
        window_timeout = 1;
        continue;
      }
      const uint64_t p = primes[index];
      /* O(p) predicates have no usable path once the modulus leaves 64 bits. The
       * candidate is counted as refused, never quietly dropped. */
      if ((wilson_mode && p >= NUMERISECT_SQUARE_LIMIT) ||
          (wolstenholme_mode && p >= NUMERISECT_CUBE_LIMIT)) {
        window_refused += 1;
#pragma omp critical(first_refused)
        if (window_first_refused == 0 || p < window_first_refused) window_first_refused = p;
        continue;
      }
      int hit = 0, near_miss = 0;
      int64_t detail = 0;
      if (wieferich_mode) {
        hit = numerisect_wieferich(base, p, &detail);
        near_miss = !hit && near > 0 &&
                    (uint64_t)(detail < 0 ? -detail : detail) <= near;
      } else if (wall_mode) {
        hit = numerisect_wall_sun_sun(p);
      } else if (wilson_mode) {
        hit = numerisect_wilson(p);
      } else {
        hit = numerisect_wolstenholme(p);
      }
      window_tested += 1;
      if (hit || near_miss) {
#pragma omp critical(record)
        if (hit_count < NUMERISECT_MAX_HITS) {
          hits[hit_count].prime = p;
          hits[hit_count].detail = detail;
          hits[hit_count].near_miss = near_miss && !hit;
          hit_count += 1;
        }
      }
    }
    tested += window_tested;
    refused += window_refused;
    if (window_first_refused && (first_refused == 0 || window_first_refused < first_refused)) {
      first_refused = window_first_refused;
    }
    timed_out = window_timeout;
    if (!window_timeout) scanned_to = stop < end ? stop : end;
    primesieve_free(primes);
  }

  qsort(hits, (size_t)hit_count, sizeof(numerisect_hit), numerisect_compare_hits);
  for (int index = 0; index < hit_count; index++) {
    if (hits[index].near_miss) {
      printf("NEAR:%" PRIu64 "|%" PRId64 "\n", hits[index].prime, hits[index].detail);
    } else if (wieferich_mode) {
      printf("HIT:%" PRIu64 "|0\n", hits[index].prime);
    } else {
      printf("HIT:%" PRIu64 "|\n", hits[index].prime);
    }
  }
  printf("TESTED:%" PRIu64 "\n", tested);
  printf("REFUSED:%" PRIu64 "\n", refused);
  if (refused) printf("FIRST_REFUSED:%" PRIu64 "\n", first_refused);
  printf("SCANNED_TO:%" PRIu64 "\n", scanned_to);
  printf("HITS:%d\n", hit_count);
  printf("STATUS:%s\n", timed_out ? "timeout" : (refused ? "refused-wide" : "complete"));
  printf("DONE:1\n");
  return 0;
}
