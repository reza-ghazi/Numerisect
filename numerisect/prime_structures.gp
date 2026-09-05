\\ Numerisect structural-prime engine for PARI/GP.

ps_batch_primality(values, fast) =
{
  my(status);
  for(i = 1, #values,
    status = if(values[i] < 2, -1, if(fast, ispseudoprime(values[i]), isprime(values[i])));
    print("ROW:", values[i], "|", status);
  );
  print("DONE:", #values);
};

ps_progression_primes(lo, hi, m, r, result_limit) =
{
  my(g, first, c = 0, total = 0, nx = 0);
  r = r % m; lo = max(2, lo); g = gcd(m, r);
  if(g > 1,
    if(g >= lo && g <= hi && g % m == r && isprime(g),
      print("ROW:", g); c = 1; total = g;
    );
  ,
    first = lo + (r - lo) % m;
    if(first <= hi && (hi - first) \ m + 1 > 1000000,
      error("This scan exceeds 1,000,000 progression candidates; narrow the interval")
    );
    forstep(p = first, hi, m,
      if(isprime(p),
        if(c == result_limit, nx = p; break());
        print("ROW:", p); total += p; c++;
      );
    );
  );
  print("SUM:", total); print("RESIDUE:", r); print("NEXT:", nx);
  print("DONE:", c);
};

ps_prime_modular(p, a, exponent, operation) =
{
  if(p < 2 || !isprime(p), error("Modulus must be a proven positive prime"));
  my(x = Mod(a, p), roots);
  if(operation == 0,
    if(x == 0, error("Zero has no multiplicative inverse modulo p"));
    print("ROW:", lift(1/x));
  );
  if(operation == 1,
    if(x == 0 && exponent < 0, error("Zero cannot be raised to a negative modular power"));
    print("ROW:", lift(x^exponent));
  );
  if(operation == 2,
    if(x == 0, error("Multiplicative order is undefined for zero modulo p"));
    default(factor_proven, 1);
    print("ROW:", znorder(x));
  );
  if(operation == 3,
    if(issquare(x),
      roots = Set([lift(sqrt(x)), lift(-sqrt(x))]);
      for(i = 1, #roots, print("ROW:", roots[i]));
      print("DONE:", #roots); return();
    );
    print("DONE:0"); return();
  );
  if(operation == 4,
    default(factor_proven, 1);
    print("ROW:", lift(znprimroot(p)));
  );
  print("DONE:1");
};

ps_rotations(n) =
{
  my(d = digits(n), length = #d, values = vector(length), current = d);
  for (i = 1, length,
    values[i] = fromdigits(current);
    current = concat(current[2..length], current[1]);
  );
  Vec(Set(values));
};

ps_is_absolute_prime(n) =
{
  if (!isprime(n), return(0));
  my(values = ps_rotations(n));
  for (i = 1, #values, if (!isprime(values[i]), return(0)));
  1;
};

ps_find_absolute_primes(start, finish, result_limit) =
{
  my(found = 0, next_start = 0, values);
  forprime (p = max(2, start), finish,
    if (!isprime(p), next());
    if (p >= 10,
      my(d = digits(p));
      if (setsearch(Set(d), 0) || setsearch(Set(d), 2) || setsearch(Set(d), 4) ||
          setsearch(Set(d), 5) || setsearch(Set(d), 6) || setsearch(Set(d), 8), next());
    );
    values = ps_rotations(p);
    if (p != vecmin(values), next());
    if (!vecmin(vector(#values, i, isprime(values[i]))), next());
    if (found >= result_limit, next_start = p; break());
    print("ABSOLUTE:", p, "|", values);
    found++;
  );
  print("NEXT:", next_start);
};

ps_gaussian_is_prime(a, b) =
{
  if (a == 0 && b == 0, return(0));
  if (a == 0, return(isprime(abs(b)) && abs(b) % 4 == 3));
  if (b == 0, return(isprime(abs(a)) && abs(a) % 4 == 3));
  isprime(a^2 + b^2);
};

ps_analyze_gaussian(a, b) =
{
  my(norm = a^2 + b^2, gaussian_prime = ps_gaussian_is_prime(a, b));
  print("GAUSSIAN:", gaussian_prime);
  print("NORM:", norm);
  print("NORM_PRIME:", isprime(norm));
  if ((a == 0 || b == 0) && isprime(abs(a + b)) && !gaussian_prime,
    my(p = abs(a + b), solution = qfbsolve(Qfb(1, 0, 1), p));
    if (#solution == 2,
      print("FACTOR:", abs(solution[1]), "|", abs(solution[2]));
      print("FACTOR:", abs(solution[1]), "|", -abs(solution[2]));
    );
  );
};

ps_find_gaussian_primes(bound, result_limit) =
{
  my(found = 0, truncated = 0);
  for (a = -bound, bound,
    for (b = -bound, bound,
      if (ps_gaussian_is_prime(a, b),
        if (found >= result_limit, truncated = 1; break(2));
        print("GAUSSIAN_POINT:", a, "|", b, "|", a^2 + b^2);
        found++;
      );
    );
  );
  print("TRUNCATED:", truncated);
};

ps_modular_wheel(modulus, maximum) =
{
  for (value = 0, maximum,
    print("CELL:", value, "|", value % modulus, "|", value \ modulus, "|",
          isprime(value), "|", gcd(value, modulus) == 1);
  );
};

ps_paterson_companion(p) = fromdigits(digits(p, 4), 10);

ps_is_paterson_prime(p) = isprime(p) && isprime(ps_paterson_companion(p));

ps_find_paterson_primes(start, finish, result_limit) =
{
  my(found = 0, next_start = 0, companion);
  forprime (p = max(2, start), finish,
    if (!isprime(p), next());
    companion = ps_paterson_companion(p);
    if (!isprime(companion), next());
    if (found >= result_limit, next_start = p; break());
    print("PATERSON:", p, "|", companion, "|", digits(p, 4));
    found++;
  );
  print("NEXT:", next_start);
};

ps_generate_even_perfect_numbers(requested) =
{
  my(found = 0, exponent = 2, mersenne, perfect);
  while (found < requested,
    mersenne = 2^exponent - 1;
    if (isprime(mersenne),
      perfect = 2^(exponent - 1) * mersenne;
      print("PERFECT:", exponent, "|", mersenne, "|", perfect);
      found++;
    );
    exponent = nextprime(exponent + 1);
    while (!isprime(exponent), exponent = nextprime(exponent + 1));
  );
};

ps_find_full_reptend_primes(start, finish, result_limit) =
{
  my(found = 0, next_start = 0);
  forprime (p = max(3, start), finish,
    if (p == 5 || !isprime(p), next());
    if (znorder(Mod(10, p)) != p - 1, next());
    if (found >= result_limit, next_start = p; break());
    print("REPTEND:", p, "|", p - 1);
    found++;
  );
  print("NEXT:", next_start);
};

ps_prime_insertion_pyramid(levels) =
{
  my(d = [1, 1], k = 2, i);
  for (level = 1, levels,
    print("INSERTION_LEVEL:", level, "|", if(level == 1, 2, k - 1), "|", fromdigits(d));
    if (level == levels, break());
    i = 1;
    while (i < #d,
      if (d[i] + d[i + 1] == k,
        d = concat(d[1..i], concat(digits(k), d[i + 1..#d]));
      );
      i++;
    );
    k++;
  );
};

ps_prime_multiplication_pyramid(rows) =
{
  for (i = 1, rows,
    for (j = 1, i,
      my(value = i * j);
      print("PYRAMID_CELL:", i, "|", j, "|", value, "|", isprime(value));
    );
  );
};

ps_is_carmichael(n) =
{
  if (n < 3 || isprime(n), return(0));
  my(f = factor(n));
  if (vecmax(f[, 2]) > 1, return(0));
  for (i = 1, matsize(f)[1], if ((n - 1) % (f[i, 1] - 1), return(0)));
  1;
};

ps_is_strong_pseudoprime_base(n, base) =
{
  if (n < 3 || n % 2 == 0 || gcd(n, base) != 1, return(0));
  my(s = valuation(n - 1, 2), d = (n - 1) \ 2^s, x = lift(Mod(base, n)^d));
  if (x == 1 || x == n - 1, return(1));
  for (r = 1, s - 1, x = x^2 % n; if (x == n - 1, return(1)));
  0;
};

ps_lucky_numbers(finish) =
{
  my(values = vector((finish + 1) \ 2, i, 2 * i - 1), index = 2, step, kept);
  while (index <= #values,
    step = values[index];
    if (step > #values, break());
    kept = List();
    for (position = 1, #values,
      if (position % step, listput(kept, values[position]));
    );
    values = Vec(kept);
    index++;
  );
  values;
};

ps_find_special_numbers(kind, start, finish, result_limit) =
{
  my(found = 0, next_start = 0, values, candidate, a, b, c, index);
  if (kind == "lucky_prime",
    values = ps_lucky_numbers(finish);
    for (i = 1, #values,
      candidate = values[i];
      if (candidate < max(2, start) || !isprime(candidate), next());
      if (found >= result_limit, next_start = candidate; break());
      print("SPECIAL:", candidate, "|lucky prime"); found++;
    );
    print("NEXT:", next_start); return();
  );
  if (kind == "jacobsthal_prime",
    a = 0; b = 1; index = 1;
    while (a <= finish,
      if (a >= max(2, start) && isprime(a),
        if (found >= result_limit, next_start = a; break());
        print("SPECIAL:", a, "|Jacobsthal index ", index - 1); found++;
      );
      c = b + 2 * a; a = b; b = c; index++;
    );
    print("NEXT:", next_start); return();
  );
  for (candidate = max(3, start), finish,
    my(match = 0);
    if (kind == "carmichael",
      match = ps_is_carmichael(candidate),
      if (kind == "fermat_pseudoprime_base2",
        match = !isprime(candidate) && gcd(candidate, 2) == 1 && lift(Mod(2, candidate)^(candidate - 1)) == 1,
        if (kind == "strong_pseudoprime_bases2_3",
          match = !isprime(candidate) && ps_is_strong_pseudoprime_base(candidate, 2) && ps_is_strong_pseudoprime_base(candidate, 3),
          error("unknown special-number kind")
        )
      )
    );
    if (match,
      if (found >= result_limit, next_start = candidate; break());
      print("SPECIAL:", candidate, "|", kind); found++;
    );
  );
  print("NEXT:", next_start);
};

ps_analyze_miller_rabin(n, base, preview_limit, enumerate_all) =
{
  my(s = valuation(n - 1, 2), d = (n - 1) \ 2^s, divisor = gcd(base, n));
  my(prime = isprime(n), passes = ps_is_strong_pseudoprime_base(n, base));
  print("MR_PRIME:", prime);
  print("MR_S:", s);
  print("MR_D:", d);
  print("MR_BASE:", base);
  print("MR_GCD:", divisor);
  print("MR_PASSES:", passes);
  print("MR_WITNESS:", !prime && !passes);
  if (!enumerate_all, return());
  my(witnesses = 0, passing = 0, shown_witnesses = 0, shown_passing = 0, result);
  for (candidate_base = 2, n - 2,
    result = ps_is_strong_pseudoprime_base(n, candidate_base);
    if (result,
      passing++;
      if (shown_passing < preview_limit, print("MR_PASSING_BASE:", candidate_base); shown_passing++),
      witnesses++;
      if (shown_witnesses < preview_limit, print("MR_WITNESS_BASE:", candidate_base); shown_witnesses++)
    );
  );
  print("MR_WITNESS_COUNT:", witnesses);
  print("MR_PASSING_COUNT:", passing);
  print("MR_BASE_COUNT:", max(0, n - 3));
};

ps_gap_statistics(start, finish, result_limit) =
{
  my(previous = 0, gaps = List(), truncated = 0, next_start = 0);
  forprime (p = max(2, start), finish,
    if (!isprime(p), next());
    if (previous,
      if (#gaps >= result_limit, truncated = 1; next_start = previous; break());
      listput(gaps, p - previous);
    );
    previous = p;
  );
  my(values = Vec(gaps));
  print("GAPSTAT_COUNT:", #values);
  print("GAPSTAT_TRUNCATED:", truncated);
  print("GAPSTAT_NEXT:", next_start);
  if (!#values, return());
  my(ordered = vecsort(values), total = vecsum(values), mean = total / #values, median);
  if (#ordered % 2,
    median = ordered[(#ordered + 1) \ 2],
    median = (ordered[#ordered \ 2] + ordered[#ordered \ 2 + 1]) / 2
  );
  print("GAPSTAT_MIN:", ordered[1]);
  print("GAPSTAT_MAX:", ordered[#ordered]);
  print("GAPSTAT_MEAN:", numerator(mean), "|", denominator(mean));
  print("GAPSTAT_MEDIAN:", numerator(median), "|", denominator(median));
  my(unique = Set(ordered), best_gap = 0, best_count = -1, frequency);
  for (i = 1, #unique,
    frequency = #select(x -> x == unique[i], ordered);
    print("GAPSTAT_FREQ:", unique[i], "|", frequency);
    if (frequency > best_count, best_gap = unique[i]; best_count = frequency);
  );
  print("GAPSTAT_MODE:", best_gap, "|", best_count);
};

ps_generate_primorials(requested) =
{
  my(product = 1, p = 2);
  for (index = 1, requested,
    product *= p;
    print("PRIMORIAL:", index, "|", p, "|", product);
    p = nextprime(p + 1); while (!isprime(p), p = nextprime(p + 1));
  );
};

ps_problem_prime_square_sums(bound, result_limit) =
{
  my(found = 0, truncated = 0, r_squared, r);
  forprime (p = 2, bound,
    if (!isprime(p), next());
    forprime (q = 2, p - 1,
      if (!isprime(q), next());
      r_squared = p^2 + 1 - q^2;
      if (r_squared > 0 && issquare(r_squared, &r) && r >= 2 && r < q && isprime(r),
        if (found >= result_limit, truncated = 1; break(2));
        print("PROBLEM_SQUARE_SUM:", p, "|", q, "|", r); found++;
      );
    );
  );
  print("TRUNCATED:", truncated);
};

ps_problem_quartan_primes(bound, result_limit) =
{
  my(found = 0, truncated = 0, value, a = 1, b);
  while (2 * a^4 <= bound,
    b = a;
    while ((value = a^4 + b^4) <= bound,
      if (isprime(value),
        if (found >= result_limit, truncated = 1; break(2));
        print("PROBLEM_QUARTAN:", value, "|", a, "|", b); found++;
      );
      b++;
    );
    a++;
  );
  print("TRUNCATED:", truncated);
};

ps_problem_three_prime_factors(start, finish, result_limit) =
{
  my(found = 0, truncated = 0, value, f);
  for (n = max(3, start), finish,
    value = n^2 - 1; f = factor(value);
    if (vecsum(f[, 2]) == 3,
      if (found >= result_limit, truncated = 1; break());
      print("PROBLEM_THREE_FACTORS:", n, "|", value, "|", factorback(f), "|", f); found++;
    );
  );
  print("TRUNCATED:", truncated);
};

ps_problem_sigma_square(prime_count, result_limit) =
{
  my(found = 0, truncated = 0, p, sigma, root);
  for (index = 1, prime_count,
    p = prime(index); sigma = p^4 + p^3 + p^2 + p + 1;
    if (issquare(sigma, &root),
      if (found >= result_limit, truncated = 1; break());
      print("PROBLEM_SIGMA_SQUARE:", p, "|", sigma, "|", root, "|", index); found++;
    );
  );
  print("TRUNCATED:", truncated);
};

ps_contiguous_digit_primes(n) =
{
  my(d = digits(abs(n)), values = Set(), candidate);
  for (i = 1, #d,
    for (j = i, #d,
      candidate = fromdigits(d[i..j]);
      if (isprime(candidate), values = setunion(values, Set([candidate])));
    );
  );
  for (i = 1, #values, print("DIGIT_PRIME:", values[i]));
};

ps_random_primes_in_range(start, finish, requested) =
{
  my(values = Set(), attempts = 0, p, maximum_attempts = max(10000, requested * 5000));
  while (#values < requested && attempts < maximum_attempts,
    p = randomprime([max(2, start), finish]);
    if (isprime(p), values = setunion(values, Set([p])));
    attempts++;
  );
  for (i = 1, #values, print("RANDOM_PRIME:", values[i]));
  print("FOUND:", #values);
};

ps_goldbach_partitions(n, result_limit) =
{
  my(found = 0, truncated = 0, q);
  forprime (p = 2, n \ 2,
    if (!isprime(p), next()); q = n - p;
    if (isprime(q),
      if (found >= result_limit, truncated = 1; break());
      print("GOLDBACH:", p, "|", q); found++;
    );
  );
  print("TRUNCATED:", truncated);
};

ps_carmichael_lambda_from_factor(f) =
{
  my(value = 1, component, p, exponent);
  for (i = 1, matsize(f)[1],
    p = f[i, 1]; exponent = f[i, 2];
    component = if(p == 2 && exponent >= 3, 2^(exponent - 2), (p - 1) * p^(exponent - 1));
    value = lcm(value, component);
  );
  value;
};

ps_integer_profile(n, divisor_limit) =
{
  my(value = abs(n), f, omega, bigomega, radical = 1, divisor_count,
     divisor_sum, aliquot_sum, classification, shown = 0);
  if (value < 1, error("integer profile requires a nonzero integer"));
  f = factor(value); omega = matsize(f)[1];
  bigomega = if(omega, vecsum(f[, 2]), 0);
  for (i = 1, omega, radical *= f[i, 1]; print("PROFILE_FACTOR:", f[i, 1], "|", f[i, 2]));
  divisor_count = numdiv(value); divisor_sum = sigma(value); aliquot_sum = divisor_sum - value;
  classification = if(value == 1, "unit", if(aliquot_sum == value, "perfect", if(aliquot_sum > value, "abundant", "deficient")));
  print("PROFILE_NUMBER:", n);
  print("PROFILE_ABSOLUTE:", value);
  print("PROFILE_PRIME:", isprime(value));
  print("PROFILE_SEMIPRIME:", bigomega == 2);
  print("PROFILE_OMEGA:", omega);
  print("PROFILE_BIGOMEGA:", bigomega);
  print("PROFILE_TAU:", divisor_count);
  print("PROFILE_SIGMA:", divisor_sum);
  print("PROFILE_ALIQUOT:", aliquot_sum);
  print("PROFILE_PHI:", eulerphi(value));
  print("PROFILE_LAMBDA:", ps_carmichael_lambda_from_factor(f));
  print("PROFILE_MOBIUS:", moebius(value));
  print("PROFILE_RADICAL:", radical);
  print("PROFILE_CLASS:", classification);
  fordiv (value, d,
    if (shown >= divisor_limit, break());
    print("PROFILE_DIVISOR:", d); shown++;
  );
  print("PROFILE_DIVISORS_SHOWN:", shown);
};

ps_coprime_profile(modulus, start, requested, residue_limit) =
{
  my(m = abs(modulus), candidate = start + 1, found = 0, shown = 0);
  if (m < 2, error("coprime modulus must be at least 2"));
  print("COPRIME_PHI:", eulerphi(m));
  while (found < requested,
    if (gcd(candidate, m) == 1, print("COPRIME_AFTER:", candidate); found++);
    candidate++;
  );
  for (residue = 1, m - 1,
    if (shown >= residue_limit, break());
    if (gcd(residue, m) == 1, print("COPRIME_RESIDUE:", residue); shown++);
  );
  print("COPRIME_RESIDUES_SHOWN:", shown);
};

ps_prime_distribution(start, finish, bin_count, modulus) =
{
  my(width = finish - start + 1, bins = vector(bin_count), residues = vector(modulus),
     count = 0, previous = 0, twin_count = 0, maximum_gap = 0, maximum_gap_at = 0,
     index, gap, lower, upper);
  forprime (p = max(2, start), finish,
    index = min(bin_count, ((p - start) * bin_count) \ width + 1);
    bins[index]++; residues[p % modulus + 1]++; count++;
    if (previous,
      gap = p - previous;
      if (gap == 2, twin_count++);
      if (gap > maximum_gap, maximum_gap = gap; maximum_gap_at = previous);
    );
    previous = p;
  );
  print("DISTRIBUTION_COUNT:", count);
  print("DISTRIBUTION_TWINS:", twin_count);
  print("DISTRIBUTION_MAX_GAP:", maximum_gap);
  print("DISTRIBUTION_MAX_GAP_AT:", maximum_gap_at);
  for (i = 1, bin_count,
    lower = start + ((i - 1) * width) \ bin_count;
    upper = start + (i * width) \ bin_count - 1;
    if (i == bin_count, upper = finish);
    print("DISTRIBUTION_BIN:", lower, "|", upper, "|", bins[i]);
  );
  for (i = 1, modulus, print("DISTRIBUTION_RESIDUE:", i - 1, "|", residues[i]));
};

ps_factor_count_distribution(start, finish) =
{
  my(maximum = logint(max(2, finish), 2) + 1, distinct = vector(maximum + 1),
     multiplicity = vector(maximum + 1), f, omega, bigomega);
  for (n = start, finish,
    f = factor(n); omega = matsize(f)[1]; bigomega = if(omega, vecsum(f[, 2]), 0);
    distinct[omega + 1]++; multiplicity[bigomega + 1]++;
  );
  print("FACTOR_DISTRIBUTION_TOTAL:", finish - start + 1);
  for (i = 1, maximum + 1,
    if (distinct[i] || multiplicity[i],
      print("FACTOR_DISTRIBUTION:", i - 1, "|", distinct[i], "|", multiplicity[i]);
    );
  );
};

ps_dc_allowed = [];
ps_dc_limit = 0;
ps_dc_candidate_limit = 0;
ps_dc_found = 0;
ps_dc_candidates = 0;
ps_dc_stopped = 0;

ps_digit_prime_walk(prefix, remaining) =
{
  if (ps_dc_stopped, return());
  if (remaining == 0,
    ps_dc_candidates++;
    if (ps_dc_candidates > ps_dc_candidate_limit, ps_dc_stopped = 2; return());
    if (isprime(prefix),
      if (ps_dc_found >= ps_dc_limit, ps_dc_stopped = 1; return());
      print("CONSTRAINED_PRIME:", prefix); ps_dc_found++;
    );
    return();
  );
  for (i = 1, #ps_dc_allowed,
    ps_digit_prime_walk(prefix * 10 + ps_dc_allowed[i], remaining - 1);
    if (ps_dc_stopped, break());
  );
};

ps_digit_constrained_primes(allowed, minimum_digits, maximum_digits, result_limit, candidate_limit) =
{
  ps_dc_allowed = allowed; ps_dc_limit = result_limit; ps_dc_candidate_limit = candidate_limit;
  ps_dc_found = 0; ps_dc_candidates = 0; ps_dc_stopped = 0;
  for (length = minimum_digits, maximum_digits,
    for (i = 1, #allowed,
      if (allowed[i] == 0, next());
      ps_digit_prime_walk(allowed[i], length - 1);
      if (ps_dc_stopped, break(2));
    );
  );
  print("CONSTRAINED_CANDIDATES:", ps_dc_candidates);
  print("CONSTRAINED_TRUNCATED:", ps_dc_stopped == 1);
  print("CONSTRAINED_CANDIDATE_LIMITED:", ps_dc_stopped == 2);
};

ps_prime_polynomial(k, start, finish, result_limit, obstruction_bound) =
{
  my(total = 0, emitted = 0, current_run = 0, longest_run = 0,
     longest_start = 0, run_start = 0, value, roots);
  for (n = start, finish,
    value = n^2 - n + k;
    if (isprime(value),
      total++;
      if (!current_run, run_start = n);
      current_run++;
      if (current_run > longest_run, longest_run = current_run; longest_start = run_start);
      if (emitted < result_limit, print("POLYNOMIAL_PRIME:", n, "|", value); emitted++),
      current_run = 0
    );
  );
  print("POLYNOMIAL_TOTAL:", total);
  print("POLYNOMIAL_TRUNCATED:", total > emitted);
  print("POLYNOMIAL_LONGEST:", longest_run);
  print("POLYNOMIAL_LONGEST_START:", longest_start);
  forprime (q = 2, obstruction_bound,
    roots = List();
    for (r = 0, q - 1, if ((r^2 - r + k) % q == 0, listput(roots, r)));
    if (#roots, print("POLYNOMIAL_ROOTS:", q, "|", Vec(roots)));
  );
};

ps_palindrome_derived_primes(start, finish, result_limit) =
{
  my(total = 0, emitted = 0, reversed, value);
  for (n = max(1, start), finish,
    reversed = fromdigits(Vecrev(digits(n)));
    value = abs(n - reversed) + 1;
    if (isprime(value),
      total++;
      if (emitted < result_limit,
        print("PALINDROME_DERIVED:", n, "|", reversed, "|", value); emitted++
      );
    );
  );
  print("PALINDROME_TOTAL:", total);
  print("PALINDROME_TRUNCATED:", total > emitted);
};

ps_prime_indicator_constant(decimal_digits) =
{
  my(terms = 4 * (decimal_digits + 10), numerator = 0, denominator,
     lower_text, upper_text, old_precision = default(realprecision));
  default(realprecision, decimal_digits + 20);
  for (n = 1, terms, numerator = 2 * numerator + isprime(n));
  denominator = 2^terms;
  lower_text = Strprintf("%.*f", decimal_digits, numerator / denominator * 1.0);
  upper_text = Strprintf("%.*f", decimal_digits, (numerator + 1) / denominator * 1.0);
  while (lower_text != upper_text,
    for (n = terms + 1, terms + 100,
      numerator = 2 * numerator + isprime(n);
    );
    terms += 100; denominator = 2^terms;
    lower_text = Strprintf("%.*f", decimal_digits, numerator / denominator * 1.0);
    upper_text = Strprintf("%.*f", decimal_digits, (numerator + 1) / denominator * 1.0);
  );
  print("PRIME_CONSTANT:", lower_text);
  print("PRIME_CONSTANT_TERMS:", terms);
  print("PRIME_CONSTANT_ERROR_POWER:", terms);
  default(realprecision, old_precision);
};
