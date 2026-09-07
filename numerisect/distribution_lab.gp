\\ Numerisect analytic prime-distribution engine for PARI/GP.
\\
\\ Every mathematical quantity produced by this file comes from a PARI library
\\ routine: primepi, forprime, eint1 (logarithmic integral), intnum (singular
\\ series and Bateman-Horn integrals), polisirreducible, polrootsmod, poldegree,
\\ gcd, log, exp and Euler.  Exact pi(x), the exact n-th prime and k-tuplet
\\ counts arrive from the primecount and primesieve engines, which Python
\\ launches separately and passes in as already-computed integers.  Python and
\\ JavaScript never evaluate any of these quantities.
\\
\\ Protocol: TAG:value or TAG:a|b|c lines, always closed by DONE:<count>.

\\ ---------------------------------------------------------------------------
\\ Published first-occurrence (maximal) prime gaps, OEIS A005250 (gap) paired
\\ with A002386 (the prime that starts the gap).  Source: Thomas R. Nicely,
\\ "First occurrence prime gaps", and the OEIS b-files for A002386/A005250.
\\ The table covers every maximal gap through 4.3 * 10^9, comfortably beyond
\\ the 10^9 verification target.
\\ ---------------------------------------------------------------------------
{
DL_MAXIMAL_GAP_TABLE = [
  [1, 2], [2, 3], [4, 7], [6, 23], [8, 89], [14, 113], [18, 523], [20, 887],
  [22, 1129], [34, 1327], [36, 9551], [44, 15683], [52, 19609], [72, 31397],
  [86, 155921], [96, 360653], [112, 370261], [114, 492113], [118, 1349533],
  [132, 1357201], [148, 2010733], [154, 4652353], [180, 17051707],
  [210, 20831323], [220, 47326693], [222, 122164747], [234, 189695659],
  [248, 191912783], [250, 387096133], [282, 436273009], [288, 1294268491],
  [292, 1453168141], [320, 2300942549], [336, 3842610773], [354, 4302407359]
];
}

dl_number(value, digits) =
{
  if(value == 0, return("0"));
  strjoin(strsplit(Strprintf(Strprintf("%%.%dg", digits), value), " "), "")
};

\\ li(x) = principal value of the integral of 1/log t from 0 to x, evaluated
\\ through PARI's exponential-integral routine eint1.
dl_li(x) = real(-eint1(-log(x * 1.0)));

dl_sign(value) = if(value > 0, 1, if(value < 0, -1, 0));

\\ ---------------------------------------------------------------------------
\\ Shared log-spaced integer grid (roadmap items 76, 81, 82).
\\ ---------------------------------------------------------------------------
dl_grid(exponent_from, exponent_to, points) =
{
  if(points < 2 || points > 64, error("A grid needs between 2 and 64 points"));
  if(exponent_from < 1 || exponent_to <= exponent_from,
     error("Grid exponents must satisfy 1 <= from < to"));
  my(old = default(realprecision), value, previous = 0, emitted = 0);
  default(realprecision, 80);
  for(i = 0, points - 1,
    value = round(10^(exponent_from + (exponent_to - exponent_from) * i / (points - 1)));
    if(value > previous, print("GRID:", value); previous = value; emitted++);
  );
  default(realprecision, old);
  print("DONE:", emitted);
};

\\ ---------------------------------------------------------------------------
\\ Item 76: absolute and relative approximation error of x/log x, li(x) and
\\ R(x) against exact pi(x).  exact_counts come from primecount, riemann_r
\\ comes from "primecount --RiemannR"; li(x) and every error term are PARI.
\\ ---------------------------------------------------------------------------
dl_approximation_error(xs, exact_counts, riemann_r) =
{
  if(#xs < 1 || #xs != #exact_counts || #xs != #riemann_r,
     error("Approximation grids must be nonempty and of equal length"));
  my(old = default(realprecision), x, exact, elementary, logint, riemann);
  default(realprecision, 60);
  for(i = 1, #xs,
    x = xs[i]; exact = exact_counts[i]; riemann = riemann_r[i];
    if(x < 3, error("The approximation grid requires x at least 3"));
    if(exact < 1, error("Exact pi(x) must be positive on the grid"));
    elementary = x / log(x * 1.0);
    logint = dl_li(x);
    print("ROW:", x, "|", exact,
          "|", dl_number(elementary, 20), "|", dl_number(logint, 20), "|", riemann,
          "|", dl_number(elementary - exact, 20),
          "|", dl_number(logint - exact, 20),
          "|", dl_number(riemann - exact, 20),
          "|", dl_number((elementary - exact) / exact * 100, 12),
          "|", dl_number((logint - exact) / exact * 100, 12),
          "|", dl_number((riemann - exact) / exact * 100, 12));
  );
  default(realprecision, old);
  print("DONE:", #xs);
};

\\ ---------------------------------------------------------------------------
\\ Item 82: prime-number-theorem convergence laboratory.
\\ ---------------------------------------------------------------------------
dl_pnt_convergence(xs, exact_counts) =
{
  if(#xs < 1 || #xs != #exact_counts,
     error("Convergence grids must be nonempty and of equal length"));
  my(old = default(realprecision), x, exact, elementary, logint, difference,
     normalized, sign_now, sign_previous = 0, changes = 0);
  default(realprecision, 60);
  for(i = 1, #xs,
    x = xs[i]; exact = exact_counts[i];
    if(x < 3, error("The convergence grid requires x at least 3"));
    if(exact < 1, error("Exact pi(x) must be positive on the grid"));
    elementary = x / log(x * 1.0);
    logint = dl_li(x);
    difference = exact - logint;
    normalized = difference * log(x * 1.0) / sqrt(x * 1.0);
    sign_now = dl_sign(difference);
    if(sign_previous != 0 && sign_now != 0 && sign_now != sign_previous,
       changes++;
       print("SIGNCHANGE:", x, "|", sign_previous, "|", sign_now));
    if(sign_now != 0, sign_previous = sign_now);
    print("ROW:", x, "|", exact,
          "|", dl_number(exact / elementary, 16),
          "|", dl_number(exact / logint, 16),
          "|", dl_number(difference, 20),
          "|", dl_number(normalized, 16),
          "|", sign_now);
  );
  print("SIGN_CHANGES:", changes);
  default(realprecision, old);
  print("DONE:", #xs);
};

\\ ---------------------------------------------------------------------------
\\ Item 81: explicit n-th prime bounds evaluated at high precision and checked
\\ against the exact p_n supplied by primecount.  Each bound carries its own
\\ published validity range; outside that range the bound is reported as
\\ inapplicable rather than as a failure.
\\ ---------------------------------------------------------------------------
dl_nth_prime_bounds(indices, exact_primes) =
{
  if(#indices < 1 || #indices != #exact_primes,
     error("Index grids must be nonempty and of equal length"));
  my(old = default(realprecision), n, p, ln, lln, value, side, valid, holds,
     names, sides, emitted = 0);
  default(realprecision, 60);
  names = ["Rosser 1939 - n*log n",
           "Rosser-Schoenfeld 1962 (3.12) - n*(log n + log log n - 3/2)",
           "Rosser-Schoenfeld 1962 (3.13) - n*(log n + log log n - 1/2)",
           "Dusart 1999 Thm 3 - n*(log n + log log n - 1)",
           "Dusart 2010 Prop 5.15 lower - n*(log n + log log n - 1 + (log log n - 2.1)/log n)",
           "Dusart 2010 Prop 5.15 upper - n*(log n + log log n - 1 + (log log n - 2)/log n)"];
  sides = [-1, -1, 1, -1, -1, 1];
  for(i = 1, #indices,
    n = indices[i]; p = exact_primes[i];
    if(n < 1, error("Prime indices must be positive"));
    if(p < 2, error("The exact n-th prime must be at least 2"));
    ln = log(n * 1.0);
    lln = if(n >= 3, log(ln), 0);
    for(b = 1, 6,
      valid = 0;
      if(b == 1, value = n * ln; valid = (n >= 1));
      if(b == 2, value = n * (ln + lln - 3/2); valid = (n >= 2));
      if(b == 3, value = n * (ln + lln - 1/2); valid = (n >= 20));
      if(b == 4, value = n * (ln + lln - 1); valid = (n >= 2));
      if(b == 5, value = n * (ln + lln - 1 + (lln - 2.1) / ln); valid = (n >= 3));
      if(b == 6, value = n * (ln + lln - 1 + (lln - 2) / ln); valid = (n >= 688383));
      side = sides[b];
      holds = if(side < 0, value <= p, value >= p);
      print("BOUND:", n, "|", p, "|", b, "|", names[b], "|", dl_number(value, 20),
            "|", side, "|", if(valid, 1, 0), "|", if(holds, 1, 0),
            "|", dl_number(value - p, 20));
      emitted++;
    );
  );
  default(realprecision, old);
  print("DONE:", emitted);
};

\\ ---------------------------------------------------------------------------
\\ Item 83: prime races and Chebyshev bias.  PARI's forprime iterator drives a
\\ single pass; counts, leaders, lead changes and normalized biases are exact
\\ integer counts plus PARI real arithmetic.
\\ ---------------------------------------------------------------------------
dl_prime_race(q, xmax, checkpoints) =
{
  if(q < 3 || q > 5040, error("The race modulus must satisfy 3 <= q <= 5040"));
  if(xmax < 10, error("The race endpoint must be at least 10"));
  if(checkpoints < 1 || checkpoints > 64, error("Use between 1 and 64 checkpoints"));
  my(old = default(realprecision), classes = List(), position = vector(q), counts,
     stops = List(), value, previous = 0, cursor = 1, total = 0, leader, best,
     ties, changes = 0, previous_leader = -1, emitted = 0, logint, mean, k);
  default(realprecision, 60);
  for(a = 0, q - 1, if(gcd(a, q) == 1, listput(classes, a); position[a + 1] = #classes));
  k = #classes;
  if(k > 64, error("The race modulus must have at most 64 reduced residue classes"));
  counts = vector(k);
  for(j = 1, checkpoints,
    value = round((xmax * 1.0)^(j / checkpoints));
    if(value > previous && value >= 2, listput(stops, value); previous = value);
  );
  if(#stops == 0 || stops[#stops] != xmax, listput(stops, xmax));
  forprime(p = 2, xmax,
    while(cursor <= #stops && p > stops[cursor],
      logint = dl_li(stops[cursor]);
      mean = logint / k;
      best = -1; leader = -1; ties = 0;
      for(c = 1, k,
        if(counts[c] > best, best = counts[c]; leader = classes[c]; ties = 1,
           if(counts[c] == best, ties++));
      );
      if(ties > 1, leader = -1);
      if(previous_leader >= 0 && leader >= 0 && leader != previous_leader, changes++);
      if(leader >= 0, previous_leader = leader);
      for(c = 1, k,
        print("RACE:", stops[cursor], "|", classes[c], "|", counts[c], "|",
              dl_number((counts[c] - mean) * log(stops[cursor] * 1.0) / sqrt(stops[cursor] * 1.0), 12));
        emitted++;
      );
      print("LEAD:", stops[cursor], "|", leader, "|", best, "|", total);
      cursor++;
    );
    if(q % p != 0, counts[position[p % q + 1]]++; total++);
  );
  while(cursor <= #stops,
    logint = dl_li(stops[cursor]);
    mean = logint / k;
    best = -1; leader = -1; ties = 0;
    for(c = 1, k,
      if(counts[c] > best, best = counts[c]; leader = classes[c]; ties = 1,
         if(counts[c] == best, ties++));
    );
    if(ties > 1, leader = -1);
    if(previous_leader >= 0 && leader >= 0 && leader != previous_leader, changes++);
    if(leader >= 0, previous_leader = leader);
    for(c = 1, k,
      print("RACE:", stops[cursor], "|", classes[c], "|", counts[c], "|",
            dl_number((counts[c] - mean) * log(stops[cursor] * 1.0) / sqrt(stops[cursor] * 1.0), 12));
      emitted++;
    );
    print("LEAD:", stops[cursor], "|", leader, "|", best, "|", total);
    cursor++;
  );
  print("CLASSES:", k);
  print("CHECKPOINTS:", #stops);
  print("LEAD_CHANGES:", changes);
  print("RACE_TOTAL:", total);
  default(realprecision, old);
  print("DONE:", emitted);
};

\\ ---------------------------------------------------------------------------
\\ Item 84: primes in arithmetic progressions, observed pi(x;q,a) against the
\\ expected li(x)/phi(q).
\\ ---------------------------------------------------------------------------
dl_progression_deviation(q, x) =
{
  if(q < 2 || q > 5040, error("The progression modulus must satisfy 2 <= q <= 5040"));
  if(x < 10, error("The progression endpoint must be at least 10"));
  my(old = default(realprecision), classes = List(), position = vector(q), counts,
     k, total = 0, expected, logint, deviation, worst = 0, worst_class = -1,
     excluded = 0);
  default(realprecision, 60);
  for(a = 0, q - 1, if(gcd(a, q) == 1, listput(classes, a); position[a + 1] = #classes));
  k = #classes;
  if(k > 128, error("The progression modulus must have at most 128 reduced residue classes"));
  counts = vector(k);
  forprime(p = 2, x,
    if(q % p == 0, excluded++, counts[position[p % q + 1]]++; total++);
  );
  logint = dl_li(x);
  expected = logint / k;
  for(c = 1, k,
    deviation = counts[c] - expected;
    if(abs(deviation) > worst, worst = abs(deviation); worst_class = classes[c]);
    print("PROG:", classes[c], "|", counts[c], "|", dl_number(expected, 16),
          "|", dl_number(deviation, 16),
          "|", dl_number(deviation / expected * 100, 12),
          "|", dl_number(deviation * log(x * 1.0) / sqrt(x * 1.0), 12));
  );
  print("PROG_CLASSES:", k);
  print("PROG_TOTAL:", total);
  print("PROG_EXCLUDED:", excluded);
  print("PROG_LI:", dl_number(logint, 20));
  print("PROG_EXPECTED:", dl_number(expected, 20));
  print("PROG_WORST:", worst_class);
  print("PROG_WORST_DEVIATION:", dl_number(worst, 16));
  default(realprecision, old);
  print("DONE:", k);
};

\\ ---------------------------------------------------------------------------
\\ Items 85 and 86: Hardy-Littlewood k-tuple singular series, admissibility,
\\ rigorous truncation bound, and predicted versus observed constellations.
\\
\\ Tail bound.  For every prime p greater than the largest offset the pattern
\\ occupies k distinct residues, so the local factor is
\\   (1 - k/p) / (1 - 1/p)^k = exp(-sum_{m>=2} (k^m - k)/(m p^m)),
\\ whose logarithm is bounded in absolute value by (k/p)^2 whenever k/p <= 1/2.
\\ Summing over p > P and using sum_{n>P} 1/n^2 < 1/P gives
\\   |log(tail)| < k^2 / P,
\\ so the truncated product is correct to the relative bound exp(k^2/P) - 1.
\\ ---------------------------------------------------------------------------
dl_singular_series(offsets, cutoff) =
{
  my(k = #offsets, admissible = 1, product = 1.0, residues, w, span, bound);
  if(k < 2 || k > 32, error("A prime constellation needs between 2 and 32 offsets"));
  if(offsets[1] != 0, error("Constellation offsets must start at 0"));
  span = offsets[k];
  if(cutoff < 2 * k || cutoff > 100000000,
     error("The singular-series cutoff must lie between 2k and 10^8"));
  for(i = 2, k,
    if(offsets[i] <= offsets[i - 1], error("Constellation offsets must strictly increase"));
  );
  forprime(p = 2, cutoff,
    residues = Set(vector(k, i, offsets[i] % p));
    w = #residues;
    if(w >= p,
      admissible = 0;
      print("OBSTRUCTION:", p, "|", w);
    );
    product *= (1 - w / p) / (1 - 1 / p)^k;
  );
  bound = exp((k * k * 1.0) / cutoff) - 1;
  print("TUPLE_SIZE:", k);
  print("TUPLE_SPAN:", span);
  print("ADMISSIBLE:", if(admissible, 1, 0));
  print("SINGULAR_SERIES:", dl_number(product, 16));
  print("SINGULAR_CUTOFF:", cutoff);
  print("SINGULAR_TAIL_BOUND:", dl_number(bound, 8));
  print("SINGULAR_LOW:", dl_number(product * exp(-(k * k * 1.0) / cutoff), 16));
  print("SINGULAR_HIGH:", dl_number(product * exp((k * k * 1.0) / cutoff), 16));
  product
};

dl_singular_series_report(offsets, cutoff) =
{
  my(old = default(realprecision));
  default(realprecision, 40);
  dl_singular_series(offsets, cutoff);
  default(realprecision, old);
  print("DONE:1");
};

\\ Sliding-window constellation count driven entirely by PARI's forprime
\\ iterator: no primality test is repeated, each prime is visited once.  A
\\ constellation is counted when the whole pattern lies inside [start, end],
\\ which is exactly the convention primesieve's --count=k uses.
dl_tuple_scan(offsets, start, end) =
{
  my(k = #offsets, span = offsets[k], modulus, slot, count = 0, q, target, ok);
  modulus = span + 1;
  slot = vector(modulus);
  forprime(p = max(2, start), end,
    slot[1 + (p % modulus)] = p;
    q = p - span;
    if(q >= start && q >= 2 && slot[1 + (q % modulus)] == q,
      ok = 1;
      for(i = 2, k,
        target = q + offsets[i];
        if(slot[1 + (target % modulus)] != target, ok = 0; break);
      );
      if(ok, count++);
    );
  );
  count
};

\\ observed < 0 asks PARI to count the constellations; otherwise the count was
\\ produced by primesieve and is only compared here.
dl_tuple_prediction(offsets, start, end, cutoff, observed) =
{
  my(old = default(realprecision), k = #offsets, series, integral, predicted,
     seen, ratio);
  default(realprecision, 40);
  if(start < 2, error("The constellation range must start at 2 or above"));
  if(end <= start, error("The constellation range must be nonempty"));
  series = dl_singular_series(offsets, cutoff);
  integral = intnum(t = start, end, 1 / log(t)^k);
  predicted = series * integral;
  seen = if(observed < 0, dl_tuple_scan(offsets, start, end), observed);
  print("TUPLE_START:", start);
  print("TUPLE_END:", end);
  print("TUPLE_INTEGRAL:", dl_number(integral, 16));
  print("TUPLE_PREDICTED:", dl_number(predicted, 16));
  print("TUPLE_OBSERVED:", seen);
  print("TUPLE_COUNTED_BY:", if(observed < 0, 1, 0));
  ratio = if(predicted == 0, 0, seen / predicted);
  print("TUPLE_RATIO:", dl_number(ratio, 12));
  print("TUPLE_DIFFERENCE:", dl_number(seen - predicted, 16));
  default(realprecision, old);
  print("DONE:1");
};

\\ ---------------------------------------------------------------------------
\\ Item 87: Bateman-Horn predictions.  polisirreducible decides irreducibility,
\\ polrootsmod supplies omega(p) = #{n mod p : F(n) = 0}, intnum evaluates the
\\ predicted count and forprime/isprime supply the observed count.
\\
\\ The Bateman-Horn constant has no elementary tail bound: the local factors
\\ average to 1 only through equidistribution, so the truncated product is an
\\ ESTIMATE and is labelled as one.
\\ ---------------------------------------------------------------------------
dl_bateman_horn(polynomials, start, end, cutoff) =
{
  my(old = default(realprecision), k = #polynomials, polys = vector(#polynomials),
     product = 1.0, degrees = 1, total_degree = 0, omega, constant, integral,
     predicted, observed = 0, ok, value, reduced, combined, first = 0, last = 0,
     count = 0);
  default(realprecision, 40);
  if(k < 1 || k > 8, error("Supply between 1 and 8 polynomials"));
  if(end <= start, error("The Bateman-Horn range must be nonempty"));
  if(end - start > 1000000, error("The Bateman-Horn range may span at most 10^6 integers"));
  if(cutoff < 3 || cutoff > 1000000, error("The Bateman-Horn cutoff must lie between 3 and 10^6"));
  for(i = 1, k,
    polys[i] = Polrev(polynomials[i]);
    if(poldegree(polys[i]) < 1, error("Every Bateman-Horn polynomial must have degree at least 1"));
    if(polcoeff(polys[i], poldegree(polys[i])) <= 0,
       error("Every Bateman-Horn polynomial needs a positive leading coefficient"));
    if(!polisirreducible(polys[i]),
       print("REDUCIBLE:", i, "|", polys[i]);
       error("Every Bateman-Horn polynomial must be irreducible over Q"));
    print("POLYNOMIAL:", i, "|", polys[i], "|", poldegree(polys[i]));
    degrees *= poldegree(polys[i]);
    total_degree += poldegree(polys[i]);
  );
  combined = 1;
  for(i = 1, k, combined = combined * polys[i]);
  forprime(p = 2, cutoff,
    reduced = combined * Mod(1, p);
    omega = if(reduced == 0, p, #polrootsmod(lift(reduced), p));
    if(omega >= p, print("FIXED_DIVISOR:", p, "|", omega));
    product *= (1 - omega / p) / (1 - 1 / p)^k;
  );
  constant = product / degrees;
  integral = intnum(t = max(start, 2), end, 1 / log(t)^k);
  predicted = constant * integral;
  for(n = start, end,
    ok = 1;
    for(i = 1, k,
      value = subst(polys[i], 'x, n);
      if(value < 2 || !isprime(value), ok = 0; break);
    );
    if(ok,
      observed++;
      if(first == 0, first = n);
      last = n;
      if(count < 200, print("HIT:", n); count++);
    );
  );
  print("BH_POLYNOMIALS:", k);
  print("BH_DEGREE_PRODUCT:", degrees);
  print("BH_TOTAL_DEGREE:", total_degree);
  print("BH_CUTOFF:", cutoff);
  print("BH_PRODUCT:", dl_number(product, 12));
  print("BH_CONSTANT:", dl_number(constant, 12));
  print("BH_INTEGRAL:", dl_number(integral, 12));
  print("BH_PREDICTED:", dl_number(predicted, 12));
  print("BH_OBSERVED:", observed);
  print("BH_RATIO:", dl_number(if(predicted == 0, 0, observed / predicted), 10));
  print("BH_FIRST:", first);
  print("BH_LAST:", last);
  print("BH_SHOWN:", count);
  default(realprecision, old);
  print("DONE:1");
};

\\ ---------------------------------------------------------------------------
\\ Items 88, 89, 90 and 91: bounded record prime-gap search with merit,
\\ normalized merit, published-table verification and conjectural comparisons.
\\
\\ Cramer (1936): limsup g_n / log^2 p_n = 1.
\\ Granville (1995): the Cramer-Shanks-Granville ratio should exceed
\\   2*exp(-Euler) = 1.1229..., so g / (2 e^-gamma log^2 p) is reported.
\\ Firoozbakht: p_{n+1}^(1/(n+1)) < p_n^(1/n) implies, by Kourbatov (2015),
\\   g_n < log^2 p_n - log p_n - 1 for every p_n > 29.
\\ ---------------------------------------------------------------------------
dl_maximal_gaps(start, end, baseline, prime_cap) =
{
  if(start < 2, error("The gap search must start at 2 or above"));
  if(end <= start, error("The gap search range must be nonempty"));
  if(prime_cap < 100 || prime_cap > 10000000000,
     error("The scan cap must lie between 100 and 10^10 primes"));
  if(baseline < 0, error("The record baseline must be nonnegative"));
  my(old = default(realprecision), previous = 0, record = baseline, scanned = 0,
     truncated = 0, next_start = 0, records = List(), gap, markers = 0,
     step, lp, merit, cramer, granville, firoozbakht, verdict, found, entry,
     published, status, checks = 0, agreements = 0, mismatches = 0, last_prime = 0,
     applicable);
  default(realprecision, 60);
  step = max(100000, prime_cap \ 32);
  forprime(p = start, end,
    if(previous,
      gap = p - previous;
      if(gap > record,
        record = gap;
        listput(records, [previous, p, gap]);
      );
    );
    previous = p;
    last_prime = p;
    scanned++;
    if(scanned % step == 0 && markers < 64,
      print("PROGRESS:", p, "|", scanned);
      markers++;
    );
    if(scanned >= prime_cap,
      truncated = 1;
      next_start = p;
      break;
    );
  );
  for(i = 1, #records,
    entry = records[i];
    lp = log(entry[1] * 1.0);
    merit = entry[3] / lp;
    cramer = entry[3] / lp^2;
    granville = entry[3] / (2 * exp(-Euler) * lp^2);
    firoozbakht = lp^2 - lp - 1;
    verdict = if(entry[1] <= 29, -1, if(entry[3] < firoozbakht, 1, 0));
    found = 0;
    for(j = 1, #DL_MAXIMAL_GAP_TABLE,
      if(DL_MAXIMAL_GAP_TABLE[j][1] == entry[3] && DL_MAXIMAL_GAP_TABLE[j][2] == entry[1],
         found = 1; break);
    );
    print("RECORD:", entry[1], "|", entry[2], "|", entry[3],
          "|", dl_number(merit, 12), "|", dl_number(cramer, 12),
          "|", dl_number(granville, 12), "|", dl_number(firoozbakht, 12),
          "|", verdict, "|", found);
  );
  applicable = (start <= 2 && baseline == 0);
  if(applicable,
    for(j = 1, #DL_MAXIMAL_GAP_TABLE,
      published = DL_MAXIMAL_GAP_TABLE[j];
      if(published[2] + published[1] > last_prime || published[2] + published[1] > end,
        status = -1,
        checks++;
        status = 0;
        for(i = 1, #records,
          if(records[i][1] == published[2] && records[i][3] == published[1], status = 1; break);
        );
        if(status == 1, agreements++, mismatches++);
      );
      if(status >= 0,
        print("TABLECHECK:", published[1], "|", published[2], "|", status);
      );
    );
  );
  print("SCANNED:", scanned);
  print("RECORD_COUNT:", #records);
  print("LARGEST_GAP:", record);
  print("TRUNCATED:", truncated);
  print("NEXT_START:", next_start);
  print("LAST_PRIME:", last_prime);
  print("TABLE_APPLICABLE:", if(applicable, 1, 0));
  print("TABLE_CHECKED:", checks);
  print("TABLE_AGREEMENTS:", agreements);
  print("TABLE_MISMATCHES:", mismatches);
  print("TABLE_SIZE:", #DL_MAXIMAL_GAP_TABLE);
  default(realprecision, old);
  print("DONE:", #records);
};

\\ ---------------------------------------------------------------------------
\\ Item 92: Maier-matrix short-interval experiment.  Row k of the matrix is the
\\ interval [q*k + 1, q*k + length]; PARI counts the primes in each row and
\\ compares them with the naive expectation length / log(q*k).
\\ ---------------------------------------------------------------------------
dl_short_interval(q, first_row, rows, length) =
{
  if(q < 2, error("The matrix modulus must be at least 2"));
  if(first_row < 1, error("The first matrix row must be positive"));
  if(rows < 1 || rows > 512, error("Use between 1 and 512 matrix rows"));
  if(length < 2 || length > 1000000, error("Row length must lie between 2 and 10^6"));
  my(old = default(realprecision), base, count, expected, ratio, total = 0,
     ratio_sum = 0.0, best = -1, worst = -1, best_row = 0, worst_row = 0,
     empty = 0, log_base);
  default(realprecision, 60);
  for(k = first_row, first_row + rows - 1,
    base = q * k;
    count = 0;
    forprime(p = base + 1, base + length, count++);
    log_base = log(base * 1.0);
    expected = length / log_base;
    ratio = count / expected;
    total += count;
    ratio_sum += ratio;
    if(count == 0, empty++);
    if(best < 0 || ratio > best, best = ratio; best_row = k);
    if(worst < 0 || ratio < worst, worst = ratio; worst_row = k);
    print("MATRIX:", k, "|", base + 1, "|", base + length, "|", count,
          "|", dl_number(expected, 12), "|", dl_number(ratio, 10));
  );
  print("MATRIX_ROWS:", rows);
  print("MATRIX_TOTAL:", total);
  print("MATRIX_EMPTY:", empty);
  print("MATRIX_MEAN_RATIO:", dl_number(ratio_sum / rows, 10));
  print("MATRIX_MAX_RATIO:", dl_number(best, 10));
  print("MATRIX_MAX_ROW:", best_row);
  print("MATRIX_MIN_RATIO:", dl_number(worst, 10));
  print("MATRIX_MIN_ROW:", worst_row);
  default(realprecision, old);
  print("DONE:", rows);
};

\\ ---------------------------------------------------------------------------
\\ Item 93: prime-density surface over two parameters (block position along
\\ [start, end] and reduced residue class modulo q).  JavaScript only paints
\\ the numbers computed here.
\\ ---------------------------------------------------------------------------
dl_density_surface(start, end, blocks, q) =
{
  if(start < 2, error("The density surface must start at 2 or above"));
  if(end <= start, error("The density range must be nonempty"));
  if(blocks < 1 || blocks > 64, error("Use between 1 and 64 blocks"));
  if(q < 2 || q > 256, error("The residue modulus must satisfy 2 <= q <= 256"));
  my(old = default(realprecision), width, classes = List(), position = vector(q),
     k, grid, index, residue, total = 0, excluded = 0, base, density, emitted = 0,
     maximum = 0.0);
  default(realprecision, 60);
  width = (end - start + 1) \ blocks;
  if(width < 2, error("Each block needs at least two integers"));
  for(a = 0, q - 1, if(gcd(a, q) == 1, listput(classes, a); position[a + 1] = #classes));
  k = #classes;
  grid = matrix(blocks, k);
  forprime(p = start, start + width * blocks - 1,
    if(q % p == 0, excluded++; next);
    index = (p - start) \ width + 1;
    residue = position[p % q + 1];
    if(residue > 0, grid[index, residue]++; total++);
  );
  for(b = 1, blocks,
    base = start + (b - 1) * width;
    for(c = 1, k,
      density = grid[b, c] * k * log(base * 1.0) / width;
      if(density > maximum, maximum = density);
      print("CELL:", b, "|", classes[c], "|", grid[b, c], "|", dl_number(density, 10));
      emitted++;
    );
    print("BLOCK:", b, "|", base, "|", base + width - 1);
  );
  print("SURFACE_BLOCKS:", blocks);
  print("SURFACE_CLASSES:", k);
  print("SURFACE_WIDTH:", width);
  print("SURFACE_TOTAL:", total);
  print("SURFACE_EXCLUDED:", excluded);
  print("SURFACE_MAX_DENSITY:", dl_number(maximum, 10));
  default(realprecision, old);
  print("DONE:", emitted);
};
