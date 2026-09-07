\\ Numerisect algebra laboratory for PARI/GP.
\\
\\ Modular, arithmetic, and algebraic workbenches: quadratic-reciprocity traces,
\\ composite-modulus congruences, discrete logarithms with selectable algorithms,
\\ finite-field arithmetic, divisor lattices, smoothness, record divisor numbers,
\\ weird-number proofs, sociable cycles, Cornacchia traces, quadratic rings,
\\ general number fields, and Chebotarev experiments.  Python validates requests
\\ and parses the tagged protocol; every calculation lives here.
\\
\\ This file is a driver over PARI's own routines, not a reimplementation of them:
\\   45       kronecker, valuation, gcd, isprime
\\   48       factor, polrootsmod, chinese, deriv, subst
\\   50       znlog, znorder, factor, chinese
\\   57       ffinit, ffgen, fforder, ffprimroot, minpoly, polisirreducible
\\   61       factor, divisors, sigma, numdiv, bigomega, isprime
\\   68       factor
\\   69       numdiv, sigma, nextprime, log
\\   70       sigma, divisors, shift/bitor/bitand/bittest
\\   71       sigma
\\   74       qfbsolve, qfbcornacchia, polrootsmod, issquare, sqrtint, fordiv
\\   110-111  core, quaddisc, quadgen, norm, trace, quadunit, quadclassunit,
\\            bnfinit, bnfcertify, kronecker, idealprimedec, bnfisprincipal, nfbasistoalg
\\   112-113  nfinit, idealprimedec, idealfactor, nfeltnorm, polgalois, bnfinit, bnfcertify
\\   115      factormod, polgalois, nfsplitting, nfgaloisconj, permcycles, partitions
\\
\\ Steps are written out only where the feature exists to display them (45, the
\\ BSGS/Pohlig-Hellman/Pollard-rho comparison in 50, and the Cornacchia descent in
\\ 74); each of those is cross-checked against the corresponding native routine.
\\ PARI has no routine for all roots modulo p^k (polrootspadic returns only the
\\ p-adically liftable ones), for highly composite / colossally abundant numbers, or
\\ for subset sums, so those three are built from PARI primitives.

al_join(values) =
{
  my(s = "");
  for(i = 1, #values, s = concat(concat(s, if(i > 1, ",", "")), Str(values[i])));
  s;
};

\\ Ascending integer coordinates of a field element or polynomial, padded to `length`.
\\ lift() is a no-op on t_FFELT, so the representative polynomial must be taken with .pol.
al_coeffs(poly, length) =
{
  my(v = Vecrev(if(type(poly) == "t_FFELT", poly.pol, lift(poly))), out = vector(length, i, 0));
  for(i = 1, min(#v, length), out[i] = lift(v[i]));
  out;
};

\\ ---------------------------------------------------------------- 45
\\ Jacobi/Legendre reduction trace.  STEP:index|kind|a|n|factor|detail
al_reciprocity(a0, n0, trace_limit) =
{
  if(n0 < 1 || n0 % 2 == 0, error("The reciprocity denominator must be a positive odd integer"));
  my(a = a0, n = n0, sign = 1, steps = List(), k, factor_value, reduced, exponent, emitted);
  while(1,
    if(a < 0 || a >= n,
      reduced = a % n;
      listput(steps, ["reduce", reduced, n, 1, Str("a reduced modulo ", n)]);
      a = reduced;
    );
    if(n == 1, listput(steps, ["terminal", a, n, 1, "(a/1) = 1"]); break());
    if(a == 0, listput(steps, ["terminal", a, n, 0, "(0/n) = 0 for n > 1"]); sign = 0; break());
    if(a == 1, listput(steps, ["terminal", a, n, 1, "(1/n) = 1"]); break());
    if(gcd(a, n) > 1,
      listput(steps, ["common-factor", a, n, 0, Str("gcd(a, n) = ", gcd(a, n), " so the symbol is 0")]);
      sign = 0; break();
    );
    k = valuation(a, 2);
    if(k > 0,
      factor_value = if(n % 8 == 1 || n % 8 == 7, 1, -1);
      exponent = if(k % 2, factor_value, 1);
      a >>= k;
      listput(steps, ["two-power", a, n, exponent,
                      Str("(2/n)^", k, " with n = ", n % 8, " (mod 8) gives ", exponent)]);
      sign *= exponent;
      if(a == 1, listput(steps, ["terminal", a, n, 1, "(1/n) = 1"]); break());
    );
    factor_value = if(a % 4 == 3 && n % 4 == 3, -1, 1);
    listput(steps, ["flip", n, a, factor_value,
                    Str("(a/n) = ", if(factor_value == -1, "-", ""), "(n/a): a = ", a % 4, ", n = ", n % 4, " (mod 4)")]);
    sign *= factor_value;
    [a, n] = [n, a];
  );
  emitted = min(#steps, trace_limit);
  for(i = 1, emitted,
    print("STEP:", i, "|", steps[i][1], "|", steps[i][2], "|", steps[i][3], "|", steps[i][4], "|", steps[i][5]));
  print("VALUE:", sign);
  print("KRONECKER:", kronecker(a0, n0));
  print("VERIFIED:", sign == kronecker(a0, n0));
  print("LEGENDRE_AVAILABLE:", n0 > 2 && isprime(n0));
  print("STEPS:", #steps); print("TRUNCATED:", #steps > trace_limit);
  print("DONE:", emitted);
};

\\ ---------------------------------------------------------------- 48
\\ Roots of P modulo p^e by Hensel lifting including singular roots.
\\ Returns [roots, complete].
al_prime_power_roots(P, p, exponent, root_cap) =
{
  my(Pp = Mod(1, p) * P, derivative = deriv(P), roots = List(), next_roots,
     modulus = p, next_modulus, residue, value, derivative_value, quotient,
     digit, complete = 1);
  if(Pp == 0,
    if(p > root_cap, return([List(), 0]));
    for(r = 0, p - 1, listput(roots, r));
  ,
    if(poldegree(Pp) < 1, return([List(), 1]));
    my(base = polrootsmod(P, p));
    for(i = 1, #base, listput(roots, lift(base[i])));
  );
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
          if(p > root_cap, complete = 0; break(2));
          for(digit = 0, p - 1,
            listput(next_roots, residue + digit * modulus);
            if(#next_roots > root_cap, complete = 0; break(2));
          );
        );
      );
    );
    roots = next_roots; modulus = next_modulus;
    if(!complete, break());
  );
  if(#roots > root_cap, complete = 0);
  [roots, complete];
};

\\ All roots of P modulo m (composite allowed).  Returns [roots, count, complete]
\\ where count is exact whenever complete is 1 (roots may still be capped).
al_all_roots_mod(P, m, root_cap) =
{
  my(f = factor(m), parts = vector(matsize(f)[1]), count = 1, complete = 1, roots = List(),
     odometer, current, total);
  for(i = 1, matsize(f)[1],
    parts[i] = al_prime_power_roots(P, f[i, 1], f[i, 2], root_cap);
    if(!parts[i][2], complete = 0);
    count *= #parts[i][1];
  );
  if(!complete, return([List(), -1, 0, f]));
  if(count == 0, return([List(), 0, 1, f]));
  total = min(count, root_cap);
  odometer = vector(#parts, i, 1);
  for(t = 1, total,
    current = Mod(0, 1);
    for(i = 1, #parts,
      current = chinese(current, Mod(parts[i][1][odometer[i]], f[i, 1]^f[i, 2]));
    );
    listput(roots, lift(current));
    for(i = 1, #parts,
      odometer[i]++;
      if(odometer[i] <= #parts[i][1], break());
      odometer[i] = 1;
    );
  );
  [roots, count, 1, f];
};

al_congruence(coefficients, m, result_limit) =
{
  if(#coefficients < 2, error("A congruence needs at least two coefficients"));
  if(m < 2, error("The modulus must be at least 2"));
  my(P = Polrev(coefficients), reduced = Polrev(apply(c -> c % m, coefficients)), result, f, roots, hit);
  print("POLYNOMIAL:", P);
  print("REDUCED:", reduced);
  if(reduced == 0,
    f = factor(m);
    for(i = 1, matsize(f)[1], print("PRIME_POWER:", f[i, 1], "|", f[i, 2], "|", f[i, 1]^f[i, 2], "|1"));
    for(r = 0, min(m, result_limit) - 1, print("SOLUTION:", r));
    print("SOLUTION_COUNT:", m); print("COMPLETE:1"); print("TRUNCATED:", m > result_limit);
    print("DONE:", min(m, result_limit)); return();
  );
  result = al_all_roots_mod(P, m, result_limit);
  f = result[4];
  for(i = 1, matsize(f)[1],
    my(part = al_prime_power_roots(P, f[i, 1], f[i, 2], result_limit));
    print("PRIME_POWER:", f[i, 1], "|", f[i, 2], "|", if(part[2], #part[1], -1), "|", part[2]);
  );
  roots = result[1];
  for(i = 1, #roots,
    hit = subst(P, x, roots[i]) % m;
    if(hit != 0, error("Internal congruence verification failed"));
    print("SOLUTION:", roots[i]);
  );
  print("SOLUTION_COUNT:", result[2]);
  print("COMPLETE:", result[3]);
  print("TRUNCATED:", !result[3] || result[2] > result_limit);
  print("DONE:", #roots);
};

\\ ---------------------------------------------------------------- 50
al_bsgs(h, g, order, step_limit) =
{
  my(m = sqrtint(order - 1) + 1, table = Map(), current = Mod(1, g.mod), giant, steps = 0, factor_step, found = -1);
  if(m > step_limit, print("BABY_STEPS:", m); return([-1, 0, 1]));
  for(j = 0, m - 1,
    if(!mapisdefined(table, lift(current)), mapput(table, lift(current), j));
    current *= g; steps++;
  );
  print("BABY_STEPS:", m);
  factor_step = g^-m; giant = h;
  for(i = 0, m - 1,
    steps++;
    if(mapisdefined(table, lift(giant)),
      found = i * m + mapget(table, lift(giant)); print("GIANT_STEPS:", i + 1); break();
    );
    giant *= factor_step;
    if(steps > step_limit, return([-1, steps, 1]));
  );
  if(found < 0, print("GIANT_STEPS:", m));
  [found, steps, 0];
};

al_pohlig_hellman(h, g, order, step_limit) =
{
  my(f = factor(order), q, e, gi, hi, xi, digit, gq, hk, steps = 0, result, x = Mod(0, 1), total_steps = 0);
  for(i = 1, matsize(f)[1],
    q = f[i, 1]; e = f[i, 2];
    gi = g^(order / q^e); hi = h^(order / q^e); xi = 0;
    gq = gi^(q^(e - 1));
    for(k = 0, e - 1,
      hk = (hi * gi^(-xi))^(q^(e - 1 - k));
      result = al_bsgs(hk, gq, q, step_limit - total_steps);
      total_steps += result[2];
      if(result[3], print("SUBLOG:", q, "|", e, "|-1|", k); return([-1, total_steps, 1]));
      if(result[1] < 0, print("SUBLOG:", q, "|", e, "|-1|", k); return([-2, total_steps, 0]));
      xi += result[1] * q^k;
    );
    print("SUBLOG:", q, "|", e, "|", xi, "|", e);
    x = chinese(x, Mod(xi, q^e));
  );
  [lift(x), total_steps, 0];
};

al_pollard_rho(h, g, order, step_limit) =
{
  my(n = g.mod, f(v) = my(c = lift(v[1]) % 3);
       if(c == 0, [v[1] * h, v[2], v[3] + 1],
          c == 1, [v[1]^2, 2 * v[2], 2 * v[3]],
                  [v[1] * g, v[2] + 1, v[3]]),
     tortoise, hare, steps = 0, a, b, d, candidates, attempt = 0, seed = 1);
  setrand(1);
  while(attempt < 8,
    attempt++;
    a = random(order); b = random(order);
    tortoise = [g^a * h^b, a, b]; hare = tortoise;
    while(steps < step_limit,
      tortoise = f(tortoise); hare = f(f(hare)); steps++;
      if(tortoise[1] == hare[1],
        \\ g^(a1) h^(b1) = g^(a2) h^(b2)  =>  x (b1 - b2) = a2 - a1 (mod order)
        a = (tortoise[2] - hare[2]) % order; b = (hare[3] - tortoise[3]) % order;
        d = gcd(b, order);
        if(d == 0, break());
        if(a % d, break());
        if(d > 4096, break());
        for(t = 0, d - 1,
          my(candidate = lift(Mod(a / d, order / d) / Mod(b / d, order / d)) + t * order / d);
          if(g^candidate == h, print("COLLISIONS:", attempt); return([candidate, steps, 0]));
        );
        break();
      );
    );
    if(steps >= step_limit, print("COLLISIONS:", attempt); return([-1, steps, 1]));
  );
  print("COLLISIONS:", attempt);
  [-1, steps, 1];
};

al_dlog(target, generator, modulus, algorithm, step_limit) =
{
  if(modulus < 2, error("The modulus must be at least 2"));
  if(gcd(target, modulus) != 1 || gcd(generator, modulus) != 1,
    error("The target and base must be units modulo n"));
  my(g = Mod(generator, modulus), h = Mod(target, modulus), order = znorder(g), result, value);
  print("BASE:", lift(g)); print("TARGET:", lift(h));
  print("ORDER:", order);
  print("ALGORITHM:", algorithm);
  if(algorithm == 3,
    value = znlog(h, g, [order, factor(order)]);
    result = if(type(value) == "t_VEC" && #value == 0, [-2, 0, 0], [value, 0, 0]);
  , algorithm == 0, result = al_bsgs(h, g, order, step_limit);
  , algorithm == 1, result = al_pohlig_hellman(h, g, order, step_limit);
  , algorithm == 2, result = al_pollard_rho(h, g, order, step_limit);
  , error("Unknown discrete-logarithm algorithm"));
  print("STEPS:", result[2]);
  print("LIMIT_REACHED:", result[3]);
  if(result[1] >= 0,
    if(g^result[1] != h, error("Internal discrete-logarithm verification failed"));
    print("STATUS:1"); print("LOG:", result[1] % order);
  , result[1] == -2,
    print("STATUS:0");
  ,
    print("STATUS:-1");
  );
  print("DONE:1");
};

\\ ---------------------------------------------------------------- 57
al_ff_element(name, e, p, m) =
{
  my(order_value);
  print("ELEMENT:", name, "|", al_join(al_coeffs(e, m)), "|", if(e == 0, 0, poldegree(minpoly(e))));
  if(e != 0,
    order_value = fforder(e);
    print("ORDER:", name, "|", order_value, "|", order_value == p^m - 1);
    print("MINPOLY:", name, "|", al_join(Vecrev(lift(minpoly(e)))));
    print("FROBENIUS:", name, "|", al_join(al_coeffs(e^p, m)));
  );
};

al_finite_field(p, m, modulus_coefficients, a_coefficients, b_coefficients, exponent) =
{
  if(p < 2 || !isprime(p), error("The field characteristic must be a proven prime"));
  if(m < 1, error("The extension degree must be positive"));
  my(T, g, a, b, primitive);
  if(#modulus_coefficients,
    T = Mod(1, p) * Polrev(modulus_coefficients);
    if(poldegree(T) != m, error("The modulus polynomial must have degree exactly m modulo p"));
    if(!polisirreducible(T), error("The modulus polynomial is reducible modulo p"));
    T /= pollead(T);
  ,
    T = ffinit(p, m);
  );
  g = ffgen(T, 'a);
  print("MODULUS:", al_join(Vecrev(lift(g.mod))));
  print("FIELD_ORDER:", p^m);
  a = 0 * g + sum(i = 1, #a_coefficients, (a_coefficients[i] % p) * g^(i - 1));
  b = 0 * g + sum(i = 1, #b_coefficients, (b_coefficients[i] % p) * g^(i - 1));
  al_ff_element("a", a, p, m);
  al_ff_element("b", b, p, m);
  print("RESULT:sum|", al_join(al_coeffs(a + b, m)));
  print("RESULT:difference|", al_join(al_coeffs(a - b, m)));
  print("RESULT:product|", al_join(al_coeffs(a * b, m)));
  if(b != 0, print("RESULT:quotient|", al_join(al_coeffs(a / b, m))), print("QUOTIENT_UNDEFINED:1"));
  if(a != 0 || exponent >= 0,
    print("RESULT:power|", al_join(al_coeffs(a^exponent, m))), print("POWER_UNDEFINED:1"));
  primitive = ffprimroot(g);
  print("PRIMITIVE_ELEMENT:", al_join(al_coeffs(primitive, m)));
  \\ For m = 1 the residue of the degree-one modulus can be 0, which has no multiplicative order.
  print("GENERATOR_ORDER:", if(g == 0, 0, fforder(g)));
  print("DONE:1");
};

\\ ---------------------------------------------------------------- 61
al_divisor_lattice(n, divisor_limit, lattice_cap) =
{
  if(n < 1, error("Divisor enumeration requires a positive integer"));
  my(f = factor(n), divs = divisors(f), count = #divs, edges = 0);
  for(i = 1, matsize(f)[1], print("PRIME:", f[i, 1], "|", f[i, 2]));
  print("DIVISOR_COUNT:", count); print("SIGMA:", sigma(n));
  for(i = 1, min(count, divisor_limit),
    print("DIVISOR:", divs[i], "|", n / divs[i], "|", bigomega(divs[i]), "|", isprime(divs[i]));
  );
  print("DIVISORS_COMPLETE:", count <= divisor_limit);
  if(count <= lattice_cap,
    for(i = 1, count,
      for(j = 1, matsize(f)[1],
        if((n / divs[i]) % f[j, 1] == 0, print("EDGE:", divs[i], "|", divs[i] * f[j, 1], "|", f[j, 1]); edges++);
      );
    );
    print("LATTICE_COMPLETE:1");
  ,
    print("LATTICE_COMPLETE:0");
  );
  print("EDGE_COUNT:", edges);
  print("DONE:", min(count, divisor_limit));
};

\\ ---------------------------------------------------------------- 68
al_smoothness(n, smooth_bound, rough_bound) =
{
  if(n == 0 || abs(n) == 1, error("Smoothness analysis requires |n| at least 2"));
  if(smooth_bound < 2 || rough_bound < 2, error("Bounds must be at least 2"));
  my(a = abs(n), f = factor(a), largest_power = 1, smooth_part = 1, rough_part = 1, pp);
  for(i = 1, matsize(f)[1],
    pp = f[i, 1]^f[i, 2];
    print("PRIME:", f[i, 1], "|", f[i, 2], "|", pp, "|", f[i, 1] <= smooth_bound, "|", pp <= smooth_bound, "|", f[i, 1] >= rough_bound);
    largest_power = max(largest_power, pp);
    if(f[i, 1] <= smooth_bound, smooth_part *= pp, rough_part *= pp);
  );
  print("LEAST_PRIME_FACTOR:", f[1, 1]);
  print("LARGEST_PRIME_FACTOR:", f[matsize(f)[1], 1]);
  print("LARGEST_PRIME_POWER:", largest_power);
  print("SMOOTHNESS_BOUND:", f[matsize(f)[1], 1]);
  print("POWERSMOOTHNESS_BOUND:", largest_power);
  print("ROUGHNESS_BOUND:", f[1, 1]);
  print("B_SMOOTH:", f[matsize(f)[1], 1] <= smooth_bound);
  print("B_POWERSMOOTH:", largest_power <= smooth_bound);
  print("B_ROUGH:", f[1, 1] >= rough_bound);
  print("SMOOTH_PART:", smooth_part); print("ROUGH_PART:", rough_part);
  print("DONE:1");
};

\\ ---------------------------------------------------------------- 69
\\ Candidates with non-increasing exponents over consecutive primes, all <= bound.
al_record_candidates(bound) =
{
  \\ Breadth-first expansion; GP closures capture by value, so no recursion here.
  my(out = List([1]), frontier = List([[1, 1, logint(max(bound, 2), 2)]]), next_level, value, index, cap, p, power);
  while(#frontier,
    next_level = List();
    for(i = 1, #frontier,
      value = frontier[i][1]; index = frontier[i][2]; cap = frontier[i][3];
      p = prime(index); power = 1;
      for(e = 1, cap,
        power *= p;
        if(value * power > bound, break());
        listput(out, value * power);
        listput(next_level, [value * power, index + 1, e]);
      );
    );
    frontier = next_level;
  );
  vecsort(Vec(out));
};

\\ Feasible epsilon interval test.  Returns [status, lower, upper].
al_epsilon_interval(f, kind) =
{
  my(lower = 0, upper = 10^6, p, a, lo, hi, q = 2, value);
  default(realprecision, 80);
  for(i = 1, matsize(f)[1],
    p = f[i, 1]; a = f[i, 2];
    if(kind == 0,
      lo = log((a + 2) / (a + 1)) / log(p); hi = log((a + 1) / a) / log(p);
    ,
      lo = log((p^(a + 2) - 1) / (p^(a + 1) - 1)) / log(p) - 1;
      hi = log((p^(a + 1) - 1) / (p^a - 1)) / log(p) - 1;
    );
    lower = max(lower, lo); upper = min(upper, hi);
  );
  while(matsize(f)[1] && setsearch(Set(f[, 1]), q), q = nextprime(q + 1));
  value = if(kind == 0, log(2) / log(q), log(q + 1) / log(q) - 1);
  lower = max(lower, value);
  if(upper - lower > 10^-30, return([1, lower, upper]));
  if(lower - upper > 10^-30, return([0, lower, upper]));
  [-1, lower, upper];
};

\\ Enumerate superior highly composite (kind 0) or colossally abundant (kind 1) numbers.
al_threshold_sequence(bound, kind, result_limit, tag) =
{
  my(exponents = Map(), value = 1, primes_used = List(), q = 2, best, best_p, threshold, count = 0, tie = 0, a, p);
  default(realprecision, 80);
  while(count < result_limit,
    best = -1; best_p = 0; tie = 0;
    for(i = 1, #primes_used + 1,
      p = if(i <= #primes_used, primes_used[i], q);
      a = if(mapisdefined(exponents, p), mapget(exponents, p), 0);
      threshold = if(kind == 0, log((a + 2) / (a + 1)) / log(p),
                     log((p^(a + 2) - 1) / (p^(a + 1) - 1)) / log(p) - 1);
      if(abs(threshold - best) < 10^-30, tie = 1);
      if(threshold > best, best = threshold; best_p = p);
    );
    if(tie, print("THRESHOLD_TIE:1"); break());
    if(value * best_p > bound, break());
    value *= best_p;
    a = if(mapisdefined(exponents, best_p), mapget(exponents, best_p), 0);
    mapput(exponents, best_p, a + 1);
    if(best_p == q, listput(primes_used, q); q = nextprime(q + 1));
    count++;
    print(tag, ":", value, "|", numdiv(value), "|", sigma(value), "|", Strprintf("%.12g", best));
  );
  count;
};

al_record_numbers(n, bound, result_limit) =
{
  if(n < 1 || bound < 1, error("Record-number analysis requires positive integers"));
  my(f = factor(n), candidates, record, hcn = List(), sa = List(), ratio, is_hcn = 0, is_sa = 0,
     shcn, ca, emitted = 0, best_ratio);
  \\ Highly composite and superabundant records among candidates <= max(n, bound).
  candidates = al_record_candidates(max(n, bound));
  record = 0; best_ratio = 0;
  for(i = 1, #candidates,
    my(c = candidates[i], dc = numdiv(c), sc = sigma(c));
    if(dc > record, record = dc; listput(hcn, [c, dc]); if(c == n, is_hcn = 1));
    ratio = sc / c;
    if(ratio > best_ratio, best_ratio = ratio; listput(sa, [c, sc]); if(c == n, is_sa = 1));
  );
  print("NUMDIV:", numdiv(n)); print("SIGMA:", sigma(n));
  print("IS_HCN:", is_hcn); print("IS_SUPERABUNDANT:", is_sa);
  shcn = al_epsilon_interval(f, 0);
  print("IS_SHCN:", shcn[1]);
  if(shcn[1] == 1, print("SHCN_EPSILON:", Strprintf("%.12g", shcn[2]), "|", Strprintf("%.12g", shcn[3])));
  ca = al_epsilon_interval(f, 1);
  print("IS_CA:", ca[1]);
  if(ca[1] == 1, print("CA_EPSILON:", Strprintf("%.12g", ca[2]), "|", Strprintf("%.12g", ca[3])));
  for(i = 1, #hcn, if(hcn[i][1] <= bound && emitted < result_limit, print("HCN:", hcn[i][1], "|", hcn[i][2]); emitted++));
  print("HCN_COUNT:", #select(v -> v[1] <= bound, Vec(hcn)));
  emitted = 0;
  for(i = 1, #sa, if(sa[i][1] <= bound && emitted < result_limit, print("SA:", sa[i][1], "|", sa[i][2]); emitted++));
  print("SA_COUNT:", #select(v -> v[1] <= bound, Vec(sa)));
  print("SHCN_COUNT:", al_threshold_sequence(bound, 0, result_limit, "SHCN"));
  print("CA_COUNT:", al_threshold_sequence(bound, 1, result_limit, "CA"));
  print("DONE:1");
};

\\ ---------------------------------------------------------------- 70
al_weird(n, subset_cap, witness_bits) =
{
  if(n < 1, error("Divisor classification requires a positive integer"));
  my(total = sigma(n), proper = total - n, divs = divisors(n), count = #divs - 1,
     reach, mask, prefixes, semiperfect = -1, witness = List(), target, store);
  print("SIGMA:", total); print("PROPER_SUM:", proper); print("ABUNDANCE:", total - 2 * n);
  print("DIVISOR_COUNT:", #divs);
  print("CLASS:", if(proper < n, -1, proper > n));
  print("ALMOST_PERFECT:", proper == n - 1); print("QUASIPERFECT:", proper == n + 1);
  print("MULTIPERFECT_K:", if(total % n == 0, total / n, 0));
  if(proper < n, semiperfect = 0);
  if(proper == n, semiperfect = 1; for(i = 1, count, listput(witness, divs[i])));
  if(semiperfect == -1 && count <= subset_cap,
    mask = 2^(n + 1) - 1;
    store = count * n <= witness_bits;
    prefixes = if(store, vector(count), 0);
    reach = 1;
    for(i = 1, count,
      if(store, prefixes[i] = reach);
      reach = bitand(bitor(reach, shift(reach, divs[i])), mask);
    );
    semiperfect = bittest(reach, n);
    if(semiperfect && store,
      target = n;
      forstep(i = count, 1, -1,
        if(target >= divs[i] && !bittest(prefixes[i], target),
          listput(witness, divs[i]); target -= divs[i];
        , if(!bittest(prefixes[i], target), error("Internal subset-sum reconstruction failed")));
        if(target == 0, break());
      );
      if(vecsum(Vec(witness)) != n, error("Internal subset-sum witness failed"));
    );
    print("WITNESS_AVAILABLE:", store);
  ,
    print("WITNESS_AVAILABLE:", semiperfect != -1);
  );
  print("SEMIPERFECT:", semiperfect);
  print("WEIRD:", if(semiperfect == -1, -1, proper > n && !semiperfect));
  for(i = 1, #witness, print("WITNESS:", witness[i]));
  print("DONE:1");
};

\\ ---------------------------------------------------------------- 71
al_sociable(start, end, max_length, term_bound, result_limit, dedupe) =
{
  if(start < 1 || end < start, error("The search range must satisfy 1 <= start <= end"));
  my(current, members, found = 0, inconclusive = 0, truncated = 0, cycle_lengths = Map(), length_value,
     status, shown = 0);
  for(n = start, end,
    current = n; members = List([n]); status = 0;
    for(step = 1, max_length,
      current = sigma(current) - current;
      if(current == n,
        if(found >= result_limit, truncated = 1; break(2));
        print("CYCLE:", step, "|", n, "|", al_join(Vec(members)));
        length_value = if(mapisdefined(cycle_lengths, step), mapget(cycle_lengths, step), 0);
        mapput(cycle_lengths, step, length_value + 1);
        found++; status = 1; break();
      );
      \\ A run that terminates at 0/1, or that is dominated by an already-scanned start,
      \\ is settled: no cycle through n survives.
      if(current == 0 || current == 1 || (dedupe && current < n), status = 2; break());
      \\ Exceeding the term bound or the iteration cap leaves the question open.
      if(current > term_bound, status = 3; break());
      listput(members, current);
    );
    if(status == 0 || status == 3,
      inconclusive++;
      if(shown < result_limit,
        print("INCONCLUSIVE:", n, "|", if(status == 3, "bound", "length"), "|", current); shown++);
    );
  );
  my(keys = vecsort(Vec(cycle_lengths)));
  for(i = 1, #keys, print("LENGTH_COUNT:", keys[i], "|", mapget(cycle_lengths, keys[i])));
  print("INCONCLUSIVE_COUNT:", inconclusive);
  print("INCONCLUSIVE_SHOWN:", shown);
  print("TRUNCATED:", truncated);
  print("DONE:", found);
};

\\ ---------------------------------------------------------------- 74
\\ Every integer pair equivalent to [x, y] under the automorphism group of x^2 + d*y^2.
\\ For d > 1 that group is {+-1}; for d = 1 the form is x^2 + y^2, whose full symmetry
\\ group (proper rotations together with the coordinate swap) also contains [y, x].
al_form_orbit(pair, d) =
{
  my(x = pair[1], y = pair[2], out = List());
  for(sx = 0, 1,
    for(sy = 0, 1,
      listput(out, [(-1)^sx * x, (-1)^sy * y]);
      if(d == 1, listput(out, [(-1)^sx * y, (-1)^sy * x]));
    );
  );
  Set(Vec(out));
};

\\ Union of the orbits of every pair in `pairs`, as an order-insensitive set.
al_form_closure(pairs, d) =
{
  my(out = List());
  for(i = 1, #pairs,
    my(orbit = al_form_orbit(pairs[i], d));
    for(j = 1, #orbit, listput(out, orbit[j]));
  );
  Set(Vec(out));
};

al_cornacchia(d, n, trace_limit) =
{
  if(d < 1 || n < 1, error("Cornacchia requires d >= 1 and n >= 1"));
  my(solutions = List(), traced = 0, root_result, roots, g2, m, a, b, r, c, y, lines = 0, all, total, ours, bound,
     native_set, trace_set);
  if(issquare(n), listput(solutions, [sqrtint(n), 0]));
  if(n % d == 0 && issquare(n / d), listput(solutions, [0, sqrtint(n / d)]));
  fordiv(n, g2,
    if(!issquare(g2), next());
    m = n / g2;
    root_result = al_all_roots_mod(x^2 + d, m, 4096);
    if(!root_result[3], print("ROOTS_COMPLETE:0"); print("DONE:0"); return());
    roots = root_result[1];
    for(i = 1, #roots,
      r = roots[i];
      if(r == 0, next());
      a = m; b = r; bound = sqrtint(m);
      if(!traced, print("TRACE:", g2, "|", r, "|0|", a, "|", b); lines++);
      while(b > bound,
        [a, b] = [b, a % b];
        if(!traced && lines < trace_limit, print("TRACE:", g2, "|", r, "|", lines, "|", a, "|", b); lines++);
      );
      c = m - b^2;
      if(c >= 0 && c % d == 0 && issquare(c / d),
        y = sqrtint(c / d);
        if(!traced, print("TRACE_RESULT:", g2, "|", r, "|", b, "|", y));
        listput(solutions, [b * sqrtint(g2), y * sqrtint(g2)]);
      , if(!traced, print("TRACE_RESULT:", g2, "|", r, "|", b, "|-1")));
      traced = 1;
    );
  );
  solutions = Set(Vec(solutions));
  for(i = 1, #solutions,
    if(solutions[i][1]^2 + d * solutions[i][2]^2 != n, error("Internal Cornacchia verification failed"));
    print("SOLUTION:", solutions[i][1], "|", solutions[i][2], "|", gcd(solutions[i][1], solutions[i][2]) == 1);
  );
  \\ Cross-check: qfbsolve enumerates every solution up to the automorphism group of the
  \\ form, and Cornacchia returns one representative per unordered pair.  Comparing the
  \\ two closed-up solution SETS is order-insensitive and independent of how many
  \\ representatives either side happens to list.
  all = qfbsolve(Qfb(1, 0, d), n, 3);
  if(type(all) != "t_VEC", all = []);
  if(#all && type(all[1]) != "t_VEC", all = [all]);
  native_set = al_form_closure(all, d);
  trace_set = al_form_closure(Vec(solutions), d);
  total = #native_set; ours = #trace_set;
  print("NATIVE_TOTAL:", total); print("TRACE_TOTAL:", ours);
  print("CROSS_CHECK:", native_set == trace_set);
  if(isprime(n),
    my(native = qfbcornacchia(d, n));
    print("QFBCORNACCHIA:", if(#native, concat(Str(native[1]), concat("|", Str(native[2]))), "none"));
  );
  print("ROOTS_COMPLETE:1");
  print("DONE:", #solutions);
};

\\ ---------------------------------------------------------------- 110-111
al_quadratic_ring(d, a, b, p, certify_seconds) =
{
  if(d == 0 || d == 1 || issquare(d), error("The radicand must be a nonsquare integer other than 0 and 1"));
  if(p < 2 || !isprime(p), error("The rational prime must be a proven prime"));
  my(core_value = core(d), D = quaddisc(d), w = quadgen(D), elt = a + b * w, N = norm(elt), T = trace(elt),
     q = quadclassunit(D), K = bnfinit(y^2 - core_value, 1), dec, certified, u, ideal, gen, alg, u_coef, v_coef, coords, symbol, prime_status);
  print("CORE:", core_value); print("DISCRIMINANT:", D);
  print("RING:", if(D % 4 == 0, 0, 1));
  print("NORM:", N); print("TRACE:", T);
  print("IS_UNIT:", abs(N) == 1);
  prime_status = 0;
  if(elt != 0 && abs(N) != 1,
    if(isprime(abs(N)), prime_status = 1);
    if(!prime_status && issquare(abs(N)) && isprime(sqrtint(abs(N))),
      my(qq = sqrtint(abs(N)));
      if(kronecker(D, qq) == -1 && a % qq == 0 && b % qq == 0, prime_status = 2);
    );
  );
  print("ELEMENT_PRIME:", prime_status);
  if(D > 0,
    u = quadunit(D);
    print("FUNDAMENTAL_UNIT:", component(u, 2), "|", component(u, 3), "|", norm(u));
    print("ROOTS_OF_UNITY:2");
  ,
    print("ROOTS_OF_UNITY:", if(D == -4, 4, if(D == -3, 6, 2)));
  );
  print("CLASS_NUMBER:", q.no);
  for(i = 1, #q.cyc, print("CLASS_CYCLE:", q.cyc[i]));
  certified = alarm(certify_seconds, bnfcertify(K));
  print("CLASS_CERTIFIED:", if(type(certified) == "t_ERROR", -1, certified == 1));
  symbol = kronecker(D, p);
  print("KRONECKER:", symbol);
  dec = idealprimedec(K, p);
  print("BEHAVIOR:", if(symbol == 0, "ramified", if(#dec == 2, "split", "inert")));
  for(i = 1, #dec,
    ideal = bnfisprincipal(K, dec[i], 3);
    \\ A trivial class group returns an empty exponent vector, so test emptiness first.
    if(#ideal[1] == 0 || vecmax(abs(ideal[1])) == 0,
      alg = lift(nfbasistoalg(K, ideal[2]));
      u_coef = polcoef(alg, 0); v_coef = polcoef(alg, 1);
      coords = if(D % 4 == 0, [u_coef, v_coef], [u_coef - v_coef, 2 * v_coef]);
      if(denominator(coords[1]) != 1 || denominator(coords[2]) != 1, error("Internal generator conversion failed"));
      if(abs(norm(coords[1] + coords[2] * w)) != p^dec[i].f, error("Internal prime-element verification failed"));
      print("PRIME_IDEAL:", i, "|", dec[i].e, "|", dec[i].f, "|", p^dec[i].f, "|1|", coords[1], "|", coords[2]);
    ,
      print("PRIME_IDEAL:", i, "|", dec[i].e, "|", dec[i].f, "|", p^dec[i].f, "|0|0|0");
    );
  );
  print("IDEAL_COUNT:", #dec);
  print("DONE:1");
};

\\ ---------------------------------------------------------------- 112-113
al_number_field(coefficients, prime_list, element_coefficients, class_seconds) =
{
  if(#coefficients < 3, error("The defining polynomial must have degree at least 2"));
  my(f = Polrev(coefficients), K, dec, elt, F, bnf, certified, inert, e_max, deg);
  if(pollead(f) != 1, error("The defining polynomial must be monic"));
  if(!polisirreducible(f), error("The defining polynomial must be irreducible over the rationals"));
  K = nfinit(f); deg = poldegree(f);
  print("DEGREE:", deg); print("DISCRIMINANT:", K.disc); print("POLYNOMIAL_DISCRIMINANT:", poldisc(f));
  print("SIGNATURE:", K.sign[1], "|", K.sign[2]); print("INDEX:", K.index);
  for(i = 1, #K.zk, print("BASIS:", i, "|", K.zk[i]));
  if(deg <= 7,
    my(G = polgalois(f)); print("GALOIS:", G[1], "|", G[2], "|", G[3]); print("GALOIS_NAME:", G[4]);
  );
  for(j = 1, #prime_list,
    my(p = prime_list[j]);
    if(!isprime(p), error("Every rational prime must be a proven prime"));
    dec = idealprimedec(K, p);
    e_max = vecmax(vector(#dec, i, dec[i].e));
    print("PRIME:", p, "|", #dec, "|", e_max, "|", kronecker(K.disc, p), "|", K.disc % p == 0,
          "|", if(K.disc % p == 0, "ramified",
                  if(#dec == 1, "inert",
                     if(#dec == deg, "totally split", "partially split"))));
    for(i = 1, #dec, print("PRIME_IDEAL:", p, "|", i, "|", dec[i].e, "|", dec[i].f, "|", p^dec[i].f));
  );
  if(#element_coefficients,
    elt = Polrev(element_coefficients);
    if(elt == 0, error("The element must be nonzero"));
    if(poldegree(elt) >= deg, error("Element coordinates must have fewer entries than the degree"));
    print("ELEMENT_NORM:", nfeltnorm(K, elt));
    F = idealfactor(K, elt);
    for(i = 1, matsize(F)[1],
      print("ELEMENT_FACTOR:", F[i, 1].p, "|", F[i, 1].e, "|", F[i, 1].f, "|", F[i, 2], "|", F[i, 1].p^F[i, 1].f);
    );
    print("ELEMENT_FACTOR_COUNT:", matsize(F)[1]);
  );
  bnf = alarm(class_seconds, bnfinit(f, 1));
  if(type(bnf) == "t_ERROR",
    print("CLASS_NUMBER:-1"); print("CLASS_CERTIFIED:-1");
  ,
    print("CLASS_NUMBER:", bnf.no);
    for(i = 1, #bnf.cyc, print("CLASS_CYCLE:", bnf.cyc[i]));
    certified = alarm(class_seconds, bnfcertify(bnf));
    print("CLASS_CERTIFIED:", if(type(certified) == "t_ERROR", -1, certified == 1));
  );
  print("DONE:1");
};

\\ ---------------------------------------------------------------- 115
\\ Cycle-length multiset of a permutation, via PARI's native permcycles.
al_cycle_type(perm) =
{
  my(cycles = permcycles(Vecsmall(perm)));
  vecsort(vector(#cycles, i, #cycles[i]), , 4);
};

al_pattern_key(lengths) = al_join(vecsort(lengths, , 4));

\\ Cycle-type class sizes of the Galois group acting on the roots.
\\ Returns [status, Map(pattern -> class size), order, name, sign].
al_galois_classes(f, group_seconds) =
{
  my(n = poldegree(f), G = polgalois(f), order = G[1], name = G[4], classes = Map(), parts, key, size, computed);
  if(name == Str("S", n) || name == Str("A", n),
    parts = partitions(n);
    for(i = 1, #parts,
      my(lambda = Vec(parts[i]), parity = sum(j = 1, #lambda, lambda[j] - 1), mult = Map(), denom = 1);
      if(name == Str("A", n) && parity % 2, next());
      for(j = 1, #lambda, denom *= lambda[j]);
      for(j = 1, #lambda,
        my(c = if(mapisdefined(mult, lambda[j]), mapget(mult, lambda[j]), 0) + 1);
        mapput(mult, lambda[j], c);
      );
      my(keys = Vec(mult)); for(j = 1, #keys, denom *= (mapget(mult, keys[j]))!);
      mapput(classes, al_pattern_key(lambda), n! / denom);
    );
    return([1, classes, order, name, G[2]]);
  );
  computed = alarm(group_seconds, al_galois_classes_split(f, order));
  if(type(computed) == "t_ERROR" || computed == 0, return([0, classes, order, name, G[2]]));
  [1, computed, order, name, G[2]];
};

al_galois_classes_split(f, order) =
{
  my(R = nfsplitting(f, , 1), L = R[1], alpha = R[2], auts, roots, images, perm, key, classes = Map(), size);
  auts = nfgaloisconj(L, 4);
  if(#auts != order, return(0));
  roots = Set(vector(#auts, i, Mod(subst(alpha, x, auts[i]), L)));
  if(#roots != poldegree(f), return(0));
  for(i = 1, #auts,
    perm = vector(#roots, j, setsearch(roots, Mod(subst(lift(roots[j]), x, auts[i]), L)));
    if(vecmin(perm) == 0, return(0));
    key = al_pattern_key(al_cycle_type(perm));
    size = if(mapisdefined(classes, key), mapget(classes, key), 0) + 1;
    mapput(classes, key, size);
  );
  classes;
};

al_chebotarev(coefficients, bound, group_seconds) =
{
  if(#coefficients < 3, error("The polynomial must have degree at least 2"));
  my(f = Polrev(coefficients), n, disc, observed = Map(), used = 0, skipped = 0, key, count, classes, keys, total_seen,
     predicted, pattern_rows = Map());
  if(pollead(f) != 1, error("The polynomial must be monic"));
  if(poldegree(f) > 7, error("Chebotarev experiments support degree at most 7"));
  if(!polisirreducible(f), error("The polynomial must be irreducible over the rationals"));
  n = poldegree(f); disc = poldisc(f);
  print("DEGREE:", n); print("DISCRIMINANT:", disc);
  classes = al_galois_classes(f, group_seconds);
  print("GROUP_ORDER:", classes[3]); print("GROUP_SIGN:", classes[5]); print("GROUP_NAME:", classes[4]);
  print("PREDICTED_AVAILABLE:", classes[1]);
  forprime(p = 2, bound,
    if(disc % p == 0, skipped++; next());
    my(F = factormod(f, p), lengths = vector(matsize(F)[1], i, poldegree(F[i, 1])));
    key = al_pattern_key(lengths);
    count = if(mapisdefined(observed, key), mapget(observed, key), 0) + 1;
    mapput(observed, key, count); used++;
  );
  keys = Set(concat(Vec(observed), if(classes[1], Vec(classes[2]), [])));
  for(i = 1, #keys,
    my(o = if(mapisdefined(observed, keys[i]), mapget(observed, keys[i]), 0),
       c = if(classes[1] && mapisdefined(classes[2], keys[i]), mapget(classes[2], keys[i]), 0));
    print("PATTERN:", keys[i], "|", o, "|", if(used, Strprintf("%.6f", 100.0 * o / used), "0"), "|",
          c, "|", if(classes[1], Strprintf("%.6f", 100.0 * c / classes[3]), "-1"));
  );
  print("PRIMES_USED:", used); print("PRIMES_SKIPPED:", skipped);
  print("DONE:", #keys);
};
