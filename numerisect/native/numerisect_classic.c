/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * numerisect-classic - three classical factoring methods that no installed engine
 * provides: the continued-fraction method (CFRAC, Morrison and Brillhart 1975), Lehman's
 * deterministic method (1974), and Hart's one-line factorization (2012).
 *
 * WHY THESE THREE, AND WHY HERE
 * -----------------------------
 * The installed engines cover the methods that win races: YAFU and Msieve do QS and NFS,
 * GMP-ECM does ECM and P-1/P+1, PARI/GP exposes rho and its own factorint strategies, and
 * numerisect_squfof.c already supplies SQUFOF. None of them exposes CFRAC, Lehman or
 * Hart. They are not added here to be fastest - CFRAC was superseded by the quadratic
 * sieve in 1981 - but because each answers a question the fast engines cannot:
 *
 *   CFRAC    the first subexponential method, and the one that made the smoothness-plus-
 *            linear-algebra idea concrete. Its relations come from the continued fraction
 *            of sqrt(N), so it needs no sieving interval at all, and the dependency it
 *            finds is a congruence of squares a reader can check by hand.
 *   LEHMAN   deterministic, with a proven O(N^(1/3)) bound. No probabilistic method here
 *            carries a guarantee, and a guarantee is the point of running it.
 *   HART     one line of arithmetic per iteration, and remarkably effective on numbers
 *            with two close factors - exactly where rho and ECM struggle.
 *
 * All three are exact: a reported factor is a divisor, verified by division before it is
 * printed. None of them proves primality, which PARI/GP does afterwards.
 *
 * WHAT A FAILURE MEANS
 * --------------------
 * Each method has a bound - iterations for Hart, the k range for Lehman, relations and
 * the factor base for CFRAC. Exhausting a bound means the method did not succeed within
 * it, which is reported as `exhausted`. It is never evidence that N is prime, and the
 * STATUS line distinguishes it from a factor found and from a wall-clock timeout.
 *
 * Build (the Python side does this automatically):
 *   cc -O3 -std=c11 numerisect_classic.c -o numerisect-classic -lgmp -lm
 */

/* clock_gettime is POSIX, not C11, and -std=c11 hides it without this. */
#define _POSIX_C_SOURCE 200809L

#include <gmp.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* A relation keeps its exponent vector twice: reduced mod 2 as a bitmap for the linear
 * algebra, and in full as (index, exponent) pairs so the square root can be rebuilt. */
#define NUMERISECT_MAX_FACTORS 64

typedef struct {
  mpz_t residue;                 /* A_{i-1} mod N */
  uint64_t *parity;              /* exponent vector mod 2, one bit per base element */
  uint64_t *history;             /* which relations were combined to make this row */
  int indices[NUMERISECT_MAX_FACTORS];
  int exponents[NUMERISECT_MAX_FACTORS];
  int term_count;
} numerisect_relation;

static double numerisect_now(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

static size_t numerisect_words(size_t bits) { return (bits + 63) / 64; }

static int numerisect_bit(const uint64_t *vector, size_t index) {
  return (vector[index / 64] >> (index % 64)) & 1ULL;
}

static void numerisect_flip(uint64_t *vector, size_t index) {
  vector[index / 64] ^= 1ULL << (index % 64);
}

static void numerisect_xor(uint64_t *into, const uint64_t *from, size_t words) {
  for (size_t i = 0; i < words; i++) into[i] ^= from[i];
}

static int numerisect_is_zero(const uint64_t *vector, size_t words) {
  for (size_t i = 0; i < words; i++) {
    if (vector[i]) return 0;
  }
  return 1;
}

/* Report a divisor once it has been verified by division. Returns 1 when the split is
 * nontrivial, so callers can treat a trivial gcd as "keep going". */
static int numerisect_report(const mpz_t n, const mpz_t candidate, const char *how) {
  if (mpz_cmp_ui(candidate, 1) <= 0) return 0;
  if (mpz_cmp(candidate, n) == 0) return 0;
  if (!mpz_divisible_p(n, candidate)) return 0;
  mpz_t cofactor;
  mpz_init(cofactor);
  mpz_divexact(cofactor, n, candidate);
  char *factor_text = mpz_get_str(NULL, 10, candidate);
  char *cofactor_text = mpz_get_str(NULL, 10, cofactor);
  printf("FACTOR:%s|%s|%s\n", factor_text, cofactor_text, how);
  free(factor_text);
  free(cofactor_text);
  mpz_clear(cofactor);
  return 1;
}

/* ---------------------------------------------------------------------------------
 * HART'S ONE-LINE FACTORIZATION
 *
 * For i = 1, 2, 3, ...: s = ceil(sqrt(N*i)), m = s^2 mod N. When m is a perfect square,
 * gcd(N, s - sqrt(m)) is usually a proper divisor. That is the whole method; its strength
 * is that each iteration is one square root, one squaring and one reduction.
 * ------------------------------------------------------------------------------- */
static int numerisect_hart(const mpz_t n, uint64_t iterations, double budget, double began,
                           uint64_t *used, int *timed_out) {
  mpz_t s, m, root, difference, divisor, scaled;
  mpz_inits(s, m, root, difference, divisor, scaled, NULL);
  int found = 0;
  uint64_t i;
  for (i = 1; i <= iterations; i++) {
    mpz_mul_ui(scaled, n, i);
    mpz_sqrt(s, scaled);
    if (mpz_perfect_square_p(scaled) == 0) mpz_add_ui(s, s, 1);   /* ceil */
    mpz_mul(m, s, s);
    mpz_mod(m, m, n);
    if (mpz_perfect_square_p(m)) {
      mpz_sqrt(root, m);
      mpz_sub(difference, s, root);
      mpz_gcd(divisor, difference, n);
      if (numerisect_report(n, divisor, "Hart one-line")) {
        found = 1;
        break;
      }
    }
    if (budget > 0.0 && (i & 0x3FF) == 0 && numerisect_now() - began > budget) {
      *timed_out = 1;
      break;
    }
  }
  *used = i > iterations ? iterations : i;
  mpz_clears(s, m, root, difference, divisor, scaled, NULL);
  return found;
}

/* ---------------------------------------------------------------------------------
 * LEHMAN'S METHOD
 *
 * Deterministic in O(N^(1/3)). Trial division up to N^(1/3) finds any small factor; past
 * that, if N = pq with both factors above N^(1/3), then for some k <= N^(1/3) there is an
 * a in a short interval above 2*sqrt(k*N) with a^2 - 4kN a perfect square. The interval
 * has length about N^(1/6)/(4 sqrt k), which is what bounds the total work.
 * ------------------------------------------------------------------------------- */
static int numerisect_lehman(const mpz_t n, double budget, double began, uint64_t *used,
                             int *timed_out) {
  mpz_t cube_root, divisor, product, a, square, root, difference, limit;
  mpz_inits(cube_root, divisor, product, a, square, root, difference, limit, NULL);
  int found = 0;

  /* N^(1/3), rounded up, bounds both the trial division and the k loop. */
  mpz_root(cube_root, n, 3);
  mpz_add_ui(cube_root, cube_root, 1);
  if (!mpz_fits_ulong_p(cube_root)) {
    printf("REFUSED:the cube root of N exceeds the deterministic bound this build can walk\n");
    mpz_clears(cube_root, divisor, product, a, square, root, difference, limit, NULL);
    return -1;
  }
  const uint64_t bound = mpz_get_ui(cube_root);
  for (uint64_t d = 2; d <= bound; d++) {
    if (mpz_divisible_ui_p(n, d)) {
      mpz_set_ui(divisor, d);
      if (numerisect_report(n, divisor, "Lehman trial division below N^(1/3)")) {
        found = 1;
        break;
      }
    }
    if (budget > 0.0 && (d & 0xFFFF) == 0 && numerisect_now() - began > budget) {
      *timed_out = 1;
      break;
    }
  }
  uint64_t k = 0;
  if (!found && !*timed_out) {
    for (k = 1; k <= bound; k++) {
      mpz_mul_ui(product, n, 4 * k);                 /* 4kN */
      mpz_sqrt(a, product);
      /* The interval is [ceil(2 sqrt(kN)), that + N^(1/6)/(4 sqrt k)]. */
      const double span = pow(mpz_get_d(n), 1.0 / 6.0) / (4.0 * sqrt((double)k));
      const uint64_t steps = (uint64_t)span + 2;
      for (uint64_t step = 0; step <= steps && !found; step++) {
        mpz_add_ui(limit, a, step);
        mpz_mul(square, limit, limit);
        mpz_sub(square, square, product);            /* a^2 - 4kN */
        if (mpz_sgn(square) < 0) continue;
        if (!mpz_perfect_square_p(square)) continue;
        mpz_sqrt(root, square);
        mpz_add(difference, limit, root);
        mpz_gcd(divisor, difference, n);
        if (numerisect_report(n, divisor, "Lehman congruence of squares")) found = 1;
      }
      if (found) break;
      if (budget > 0.0 && (k & 0xFF) == 0 && numerisect_now() - began > budget) {
        *timed_out = 1;
        break;
      }
    }
  }
  *used = k;
  mpz_clears(cube_root, divisor, product, a, square, root, difference, limit, NULL);
  return found;
}

/* ---------------------------------------------------------------------------------
 * CFRAC (MORRISON AND BRILLHART)
 *
 * The continued fraction of sqrt(N) supplies congruences A_{i-1}^2 = (-1)^i Q_i (mod N)
 * with |Q_i| < 2 sqrt(N), which is why its relations are small without any sieving. The
 * Q_i that factor completely over a chosen base become rows of a matrix over GF(2); any
 * dependency multiplies to a square on both sides, giving X^2 = Y^2 (mod N) and the
 * factor from gcd(X - Y, N).
 *
 * The recurrences used are the standard ones:
 *   P_i = a_{i-1} Q_{i-1} - P_{i-1},  Q_i = (N - P_i^2)/Q_{i-1},
 *   a_i = floor((floor(sqrt N) + P_i)/Q_i),  A_i = a_i A_{i-1} + A_{i-2} (mod N).
 *
 * Only -1 and primes p with N a quadratic residue mod p can divide a Q_i, so the base is
 * restricted accordingly; including others would only waste trial divisions.
 * ------------------------------------------------------------------------------- */
static int numerisect_cfrac(const mpz_t n, uint64_t base_bound, uint64_t max_iterations,
                            double budget, double began, uint64_t *relations_found,
                            uint64_t *iterations_used, int *timed_out) {
  /* Build the factor base: index 0 is the sign, then the admissible primes. */
  int *base = malloc((size_t)base_bound * sizeof(int));
  if (base == NULL) return -1;
  size_t base_size = 1;                      /* slot 0 is -1 */
  char *composite = calloc((size_t)base_bound + 1, 1);
  if (composite == NULL) {
    free(base);
    return -1;
  }
  for (uint64_t p = 2; p <= base_bound; p++) {
    if (composite[p]) continue;
    for (uint64_t q = p * p; q <= base_bound; q += p) composite[q] = 1;
    if (p == 2 || mpz_kronecker_ui(n, (unsigned long)p) >= 0) {
      base[base_size++] = (int)p;
    }
  }
  free(composite);

  const size_t words = numerisect_words(base_size);
  const size_t wanted = base_size + 16;      /* a margin over the matrix width */
  numerisect_relation *rows = calloc(wanted, sizeof(numerisect_relation));
  uint64_t **pivot_parity = calloc(base_size, sizeof(uint64_t *));
  uint64_t **pivot_history = calloc(base_size, sizeof(uint64_t *));
  if (rows == NULL || pivot_parity == NULL || pivot_history == NULL) {
    free(base);
    free(rows);
    free(pivot_parity);
    free(pivot_history);
    return -1;
  }

  /* State at the top of iteration i: p = P_i, q = Q_i, a_numerator = A_{i-1} and
   * a_before = A_{i-2}. Initialised for i = 1 from a_0 = floor(sqrt N):
   * P_1 = a_0, Q_1 = N - a_0^2, A_0 = a_0, A_{-1} = 1. */
  mpz_t sqrt_n, p, q, a_i, a_numerator, a_before, next_p, next_q, temp, residue;
  mpz_t x, y, difference, divisor, power;
  mpz_inits(sqrt_n, p, q, a_i, a_numerator, a_before, next_p, next_q, temp, residue,
            x, y, difference, divisor, power, NULL);
  mpz_sqrt(sqrt_n, n);
  mpz_set(p, sqrt_n);
  mpz_mul(temp, sqrt_n, sqrt_n);
  mpz_sub(q, n, temp);
  mpz_set(a_numerator, sqrt_n);
  mpz_set_ui(a_before, 1);

  int found = 0, parity_sign = 1;
  size_t row_count = 0;
  uint64_t iteration = 0;
  uint64_t *scratch_parity = calloc(words, sizeof(uint64_t));
  uint64_t *scratch_history = calloc(numerisect_words(wanted), sizeof(uint64_t));
  if (scratch_parity == NULL || scratch_history == NULL) found = -1;

  while (found == 0 && iteration < max_iterations && row_count < wanted) {
    iteration++;
    parity_sign = -parity_sign;              /* (-1)^i for this Q_i */

    /* Try to factor Q_i over the base. */
    mpz_abs(residue, q);
    memset(scratch_parity, 0, words * sizeof(uint64_t));
    int indices[NUMERISECT_MAX_FACTORS];
    int exponents[NUMERISECT_MAX_FACTORS];
    int terms = 0;
    int smooth = 1;
    if (parity_sign < 0) {                   /* the sign is base element 0 */
      numerisect_flip(scratch_parity, 0);
      indices[terms] = 0;
      exponents[terms] = 1;
      terms++;
    }
    for (size_t index = 1; index < base_size && smooth; index++) {
      /* Named `prime` rather than `p`, which is the continued fraction's P_i here. */
      const unsigned long prime = (unsigned long)base[index];
      int exponent = 0;
      while (mpz_divisible_ui_p(residue, prime)) {
        mpz_divexact_ui(residue, residue, prime);
        exponent++;
      }
      if (exponent == 0) continue;
      if (terms >= NUMERISECT_MAX_FACTORS) {
        smooth = 0;
        break;
      }
      indices[terms] = (int)index;
      exponents[terms] = exponent;
      terms++;
      if (exponent & 1) numerisect_flip(scratch_parity, index);
    }
    if (smooth && mpz_cmp_ui(residue, 1) == 0) {
      numerisect_relation *row = &rows[row_count];
      mpz_init_set(row->residue, a_numerator);
      mpz_mod(row->residue, row->residue, n);
      row->parity = calloc(words, sizeof(uint64_t));
      row->history = calloc(numerisect_words(wanted), sizeof(uint64_t));
      if (row->parity == NULL || row->history == NULL) {
        found = -1;
        break;
      }
      memcpy(row->parity, scratch_parity, words * sizeof(uint64_t));
      numerisect_flip(row->history, row_count);
      memcpy(row->indices, indices, (size_t)terms * sizeof(int));
      memcpy(row->exponents, exponents, (size_t)terms * sizeof(int));
      row->term_count = terms;
      row_count++;

      /* Reduce the new row against the pivots collected so far. */
      memcpy(scratch_parity, row->parity, words * sizeof(uint64_t));
      memcpy(scratch_history, row->history, numerisect_words(wanted) * sizeof(uint64_t));
      for (size_t column = 0; column < base_size; column++) {
        if (!numerisect_bit(scratch_parity, column)) continue;
        if (pivot_parity[column] == NULL) {
          pivot_parity[column] = malloc(words * sizeof(uint64_t));
          pivot_history[column] = malloc(numerisect_words(wanted) * sizeof(uint64_t));
          if (pivot_parity[column] == NULL || pivot_history[column] == NULL) {
            found = -1;
            break;
          }
          memcpy(pivot_parity[column], scratch_parity, words * sizeof(uint64_t));
          memcpy(pivot_history[column], scratch_history,
                 numerisect_words(wanted) * sizeof(uint64_t));
          break;
        }
        numerisect_xor(scratch_parity, pivot_parity[column], words);
        numerisect_xor(scratch_history, pivot_history[column], numerisect_words(wanted));
      }
      if (found == 0 && numerisect_is_zero(scratch_parity, words)) {
        /* A dependency: the combined relation is a square on both sides. */
        mpz_set_ui(x, 1);
        int *total = calloc(base_size, sizeof(int));
        if (total == NULL) {
          found = -1;
          break;
        }
        for (size_t member = 0; member < row_count; member++) {
          if (!numerisect_bit(scratch_history, member)) continue;
          mpz_mul(x, x, rows[member].residue);
          mpz_mod(x, x, n);
          for (int term = 0; term < rows[member].term_count; term++) {
            total[rows[member].indices[term]] += rows[member].exponents[term];
          }
        }
        mpz_set_ui(y, 1);
        int square = 1;
        for (size_t index = 1; index < base_size; index++) {
          if (total[index] % 2 != 0) {
            square = 0;                      /* cannot happen; guarded rather than assumed */
            break;
          }
          if (total[index] == 0) continue;
          mpz_ui_pow_ui(power, (unsigned long)base[index],
                        (unsigned long)(total[index] / 2));
          mpz_mul(y, y, power);
          mpz_mod(y, y, n);
        }
        free(total);
        if (square) {
          mpz_sub(difference, x, y);
          mpz_gcd(divisor, difference, n);
          if (numerisect_report(n, divisor, "CFRAC congruence of squares")) {
            found = 1;
          } else {
            mpz_add(difference, x, y);
            mpz_gcd(divisor, difference, n);
            if (numerisect_report(n, divisor, "CFRAC congruence of squares")) found = 1;
          }
        }
      }
    }

    /* Advance one step of the expansion:
     *   a_i      = floor((floor(sqrt N) + P_i) / Q_i)
     *   A_i      = a_i A_{i-1} + A_{i-2}  (mod N)
     *   P_{i+1}  = a_i Q_i - P_i
     *   Q_{i+1}  = (N - P_{i+1}^2) / Q_i
     * The division is exact, which is what keeps every Q_i below 2 sqrt(N). */
    if (mpz_sgn(q) == 0) break;                 /* only for a perfect square N */
    mpz_add(temp, sqrt_n, p);
    mpz_fdiv_q(a_i, temp, q);

    mpz_mul(temp, a_i, a_numerator);
    mpz_add(temp, temp, a_before);
    mpz_mod(temp, temp, n);
    mpz_set(a_before, a_numerator);
    mpz_set(a_numerator, temp);

    mpz_mul(next_p, a_i, q);
    mpz_sub(next_p, next_p, p);
    mpz_mul(temp, next_p, next_p);
    mpz_sub(temp, n, temp);
    mpz_divexact(next_q, temp, q);
    mpz_set(p, next_p);
    mpz_set(q, next_q);

    if (budget > 0.0 && (iteration & 0xFF) == 0 && numerisect_now() - began > budget) {
      *timed_out = 1;
      break;
    }
  }

  *relations_found = row_count;
  *iterations_used = iteration;
  for (size_t index = 0; index < row_count; index++) {
    mpz_clear(rows[index].residue);
    free(rows[index].parity);
    free(rows[index].history);
  }
  for (size_t index = 0; index < base_size; index++) {
    free(pivot_parity[index]);
    free(pivot_history[index]);
  }
  free(scratch_parity);
  free(scratch_history);
  free(rows);
  free(pivot_parity);
  free(pivot_history);
  free(base);
  mpz_clears(sqrt_n, p, q, a_i, a_numerator, a_before, next_p, next_q, temp, residue,
             x, y, difference, divisor, power, NULL);
  printf("BASE_SIZE:%zu\n", base_size);
  return found;
}

int main(int argc, char **argv) {
  if (argc < 3) {
    fprintf(stderr,
            "usage: numerisect-classic <cfrac|lehman|hart> <n> [bound] [seconds]\n");
    return 2;
  }
  const char *mode = argv[1];
  mpz_t n;
  mpz_init(n);
  if (mpz_set_str(n, argv[2], 10) != 0 || mpz_cmp_ui(n, 4) < 0) {
    fprintf(stderr, "numerisect-classic: n must be an integer of at least 4\n");
    mpz_clear(n);
    return 2;
  }
  const uint64_t bound = (argc >= 4) ? strtoull(argv[3], NULL, 10) : 0;
  const double budget = (argc >= 5) ? strtod(argv[4], NULL) : 0.0;

  printf("MODE:%s\n", mode);
  char *text = mpz_get_str(NULL, 10, n);
  printf("N:%s\nDIGITS:%zu\n", text, strlen(text));
  free(text);
  if (mpz_probab_prime_p(n, 25)) {
    /* Every one of these methods looks for a split; there is none to find. */
    printf("PRIME_INPUT:1\nSTATUS:prime-input\nDONE:1\n");
    mpz_clear(n);
    return 0;
  }

  const double began = numerisect_now();
  int timed_out = 0, found = 0;
  uint64_t used = 0, relations = 0, iterations = 0;

  if (strcmp(mode, "hart") == 0) {
    const uint64_t iteration_limit = bound ? bound : 1000000;
    found = numerisect_hart(n, iteration_limit, budget, began, &used, &timed_out);
    printf("ITERATIONS:%" PRIu64 "\nLIMIT:%" PRIu64 "\n", used, iteration_limit);
  } else if (strcmp(mode, "lehman") == 0) {
    found = numerisect_lehman(n, budget, began, &used, &timed_out);
    printf("K_REACHED:%" PRIu64 "\n", used);
  } else if (strcmp(mode, "cfrac") == 0) {
    const uint64_t base_bound = bound ? bound : 2000;
    const uint64_t iteration_limit = 20000000;
    found = numerisect_cfrac(n, base_bound, iteration_limit, budget, began, &relations,
                             &iterations, &timed_out);
    printf("BASE_BOUND:%" PRIu64 "\nRELATIONS:%" PRIu64 "\nITERATIONS:%" PRIu64 "\n",
           base_bound, relations, iterations);
  } else {
    fprintf(stderr, "numerisect-classic: unknown mode '%s'\n", mode);
    mpz_clear(n);
    return 2;
  }

  if (found < 0) {
    fprintf(stderr, "numerisect-classic: the method could not run on this input\n");
    mpz_clear(n);
    return 1;
  }
  printf("SECONDS:%.3f\n", numerisect_now() - began);
  printf("STATUS:%s\n", found ? "factor-found" : (timed_out ? "timeout" : "exhausted"));
  printf("DONE:1\n");
  mpz_clear(n);
  return 0;
}
