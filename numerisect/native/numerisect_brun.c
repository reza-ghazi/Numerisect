/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * numerisect-brun - Brun-type constants: the sum of reciprocals over twin, cousin, sexy,
 * triplet and quadruplet primes, truncated at a stated bound and computed in MPFR.
 *
 * WHY THIS EXISTS
 * ---------------
 * Brun proved that the sum of 1/p over twin primes converges, which is why the constant
 * exists at all. No installed library computes it. primesieve enumerates and counts
 * k-tuplets but sums nothing; primecount counts primes; PARI/GP can express the sum but
 * must iterate in the interpreter, and the sum needs billions of terms to say anything.
 * Numerisect had no Brun computation of any kind: the twin-prime constant appeared in the
 * documentation as prose and nowhere in the application.
 *
 * WHAT THE RESULT IS, AND WHAT IT IS NOT
 * --------------------------------------
 * This computes the TRUNCATED sum up to a bound, exactly as defined, with every term
 * added in MPFR at the requested precision. It is not the constant, and the program never
 * calls it one. Convergence is of order 1/log(x): at x = 10^10 the twin sum is near 1.83
 * against a literature value near 1.902, so the leading digits of the constant itself are
 * NOT determined by any bound reachable here. Published estimates rely on extrapolation
 * models, which this program deliberately does not apply - an extrapolated digit is not a
 * computed digit, and the two must not appear in the same number.
 *
 * The sum is reported with the count of tuples and the largest one found, so a reader can
 * see precisely which finite sum was evaluated.
 *
 * COUNTING CONVENTION
 * -------------------
 * Brun's constant is sum over twin pairs (p, p+2) of (1/p + 1/(p+2)). A prime in two
 * pairs contributes once for each: 5 appears in (3,5) and in (5,7), and B_2 counts both.
 * The same convention extends to the other patterns, one reciprocal per tuple member.
 *
 * PATTERNS, AND WHY THESE
 * -----------------------
 *   twin        (p, p+2)
 *   cousin      (p, p+4)
 *   sexy        (p, p+6)
 *   triplet     (p, p+2, p+6) and (p, p+4, p+6), the two admissible shapes
 *   quadruplet  (p, p+2, p+6, p+8)
 *
 * Admissibility is why no other shape appears: (p, p+2, p+4) contains a multiple of 3 for
 * every p > 3, so it cannot recur.
 *
 * A pattern's members need not be consecutive primes - (3, 7) is a cousin pair with 5
 * between them, and sexy pairs routinely have one or two primes inside the gap - so each
 * required offset is looked for by arithmetic rather than by taking the next prime.
 *
 * WINDOWS WITHOUT DOUBLE COUNTING
 * -------------------------------
 * Primes are generated in windows, each extended by a short lookahead so a tuple whose
 * first member sits near the end can still see its later members. A tuple is counted by
 * the window containing its FIRST member only, so every tuple is counted exactly once no
 * matter where a boundary falls.
 *
 * Build (the Python side does this automatically):
 *   cc -O3 -std=c11 numerisect_brun.c -o numerisect-brun -lprimesieve -lmpfr -lgmp -lm
 */

/* clock_gettime is POSIX, not C11, and -std=c11 hides it without this. */
#define _POSIX_C_SOURCE 200809L

#include <inttypes.h>
#include <mpfr.h>
#include <primesieve.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define NUMERISECT_WINDOW 10000000ULL
/* The widest pattern spans 8, so a lookahead of 16 always covers every member. */
#define NUMERISECT_LOOKAHEAD 16ULL
#define NUMERISECT_MAX_MEMBERS 4

static double numerisect_now(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

/* One admissible shape: the offsets from the first member. */
typedef struct {
  int length;
  uint64_t offsets[NUMERISECT_MAX_MEMBERS];
} numerisect_shape;

typedef struct {
  const char *name;
  int shape_count;
  numerisect_shape shapes[2];
} numerisect_pattern;

static const numerisect_pattern NUMERISECT_PATTERNS[] = {
    {"twin", 1, {{2, {0, 2}}}},
    {"cousin", 1, {{2, {0, 4}}}},
    {"sexy", 1, {{2, {0, 6}}}},
    {"triplet", 2, {{3, {0, 2, 6}}, {3, {0, 4, 6}}}},
    {"quadruplet", 1, {{4, {0, 2, 6, 8}}}},
};

/* Is `value` present among window[index..count-1]? The scan stops as soon as the window
 * passes `value`, so it touches only the few primes inside the pattern's span. */
static int numerisect_present(const uint64_t *window, size_t index, size_t count,
                              uint64_t value) {
  for (size_t j = index; j < count && window[j] <= value; j++) {
    if (window[j] == value) return 1;
  }
  return 0;
}

int main(int argc, char **argv) {
  if (argc < 3) {
    fprintf(stderr,
            "usage: numerisect-brun <twin|cousin|sexy|triplet|quadruplet> <limit>"
            " [digits] [seconds]\n");
    return 2;
  }
  const char *kind = argv[1];
  const uint64_t limit = strtoull(argv[2], NULL, 10);
  const int digits = (argc >= 4) ? atoi(argv[3]) : 20;
  const double budget = (argc >= 5) ? strtod(argv[4], NULL) : 0.0;

  const numerisect_pattern *pattern = NULL;
  for (size_t i = 0; i < sizeof(NUMERISECT_PATTERNS) / sizeof(NUMERISECT_PATTERNS[0]); i++) {
    if (strcmp(kind, NUMERISECT_PATTERNS[i].name) == 0) pattern = &NUMERISECT_PATTERNS[i];
  }
  if (pattern == NULL) {
    fprintf(stderr, "numerisect-brun: unknown pattern '%s'\n", kind);
    return 2;
  }
  if (limit < 5 || digits < 3 || digits > 1000) {
    fprintf(stderr, "numerisect-brun: limit must be >= 5 and digits between 3 and 1000\n");
    return 2;
  }

  /* Guard bits above what is printed: every term is rounded once and there are many
   * terms, so the working precision must exceed the reported precision. */
  const mpfr_prec_t precision = (mpfr_prec_t)((double)digits * 3.3219281) + 96;
  mpfr_t total, term;
  mpfr_init2(total, precision);
  mpfr_init2(term, precision);
  mpfr_set_zero(total, 1);

  const double began = numerisect_now();
  uint64_t tuples = 0, members = 0, largest = 0, reached = 0;
  int timed_out = 0;

  for (uint64_t low = 2; low <= limit && !timed_out; low += NUMERISECT_WINDOW) {
    const uint64_t high = (limit - low < NUMERISECT_WINDOW) ? limit
                                                            : low + NUMERISECT_WINDOW - 1;
    /* Generate past `high` so a tuple starting just below it is complete here, but never
     * past the requested limit, whose members would be excluded anyway. */
    const uint64_t generate_to = (limit - high < NUMERISECT_LOOKAHEAD)
                                     ? limit
                                     : high + NUMERISECT_LOOKAHEAD;
    size_t count = 0;
    uint64_t *window = (uint64_t *)primesieve_generate_primes(low, generate_to, &count,
                                                              UINT64_PRIMES);
    if (window == NULL) {
      fprintf(stderr, "numerisect-brun: primesieve could not generate a window\n");
      mpfr_clears(total, term, NULL);
      return 1;
    }
    for (size_t index = 0; index < count; index++) {
      const uint64_t p = window[index];
      if (p > high) break;              /* a lookahead prime: not this window's to start */
      for (int shape = 0; shape < pattern->shape_count; shape++) {
        const numerisect_shape *candidate = &pattern->shapes[shape];
        const uint64_t last = p + candidate->offsets[candidate->length - 1];
        if (last > limit) continue;     /* the tuple leaves the requested bound */
        int complete = 1;
        for (int member = 1; member < candidate->length && complete; member++) {
          complete = numerisect_present(window, index, count, p + candidate->offsets[member]);
        }
        if (!complete) continue;
        for (int member = 0; member < candidate->length; member++) {
          /* set_ui is exact at this precision, so each term carries exactly one
           * rounding, from the division. */
          mpfr_set_ui(term, p + candidate->offsets[member], MPFR_RNDN);
          mpfr_ui_div(term, 1, term, MPFR_RNDN);
          mpfr_add(total, total, term, MPFR_RNDN);
        }
        members += (uint64_t)candidate->length;
        tuples++;
        largest = p;
        break;                          /* the admissible shapes are mutually exclusive */
      }
    }
    primesieve_free(window);
    reached = high;
    if (budget > 0.0 && numerisect_now() - began > budget) timed_out = 1;
  }

  printf("MODE:brun\nPATTERN:%s\nLIMIT:%" PRIu64 "\n", kind, limit);
  printf("REACHED:%" PRIu64 "\n", reached);
  printf("TUPLES:%" PRIu64 "\nMEMBERS:%" PRIu64 "\n", tuples, members);
  printf("LARGEST:%" PRIu64 "\n", largest);
  printf("DIGITS:%d\nPRECISION_BITS:%ld\n", digits, (long)precision);
  mpfr_printf("SUM:%.*Rf\n", digits, total);
  printf("SECONDS:%.3f\n", numerisect_now() - began);
  printf("STATUS:%s\nDONE:1\n", timed_out ? "timeout" : "complete");
  mpfr_clears(total, term, NULL);
  return 0;
}
