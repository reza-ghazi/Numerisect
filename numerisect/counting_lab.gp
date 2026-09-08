\\ Numerisect prime-counting and integer-structure engine for PARI/GP.
\\
\\ Every mathematical quantity produced by this file comes from a PARI library
\\ routine.  Nothing here reimplements a routine that PARI or primecount already
\\ exposes:
\\
\\   primepi              additional engine-independent pi(x) method in the
\\                        comparison, and the Legendre-identity check on phi(x,a)
\\   prime, forprime      the a-th prime and the Legendre product over the first
\\                        a primes
\\   isprimepower         prime-power test; returns the exponent k of x = p^k
\\   ispseudoprimepower   the same test with a pseudo-prime base
\\   ispowerful           every prime valuation of x is at least 2
\\   istotient            x = eulerphi(n) is solvable; returns a witness n
\\   isfundamental        x is a fundamental discriminant
\\   ispolygonal          x is the N-th s-gonal number; returns N
\\   divisorslenstra      Lenstra's algorithm for the divisors of N in a fixed
\\                        residue class r mod s (requires gcd(r,s)=1, s^3 > N)
\\   factorint(n, flag)   integer factorization under an explicit strategy mask
\\   gettime              PARI's own millisecond timer for the strategy race
\\   Set, gcd, sqrt, log  agreement analysis and reporting arithmetic
\\
\\ The counts compared by cl_count_agreement are produced by the primecount
\\ engine (six mathematically distinct algorithm modes in one codebase) and by
\\ primepi; Python launches those
\\ subprocesses and passes the already-computed integers in.  Python and
\\ JavaScript never evaluate any of these quantities themselves.
\\
\\ Protocol: TAG:value or TAG:a|b|c lines, always closed by DONE:<count>.

cl_number(value, digits) =
{
  if(value == 0, return("0"));
  strjoin(strsplit(Strprintf(Strprintf("%%.%dg", digits), value), " "), "")
};

\\ ---------------------------------------------------------------------------
\\ PARI's own exact prime counter, timed by PARI's gettime.  This is the
\\ engine-independent implementation in the algorithm comparison: primepi
\\ shares no code with primecount.  Python restricts it to x where it remains
\\ practical (see counting_lab.py, PARI_PRIMEPI_LIMIT).
\\ ---------------------------------------------------------------------------
cl_primepi(x) =
{
  if(x < 0, error("primepi requires x >= 0"));
  my(value, elapsed);
  gettime();
  value = primepi(x);
  elapsed = gettime();
  print("PRIMEPI:", value);
  print("PRIMEPI_MS:", elapsed);
  print("PRIMEPI_SECONDS:", cl_number(elapsed / 1000.0, 6));
  print("DONE:", 1);
};

\\ ---------------------------------------------------------------------------
\\ Agreement analysis for independently computed values of pi(x).
\\
\\ The point of the comparison is that primecount's six modes implement distinct
\\ formulas, while PARI's primepi also crosses a codebase boundary. A single
\\ method cannot check itself; a disagreement between any two outputs exposes a
\\ defect in a method, an engine build, this machine, or the request, and must be
\\ reported rather than resolved.  This routine therefore never picks a
\\ "winner": it publishes every distinct value with its multiplicity and the
\\ signed difference of every source from the first-listed reference.
\\ ---------------------------------------------------------------------------
cl_count_agreement(values) =
{
  if(#values < 1, error("The agreement analysis needs at least one count"));
  my(distinct, reference = values[1], multiplicity, best = 0, consensus = values[1],
     agree = 1, low, high);
  distinct = Set(values);
  for(i = 1, #distinct,
    multiplicity = sum(j = 1, #values, values[j] == distinct[i]);
    if(multiplicity > best, best = multiplicity; consensus = distinct[i]);
    print("VALUE:", distinct[i], "|", multiplicity);
  );
  if(#distinct > 1, agree = 0);
  low = vecmin(values); high = vecmax(values);
  for(i = 1, #values,
    print("DELTA:", i, "|", values[i], "|", values[i] - consensus, "|",
          if(values[i] == consensus, 1, 0));
  );
  print("AGREE:", agree);
  print("DISTINCT:", #distinct);
  print("CONSENSUS:", consensus);
  print("CONSENSUS_MULTIPLICITY:", best);
  print("REFERENCE:", reference);
  print("SPREAD:", high - low);
  print("DONE:", #values);
};

\\ ---------------------------------------------------------------------------
\\ Context for Legendre's phi(x, a), the count of integers in [1, x] divisible
\\ by none of the first a primes.  primecount computes phi itself; PARI supplies
\\ the a-th prime, the Legendre product x * prod_{i<=a} (1 - 1/p_i) that phi
\\ approximates, and -- when x < p_{a+1}^2, so that every surviving integer
\\ above 1 is prime -- the exact identity pi(x) = phi(x, a) + a - 1 through
\\ primepi.  Outside that window the identity is reported as inapplicable
\\ rather than approximated.
\\ ---------------------------------------------------------------------------
cl_phi_context(x, a, phi_value) =
{
  if(x < 1, error("phi(x, a) requires x >= 1"));
  if(a < 0, error("phi(x, a) requires a >= 0"));
  my(old = default(realprecision), pa, next_prime, product = 1.0, applies, exact);
  default(realprecision, 60);
  pa = if(a >= 1, prime(a), 1);
  next_prime = prime(a + 1);
  if(a >= 1, forprime(p = 2, pa, product *= (1 - 1.0 / p)));
  print("PHI_A_TH_PRIME:", pa);
  print("PHI_NEXT_PRIME:", next_prime);
  print("PHI_LEGENDRE_PRODUCT:", cl_number(x * product, 20));
  print("PHI_RATIO:", cl_number(phi_value / (x * product), 12));
  applies = if(x < next_prime^2, 1, 0);
  print("PHI_IDENTITY_APPLIES:", applies);
  if(applies,
    exact = primepi(x);
    print("PHI_PI:", exact);
    print("PHI_IDENTITY_VALUE:", phi_value + a - 1);
    print("PHI_IDENTITY_MATCH:", if(phi_value + a - 1 == exact, 1, 0));
  );
  default(realprecision, old);
  print("DONE:", 1);
};

\\ ---------------------------------------------------------------------------
\\ Signed and relative error of the two inverse approximations to the n-th
\\ prime.  primecount computes the exact n-th prime, Li^-1(n) and R^-1(n);
\\ PARI computes every error term at 60-digit precision.  Row order is fixed by
\\ the caller: 1 = Li^-1, 2 = R^-1.
\\ ---------------------------------------------------------------------------
cl_nth_prime_errors(n, exact, estimates) =
{
  if(n < 1, error("The n-th prime requires n >= 1"));
  if(exact < 2, error("The exact n-th prime must be at least 2"));
  my(old = default(realprecision), estimate);
  default(realprecision, 60);
  for(i = 1, #estimates,
    estimate = estimates[i];
    print("ROW:", i, "|", estimate, "|", estimate - exact, "|",
          cl_number(100.0 * (estimate - exact) / exact, 12));
  );
  my(best = 1);
  for(i = 1, #estimates,
    if(abs(estimates[i] - exact) < abs(estimates[best] - exact), best = i);
  );
  print("NTH_CLOSEST:", best);
  print("NTH_EXACT:", exact);
  print("NTH_INDEX:", n);
  default(realprecision, old);
  print("DONE:", #estimates);
};

\\ ---------------------------------------------------------------------------
\\ Integer-structure predicates.  Each line is one PARI library routine; none
\\ of these tests is recomputed here.  The optional reference arguments return
\\ the prime-power base, the totient witness and the polygonal index, which are
\\ the parts a bare true/false answer throws away.
\\ ---------------------------------------------------------------------------
cl_integer_predicates(n, sides) =
{
  if(sides < 3, error("A polygonal side count must be at least 3"));
  my(exponent, base, witness, index, totient, polygonal);
  print("PREDICATE_N:", n);
  print("PREDICATE_SIDES:", sides);
  exponent = if(n > 0, isprimepower(n, &base), 0);
  print("PRIMEPOWER:", exponent);
  print("PRIMEPOWER_BASE:", if(exponent, base, 0));
  exponent = if(n > 0, ispseudoprimepower(n, &base), 0);
  print("PSEUDOPRIMEPOWER:", exponent);
  print("PSEUDOPRIMEPOWER_BASE:", if(exponent, base, 0));
  print("POWERFUL:", if(n > 0, ispowerful(n), 0));
  totient = if(n > 0, istotient(n, &witness), 0);
  print("TOTIENT:", totient);
  print("TOTIENT_WITNESS:", if(totient, witness, 0));
  print("FUNDAMENTAL:", isfundamental(n));
  polygonal = if(n >= 0, ispolygonal(n, sides, &index), 0);
  print("POLYGONAL:", polygonal);
  print("POLYGONAL_INDEX:", if(polygonal, index, 0));
  print("DONE:", 1);
};

\\ ---------------------------------------------------------------------------
\\ Divisors of N in the residue class r mod s, by Lenstra's algorithm.
\\ PARI does not enforce the hypotheses of the algorithm, so they are checked
\\ here: without gcd(r, s) = 1 the class is not invertible, and without
\\ s^3 > N the returned list is silently incomplete.
\\ ---------------------------------------------------------------------------
cl_divisors_lenstra(n, r, s) =
{
  if(n < 1, error("Lenstra's divisor search requires a positive N"));
  if(s < 2, error("The residue modulus must satisfy s >= 2"));
  if(r < 0 || r >= s, error("The residue must satisfy 0 <= r < s"));
  if(gcd(r, s) != 1, error("Lenstra's algorithm requires gcd(r, s) = 1"));
  if(s^3 <= n, error("Lenstra's algorithm requires s^3 > N"));
  my(found, count = 0);
  found = divisorslenstra(n, r, s);
  print("LENSTRA_N:", n);
  print("LENSTRA_RESIDUE:", r);
  print("LENSTRA_MODULUS:", s);
  print("LENSTRA_TAU:", numdiv(n));
  for(i = 1, #found,
    print("DIVISOR:", found[i], "|", n / found[i], "|", isprime(found[i]));
    count++;
  );
  print("LENSTRA_FOUND:", count);
  print("DONE:", count);
};

\\ ---------------------------------------------------------------------------
\\ factorint strategy race.  The second argument of factorint is a bitmask of
\\ methods to AVOID: 1 avoids MPQS, 2 avoids the first-stage ECM, 4 avoids
\\ Pollard-Brent rho and Shanks SQUFOF, 8 skips the final ECM (after which a
\\ huge composite may be declared prime).  Running the same input under several
\\ masks is a PARI-side comparison of factoring methods; PARI's own gettime
\\ measures each run and isprime audits every returned base, which is the only
\\ way to see what mask 8 gave up.
\\ ---------------------------------------------------------------------------
cl_factorint_strategies(n, flags) =
{
  if(n < 2, error("A factorization strategy race requires n >= 2"));
  if(#flags < 1, error("Select at least one factorint strategy mask"));
  my(decomposition, elapsed, rows, product, certified, emitted = 0);
  for(i = 1, #flags,
    if(flags[i] < 0 || flags[i] > 15, error("A factorint mask must lie in [0, 15]"));
    gettime();
    decomposition = factorint(n, flags[i]);
    elapsed = gettime();
    rows = matsize(decomposition)[1];
    product = 1;
    certified = 1;
    for(j = 1, rows,
      product *= decomposition[j, 1]^decomposition[j, 2];
      if(!isprime(decomposition[j, 1]), certified = 0);
      print("FACTOR:", flags[i], "|", decomposition[j, 1], "|", decomposition[j, 2],
            "|", if(isprime(decomposition[j, 1]), 1, 0));
    );
    print("STRATEGY:", flags[i], "|", elapsed, "|", rows, "|",
          if(product == n, 1, 0), "|", certified);
    emitted++;
  );
  print("STRATEGY_COUNT:", emitted);
  print("DONE:", emitted);
};
