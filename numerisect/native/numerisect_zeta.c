#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <flint/acb.h>
#include <flint/acb_dirichlet.h>
#include <flint/acb_hypgeom.h>
#include <flint/arb.h>
#include <flint/arb_hypgeom.h>
#include <flint/arf.h>
#include <flint/dirichlet.h>
#include <flint/flint.h>
#include <flint/fmpz.h>
#include <flint/mag.h>
#include <flint/ulong_extras.h>

#ifdef _OPENMP
#include <omp.h>
#endif

typedef struct
{
    double x;
    double y;
    double real;
    double imag;
    double magnitude;
    double argument;
} zeta_sample_t;

static void fail(const char *message)
{
    fprintf(stderr, "%s\n", message);
    exit(EXIT_FAILURE);
}

static slong parse_slong(const char *text, slong minimum, slong maximum, const char *name)
{
    char *end = NULL;
    long value;

    errno = 0;
    value = strtol(text, &end, 10);
    if (errno || end == text || *end != '\0' || value < minimum || value > maximum)
    {
        fprintf(stderr, "invalid %s\n", name);
        exit(EXIT_FAILURE);
    }
    return (slong) value;
}

static slong decimal_digits_to_bits(slong digits)
{
    return (slong) ceil((double) digits * 3.32192809488736234787) + 32;
}

static void set_real(arb_t value, const char *text, slong precision)
{
    if (arb_set_str(value, text, precision) != 0 || !arb_is_finite(value))
        fail("invalid real value");
}

static char *ball_string(const arb_t value, slong digits)
{
    return arb_get_str(value, digits, ARB_STR_MORE);
}

static char *midpoint_string(const arb_t value, slong digits)
{
    arb_t midpoint;
    char *text;

    arb_init(midpoint);
    arb_get_mid_arb(midpoint, value);
    text = arb_get_str(midpoint, digits, ARB_STR_NO_RADIUS);
    arb_clear(midpoint);
    return text;
}

static double midpoint_double(const arb_t value)
{
    return arf_get_d(arb_midref(value), ARF_RND_NEAR);
}

static void print_complex_value(const char *prefix, const acb_t value, slong digits)
{
    char *real_text = ball_string(acb_realref(value), digits);
    char *imag_text = ball_string(acb_imagref(value), digits);
    printf("%s_REAL:%s\n", prefix, real_text);
    printf("%s_IMAG:%s\n", prefix, imag_text);
    flint_free(real_text);
    flint_free(imag_text);
}

static void command_evaluate(int argc, char **argv)
{
    slong digits, precision;
    arb_t sigma, ordinate, magnitude, argument;
    acb_t input, value;
    char *real_text, *imag_text, *magnitude_text, *argument_text;

    if (argc != 5)
        fail("usage: numerisect-zeta evaluate SIGMA T DIGITS");
    digits = parse_slong(argv[4], 16, 1000, "precision");
    precision = decimal_digits_to_bits(digits);
    arb_init(sigma);
    arb_init(ordinate);
    arb_init(magnitude);
    arb_init(argument);
    acb_init(input);
    acb_init(value);
    set_real(sigma, argv[2], precision);
    set_real(ordinate, argv[3], precision);
    acb_set_arb_arb(input, sigma, ordinate);
    acb_zeta(value, input, precision);
    if (!acb_is_finite(value))
        fail("zeta is not finite at this point (s = 1 is a pole)");
    acb_abs(magnitude, value, precision);
    acb_arg(argument, value, precision);

    real_text = ball_string(acb_realref(value), digits);
    imag_text = ball_string(acb_imagref(value), digits);
    magnitude_text = ball_string(magnitude, digits);
    argument_text = ball_string(argument, digits);
    printf("REAL:%s\n", real_text);
    printf("IMAG:%s\n", imag_text);
    printf("ABS:%s\n", magnitude_text);
    printf("ARG:%s\n", argument_text);
    flint_free(real_text);
    flint_free(imag_text);
    flint_free(magnitude_text);
    flint_free(argument_text);
    acb_clear(value);
    acb_clear(input);
    arb_clear(argument);
    arb_clear(magnitude);
    arb_clear(ordinate);
    arb_clear(sigma);
}

static void command_zeros(int argc, char **argv)
{
    slong count, digits, threads, precision, i;
    fmpz_t start, index;
    arb_ptr zeros;

    if (argc != 6)
        fail("usage: numerisect-zeta zeros START COUNT DIGITS THREADS");
    count = parse_slong(argv[3], 1, 10000, "zero count");
    digits = parse_slong(argv[4], 16, 1000, "precision");
    threads = parse_slong(argv[5], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);
    fmpz_init(start);
    fmpz_init(index);
    if (fmpz_set_str(start, argv[2], 10) != 0 || fmpz_sgn(start) <= 0)
        fail("the starting zero index must be positive");
    flint_set_num_threads((int) threads);
    zeros = _arb_vec_init(count);
    acb_dirichlet_hardy_z_zeros(zeros, start, count, precision);
    fmpz_set(index, start);

    for (i = 0; i < count; i++)
    {
        arb_t radius;
        char *midpoint, *radius_text, *interval;
        arb_init(radius);
        arb_get_rad_arb(radius, zeros + i);
        midpoint = midpoint_string(zeros + i, digits);
        radius_text = ball_string(radius, digits);
        interval = ball_string(zeros + i, digits);
        printf("ZERO:");
        fmpz_print(index);
        printf("|%s|%s|%s\n", midpoint, radius_text, interval);
        flint_free(midpoint);
        flint_free(radius_text);
        flint_free(interval);
        arb_clear(radius);
        fmpz_add_ui(index, index, 1);
    }

    _arb_vec_clear(zeros, count);
    fmpz_clear(index);
    fmpz_clear(start);
}

static void command_count(int argc, char **argv)
{
    slong digits, threads, precision;
    arb_t height, count_ball;
    fmpz_t count;
    char *interval;

    if (argc != 5)
        fail("usage: numerisect-zeta count HEIGHT DIGITS THREADS");
    digits = parse_slong(argv[3], 16, 1000, "precision");
    threads = parse_slong(argv[4], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);
    arb_init(height);
    arb_init(count_ball);
    fmpz_init(count);
    set_real(height, argv[2], precision);
    if (arb_is_negative(height))
        fail("the height must be nonnegative");
    flint_set_num_threads((int) threads);
    acb_dirichlet_zeta_nzeros(count_ball, height, precision);
    if (!arb_get_unique_fmpz(count, count_ball))
        fail("the zero count could not be isolated uniquely; increase precision or move the endpoint");
    interval = ball_string(count_ball, digits);
    printf("COUNT:");
    fmpz_print(count);
    printf("\nINTERVAL:%s\n", interval);
    flint_free(interval);
    fmpz_clear(count);
    arb_clear(count_ball);
    arb_clear(height);
}

static void command_hardy(int argc, char **argv)
{
    slong digits, precision;
    arb_t t;
    acb_t input, value;

    if (argc != 4)
        fail("usage: numerisect-zeta hardy T DIGITS");
    digits = parse_slong(argv[3], 16, 1000, "precision");
    precision = decimal_digits_to_bits(digits);
    arb_init(t);
    acb_init(input);
    acb_init(value);
    set_real(t, argv[2], precision);
    acb_set_arb(input, t);
    acb_dirichlet_hardy_z(value, input, NULL, NULL, 1, precision);
    if (!acb_is_finite(value))
        fail("Hardy Z could not be enclosed at this point");
    print_complex_value("VALUE", value, digits);
    acb_clear(value);
    acb_clear(input);
    arb_clear(t);
}

static void command_xi_eta(int argc, char **argv, int xi)
{
    slong digits, precision;
    arb_t sigma, ordinate;
    acb_t input, value;

    if (argc != 5)
        fail("usage: numerisect-zeta xi|eta SIGMA T DIGITS");
    digits = parse_slong(argv[4], 16, 1000, "precision");
    precision = decimal_digits_to_bits(digits);
    arb_init(sigma);
    arb_init(ordinate);
    acb_init(input);
    acb_init(value);
    set_real(sigma, argv[2], precision);
    set_real(ordinate, argv[3], precision);
    acb_set_arb_arb(input, sigma, ordinate);
    if (xi)
        acb_dirichlet_xi(value, input, precision);
    else
        acb_dirichlet_eta(value, input, precision);
    if (!acb_is_finite(value))
        fail("the requested function could not be enclosed at this point");
    print_complex_value("VALUE", value, digits);
    acb_clear(value);
    acb_clear(input);
    arb_clear(ordinate);
    arb_clear(sigma);
}

static void command_stieltjes(int argc, char **argv)
{
    slong digits, precision;
    fmpz_t index;
    acb_t a, value;

    if (argc != 4)
        fail("usage: numerisect-zeta stieltjes INDEX DIGITS");
    digits = parse_slong(argv[3], 16, 1000, "precision");
    precision = decimal_digits_to_bits(digits);
    fmpz_init(index);
    acb_init(a);
    acb_init(value);
    if (fmpz_set_str(index, argv[2], 10) != 0 || fmpz_sgn(index) < 0)
        fail("the Stieltjes index must be nonnegative");
    acb_one(a);
    acb_dirichlet_stieltjes(value, index, a, precision);
    print_complex_value("VALUE", value, digits);
    fmpz_clear(index);
    acb_clear(value);
    acb_clear(a);
}

static void command_gram(int argc, char **argv)
{
    slong digits, precision;
    fmpz_t index;
    arb_t value;
    char *text;

    if (argc != 4)
        fail("usage: numerisect-zeta gram INDEX DIGITS");
    digits = parse_slong(argv[3], 16, 1000, "precision");
    precision = decimal_digits_to_bits(digits);
    fmpz_init(index);
    arb_init(value);
    if (fmpz_set_str(index, argv[2], 10) != 0 || fmpz_cmp_si(index, -1) < 0)
        fail("the Gram-point index must be at least -1");
    acb_dirichlet_gram_point(value, index, NULL, NULL, precision);
    text = ball_string(value, digits);
    printf("VALUE:%s\n", text);
    flint_free(text);
    arb_clear(value);
    fmpz_clear(index);
}

static void command_functional_equation(int argc, char **argv)
{
    slong digits, precision;
    arb_t sigma, ordinate;
    acb_t s, reflected, left, right, base, exponent, term, residual;

    if (argc != 5)
        fail("usage: numerisect-zeta functional SIGMA T DIGITS");
    digits = parse_slong(argv[4], 16, 1000, "precision");
    precision = decimal_digits_to_bits(digits);
    arb_init(sigma);
    arb_init(ordinate);
    acb_init(s);
    acb_init(reflected);
    acb_init(left);
    acb_init(right);
    acb_init(base);
    acb_init(exponent);
    acb_init(term);
    acb_init(residual);
    set_real(sigma, argv[2], precision);
    set_real(ordinate, argv[3], precision);
    acb_set_arb_arb(s, sigma, ordinate);
    acb_one(reflected);
    acb_sub(reflected, reflected, s, precision);
    acb_zeta(left, s, precision);
    acb_zeta(right, reflected, precision);

    acb_set_ui(base, 2);
    acb_pow(term, base, s, precision);
    acb_mul(right, right, term, precision);
    acb_const_pi(base, precision);
    acb_set(exponent, s);
    acb_sub_ui(exponent, exponent, 1, precision);
    acb_pow(term, base, exponent, precision);
    acb_mul(right, right, term, precision);
    acb_mul(term, base, s, precision);
    acb_mul_2exp_si(term, term, -1);
    acb_sin(term, term, precision);
    acb_mul(right, right, term, precision);
    acb_gamma(term, reflected, precision);
    acb_mul(right, right, term, precision);
    if (!acb_is_finite(left) || !acb_is_finite(right))
        fail("the functional equation is singular at this point");
    acb_sub(residual, left, right, precision);
    print_complex_value("LEFT", left, digits);
    print_complex_value("RIGHT", right, digits);
    print_complex_value("RESIDUAL", residual, digits);
    printf("OVERLAP:%d\n", acb_overlaps(left, right));
    acb_clear(residual);
    acb_clear(term);
    acb_clear(exponent);
    acb_clear(base);
    acb_clear(right);
    acb_clear(left);
    acb_clear(reflected);
    acb_clear(s);
    arb_clear(ordinate);
    arb_clear(sigma);
}

static void calculate_sample(zeta_sample_t *sample, const arb_t sigma, const arb_t ordinate,
                             slong precision)
{
    acb_t input, value;
    arb_t magnitude, argument;

    acb_init(input);
    acb_init(value);
    arb_init(magnitude);
    arb_init(argument);
    acb_set_arb_arb(input, sigma, ordinate);
    acb_zeta(value, input, precision);
    sample->x = midpoint_double(sigma);
    sample->y = midpoint_double(ordinate);
    if (acb_is_finite(value))
    {
        acb_abs(magnitude, value, precision);
        acb_arg(argument, value, precision);
        sample->real = midpoint_double(acb_realref(value));
        sample->imag = midpoint_double(acb_imagref(value));
        sample->magnitude = midpoint_double(magnitude);
        sample->argument = midpoint_double(argument);
    }
    else
    {
        sample->real = NAN;
        sample->imag = NAN;
        sample->magnitude = NAN;
        sample->argument = NAN;
    }
    arb_clear(argument);
    arb_clear(magnitude);
    acb_clear(value);
    acb_clear(input);
}

static void command_line(int argc, char **argv)
{
    slong samples, digits, threads, precision, i;
    arb_t lower, upper, step;
    zeta_sample_t *values;

    if (argc != 7)
        fail("usage: numerisect-zeta line T_MIN T_MAX SAMPLES DIGITS THREADS");
    samples = parse_slong(argv[4], 2, 10000, "sample count");
    digits = parse_slong(argv[5], 16, 1000, "precision");
    threads = parse_slong(argv[6], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);
    arb_init(lower);
    arb_init(upper);
    arb_init(step);
    set_real(lower, argv[2], precision);
    set_real(upper, argv[3], precision);
    if (!arb_lt(lower, upper))
        fail("T_MAX must be greater than T_MIN");
    arb_sub(step, upper, lower, precision);
    arb_div_ui(step, step, (ulong) (samples - 1), precision);
    values = flint_malloc((size_t) samples * sizeof(zeta_sample_t));
    flint_set_num_threads(1);

#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic) num_threads(threads)
#endif
    for (i = 0; i < samples; i++)
    {
        arb_t sigma, ordinate, offset;
        arb_init(sigma);
        arb_init(ordinate);
        arb_init(offset);
        arb_one(sigma);
        arb_mul_2exp_si(sigma, sigma, -1);
        arb_mul_ui(offset, step, (ulong) i, precision);
        arb_add(ordinate, lower, offset, precision);
        calculate_sample(values + i, sigma, ordinate, precision);
        arb_clear(offset);
        arb_clear(ordinate);
        arb_clear(sigma);
    }
    for (i = 0; i < samples; i++)
        printf("POINT:%.17g|%.17g|%.17g|%.17g|%.17g\n", values[i].y,
               values[i].real, values[i].imag, values[i].magnitude, values[i].argument);

    flint_free(values);
    arb_clear(step);
    arb_clear(upper);
    arb_clear(lower);
}

static void command_heatmap(int argc, char **argv)
{
    slong nx, ny, digits, threads, precision, total, index;
    arb_t x_lower, x_upper, y_lower, y_upper, x_step, y_step;
    zeta_sample_t *values;

    if (argc != 10)
        fail("usage: numerisect-zeta heatmap X_MIN X_MAX Y_MIN Y_MAX NX NY DIGITS THREADS");
    nx = parse_slong(argv[6], 2, 500, "horizontal sample count");
    ny = parse_slong(argv[7], 2, 500, "vertical sample count");
    digits = parse_slong(argv[8], 16, 1000, "precision");
    threads = parse_slong(argv[9], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);
    total = nx * ny;
    arb_init(x_lower);
    arb_init(x_upper);
    arb_init(y_lower);
    arb_init(y_upper);
    arb_init(x_step);
    arb_init(y_step);
    set_real(x_lower, argv[2], precision);
    set_real(x_upper, argv[3], precision);
    set_real(y_lower, argv[4], precision);
    set_real(y_upper, argv[5], precision);
    if (!arb_lt(x_lower, x_upper) || !arb_lt(y_lower, y_upper))
        fail("heatmap maxima must be greater than minima");
    arb_sub(x_step, x_upper, x_lower, precision);
    arb_div_ui(x_step, x_step, (ulong) (nx - 1), precision);
    arb_sub(y_step, y_upper, y_lower, precision);
    arb_div_ui(y_step, y_step, (ulong) (ny - 1), precision);
    values = flint_malloc((size_t) total * sizeof(zeta_sample_t));
    flint_set_num_threads(1);

#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic) num_threads(threads)
#endif
    for (index = 0; index < total; index++)
    {
        slong ix = index % nx;
        slong iy = index / nx;
        arb_t sigma, ordinate, offset;
        arb_init(sigma);
        arb_init(ordinate);
        arb_init(offset);
        arb_mul_ui(offset, x_step, (ulong) ix, precision);
        arb_add(sigma, x_lower, offset, precision);
        arb_mul_ui(offset, y_step, (ulong) iy, precision);
        arb_add(ordinate, y_lower, offset, precision);
        calculate_sample(values + index, sigma, ordinate, precision);
        arb_clear(offset);
        arb_clear(ordinate);
        arb_clear(sigma);
    }
    printf("GRID:%ld|%ld\n", (long) nx, (long) ny);
    for (index = 0; index < total; index++)
        printf("POINT:%.17g|%.17g|%.17g|%.17g|%.17g|%.17g\n", values[index].x,
               values[index].y, values[index].real, values[index].imag,
               values[index].magnitude, values[index].argument);

    flint_free(values);
    arb_clear(y_step);
    arb_clear(x_step);
    arb_clear(y_upper);
    arb_clear(y_lower);
    arb_clear(x_upper);
    arb_clear(x_lower);
}


/* ---------------------------------------------------------------------------
 * Explicit formulas, zero statistics, Dirichlet characters and L-functions.
 *
 * Every mathematical quantity below is produced by a FLINT/Arb library routine
 * (acb_dirichlet_*, acb_hypgeom_*, arb_hypgeom_*, dirichlet_*).  The C code in
 * this section only drives those routines, accumulates their ball results, and
 * bins them; it never re-implements a special function that FLINT provides.
 * ------------------------------------------------------------------------- */

static void print_arb_tag(const char *tag, const arb_t value, slong digits)
{
    char *text = ball_string(value, digits);
    printf("%s:%s\n", tag, text);
    flint_free(text);
}

/* Report at 1, 2, 4, 8, ... zeros and always at the final index. */
static int is_checkpoint(slong index, slong total)
{
    if (index == total)
        return 1;
    return (index & (index - 1)) == 0;
}

/* Rigorous enclosure of the tail integral of Riemann's formula,
 *   I(y) = \int_y^\infty dt / (t (t^2 - 1) log t)  in  [0, B],
 *   B = log(y^2 / (y^2 - 1)) / (2 log y),
 * which follows from log t >= log y on the range of integration.  Only the
 * bound is derived here; every logarithm is an Arb enclosure. */
static void riemann_tail_integral(arb_t result, const arb_t y, slong precision)
{
    arb_t square, numerator, denominator, bound, zero;

    arb_init(square);
    arb_init(numerator);
    arb_init(denominator);
    arb_init(bound);
    arb_init(zero);
    arb_mul(square, y, y, precision);
    arb_set(numerator, square);
    arb_sub_ui(denominator, square, 1, precision);
    arb_div(bound, numerator, denominator, precision);
    arb_log(bound, bound, precision);
    arb_log(denominator, y, precision);
    arb_mul_2exp_si(denominator, denominator, 1);
    arb_div(bound, bound, denominator, precision);
    arb_zero(zero);
    arb_union(result, zero, bound, precision);
    arb_clear(zero);
    arb_clear(bound);
    arb_clear(denominator);
    arb_clear(numerator);
    arb_clear(square);
}

/* Sum over Moebius indices m of (mu(m)/m) * (-2 Re Ei(rho log(x)/m)), i.e. the
 * contribution of one critical-line zero rho = 1/2 + i*gamma (and its
 * conjugate) to Riemann's prime-counting formula.  Ei is acb_hypgeom_ei. */
static void explicit_pi_zero_term(arb_t result, const arb_t gamma, const arb_t log_x,
                                  const int *mobius, slong indices, slong precision)
{
    acb_t rho, argument, value;
    arb_t term, scaled;
    slong m;

    acb_init(rho);
    acb_init(argument);
    acb_init(value);
    arb_init(term);
    arb_init(scaled);
    arb_one(acb_realref(rho));
    arb_mul_2exp_si(acb_realref(rho), acb_realref(rho), -1);
    arb_set(acb_imagref(rho), gamma);
    arb_zero(result);
    for (m = 1; m <= indices; m++)
    {
        if (mobius[m] == 0)
            continue;
        arb_div_ui(scaled, log_x, (ulong) m, precision);
        acb_mul_arb(argument, rho, scaled, precision);
        acb_hypgeom_ei(value, argument, precision);
        arb_mul_2exp_si(term, acb_realref(value), 1);
        arb_div_ui(term, term, (ulong) m, precision);
        if (mobius[m] > 0)
            arb_sub(result, result, term, precision);
        else
            arb_add(result, result, term, precision);
    }
    arb_clear(scaled);
    arb_clear(term);
    acb_clear(value);
    acb_clear(argument);
    acb_clear(rho);
}

static void command_explicit_pi(int argc, char **argv)
{
    slong count, digits, threads, precision, i, indices;
    arb_t x, log_x, base, running, estimate, error, exact, root, term, constant;
    arb_ptr zeros, contributions;
    fmpz_t start;
    int *mobius;
    slong emitted = 0;

    if (argc != 7)
        fail("usage: numerisect-zeta explicit-pi X EXACT_PI ZEROS DIGITS THREADS");
    count = parse_slong(argv[4], 1, 5000, "zero count");
    digits = parse_slong(argv[5], 16, 1000, "precision");
    threads = parse_slong(argv[6], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);

    arb_init(x);
    arb_init(log_x);
    arb_init(base);
    arb_init(running);
    arb_init(estimate);
    arb_init(error);
    arb_init(exact);
    arb_init(root);
    arb_init(term);
    arb_init(constant);
    set_real(x, argv[2], precision);
    arb_set_ui(constant, 2);
    if (!arb_ge(x, constant))
        fail("x must be at least 2 for Riemann's explicit formula");
    set_real(exact, argv[3], precision);
    arb_log(log_x, x, precision);

    /* Determine how many Moebius indices contribute: x^(1/m) >= 2. */
    mobius = flint_calloc(65, sizeof(int));
    indices = 0;
    for (i = 1; i <= 64; i++)
    {
        arb_div_ui(root, log_x, (ulong) i, precision);
        arb_exp(root, root, precision);
        if (!arb_ge(root, constant))
            break;
        mobius[i] = n_moebius_mu((ulong) i);
        indices = i;
    }
    if (indices < 1)
        fail("x must be at least 2 for Riemann's explicit formula");

    /* Base term: sum_m (mu(m)/m) * (li(x^(1/m)) - log 2 + I(x^(1/m))). */
    arb_zero(base);
    for (i = 1; i <= indices; i++)
    {
        arb_t piece, integral, logarithm;
        if (mobius[i] == 0)
            continue;
        arb_init(piece);
        arb_init(integral);
        arb_init(logarithm);
        arb_div_ui(root, log_x, (ulong) i, precision);
        arb_exp(root, root, precision);
        arb_hypgeom_li(piece, root, 0, precision);
        arb_log_ui(logarithm, 2, precision);
        arb_sub(piece, piece, logarithm, precision);
        riemann_tail_integral(integral, root, precision);
        arb_add(piece, piece, integral, precision);
        arb_div_ui(piece, piece, (ulong) i, precision);
        if (mobius[i] > 0)
            arb_add(base, base, piece, precision);
        else
            arb_sub(base, base, piece, precision);
        arb_clear(logarithm);
        arb_clear(integral);
        arb_clear(piece);
    }

    fmpz_init(start);
    fmpz_one(start);
    zeros = _arb_vec_init(count);
    contributions = _arb_vec_init(count);
    flint_set_num_threads((int) threads);
    acb_dirichlet_hardy_z_zeros(zeros, start, count, precision);
    flint_set_num_threads(1);

#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic) num_threads(threads)
#endif
    for (i = 0; i < count; i++)
        explicit_pi_zero_term(contributions + i, zeros + i, log_x, mobius, indices, precision);

    printf("MOEBIUS_TERMS:%ld\n", (long) indices);
    print_arb_tag("EXACT", exact, digits);
    arb_set(running, base);
    for (i = 0; i < count; i++)
    {
        arb_add(running, running, contributions + i, precision);
        if (!is_checkpoint(i + 1, count))
            continue;
        arb_set(estimate, running);
        arb_sub(error, estimate, exact, precision);
        {
            char *estimate_text = ball_string(estimate, digits);
            char *error_text = ball_string(error, digits);
            printf("TERM:%ld|%s|%s|%.17g|%.17g\n", (long) (i + 1), estimate_text,
                   error_text, midpoint_double(estimate), midpoint_double(error));
            flint_free(estimate_text);
            flint_free(error_text);
        }
        emitted++;
    }
    printf("COUNT:%ld\n", (long) emitted);
    printf("ZEROS:%ld\n", (long) count);

    _arb_vec_clear(contributions, count);
    _arb_vec_clear(zeros, count);
    fmpz_clear(start);
    flint_free(mobius);
    arb_clear(constant);
    arb_clear(term);
    arb_clear(root);
    arb_clear(exact);
    arb_clear(error);
    arb_clear(estimate);
    arb_clear(running);
    arb_clear(base);
    arb_clear(log_x);
    arb_clear(x);
}

/* Exact Chebyshev psi(x) = sum_{p^k <= x} log p.  FLINT's n_primes_t sieve
 * enumerates the primes and arb_log encloses every logarithm. */
static void chebyshev_psi_exact(arb_t result, ulong limit, slong precision)
{
    n_primes_t iterator;
    arb_t logarithm;
    ulong p;

    arb_init(logarithm);
    arb_zero(result);
    n_primes_init(iterator);
    while ((p = n_primes_next(iterator)) <= limit)
    {
        ulong power = p;
        slong exponent = 0;
        while (1)
        {
            exponent++;
            if (power > limit / p)
                break;
            power *= p;
            if (power > limit)
                break;
        }
        arb_log_ui(logarithm, p, precision);
        arb_mul_si(logarithm, logarithm, exponent, precision);
        arb_add(result, result, logarithm, precision);
    }
    n_primes_clear(iterator);
    arb_clear(logarithm);
}

static void command_chebyshev_psi(int argc, char **argv)
{
    slong count, digits, threads, precision, i;
    slong emitted = 0;
    arb_t x, log_x, base, running, estimate, error, exact, scratch;
    arb_ptr zeros, contributions;
    fmpz_t start, floor_x;
    ulong limit;

    if (argc != 6)
        fail("usage: numerisect-zeta psi X ZEROS DIGITS THREADS");
    count = parse_slong(argv[3], 1, 5000, "zero count");
    digits = parse_slong(argv[4], 16, 1000, "precision");
    threads = parse_slong(argv[5], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);

    arb_init(x);
    arb_init(log_x);
    arb_init(base);
    arb_init(running);
    arb_init(estimate);
    arb_init(error);
    arb_init(exact);
    arb_init(scratch);
    fmpz_init(floor_x);
    set_real(x, argv[2], precision);
    arb_set_ui(scratch, 2);
    if (!arb_ge(x, scratch))
        fail("x must be at least 2 for the psi explicit formula");
    arb_set_ui(scratch, 10000000);
    if (!arb_le(x, scratch))
        fail("x must be at most 10^7 so that the exact Chebyshev psi(x) stays affordable");
    arb_floor(scratch, x, precision);
    if (!arb_get_unique_fmpz(floor_x, scratch))
        fail("x is too close to an integer to determine floor(x); adjust x or raise precision");
    limit = fmpz_get_ui(floor_x);
    chebyshev_psi_exact(exact, limit, precision);

    /* base = x - log(2 pi) - (1/2) log(1 - x^-2) */
    arb_log(log_x, x, precision);
    arb_set(base, x);
    arb_const_pi(scratch, precision);
    arb_mul_2exp_si(scratch, scratch, 1);
    arb_log(scratch, scratch, precision);
    arb_sub(base, base, scratch, precision);
    arb_inv(scratch, x, precision);
    arb_mul(scratch, scratch, scratch, precision);
    arb_sub_ui(scratch, scratch, 1, precision);
    arb_neg(scratch, scratch);
    arb_log(scratch, scratch, precision);
    arb_mul_2exp_si(scratch, scratch, -1);
    arb_sub(base, base, scratch, precision);

    fmpz_init(start);
    fmpz_one(start);
    zeros = _arb_vec_init(count);
    contributions = _arb_vec_init(count);
    flint_set_num_threads((int) threads);
    acb_dirichlet_hardy_z_zeros(zeros, start, count, precision);
    flint_set_num_threads(1);

#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic) num_threads(threads)
#endif
    for (i = 0; i < count; i++)
    {
        acb_t rho, power, quotient;
        acb_init(rho);
        acb_init(power);
        acb_init(quotient);
        arb_one(acb_realref(rho));
        arb_mul_2exp_si(acb_realref(rho), acb_realref(rho), -1);
        arb_set(acb_imagref(rho), zeros + i);
        acb_mul_arb(power, rho, log_x, precision);
        acb_exp(power, power, precision);
        acb_div(quotient, power, rho, precision);
        arb_mul_2exp_si(contributions + i, acb_realref(quotient), 1);
        arb_neg(contributions + i, contributions + i);
        acb_clear(quotient);
        acb_clear(power);
        acb_clear(rho);
    }

    print_arb_tag("EXACT", exact, digits);
    printf("EXACT_MID:%.17g\n", midpoint_double(exact));
    printf("LIMIT:%lu\n", (unsigned long) limit);
    arb_set(running, base);
    for (i = 0; i < count; i++)
    {
        arb_add(running, running, contributions + i, precision);
        if (!is_checkpoint(i + 1, count))
            continue;
        arb_set(estimate, running);
        arb_sub(error, estimate, exact, precision);
        {
            char *estimate_text = ball_string(estimate, digits);
            char *error_text = ball_string(error, digits);
            printf("TERM:%ld|%s|%s|%.17g|%.17g\n", (long) (i + 1), estimate_text,
                   error_text, midpoint_double(estimate), midpoint_double(error));
            flint_free(estimate_text);
            flint_free(error_text);
        }
        emitted++;
    }
    printf("COUNT:%ld\n", (long) emitted);
    printf("ZEROS:%ld\n", (long) count);

    _arb_vec_clear(contributions, count);
    _arb_vec_clear(zeros, count);
    fmpz_clear(start);
    fmpz_clear(floor_x);
    arb_clear(scratch);
    arb_clear(exact);
    arb_clear(error);
    arb_clear(estimate);
    arb_clear(running);
    arb_clear(base);
    arb_clear(log_x);
    arb_clear(x);
}

static void command_riemann_siegel(int argc, char **argv)
{
    slong terms, digits, precision, k;
    arb_t sigma, ordinate, deviation;
    acb_t s, reference, value, difference;

    if (argc != 6)
        fail("usage: numerisect-zeta riemann-siegel SIGMA T TERMS DIGITS");
    terms = parse_slong(argv[4], 0, 20, "correction-term count");
    digits = parse_slong(argv[5], 16, 1000, "precision");
    precision = decimal_digits_to_bits(digits);
    arb_init(sigma);
    arb_init(ordinate);
    arb_init(deviation);
    acb_init(s);
    acb_init(reference);
    acb_init(value);
    acb_init(difference);
    set_real(sigma, argv[2], precision);
    set_real(ordinate, argv[3], precision);
    arb_set_ui(deviation, 10);
    if (!arb_ge(ordinate, deviation))
        fail("the Riemann-Siegel expansion requires t >= 10");
    acb_set_arb_arb(s, sigma, ordinate);
    acb_dirichlet_zeta(reference, s, precision);
    if (!acb_is_finite(reference))
        fail("the reference value of zeta could not be enclosed at this point");
    print_complex_value("REFERENCE", reference, digits);

    for (k = 0; k <= terms; k++)
    {
        mag_t error;
        char *real_text, *imag_text, *deviation_text;
        mag_init(error);
        acb_dirichlet_zeta_rs(value, s, k, precision);
        acb_dirichlet_zeta_rs_bound(error, s, k);
        acb_sub(difference, value, reference, precision);
        acb_abs(deviation, difference, precision);
        real_text = ball_string(acb_realref(value), digits);
        imag_text = ball_string(acb_imagref(value), digits);
        deviation_text = ball_string(deviation, digits);
        printf("RS:%ld|%s|%s|%s|%.17g|%.17g\n", (long) k, real_text, imag_text,
               deviation_text, mag_get_d(error), midpoint_double(deviation));
        flint_free(real_text);
        flint_free(imag_text);
        flint_free(deviation_text);
        mag_clear(error);
    }
    printf("COUNT:%ld\n", (long) (terms + 1));

    acb_clear(difference);
    acb_clear(value);
    acb_clear(reference);
    acb_clear(s);
    arb_clear(deviation);
    arb_clear(ordinate);
    arb_clear(sigma);
}

static void command_euler_product(int argc, char **argv)
{
    slong wanted, digits, threads, precision, i;
    slong emitted = 0;
    arb_t sigma, ordinate, one, tail, deviation, scratch;
    acb_t s, negated, reference, product, difference;
    acb_ptr factors;
    ulong *primes;
    n_primes_t iterator;

    if (argc != 7)
        fail("usage: numerisect-zeta euler-product SIGMA T PRIMES DIGITS THREADS");
    wanted = parse_slong(argv[4], 1, 200000, "prime count");
    digits = parse_slong(argv[5], 16, 1000, "precision");
    threads = parse_slong(argv[6], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);
    arb_init(sigma);
    arb_init(ordinate);
    arb_init(one);
    arb_init(tail);
    arb_init(deviation);
    arb_init(scratch);
    acb_init(s);
    acb_init(negated);
    acb_init(reference);
    acb_init(product);
    acb_init(difference);
    set_real(sigma, argv[2], precision);
    set_real(ordinate, argv[3], precision);
    arb_one(one);
    if (!arb_gt(sigma, one))
        fail("the Euler product converges only for Re(s) > 1");
    acb_set_arb_arb(s, sigma, ordinate);
    acb_dirichlet_zeta(reference, s, precision);
    if (!acb_is_finite(reference))
        fail("zeta could not be enclosed at this point");
    print_complex_value("REFERENCE", reference, digits);

    /* FLINT's own certified Euler product for zeta(n) at integer arguments. */
    if (arb_is_zero(ordinate))
    {
        fmpz_t integral;
        fmpz_init(integral);
        if (arb_get_unique_fmpz(integral, sigma) && fmpz_cmp_ui(integral, 2) >= 0
            && fmpz_cmp_ui(integral, 1000) <= 0)
        {
            arb_t certified;
            signed char principal[1] = {1};
            arb_init(certified);
            _acb_dirichlet_euler_product_real_ui(certified, fmpz_get_ui(integral),
                                                 principal, 1, 0, precision);
            print_arb_tag("CERTIFIED_EULER", certified, digits);
            arb_clear(certified);
        }
        fmpz_clear(integral);
    }

    primes = flint_malloc((size_t) wanted * sizeof(ulong));
    n_primes_init(iterator);
    for (i = 0; i < wanted; i++)
        primes[i] = n_primes_next(iterator);
    n_primes_clear(iterator);

    acb_neg(negated, s);
    factors = _acb_vec_init(wanted);
    flint_set_num_threads(1);

#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic) num_threads(threads)
#endif
    for (i = 0; i < wanted; i++)
    {
        acb_t base, power;
        acb_init(base);
        acb_init(power);
        acb_set_ui(base, primes[i]);
        acb_pow(power, base, negated, precision);
        acb_sub_ui(power, power, 1, precision);
        acb_neg(power, power);
        acb_inv(factors + i, power, precision);
        acb_clear(power);
        acb_clear(base);
    }

    acb_one(product);
    for (i = 0; i < wanted; i++)
    {
        acb_mul(product, product, factors + i, precision);
        if (!is_checkpoint(i + 1, wanted))
            continue;
        /* Rigorous truncation bound: |log zeta(s) - log P_N(s)| <=
         * N^(1-sigma) / ((sigma - 1) (1 - N^-sigma)) with N the largest prime
         * used, so |zeta - P_N| <= |P_N| (exp(bound) - 1). */
        arb_set_ui(scratch, primes[i]);
        arb_neg(tail, sigma);
        arb_pow(tail, scratch, tail, precision);
        arb_neg(tail, tail);
        arb_add_ui(tail, tail, 1, precision);
        arb_sub_ui(deviation, sigma, 1, precision);
        arb_mul(tail, tail, deviation, precision);
        arb_sub_ui(deviation, sigma, 1, precision);
        arb_neg(deviation, deviation);
        arb_pow(deviation, scratch, deviation, precision);
        arb_div(tail, deviation, tail, precision);
        arb_expm1(tail, tail, precision);
        acb_abs(deviation, product, precision);
        arb_mul(tail, tail, deviation, precision);
        acb_sub(difference, product, reference, precision);
        acb_abs(deviation, difference, precision);
        {
            char *real_text = ball_string(acb_realref(product), digits);
            char *imag_text = ball_string(acb_imagref(product), digits);
            char *deviation_text = ball_string(deviation, digits);
            char *tail_text = midpoint_string(tail, digits);
            printf("EULER:%ld|%lu|%s|%s|%s|%s|%.17g\n", (long) (i + 1),
                   (unsigned long) primes[i], real_text, imag_text, deviation_text,
                   tail_text, midpoint_double(deviation));
            flint_free(real_text);
            flint_free(imag_text);
            flint_free(deviation_text);
            flint_free(tail_text);
        }
        emitted++;
    }
    printf("COUNT:%ld\n", (long) emitted);
    printf("PRIMES:%ld\n", (long) wanted);

    _acb_vec_clear(factors, wanted);
    flint_free(primes);
    acb_clear(difference);
    acb_clear(product);
    acb_clear(reference);
    acb_clear(negated);
    acb_clear(s);
    arb_clear(scratch);
    arb_clear(deviation);
    arb_clear(tail);
    arb_clear(one);
    arb_clear(ordinate);
    arb_clear(sigma);
}

/* Unfold a critical-line ordinate with FLINT's Riemann-Siegel theta:
 * w = theta(gamma)/pi, whose consecutive differences have mean spacing one. */
static double unfolded_ordinate(const arb_t gamma, slong precision)
{
    acb_t input, value;
    arb_t scaled, pi;
    double result;

    acb_init(input);
    acb_init(value);
    arb_init(scaled);
    arb_init(pi);
    acb_set_arb(input, gamma);
    acb_dirichlet_hardy_theta(value, input, NULL, NULL, 1, precision);
    arb_const_pi(pi, precision);
    arb_div(scaled, acb_realref(value), pi, precision);
    result = midpoint_double(scaled);
    arb_clear(pi);
    arb_clear(scaled);
    acb_clear(value);
    acb_clear(input);
    return result;
}

/* Cumulative distribution of the GUE Wigner surmise
 *   p(s) = (32/pi^2) s^2 exp(-4 s^2 / pi),
 * integrated in closed form with arb_hypgeom_erf. */
static void gue_spacing_cdf(arb_t result, double s, slong precision)
{
    arb_t x, c, term, other, pi, root;

    arb_init(x);
    arb_init(c);
    arb_init(term);
    arb_init(other);
    arb_init(pi);
    arb_init(root);
    arb_set_d(x, s);
    arb_const_pi(pi, precision);
    arb_set_ui(c, 4);
    arb_div(c, c, pi, precision);              /* c = 4/pi */
    arb_sqrt(root, c, precision);              /* sqrt(c) */

    arb_mul(term, x, x, precision);
    arb_mul(term, term, c, precision);
    arb_neg(term, term);
    arb_exp(term, term, precision);            /* exp(-c x^2) */
    arb_mul(term, term, x, precision);
    arb_div(term, term, c, precision);
    arb_mul_2exp_si(term, term, -1);           /* (x/(2c)) exp(-c x^2) */
    arb_neg(term, term);

    arb_mul(other, root, x, precision);
    arb_hypgeom_erf(other, other, precision);
    arb_sqrt(result, pi, precision);
    arb_mul(other, other, result, precision);
    arb_mul(result, c, root, precision);       /* c^(3/2) */
    arb_mul_2exp_si(result, result, 2);        /* 4 c^(3/2) */
    arb_div(other, other, result, precision);
    arb_add(term, term, other, precision);

    arb_mul(result, pi, pi, precision);
    arb_set_ui(other, 32);
    arb_div(result, other, result, precision); /* A = 32/pi^2 */
    arb_mul(result, result, term, precision);

    arb_clear(root);
    arb_clear(pi);
    arb_clear(other);
    arb_clear(term);
    arb_clear(c);
    arb_clear(x);
}

static void command_zero_spacing(int argc, char **argv)
{
    slong count, bins, digits, threads, precision, i;
    fmpz_t start;
    arb_ptr zeros;
    double *unfolded, *spacings;
    slong *histogram;
    slong overflow = 0;
    double total = 0.0, square_total = 0.0, minimum = 0.0, maximum = 0.0;
    const double window = 3.0;
    double step;

    if (argc != 7)
        fail("usage: numerisect-zeta zero-spacing START COUNT BINS DIGITS THREADS");
    count = parse_slong(argv[3], 2, 20000, "zero count");
    bins = parse_slong(argv[4], 4, 200, "bin count");
    digits = parse_slong(argv[5], 16, 1000, "precision");
    threads = parse_slong(argv[6], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);
    step = window / (double) bins;

    fmpz_init(start);
    if (fmpz_set_str(start, argv[2], 10) != 0 || fmpz_sgn(start) <= 0)
        fail("the starting zero index must be positive");
    zeros = _arb_vec_init(count);
    flint_set_num_threads((int) threads);
    acb_dirichlet_hardy_z_zeros(zeros, start, count, precision);
    flint_set_num_threads(1);

    unfolded = flint_malloc((size_t) count * sizeof(double));
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic) num_threads(threads)
#endif
    for (i = 0; i < count; i++)
        unfolded[i] = unfolded_ordinate(zeros + i, precision);

    spacings = flint_malloc((size_t) (count - 1) * sizeof(double));
    histogram = flint_calloc((size_t) bins, sizeof(slong));
    for (i = 0; i < count - 1; i++)
    {
        double value = unfolded[i + 1] - unfolded[i];
        slong bin;
        spacings[i] = value;
        total += value;
        square_total += value * value;
        if (i == 0 || value < minimum)
            minimum = value;
        if (i == 0 || value > maximum)
            maximum = value;
        bin = (slong) floor(value / step);
        if (bin < 0 || bin >= bins)
            overflow++;
        else
            histogram[bin]++;
    }

    {
        slong samples = count - 1;
        double mean = total / (double) samples;
        double variance = square_total / (double) samples - mean * mean;
        arb_t lower_cdf, upper_cdf, difference;
        arb_init(lower_cdf);
        arb_init(upper_cdf);
        arb_init(difference);
        printf("SAMPLES:%ld\n", (long) samples);
        printf("OVERFLOW:%ld\n", (long) overflow);
        printf("STATS:%.17g|%.17g|%.17g|%.17g\n", mean, variance, minimum, maximum);
        for (i = 0; i < bins; i++)
        {
            double a = (double) i * step, b = (double) (i + 1) * step;
            gue_spacing_cdf(lower_cdf, a, precision);
            gue_spacing_cdf(upper_cdf, b, precision);
            arb_sub(difference, upper_cdf, lower_cdf, precision);
            printf("BIN:%ld|%.17g|%.17g|%ld|%.17g|%.17g\n", (long) i, a, b,
                   (long) histogram[i],
                   (double) histogram[i] / ((double) samples * step),
                   midpoint_double(difference) / step);
        }
        printf("COUNT:%ld\n", (long) bins);
        arb_clear(difference);
        arb_clear(upper_cdf);
        arb_clear(lower_cdf);
    }

    flint_free(histogram);
    flint_free(spacings);
    flint_free(unfolded);
    _arb_vec_clear(zeros, count);
    fmpz_clear(start);
}

static void command_pair_correlation(int argc, char **argv)
{
    slong count, bins, limit, digits, threads, precision, i, j;
    fmpz_t start;
    arb_ptr zeros;
    double *unfolded;
    slong *histogram;
    slong pairs = 0;
    double step;

    if (argc != 8)
        fail("usage: numerisect-zeta pair-correlation START COUNT BINS UMAX DIGITS THREADS");
    count = parse_slong(argv[3], 2, 20000, "zero count");
    bins = parse_slong(argv[4], 4, 400, "bin count");
    limit = parse_slong(argv[5], 1, 20, "correlation window");
    digits = parse_slong(argv[6], 16, 1000, "precision");
    threads = parse_slong(argv[7], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);
    step = (double) limit / (double) bins;

    fmpz_init(start);
    if (fmpz_set_str(start, argv[2], 10) != 0 || fmpz_sgn(start) <= 0)
        fail("the starting zero index must be positive");
    zeros = _arb_vec_init(count);
    flint_set_num_threads((int) threads);
    acb_dirichlet_hardy_z_zeros(zeros, start, count, precision);
    flint_set_num_threads(1);

    unfolded = flint_malloc((size_t) count * sizeof(double));
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic) num_threads(threads)
#endif
    for (i = 0; i < count; i++)
        unfolded[i] = unfolded_ordinate(zeros + i, precision);

    histogram = flint_calloc((size_t) bins, sizeof(slong));
    for (i = 0; i < count; i++)
    {
        for (j = i + 1; j < count; j++)
        {
            double u = unfolded[j] - unfolded[i];
            slong bin;
            if (u >= (double) limit)
                break;
            bin = (slong) floor(u / step);
            if (bin >= 0 && bin < bins)
            {
                histogram[bin]++;
                pairs++;
            }
        }
    }

    {
        arb_t pi, argument, sine, prediction;
        arb_init(pi);
        arb_init(argument);
        arb_init(sine);
        arb_init(prediction);
        arb_const_pi(pi, precision);
        printf("SAMPLES:%ld\n", (long) count);
        printf("PAIRS:%ld\n", (long) pairs);
        for (i = 0; i < bins; i++)
        {
            double a = (double) i * step, b = (double) (i + 1) * step;
            double centre = (a + b) / 2.0;
            arb_set_d(argument, centre);
            arb_mul(argument, argument, pi, precision);
            arb_sin(sine, argument, precision);
            arb_div(sine, sine, argument, precision);
            arb_mul(prediction, sine, sine, precision);
            arb_neg(prediction, prediction);
            arb_add_ui(prediction, prediction, 1, precision);
            printf("BIN:%ld|%.17g|%.17g|%ld|%.17g|%.17g\n", (long) i, a, b,
                   (long) histogram[i],
                   (double) histogram[i] / ((double) count * step),
                   midpoint_double(prediction));
        }
        printf("COUNT:%ld\n", (long) bins);
        arb_clear(prediction);
        arb_clear(sine);
        arb_clear(argument);
        arb_clear(pi);
    }

    flint_free(histogram);
    flint_free(unfolded);
    _arb_vec_clear(zeros, count);
    fmpz_clear(start);
}

static void command_gram_blocks(int argc, char **argv)
{
    slong count, digits, threads, precision, i;
    slong exceptions = 0, inconclusive = 0, blocks = 0;
    fmpz_t start;
    arb_ptr points, values;
    int *status;
    char *pattern;

    if (argc != 6)
        fail("usage: numerisect-zeta gram-blocks START COUNT DIGITS THREADS");
    count = parse_slong(argv[3], 2, 20000, "Gram-point count");
    digits = parse_slong(argv[4], 16, 1000, "precision");
    threads = parse_slong(argv[5], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);

    fmpz_init(start);
    if (fmpz_set_str(start, argv[2], 10) != 0 || fmpz_cmp_si(start, -1) < 0)
        fail("the starting Gram index must be at least -1");
    points = _arb_vec_init(count);
    values = _arb_vec_init(count);
    status = flint_malloc((size_t) count * sizeof(int));
    flint_set_num_threads(1);

#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic) num_threads(threads)
#endif
    for (i = 0; i < count; i++)
    {
        fmpz_t index;
        acb_t input, value;
        arb_t signed_value;
        fmpz_init(index);
        acb_init(input);
        acb_init(value);
        arb_init(signed_value);
        fmpz_add_si(index, start, i);
        acb_dirichlet_gram_point(points + i, index, NULL, NULL, precision);
        acb_set_arb(input, points + i);
        acb_dirichlet_hardy_z(value, input, NULL, NULL, 1, precision);
        arb_set(values + i, acb_realref(value));
        arb_set(signed_value, values + i);
        if (fmpz_is_odd(index))
            arb_neg(signed_value, signed_value);
        if (arb_is_positive(signed_value))
            status[i] = 1;
        else if (arb_is_negative(signed_value))
            status[i] = 0;
        else
            status[i] = -1;
        arb_clear(signed_value);
        acb_clear(value);
        acb_clear(input);
        fmpz_clear(index);
    }

    for (i = 0; i < count; i++)
    {
        fmpz_t index;
        const char *label = status[i] == 1 ? "good" : (status[i] == 0 ? "bad" : "inconclusive");
        fmpz_init(index);
        fmpz_add_si(index, start, i);
        printf("GRAM:");
        fmpz_print(index);
        printf("|%.17g|%.17g|%s\n", midpoint_double(points + i),
               midpoint_double(values + i), label);
        if (status[i] == 0)
        {
            char *point_text = ball_string(points + i, digits);
            char *value_text = ball_string(values + i, digits);
            printf("EXCEPTION:");
            fmpz_print(index);
            printf("|%s|%s\n", point_text, value_text);
            flint_free(point_text);
            flint_free(value_text);
            exceptions++;
        }
        if (status[i] == -1)
            inconclusive++;
        fmpz_clear(index);
    }

    /* A Gram block of length k spans [g_n, g_{n+k}) with good endpoints and
     * exclusively bad interior Gram points; k = 1 is an ordinary interval. */
    pattern = flint_malloc((size_t) count + 1);
    for (i = 0; i < count; i++)
    {
        slong k = 1;
        if (status[i] != 1)
            continue;
        while (i + k < count && status[i + k] == 0)
            k++;
        if (i + k >= count || status[i + k] != 1 || k < 2)
            continue;
        {
            fmpz_t index;
            slong j;
            fmpz_init(index);
            fmpz_add_si(index, start, i);
            for (j = 0; j <= k; j++)
                pattern[j] = status[i + j] == 1 ? 'g' : 'b';
            pattern[k + 1] = '\0';
            printf("BLOCK:");
            fmpz_print(index);
            printf("|%ld|%s\n", (long) k, pattern);
            fmpz_clear(index);
        }
        blocks++;
    }

    printf("EXCEPTIONS:%ld\n", (long) exceptions);
    printf("INCONCLUSIVE:%ld\n", (long) inconclusive);
    printf("BLOCKS:%ld\n", (long) blocks);
    printf("COUNT:%ld\n", (long) count);

    flint_free(pattern);
    flint_free(status);
    _arb_vec_clear(values, count);
    _arb_vec_clear(points, count);
    fmpz_clear(start);
}

static void command_backlund(int argc, char **argv)
{
    slong samples, digits, threads, precision, i;
    arb_t lower, upper, step, remainder, count_ball, theta_value, bound;
    acb_t input, theta;
    fmpz_t zero_count;
    double *values;
    mag_t error;

    if (argc != 7)
        fail("usage: numerisect-zeta backlund T_MIN T_MAX SAMPLES DIGITS THREADS");
    samples = parse_slong(argv[4], 1, 20000, "sample count");
    digits = parse_slong(argv[5], 16, 1000, "precision");
    threads = parse_slong(argv[6], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);
    arb_init(lower);
    arb_init(upper);
    arb_init(step);
    arb_init(remainder);
    arb_init(count_ball);
    arb_init(theta_value);
    arb_init(bound);
    acb_init(input);
    acb_init(theta);
    fmpz_init(zero_count);
    mag_init(error);
    set_real(lower, argv[2], precision);
    set_real(upper, argv[3], precision);
    if (arb_is_negative(lower))
        fail("the ordinate range must be nonnegative");
    if (samples > 1 && !arb_lt(lower, upper))
        fail("T_MAX must be greater than T_MIN when more than one sample is requested");

    acb_dirichlet_backlund_s(remainder, upper, precision);
    acb_dirichlet_backlund_s_bound(error, upper);
    arf_set_mag(arb_midref(bound), error);
    mag_zero(arb_radref(bound));
    acb_dirichlet_zeta_nzeros(count_ball, upper, precision);
    acb_set_arb(input, upper);
    acb_dirichlet_hardy_theta(theta, input, NULL, NULL, 1, precision);
    arb_set(theta_value, acb_realref(theta));
    print_arb_tag("SVALUE", remainder, digits);
    print_arb_tag("SBOUND", bound, digits);
    print_arb_tag("THETA", theta_value, digits);
    print_arb_tag("NZEROS_INTERVAL", count_ball, digits);
    if (arb_get_unique_fmpz(zero_count, count_ball))
    {
        printf("NZEROS:");
        fmpz_print(zero_count);
        printf("\n");
    }
    else
    {
        printf("NZEROS:inconclusive\n");
    }

    values = flint_malloc((size_t) samples * sizeof(double));
    if (samples > 1)
    {
        arb_sub(step, upper, lower, precision);
        arb_div_ui(step, step, (ulong) (samples - 1), precision);
    }
    else
    {
        arb_zero(step);
        arb_set(lower, upper);
    }
    flint_set_num_threads(1);

#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic) num_threads(threads)
#endif
    for (i = 0; i < samples; i++)
    {
        arb_t ordinate, offset, sample;
        arb_init(ordinate);
        arb_init(offset);
        arb_init(sample);
        arb_mul_ui(offset, step, (ulong) i, precision);
        arb_add(ordinate, lower, offset, precision);
        acb_dirichlet_backlund_s(sample, ordinate, precision);
        values[i] = midpoint_double(sample);
        arb_clear(sample);
        arb_clear(offset);
        arb_clear(ordinate);
    }
    for (i = 0; i < samples; i++)
    {
        arb_t ordinate, offset;
        arb_init(ordinate);
        arb_init(offset);
        arb_mul_ui(offset, step, (ulong) i, precision);
        arb_add(ordinate, lower, offset, precision);
        printf("POINT:%.17g|%.17g\n", midpoint_double(ordinate), values[i]);
        arb_clear(offset);
        arb_clear(ordinate);
    }
    printf("COUNT:%ld\n", (long) samples);

    flint_free(values);
    mag_clear(error);
    fmpz_clear(zero_count);
    acb_clear(theta);
    acb_clear(input);
    arb_clear(bound);
    arb_clear(theta_value);
    arb_clear(count_ball);
    arb_clear(remainder);
    arb_clear(step);
    arb_clear(upper);
    arb_clear(lower);
}

static void command_characters(int argc, char **argv)
{
    slong limit, listed = 0;
    ulong q;
    dirichlet_group_t G;
    dirichlet_char_t chi;

    if (argc != 4)
        fail("usage: numerisect-zeta characters Q LIMIT");
    q = (ulong) parse_slong(argv[2], 1, 100000, "modulus");
    limit = parse_slong(argv[3], 1, 100000, "row limit");
    if (!dirichlet_group_init(G, q))
        fail("FLINT could not build the Dirichlet character group for this modulus");
    dirichlet_char_init(chi, G);
    dirichlet_char_one(chi, G);
    printf("MODULUS:%lu\n", (unsigned long) q);
    printf("GROUP_ORDER:%lu\n", (unsigned long) dirichlet_group_size(G));
    printf("PRIMITIVE_TOTAL:%lu\n", (unsigned long) dirichlet_group_num_primitive(G));
    do
    {
        ulong number;
        if (listed >= limit)
            break;
        number = dirichlet_char_exp(G, chi);
        printf("CHAR:%ld|%lu|%lu|%d|%lu|%d|%d|%d\n", (long) listed,
               (unsigned long) number,
               (unsigned long) dirichlet_conductor_char(G, chi),
               dirichlet_parity_char(G, chi),
               (unsigned long) dirichlet_order_char(G, chi),
               dirichlet_char_is_primitive(G, chi),
               dirichlet_char_is_real(G, chi),
               dirichlet_char_is_principal(G, chi));
        listed++;
    } while (dirichlet_char_next(chi, G) >= 0);
    printf("COUNT:%ld\n", (long) listed);
    printf("TRUNCATED:%d\n", listed < (slong) dirichlet_group_size(G));
    dirichlet_char_clear(chi);
    dirichlet_group_clear(G);
}

static void load_character(dirichlet_group_t G, dirichlet_char_t chi, const char *modulus,
                           const char *number)
{
    ulong q = (ulong) parse_slong(modulus, 1, 100000, "modulus");
    ulong m = (ulong) parse_slong(number, 1, 100000, "character number");

    if (q > 1 && n_gcd(q, m % q) != 1)
        fail("the character number must be coprime to the modulus");
    if (!dirichlet_group_init(G, q))
        fail("FLINT could not build the Dirichlet character group for this modulus");
    dirichlet_char_init(chi, G);
    dirichlet_char_log(chi, G, q > 1 ? m % q : 1);
}

static void print_character_metadata(const dirichlet_group_t G, const dirichlet_char_t chi)
{
    printf("MODULUS:%lu\n", (unsigned long) G->q);
    printf("NUMBER:%lu\n", (unsigned long) dirichlet_char_exp(G, chi));
    printf("CONDUCTOR:%lu\n", (unsigned long) dirichlet_conductor_char(G, chi));
    printf("PARITY:%d\n", dirichlet_parity_char(G, chi));
    printf("ORDER:%lu\n", (unsigned long) dirichlet_order_char(G, chi));
    printf("PRIMITIVE:%d\n", dirichlet_char_is_primitive(G, chi));
    printf("REAL_CHARACTER:%d\n", dirichlet_char_is_real(G, chi));
    printf("PRINCIPAL:%d\n", dirichlet_char_is_principal(G, chi));
}

static void command_l_function(int argc, char **argv)
{
    slong digits, precision;
    arb_t sigma, ordinate;
    acb_t s, value, cross;
    dirichlet_group_t G;
    dirichlet_char_t chi;

    if (argc != 7)
        fail("usage: numerisect-zeta l-function Q M SIGMA T DIGITS");
    digits = parse_slong(argv[6], 16, 1000, "precision");
    precision = decimal_digits_to_bits(digits);
    load_character(G, chi, argv[2], argv[3]);
    arb_init(sigma);
    arb_init(ordinate);
    acb_init(s);
    acb_init(value);
    acb_init(cross);
    set_real(sigma, argv[4], precision);
    set_real(ordinate, argv[5], precision);
    acb_set_arb_arb(s, sigma, ordinate);
    acb_dirichlet_l(value, s, G, chi, precision);
    if (!acb_is_finite(value))
        fail("L(s, chi) could not be enclosed here; principal characters have a pole at s = 1");
    acb_dirichlet_l_hurwitz(cross, s, NULL, G, chi, precision);
    print_character_metadata(G, chi);
    print_complex_value("VALUE", value, digits);
    print_complex_value("CROSS", cross, digits);
    printf("OVERLAP:%d\n", acb_overlaps(value, cross));
    if (dirichlet_char_is_primitive(G, chi))
    {
        acb_t root, gauss;
        acb_init(root);
        acb_init(gauss);
        acb_dirichlet_root_number(root, G, chi, precision);
        acb_dirichlet_gauss_sum(gauss, G, chi, precision);
        print_complex_value("ROOT_NUMBER", root, digits);
        print_complex_value("GAUSS_SUM", gauss, digits);
        acb_clear(gauss);
        acb_clear(root);
    }
    acb_clear(cross);
    acb_clear(value);
    acb_clear(s);
    arb_clear(ordinate);
    arb_clear(sigma);
    dirichlet_char_clear(chi);
    dirichlet_group_clear(G);
}

/* Rigorously narrow a bracket [a, b] on which Hardy's Z_chi changes sign.  The
 * endpoints stay exact dyadic rationals, so every evaluated enclosure is a
 * genuine certificate that Z is strictly positive or strictly negative there. */
static void refine_sign_change(arf_t a, arf_t b, int lower_positive,
                               const dirichlet_group_t G, const dirichlet_char_t chi,
                               slong iterations, slong precision)
{
    arf_t middle;
    arb_t point;
    acb_t input, value;
    slong step;

    arf_init(middle);
    arb_init(point);
    acb_init(input);
    acb_init(value);
    for (step = 0; step < iterations; step++)
    {
        int positive, negative;
        arf_add(middle, a, b, ARF_PREC_EXACT, ARF_RND_DOWN);
        arf_mul_2exp_si(middle, middle, -1);
        arb_set_arf(point, middle);
        acb_set_arb(input, point);
        acb_dirichlet_hardy_z(value, input, G, chi, 1, precision);
        positive = arb_is_positive(acb_realref(value));
        negative = arb_is_negative(acb_realref(value));
        if (!positive && !negative)
            break;
        if (positive == lower_positive)
            arf_set(a, middle);
        else
            arf_set(b, middle);
    }
    acb_clear(value);
    acb_clear(input);
    arb_clear(point);
    arf_clear(middle);
}

static void command_l_zeros(int argc, char **argv)
{
    slong samples, digits, threads, precision, i;
    slong changes = 0, minima = 0;
    arb_t lower, upper, step, smooth, theta_upper, theta_lower;
    acb_t input, theta;
    dirichlet_group_t G;
    dirichlet_char_t chi;
    double *ordinates, *real_values, *magnitudes;
    int *signs;
    int real_character;

    if (argc != 9)
        fail("usage: numerisect-zeta l-zeros Q M T_MIN T_MAX SAMPLES DIGITS THREADS");
    samples = parse_slong(argv[6], 8, 200000, "sample count");
    digits = parse_slong(argv[7], 16, 1000, "precision");
    threads = parse_slong(argv[8], 1, 256, "thread count");
    precision = decimal_digits_to_bits(digits);
    load_character(G, chi, argv[2], argv[3]);
    if (!dirichlet_char_is_primitive(G, chi))
        fail("FLINT's Hardy Z and theta functions require a primitive character");
    real_character = dirichlet_char_is_real(G, chi);

    arb_init(lower);
    arb_init(upper);
    arb_init(step);
    arb_init(smooth);
    arb_init(theta_upper);
    arb_init(theta_lower);
    acb_init(input);
    acb_init(theta);
    set_real(lower, argv[4], precision);
    set_real(upper, argv[5], precision);
    if (!arb_lt(lower, upper))
        fail("T_MAX must be greater than T_MIN");
    if (arb_is_negative(lower))
        fail("the ordinate range must be nonnegative");
    arb_sub(step, upper, lower, precision);
    arb_div_ui(step, step, (ulong) (samples - 1), precision);

    acb_set_arb(input, upper);
    acb_dirichlet_hardy_theta(theta, input, G, chi, 1, precision);
    arb_set(theta_upper, acb_realref(theta));
    acb_set_arb(input, lower);
    acb_dirichlet_hardy_theta(theta, input, G, chi, 1, precision);
    arb_set(theta_lower, acb_realref(theta));
    arb_sub(smooth, theta_upper, theta_lower, precision);
    {
        arb_t pi;
        arb_init(pi);
        arb_const_pi(pi, precision);
        arb_div(smooth, smooth, pi, precision);
        arb_clear(pi);
    }

    ordinates = flint_malloc((size_t) samples * sizeof(double));
    real_values = flint_malloc((size_t) samples * sizeof(double));
    magnitudes = flint_malloc((size_t) samples * sizeof(double));
    signs = flint_malloc((size_t) samples * sizeof(int));
    flint_set_num_threads(1);

#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic) num_threads(threads)
#endif
    for (i = 0; i < samples; i++)
    {
        arb_t ordinate, offset, magnitude;
        acb_t argument, z, s, l;
        arb_init(ordinate);
        arb_init(offset);
        arb_init(magnitude);
        acb_init(argument);
        acb_init(z);
        acb_init(s);
        acb_init(l);
        arb_mul_ui(offset, step, (ulong) i, precision);
        arb_add(ordinate, lower, offset, precision);
        acb_set_arb(argument, ordinate);
        acb_dirichlet_hardy_z(z, argument, G, chi, 1, precision);
        arb_one(acb_realref(s));
        arb_mul_2exp_si(acb_realref(s), acb_realref(s), -1);
        arb_set(acb_imagref(s), ordinate);
        acb_dirichlet_l(l, s, G, chi, precision);
        acb_abs(magnitude, l, precision);
        ordinates[i] = midpoint_double(ordinate);
        real_values[i] = midpoint_double(acb_realref(z));
        magnitudes[i] = midpoint_double(magnitude);
        if (arb_is_positive(acb_realref(z)))
            signs[i] = 1;
        else if (arb_is_negative(acb_realref(z)))
            signs[i] = -1;
        else
            signs[i] = 0;
        acb_clear(l);
        acb_clear(s);
        acb_clear(z);
        acb_clear(argument);
        arb_clear(magnitude);
        arb_clear(offset);
        arb_clear(ordinate);
    }

    printf("MODE:%s\n", real_character ? "sign-changes" : "magnitude-minima");
    print_character_metadata(G, chi);
    print_arb_tag("SMOOTH_COUNT", smooth, digits);
    printf("SAMPLES:%ld\n", (long) samples);

    if (real_character)
    {
        for (i = 0; i + 1 < samples; i++)
        {
            arf_t a, b;
            if (signs[i] == 0 || signs[i + 1] == 0 || signs[i] == signs[i + 1])
                continue;
            arf_init(a);
            arf_init(b);
            arf_set_d(a, ordinates[i]);
            arf_set_d(b, ordinates[i + 1]);
            refine_sign_change(a, b, signs[i] == 1, G, chi, 80, precision);
            printf("SIGN_CHANGE:%ld|%.17g|%.17g\n", (long) changes,
                   arf_get_d(a, ARF_RND_DOWN), arf_get_d(b, ARF_RND_UP));
            arf_clear(b);
            arf_clear(a);
            changes++;
        }
    }
    else
    {
        for (i = 1; i + 1 < samples; i++)
        {
            if (magnitudes[i] < magnitudes[i - 1] && magnitudes[i] <= magnitudes[i + 1])
            {
                printf("MINIMUM:%ld|%.17g|%.17g\n", (long) minima, ordinates[i],
                       magnitudes[i]);
                minima++;
            }
        }
    }
    for (i = 0; i < samples; i++)
        printf("POINT:%.17g|%.17g|%.17g\n", ordinates[i], real_values[i], magnitudes[i]);
    printf("CHANGES:%ld\n", (long) changes);
    printf("MINIMA:%ld\n", (long) minima);
    printf("COUNT:%ld\n", (long) samples);

    flint_free(signs);
    flint_free(magnitudes);
    flint_free(real_values);
    flint_free(ordinates);
    acb_clear(theta);
    acb_clear(input);
    arb_clear(theta_lower);
    arb_clear(theta_upper);
    arb_clear(smooth);
    arb_clear(step);
    arb_clear(upper);
    arb_clear(lower);
    dirichlet_char_clear(chi);
    dirichlet_group_clear(G);
}

int main(int argc, char **argv)
{
    if (argc < 2)
        fail("missing zeta command");
    if (strcmp(argv[1], "evaluate") == 0)
        command_evaluate(argc, argv);
    else if (strcmp(argv[1], "zeros") == 0)
        command_zeros(argc, argv);
    else if (strcmp(argv[1], "count") == 0)
        command_count(argc, argv);
    else if (strcmp(argv[1], "line") == 0)
        command_line(argc, argv);
    else if (strcmp(argv[1], "heatmap") == 0)
        command_heatmap(argc, argv);
    else if (strcmp(argv[1], "hardy") == 0)
        command_hardy(argc, argv);
    else if (strcmp(argv[1], "xi") == 0)
        command_xi_eta(argc, argv, 1);
    else if (strcmp(argv[1], "eta") == 0)
        command_xi_eta(argc, argv, 0);
    else if (strcmp(argv[1], "stieltjes") == 0)
        command_stieltjes(argc, argv);
    else if (strcmp(argv[1], "gram") == 0)
        command_gram(argc, argv);
    else if (strcmp(argv[1], "functional") == 0)
        command_functional_equation(argc, argv);
    else if (strcmp(argv[1], "explicit-pi") == 0)
        command_explicit_pi(argc, argv);
    else if (strcmp(argv[1], "psi") == 0)
        command_chebyshev_psi(argc, argv);
    else if (strcmp(argv[1], "riemann-siegel") == 0)
        command_riemann_siegel(argc, argv);
    else if (strcmp(argv[1], "euler-product") == 0)
        command_euler_product(argc, argv);
    else if (strcmp(argv[1], "zero-spacing") == 0)
        command_zero_spacing(argc, argv);
    else if (strcmp(argv[1], "pair-correlation") == 0)
        command_pair_correlation(argc, argv);
    else if (strcmp(argv[1], "gram-blocks") == 0)
        command_gram_blocks(argc, argv);
    else if (strcmp(argv[1], "backlund") == 0)
        command_backlund(argc, argv);
    else if (strcmp(argv[1], "characters") == 0)
        command_characters(argc, argv);
    else if (strcmp(argv[1], "l-function") == 0)
        command_l_function(argc, argv);
    else if (strcmp(argv[1], "l-zeros") == 0)
        command_l_zeros(argc, argv);
    else
        fail("unknown command: expected evaluate, zeros, count, line, heatmap, "
             "hardy, xi, eta, stieltjes, gram, functional, explicit-pi, psi, "
             "riemann-siegel, euler-product, zero-spacing, pair-correlation, "
             "gram-blocks, backlund, characters, l-function, or l-zeros");
    flint_cleanup_master();
    return EXIT_SUCCESS;
}
