#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <flint/acb.h>
#include <flint/acb_dirichlet.h>
#include <flint/arb.h>
#include <flint/flint.h>
#include <flint/fmpz.h>

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

int main(int argc, char **argv)
{
    if (argc < 2)
        fail("missing command: evaluate, zeros, count, line, or heatmap");
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
    else
        fail("unknown command: expected evaluate, zeros, count, line, or heatmap");
    flint_cleanup_master();
    return EXIT_SUCCESS;
}
