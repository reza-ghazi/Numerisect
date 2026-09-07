\\ Numerisect advanced number-theory engine for PARI/GP.
\\
\\ Python validates requests and parses the tagged protocol.  All arithmetic,
\\ factoring, primality decisions, group calculations, and searches live here.

nt_print_vector(tag, values) =
{
  for(i = 1, #values, print(tag, ":", lift(values[i])));
};

nt_symbols(a, n) =
{
  if(n == 0, error("The Kronecker denominator must be nonzero"));
  print("KRONECKER:", kronecker(a, n));
  if(n > 0 && n % 2,
    print("JACOBI:", kronecker(a, n));
    print("JACOBI_AVAILABLE:1");
  ,
    print("JACOBI_AVAILABLE:0");
  );
  if(n > 2 && isprime(n),
    print("LEGENDRE:", kronecker(a, n));
    print("LEGENDRE_AVAILABLE:1");
  ,
    print("LEGENDRE_AVAILABLE:0");
  );
  print("NORMALIZED:", a % abs(n));
  print("DONE:1");
};

nt_crt(residues, moduli) =
{
  if(#residues < 1 || #residues != #moduli, error("CRT vectors must have equal nonzero length"));
  my(x, modulus, a, m, g, reduced, step);
  for(i = 1, #moduli, if(moduli[i] <= 0, error("CRT moduli must be positive")));
  x = residues[1] % moduli[1]; modulus = moduli[1];
  print("SYSTEM:", x, "|", modulus);
  for(i = 2, #residues,
    a = residues[i] % moduli[i]; m = moduli[i];
    print("SYSTEM:", a, "|", m);
    g = gcd(modulus, m);
    if((a - x) % g,
      print("COMPATIBLE:0"); print("DONE:", #residues); return();
    );
    reduced = m / g;
    step = if(reduced == 1, 0,
      lift(Mod((a - x) / g, reduced) / Mod(modulus / g, reduced))
    );
    x = (x + modulus * step) % lcm(modulus, m);
    modulus = lcm(modulus, m);
  );
  print("COMPATIBLE:1"); print("RESULT:", x); print("MODULUS:", modulus);
  print("DONE:", #residues);
};

nt_modular_roots(a, k, p, result_limit) =
{
  if(p < 2 || !isprime(p), error("The modulus must be a proven prime"));
  if(k < 1, error("The root exponent must be positive"));
  my(r, z, values = List(), current, expected);
  a = a % p;
  if(a == 0,
    print("ROOT:0"); print("ROOT_COUNT:1"); print("TRUNCATED:0"); print("DONE:1"); return();
  );
  r = sqrtn(Mod(a, p), k, &z);
  if(!z,
    print("ROOT_COUNT:0"); print("TRUNCATED:0"); print("DONE:0"); return();
  );
  expected = gcd(k, p - 1); current = r;
  for(i = 1, expected,
    listput(values, lift(current)); current *= z;
  );
  values = Set(Vec(values));
  for(i = 1, min(#values, result_limit), print("ROOT:", values[i]));
  print("ROOT_COUNT:", #values);
  print("TRUNCATED:", #values > result_limit);
  print("DONE:", min(#values, result_limit));
};

nt_discrete_log(target, generator, modulus) =
{
  if(modulus < 2, error("The modulus must be at least 2"));
  if(gcd(target, modulus) != 1 || gcd(generator, modulus) != 1,
    error("The target and base must be units modulo n")
  );
  my(g = Mod(generator, modulus), order = znorder(g), value);
  value = znlog(Mod(target, modulus), g, [order, factor(order)]);
  print("ORDER:", order);
  if(type(value) == "t_VEC" && #value == 0,
    print("SOLVABLE:0");
  ,
    print("SOLVABLE:1"); print("LOG:", value);
  );
  print("DONE:1");
};

nt_unit_group(modulus, result_limit) =
{
  if(modulus < 2, error("The modulus must be at least 2"));
  my(G = znstar(modulus), cyclic, count = 0, candidate);
  print("ORDER:", G.no);
  print("CYCLIC:", #G.cyc <= 1);
  for(i = 1, #G.cyc, print("CYCLIC_FACTOR:", G.cyc[i]));
  for(i = 1, #G.gen, print("GENERATOR:", lift(G.gen[i])));
  cyclic = #G.cyc <= 1;
  if(cyclic,
    print("PRIMITIVE_COUNT:", eulerphi(G.no));
    if(G.no <= 1000000,
      for(a = 1, modulus - 1,
        if(gcd(a, modulus) == 1 && znorder(Mod(a, modulus)) == G.no,
          count++;
          if(count <= result_limit, print("PRIMITIVE:", a));
        );
      );
      print("ENUMERATION_COMPLETE:", count <= result_limit);
    ,
      print("ENUMERATION_COMPLETE:0");
    );
  ,
    print("PRIMITIVE_COUNT:0"); print("ENUMERATION_COMPLETE:1");
  );
  print("DONE:1");
};

nt_polynomial(coefficients, prime_modulus) =
{
  if(#coefficients < 2, error("A polynomial needs at least two coefficients"));
  if(prime_modulus < 2 || !isprime(prime_modulus), error("The finite-field modulus must be prime"));
  my(P = Polrev(coefficients), fq = factor(P), fp = factor(Mod(1, prime_modulus) * P), roots);
  print("POLYNOMIAL:", P);
  for(i = 1, matsize(fq)[1], print("QFACTOR:", fq[i, 1], "|", fq[i, 2]));
  for(i = 1, matsize(fp)[1], print("FFFACTOR:", lift(fp[i, 1]), "|", fp[i, 2]));
  roots = polrootsmod(P, prime_modulus);
  nt_print_vector("ROOT", roots);
  print("DONE:1");
};

nt_arithmetic(n, k, smooth_bound, form_d, divisor_limit) =
{
  if(n == 0, error("Arithmetic-function analysis is undefined at zero"));
  if(k < 0, error("The generalized divisor exponent must be nonnegative"));
  if(smooth_bound < 2, error("The smoothness bound must be at least 2"));
  if(form_d < 1, error("The quadratic-form coefficient must be positive"));
  my(a = abs(n), f = factor(abs(n)), divs = divisors(f), jordan = 1, psi = 1,
     squarefree_kernel = 1, largest = 1, least = 1, power_smooth = 1,
     reps, r2 = 0, r4 = 0, difference_a = 0, difference_b = 0);
  for(i = 1, matsize(f)[1],
    print("FACTOR:", f[i, 1], "|", f[i, 2]);
    jordan *= f[i, 1]^((f[i, 2] - 1) * k) * (f[i, 1]^k - 1);
    psi *= f[i, 1]^(f[i, 2] - 1) * (f[i, 1] + 1);
    if(f[i, 2] % 2, squarefree_kernel *= f[i, 1]);
    if(i == 1, least = f[i, 1]); largest = f[i, 1];
    if(f[i, 1]^f[i, 2] > smooth_bound, power_smooth = 0);
  );
  for(i = 1, min(#divs, divisor_limit), print("DIVISOR:", divs[i]));
  print("DIVISOR_COUNT:", #divs); print("DIVISORS_COMPLETE:", #divs <= divisor_limit);
  print("SIGMA_K:", sigma(a, k)); print("JORDAN:", jordan); print("DEDEKIND_PSI:", psi);
  print("LIOUVILLE:", (-1)^bigomega(a));
  print("VON_MANGOLDT_BASE:", if(matsize(f)[1] == 1, f[1, 1], 0));
  print("RADICAL:", if(a == 1, 1, factorback(f[, 1])));
  print("SQUAREFREE_KERNEL:", squarefree_kernel);
  print("LEAST_PRIME_FACTOR:", least); print("LARGEST_PRIME_FACTOR:", largest);
  print("B_SMOOTH:", largest <= smooth_bound); print("B_POWER_SMOOTH:", power_smooth);
  reps = qfbsolve(Qfb(1, 0, form_d), [a, f], 2);
  print("FORM_SOLVABLE:", type(reps) == "t_VEC" && #reps == 2);
  if(type(reps) == "t_VEC" && #reps == 2, print("FORM_REP:", reps[1], "|", reps[2]));
  for(i = 1, #divs,
    if(divs[i] % 4 == 1, r2 += 4, if(divs[i] % 4 == 3, r2 -= 4));
    if(divs[i] % 4, r4 += 8 * divs[i]);
  );
  print("SUM_TWO_SQUARE_COUNT:", r2);
  print("SUM_FOUR_SQUARE_COUNT:", r4);
  if(a % 4 != 2,
    if(a % 2,
      difference_a = (a + 1) / 2; difference_b = (a - 1) / 2;
    ,
      difference_a = a / 4 + 1; difference_b = abs(a / 4 - 1);
    );
    print("DIFFERENCE_SQUARES:1"); print("DIFFERENCE_REP:", difference_a, "|", difference_b);
  ,
    print("DIFFERENCE_SQUARES:0");
  );
  print("DONE:1");
};

nt_is_strong_psp(n, base) =
{
  if(n < 3 || n % 2 == 0 || gcd(n, base) != 1, return(0));
  my(s = valuation(n - 1, 2), d = (n - 1) / 2^s, x = lift(Mod(base, n)^d));
  if(x == 1 || x == n - 1, return(1));
  for(i = 1, s - 1, x = x^2 % n; if(x == n - 1, return(1)));
  0;
};

nt_primality_lab(n, base, rigorous_mode) =
{
  if(n < 2, error("Primality analysis requires an integer at least 2"));
  if(base < 2, error("The test base must be at least 2"));
  print("FERMAT:", gcd(n, base) == 1 && lift(Mod(base, n)^(n - 1)) == 1);
  print("EULER_JACOBI:", gcd(n, base) == 1 && n % 2 &&
        lift(Mod(base, n)^((n - 1) / 2)) == (kronecker(base, n) % n));
  print("MILLER_RABIN:", nt_is_strong_psp(n, base));
  print("BPSW:", ispseudoprime(n));
  if(rigorous_mode >= 0 && rigorous_mode <= 3,
    print("PROVEN:", isprime(n, rigorous_mode));
    print("PROOF_MODE:", rigorous_mode);
  ,
    print("PROVEN:-1"); print("PROOF_MODE:-1");
  );
  print("COMPOSITE:", !isprime(n));
  print("DONE:1");
};

nt_lucas_lehmer(exponent) =
{
  if(exponent < 2 || !isprime(exponent), error("The Mersenne exponent must be prime"));
  my(M = 2^exponent - 1, s = 4);
  if(exponent == 2, s = 0, for(i = 1, exponent - 2, s = (s^2 - 2) % M));
  print("NUMBER:", M); print("PASSES:", s == 0); print("PROVEN:", s == 0);
  print("DONE:1");
};

nt_pepin(index) =
{
  if(index < 0, error("The Fermat index must be nonnegative"));
  my(F = 2^(2^index) + 1, passes = if(index == 0, 1, lift(Mod(3, F)^((F - 1) / 2)) == F - 1));
  print("NUMBER:", F); print("PASSES:", passes); print("PROVEN:", passes);
  print("DONE:1");
};

nt_perfect_power(n) =
{
  if(n == 0 || abs(n) == 1,
    print("IS_POWER:0"); print("EXPONENT:0"); print("BASE:", n); print("DONE:1"); return();
  );
  my(exponent = ispower(n), base = n);
  if(exponent, ispower(n, exponent, &base));
  print("IS_POWER:", exponent > 0); print("EXPONENT:", exponent); print("BASE:", base);
  print("DONE:1");
};

nt_factor_strategy(n, trial_bound, cado_threshold) =
{
  if(n == 0 || abs(n) == 1, error("Factorization strategy requires |n| at least 2"));
  my(a = abs(n), residual = abs(n), exponent = ispower(abs(n)), base = abs(n),
     vplus, vminus, form_exponent, form_base, count = 0, e);
  if(exponent, ispower(abs(n), exponent, &base));
  print("DIGITS:", #digits(a)); print("PROBABLE_PRIME:", ispseudoprime(a));
  print("PERFECT_POWER:", exponent > 0); print("POWER_BASE:", base); print("POWER_EXPONENT:", exponent);
  vplus = valuation(a + 1, 2);
  if(2^vplus == a + 1, print("MERSENNE_FORM:", vplus), print("MERSENNE_FORM:0"));
  if(a > 2,
    vminus = valuation(a - 1, 2);
    if(2^vminus == a - 1 && (vminus == 1 || ispower(vminus, 2)),
      print("FERMAT_FORM:", if(vminus == 1, 0, valuation(vminus, 2))),
      print("FERMAT_FORM:-1")
    );
  , print("FERMAT_FORM:-1"));
  form_exponent = ispower(a + 1); form_base = 0;
  if(form_exponent, ispower(a + 1, form_exponent, &form_base));
  if(form_exponent, print("POWER_MINUS_ONE:", form_base, "|", form_exponent));
  form_exponent = ispower(a - 1); form_base = 0;
  if(form_exponent, ispower(a - 1, form_exponent, &form_base));
  if(form_exponent, print("POWER_PLUS_ONE:", form_base, "|", form_exponent));
  forprime(p = 2, trial_bound,
    if(p * p > residual, break());
    if(residual % p == 0,
      e = valuation(residual, p); print("SMALL_FACTOR:", p, "|", e);
      residual /= p^e; count++;
    );
  );
  if(residual > 1 && residual <= trial_bound^2 && isprime(residual),
    print("SMALL_FACTOR:", residual, "|1"); residual = 1; count++;
  );
  print("SMALL_FACTOR_COUNT:", count); print("RESIDUAL:", residual);
  print("RESIDUAL_DIGITS:", if(residual == 1, 0, #digits(residual)));
  if(residual == 1,
    print("STRATEGY:complete_by_trial_division");
  , if(exponent,
    print("STRATEGY:factor_perfect_power_base");
  , if(#digits(residual) < cado_threshold,
    print("STRATEGY:yafu");
  ,
    print("STRATEGY:hybrid_yafu_cado");
  )));
  print("DONE:1");
};

nt_eisenstein(a, b) =
{
  my(norm = a^2 - a*b + b^2, axis, prime);
  axis = (a == 0 || b == 0 || a == b);
  prime = isprime(norm) || (axis && isprime(abs(if(a, a, b))) && abs(if(a, a, b)) % 3 == 2);
  print("NORM:", norm); print("AXIS: ", axis); print("PRIME:", prime); print("DONE:1");
};

nt_quadratic_prime_decomposition(discriminant, p) =
{
  if(p < 2 || !isprime(p), error("The rational input must be a proven prime"));
  if(discriminant == 0 || issquare(discriminant), error("The quadratic radicand must be nonsquare"));
  my(K = nfinit(x^2 - discriminant), dec = idealprimedec(K, p));
  print("KRONECKER:", kronecker(K.disc, p)); print("FIELD_DISCRIMINANT:", K.disc);
  for(i = 1, #dec,
    print("PRIME_IDEAL:", i, "|", dec[i].e, "|", dec[i].f, "|", p^dec[i].f);
  );
  print("IDEAL_COUNT:", #dec); print("DONE:", #dec);
};

nt_prime_approximations(x, exact_count, li_value, r_value) =
{
  if(x < 3, error("Approximation comparison requires x at least 3"));
  my(old_precision = default(realprecision), elementary, relative);
  default(realprecision, 50);
  elementary = x / log(x);
  print("APPROX:Exact pi(x)|", exact_count, "|0|0");
  relative = (elementary - exact_count) / exact_count * 100;
  print("APPROX:x/log(x)|", Strprintf("%.30g", elementary), "|",
        Strprintf("%.30g", elementary - exact_count), "|", Strprintf("%.20g", relative));
  relative = (li_value - exact_count) / exact_count * 100;
  print("APPROX:Li(x)|", li_value, "|", li_value - exact_count, "|",
        Strprintf("%.20g", relative));
  relative = (r_value - exact_count) / exact_count * 100;
  print("APPROX:Riemann R(x)|", r_value, "|", r_value - exact_count, "|",
        Strprintf("%.20g", relative));
  default(realprecision, old_precision);
  print("DONE:1");
};

nt_summatory_functions(x) =
{
  if(x < 1, error("The summatory endpoint must be positive"));
  my(mertens = 0, liouville = 0, theta = 0.0, chebyshev_psi = 0.0,
     old_precision = default(realprecision));
  default(realprecision, 50);
  for(n = 1, x,
    mertens += moebius(n);
    liouville += (-1)^bigomega(n);
  );
  forprime(p = 2, x,
    theta += log(p);
    my(power = p);
    while(power <= x,
      chebyshev_psi += log(p);
      if(power > x / p, break());
      power *= p;
    );
  );
  print("MERTENS:", mertens); print("SUM_LIOUVILLE:", liouville);
  print("THETA:", Strprintf("%.30g", theta));
  print("PSI:", Strprintf("%.30g", chebyshev_psi));
  default(realprecision, old_precision);
  print("DONE:1");
};

nt_special_prime_family(kind, start_index, end_index, result_limit) =
{
  if(start_index < 0 || end_index < start_index, error("Invalid family index range"));
  my(found = 0, truncated = 0, value, aux, product = 1, factorial = 1);
  if(kind == 6,
    for(i = 1, end_index, product *= prime(i);
      if(i >= start_index,
        for(sign = -1, 1, if(sign == 0, next()); value = product + sign;
          if(value > 1 && isprime(value),
            if(found >= result_limit, truncated = 1; break(2));
            print("FAMILY:", i, "|", value, "|", sign); found++;
          );
        );
      );
    );
  , if(kind == 7,
    for(i = 1, end_index, factorial *= i;
      if(i >= start_index,
        for(sign = -1, 1, if(sign == 0, next()); value = factorial + sign;
          if(value > 1 && isprime(value),
            if(found >= result_limit, truncated = 1; break(2));
            print("FAMILY:", i, "|", value, "|", sign); found++;
          );
        );
      );
    );
  ,
    for(i = start_index, end_index,
      aux = 0;
      if(kind == 0, if(!isprime(i), next()); value = 2^i - 1; aux = i);
      if(kind == 1, value = 2^(2^i) + 1; aux = i);
      if(kind == 2, value = i * 2^i + 1; aux = i);
      if(kind == 3, value = i * 2^i - 1; aux = i);
      if(kind == 4, if(i < 3 || !isprime(i), next()); value = (2^i + 1) / 3; aux = i);
      if(kind == 5, if(i < 1, next()); value = (10^i - 1) / 9; aux = i);
      if(isprime(value),
        if(found >= result_limit, truncated = 1; break());
        print("FAMILY:", i, "|", value, "|", aux); found++;
      );
    );
  ));
  print("TRUNCATED:", truncated); print("DONE:", found);
};

nt_cunningham_chain(start_prime, chain_length, kind) =
{
  if(start_prime < 2 || !isprime(start_prime), error("The chain must start at a proven prime"));
  if(kind != 1 && kind != 2, error("Cunningham kind must be 1 or 2"));
  my(value = start_prime, status);
  for(i = 1, chain_length,
    status = isprime(value);
    print("CHAIN:", i, "|", value, "|", status);
    if(!status, print("DONE:", i); return());
    value = if(kind == 1, 2 * value + 1, 2 * value - 1);
  );
  print("DONE:", chain_length);
};

nt_ntt_primes(bits, power_two, requested, candidate_limit) =
{
  if(bits < 2 || power_two < 1 || power_two >= bits,
    error("Require 2 <= bits and 1 <= power-two exponent < bits")
  );
  my(step = 2^power_two, lower = 2^(bits - 1), upper = 2^bits - 1,
     k = (lower - 1 + step - 1) \ step, candidate, found = 0, tested = 0);
  while(found < requested && tested < candidate_limit,
    candidate = k * step + 1;
    if(candidate > upper, break());
    if(isprime(candidate), print("NTT:", k, "|", candidate); found++);
    k++; tested++;
  );
  print("TESTED:", tested); print("FOUND:", found); print("DONE:", found);
};

nt_tonelli_shanks(a, p, trace_limit) =
{
  if(p < 2 || !isprime(p), error("The modulus must be a proven prime"));
  a %= p;
  print("LEGENDRE:", kronecker(a, p));
  if(a == 0, print("ROOT:0"); print("DONE:1"); return());
  if(p == 2, print("ROOT:", a); print("DONE:1"); return());
  if(kronecker(a, p) != 1, print("DONE:0"); return());
  my(q = p - 1, s = valuation(p - 1, 2), z = 2, c, root, t, m, i, probe, b,
     steps = 0);
  q /= 2^s;
  while(kronecker(z, p) != -1, z++);
  c = lift(Mod(z, p)^q);
  root = lift(Mod(a, p)^((q + 1) / 2));
  t = lift(Mod(a, p)^q); m = s;
  print("SETUP:", q, "|", s, "|", z);
  if(trace_limit > 0, print("TRACE:0|", root, "|", t, "|", c, "|", m));
  while(t != 1,
    i = 1; probe = t^2 % p;
    while(i < m && probe != 1, probe = probe^2 % p; i++);
    if(i >= m, error("Tonelli-Shanks invariant failed"));
    b = lift(Mod(c, p)^(2^(m - i - 1)));
    root = root * b % p; t = t * b^2 % p; c = b^2 % p; m = i; steps++;
    if(steps <= trace_limit, print("TRACE:", steps, "|", root, "|", t, "|", c, "|", m));
  );
  print("ROOT:", min(root, p - root));
  if(root != 0 && root != p - root, print("ROOT:", max(root, p - root)));
  print("STEPS:", steps); print("TRACE_COMPLETE:", steps <= trace_limit);
  print("DONE:", if(root == p - root, 1, 2));
};

nt_hensel_roots(coefficients, p, exponent, result_limit) =
{
  if(#coefficients < 2, error("A polynomial needs at least two coefficients"));
  if(p < 2 || !isprime(p), error("The base modulus must be a proven prime"));
  if(exponent < 1, error("The prime-power exponent must be positive"));
  my(P = Polrev(coefficients), derivative = deriv(P), roots = List(), next_roots,
     base_roots = polrootsmod(P, p), modulus = p, next_modulus, residue, value,
     derivative_value, quotient, digit, candidate, complete = 1);
  for(i = 1, #base_roots, listput(roots, lift(base_roots[i])));
  for(level = 2, exponent,
    next_modulus = modulus * p; next_roots = List();
    for(i = 1, #roots,
      residue = roots[i]; value = subst(P, x, residue);
      derivative_value = subst(derivative, x, residue) % p;
      if(derivative_value,
        quotient = value \ modulus;
        digit = (-quotient * lift(Mod(derivative_value, p)^-1)) % p;
        listput(next_roots, residue + digit * modulus);
      ,
        if(value % next_modulus == 0,
          for(digit = 0, p - 1,
            listput(next_roots, residue + digit * modulus);
            if(#next_roots > result_limit, complete = 0; break(2));
          );
        );
      );
    );
    roots = next_roots; modulus = next_modulus;
    if(!complete, break());
  );
  print("POLYNOMIAL:", P); print("MODULUS:", p^exponent);
  print("ROOT_COUNT:", if(complete, #roots, -1));
  for(i = 1, min(#roots, result_limit), print("ROOT:", roots[i]));
  print("COMPLETE:", complete); print("TRUNCATED:", !complete || #roots > result_limit);
  print("DONE:", min(#roots, result_limit));
};

nt_order_distribution(modulus, result_limit) =
{
  if(modulus < 2 || modulus > 1000000, error("The modulus must be between 2 and 1,000,000"));
  my(counts = Map(), order, keys, emitted = 0, units = 0);
  for(a = 1, modulus - 1,
    if(gcd(a, modulus) == 1,
      units++; order = znorder(Mod(a, modulus));
      mapput(counts, order, if(mapisdefined(counts, order), mapget(counts, order) + 1, 1));
    );
  );
  keys = Vec(counts); keys = vecsort(keys);
  for(i = 1, min(#keys, result_limit),
    print("ORDER_ROW:", keys[i], "|", mapget(counts, keys[i])); emitted++;
  );
  print("UNIT_COUNT:", units); print("ORDER_COUNT:", #keys);
  print("TRUNCATED:", #keys > result_limit); print("DONE:", emitted);
};

nt_power_residues(p, exponent, result_limit) =
{
  if(p < 2 || p > 1000000 || !isprime(p), error("Require a proven prime p <= 1,000,000"));
  if(exponent < 1, error("The exponent must be positive"));
  my(counts = vector(p, i, 0), residue, distinct = 0, emitted = 0);
  for(a = 0, p - 1, residue = lift(Mod(a, p)^exponent); counts[residue + 1]++);
  for(residue = 0, p - 1,
    if(counts[residue + 1],
      distinct++;
      if(emitted < result_limit,
        print("RESIDUE:", residue, "|", counts[residue + 1]); emitted++;
      );
    );
  );
  print("DISTINCT:", distinct); print("TRUNCATED:", distinct > result_limit);
  print("DONE:", emitted);
};

nt_valuation(n, p) =
{
  if(n == 0, error("The p-adic valuation of zero is infinite"));
  if(p < 2 || !isprime(p), error("The valuation base must be a proven prime"));
  my(v = valuation(n, p), unit = n / p^v);
  print("VALUATION:", v); print("UNIT_PART:", unit); print("DONE:1");
};

nt_cyclotomic(index, p) =
{
  if(index < 1 || index > 10000, error("The cyclotomic index must be between 1 and 10,000"));
  if(p < 2 || !isprime(p), error("The finite-field modulus must be a proven prime"));
  my(P = polcyclo(index), factors = factor(Mod(1, p) * P));
  print("DEGREE:", poldegree(P)); print("POLYNOMIAL:", P);
  for(i = 1, matsize(factors)[1],
    print("CYCLO_FACTOR:", lift(factors[i, 1]), "|", factors[i, 2]);
  );
  print("FACTOR_COUNT:", matsize(factors)[1]); print("DONE:", matsize(factors)[1]);
};

nt_aliquot(n, max_steps) =
{
  if(n < 1, error("The aliquot sequence must start at a positive integer"));
  my(seen = Map(), current = n, next_value, status = 0, stop_index = 0);
  for(i = 0, max_steps,
    if(mapisdefined(seen, current), status = 2; stop_index = mapget(seen, current); break());
    mapput(seen, current, i);
    print("ALIQUOT:", i, "|", current);
    if(current == 0, status = 1; stop_index = i; break());
    next_value = sigma(current) - current;
    if(next_value == 0,
      print("ALIQUOT:", i + 1, "|0"); status = 1; stop_index = i + 1; break();
    );
    current = next_value;
  );
  print("STATUS:", status); print("STOP_INDEX:", stop_index);
  print("DONE:", #seen);
};

nt_divisor_classification(n) =
{
  if(n < 1, error("Divisor classification requires a positive integer"));
  my(total = sigma(n), proper = total - n, partner = if(proper > 0, sigma(proper) - proper, 0));
  print("SIGMA:", total); print("PROPER_SUM:", proper);
  print("ABUNDANCE:", if(proper < n, -1, proper > n));
  print("PERFECT:", proper == n); print("ALMOST_PERFECT:", proper == n - 1);
  print("MULTIPERFECT_K:", if(total % n == 0, total / n, 0));
  print("ALIQUOT_PARTNER:", proper); print("AMICABLE_PAIR:", proper != n && partner == n);
  print("DONE:1");
};
