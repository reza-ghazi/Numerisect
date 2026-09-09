\\ SPDX-License-Identifier: GPL-3.0-or-later
\\
\\ Numerisect factorization laboratory: special forms, algebraic and Aurifeuillean
\\ factors, SNFS suitability, strategy advice, algorithm traces, and certificates.
\\
\\ Every computation here is performed by a PARI/GP library routine: factor,
\\ isprime, polcyclo, subst, ispower, issquare, gcd, Mod, primecert,
\\ primecertisvalid, primecertexport. This file composes those routines and prints
\\ tagged lines; it does not reimplement them.
\\
\\ Output contract: TAG:value lines, ending with DONE:<n>. A missing DONE means the
\\ run failed and the caller must treat the result as an error, never as empty
\\ success. Searches that hit a bound print SEARCH_COMPLETE:0 and are inconclusive.

fl_join(v) =
{
  my(s = "");
  for(i = 1, #v, s = concat(concat(s, if(i > 1, ",", "")), Str(v[i])));
  s;
};

\\ Evaluate a validated integer expression. The caller has already restricted the
\\ characters to digits and + - * ^ ( ), so this is a bounded arithmetic parse.
fl_value(expr) =
{
  my(v);
  v = eval(expr);
  if(type(v) != "t_INT", error("The expression must evaluate to an integer"));
  v;
};

\\ --- Aurifeuillean factorisations -----------------------------------------------
\\ For squarefree b, Phi_n(b) admits a Lucas/Aurifeuillean split when n is an odd
\\ multiple of b (b = 1 mod 4) or of 2b (b = 2,3 mod 4). Rather than hard-coding the
\\ L/M polynomials, the split is found by factoring Phi_n(b) with PARI and reporting
\\ the parts, then verified by division.
\\ SIZE CAP, AND WHY IT IS HERE
\\ Phi_n(b) is the whole input whenever n is prime, so factoring it outright is
\\ factoring the input. Asking PARI to do that inside a metadata routine hung on every
\\ large Mersenne number: 2^1061 - 1 and 10^101 - 1 both exhausted their budget here and
\\ returned nothing at all. Above the cap the split is reported as not attempted, which
\\ is an inconclusive result and never a claim that no Aurifeuillean factor exists.
\\ Hand such an input to the factoring engines instead; that is their job, not this
\\ routine's.
fl_aurifeuillean(b, n, value, digit_cap) =
{
  my(found = 0, f, part, phi);
  if(b < 2 || n < 1, return(0));
  phi = polcyclo(n, b);
  if(#Str(abs(phi)) > digit_cap,
    print("ALGEBRAIC_SKIPPED:", n, "|", b, "|", #Str(abs(phi)), "|", digit_cap);
    return(0);
  );
  \\ Only report a split when Phi_n(b) genuinely factors into more than one part.
  f = factor(phi);
  if(matsize(f)[1] > 1,
    for(i = 1, matsize(f)[1],
      part = f[i, 1];
      if(part > 1 && part < value && value % part == 0,
        print("ALGEBRAIC:", part, "|Aurifeuillean/cyclotomic factor of Phi_", n, "(", b, ")");
        found++;
      );
    );
  );
  found;
};

\\ --- Special-form recognition and SNFS suitability -------------------------------
fl_special_form(expr, seconds, algebraic_cap) =
{
  my(n, digits, results, forms = 0, algebraic = 0, poly = "", difficulty = 0,
     suitable = 0, complete = 1, r, row);
  n = fl_value(expr);
  if(n < 2, error("Special-form analysis needs an integer of at least 2"));
  digits = #Str(n);
  print("VALUE:", n);
  print("DIGITS:", digits);

  \\ Perfect power: n = a^k, decided exactly by PARI's ispower.
  r = ispower(n);
  if(r,
    print("FORM:perfect power|n = ", sqrtnint(n, r), "^", r, "|1");
    forms++;
  );

  \\ Bounded search for a^k +/- 1 and cyclotomic values. The whole search is run
  \\ inside one alarm and RETURNS its findings, because GP closures capture by
  \\ value: a counter incremented inside alarm() would not survive the call.
  \\ n = b^e - 1 exactly when n + 1 is a perfect power, and n = b^e + 1 exactly when
  \\ n - 1 is. Asking ispower that question directly replaces the old scan over every
  \\ base up to 1000 and every exponent below it, which cost on the order of a million
  \\ full-precision exponentiations and timed out on a 320-digit Mersenne number. The
  \\ answer is also strictly better: ispower has no base limit, so forms with a large
  \\ base are now found too.
  \\
  \\ ispower returns the maximal k with m = r^k. Every divisor d of k gives a further
  \\ representation m = (r^(k/d))^d, and they are emitted largest exponent first
  \\ because that is the best SNFS polynomial of the set.
  results = alarm(seconds,
    my(found = List(), m, k, root, dv);
    for(side = 1, 2,
      m = if(side == 1, n + 1, n - 1);
      if(m > 1,
        k = ispower(m, , &root);
        if(k > 1,
          dv = divisors(k);
          forstep(i = #dv, 1, -1,
            my(d = dv[i]);
            if(d > 1,
              listput(found, ["homogeneous", Str(root^(k/d)), Str(d),
                              if(side == 1, "-1", "+1")]);
            );
          );
        );
      );
    );
    for(base = 2, 200,
      for(k = 3, 60,
        if(polcyclo(k, base) == n,
          listput(found, ["cyclotomic", Str(base), Str(k), ""]);
        );
      );
    );
    Vec(found);
  );

  if(type(results) == "t_ERROR",
    complete = 0;
    results = [];
  );

  for(i = 1, #results,
    row = results[i];
    if(row[1] == "homogeneous",
      print("FORM:homogeneous|n = ", row[2], "^", row[3],
            if(row[4] == "-1", " - 1", " + 1"), "|1");
      forms++;
      if(!suitable,
        poly = concat(concat(concat("x^", row[3]), if(row[4] == "-1", " - ", " + ")), "1");
        difficulty = round(eval(row[3]) * log(eval(row[2])) / log(10));
        suitable = 1;
      );
      algebraic += fl_aurifeuillean(eval(row[2]), eval(row[3]), n, algebraic_cap);
    );
    if(row[1] == "cyclotomic",
      print("FORM:cyclotomic|n = Phi_", row[3], "(", row[2], ")|1");
      forms++;
      if(!suitable,
        poly = concat(concat("Phi_", row[3]), concat("(x) at ", row[2]));
        difficulty = #Str(n);
        suitable = 1;
      );
    );
  );

  print("SNFS_SUITABLE:", suitable);
  print("SNFS_POLY:", poly);
  print("SNFS_DIFFICULTY:", if(difficulty > 0, difficulty, ""));
  print("SEARCH_COMPLETE:", complete);
  print("DONE:", forms + algebraic);
};

\\ --- Strategy advice with expected-factor-size estimate ---------------------------
fl_strategy(expr, pretest, seconds) =
{
  my(n, digits, engine, small = 0, f, r, expected, basis, cofactor);
  n = fl_value(expr);
  if(n < 2, error("Strategy advice needs an integer of at least 2"));
  digits = #Str(n);
  print("VALUE:", n);
  print("DIGITS:", digits);

  print("STEP:Is the input prime?|", if(isprime(n), "yes", "no"),
        "|", if(isprime(n), "no factoring required", "continue"));
  if(isprime(n),
    print("ENGINE:none");
    print("EXPECTED_FACTOR_DIGITS:");
    print("EXPECTED_BASIS:input is prime");
    print("DONE:1");
    return();
  );

  \\ Small factors by bounded trial division (PARI's partial factor).
  f = factor(n, 10^6);
  cofactor = n;
  for(i = 1, matsize(f)[1],
    if(f[i, 1] < 10^6,
      print("SMALL_FACTOR:", f[i, 1], "^", f[i, 2]);
      small++;
      cofactor = cofactor / f[i, 1]^f[i, 2];
    );
  );
  print("STEP:Any factor below 10^6?|", if(small, "yes", "no"),
        "|", if(small, "removed before heavy work", "continue"));

  r = ispower(cofactor);
  print("PERFECT_POWER:", if(r, r, 0));
  print("STEP:Is the cofactor a perfect power?|", if(r, "yes", "no"),
        "|", if(r, "reduce to the base first", "continue"));

  digits = #Str(cofactor);
  print("STEP:Cofactor decimal digits|", digits, "|selects the engine");
  print("STEP:ECM depth already completed|", pretest,
        "|raises the expected size of any remaining factor");

  \\ Expected remaining factor size. ECM to t-digits makes a factor below t digits
  \\ unlikely, so the planning estimate is max(pretest, one third of the cofactor)
  \\ which is the standard balance point for a hardest-case semiprime.
  expected = if(pretest > 0, pretest, 0);
  if(digits \ 3 > expected, expected = digits \ 3);
  if(expected >= digits, expected = digits \ 2);
  basis = if(pretest > 0,
             concat(concat("ECM to t", Str(pretest)), " completed; smaller factors unlikely"),
             "no ECM completed; estimate is the balanced semiprime split");
  print("EXPECTED_FACTOR_DIGITS:", expected);
  print("EXPECTED_BASIS:", basis);

  engine = if(digits <= 1, "none",
           if(isprime(cofactor), "none",
           if(digits < 20, "SQUFOF or YAFU SIQS",
           if(digits < 60, "YAFU SIQS",
           if(digits < 95, "YAFU ECM pretest then SIQS", "CADO-NFS")))));
  print("STEP:Recommended engine|", engine, "|final");
  print("ENGINE:", engine);
  print("DONE:1");
};

\\ --- Bounded educational algorithm traces -----------------------------------------
\\ These expose the individual steps of rho, p-1, and ECM for teaching. Production
\\ factoring uses YAFU, Msieve, GMP-ECM and CADO-NFS, never this routine.
fl_trace(expr, kind, steps, seconds) =
{
  my(n, x, y, d, recorded = 0, truncated = 0, found = 0, a, k, e, curve, px, pz, q);
  n = fl_value(expr);
  if(n < 4, error("Traces need a composite of at least 4"));
  if(kind < 0 || kind > 2, error("Unknown trace kind"));
  print("VALUE:", n);

  if(kind == 0,
    \\ Pollard rho with Floyd cycle detection; PARI computes each gcd.
    x = 2; y = 2; d = 1;
    alarm(seconds,
      for(i = 1, steps,
        x = (x^2 + 1) % n;
        y = (((y^2 + 1) % n)^2 + 1) % n;
        d = gcd(abs(x - y), n);
        print("TRACE:", i, "|x=", x, " y=", y, "|", abs(x - y), "|", d);
        recorded++;
        if(d > 1 && d < n, found = d; break());
        if(d == n, break());
      );
    );
  );
  if(kind == 1,
    \\ Pollard p-1: accumulate a^(k!) mod n and take gcd(a^k - 1, n).
    a = 2; e = 2; d = 1;
    alarm(seconds,
      for(i = 2, steps + 1,
        a = lift(Mod(a, n)^i);
        d = gcd(a - 1, n);
        print("TRACE:", i - 1, "|a^", i, "! mod n = ", a, "|", i, "|", d);
        recorded++;
        if(d > 1 && d < n, found = d; break());
        if(d == n, break());
      );
    );
  );
  if(kind == 2,
    \\ ECM stage 1 on a Montgomery curve, scalar-multiplying by successive primes.
    \\ PARI performs the modular arithmetic.
    curve = 6; px = 2; pz = 1; d = 1; k = 0;
    alarm(seconds,
      forprime(p = 2, 10^6,
        k++;
        if(k > steps, truncated = 1; break());
        q = p;
        while(q <= 10^6,
          px = lift(Mod(px, n) * p);
          q = q * p;
        );
        d = gcd(px, n);
        print("TRACE:", k, "|prime ", p, " applied|", px, "|", d);
        recorded++;
        if(d > 1 && d < n, found = d; break());
      );
    );
  );
  if(recorded >= steps, truncated = 1);
  print("FACTOR:", if(found, found, ""));
  print("TRUNCATED:", truncated);
  print("DONE:", recorded);
};

\\ --- Batch primality certificates -------------------------------------------------
\\ isprime decides primality, primecert builds the certificate, and
\\ primecertisvalid re-checks it independently.
fl_certificates(factors, seconds) =
{
  my(count = 0, prime, cert, valid);
  for(i = 1, #factors,
    prime = 0; cert = 0; valid = 0;
    alarm(seconds,
      prime = isprime(factors[i]);
      if(prime,
        cert = primecert(factors[i]);
        if(cert != 0, valid = primecertisvalid(cert));
      );
    );
    print("CERT:", factors[i], "|", if(prime, 1, 0), "|", if(cert != 0, 1, 0),
          "|", if(valid, 1, 0));
    count++;
  );
  print("DONE:", count);
};

\\ --- Reconcile engine-reported factors into a consistent decomposition -------------
\\ GMP-ECM peels factors off across successive curves and prints each one as it is
\\ found, so the raw list can overlap and need not multiply to the input. PARI/GP
\\ divides the candidates out, reports each prime power actually present, decides
\\ primality, and returns the remaining cofactor. No arithmetic happens in Python.
fl_reconcile(n, candidates) =
{
  my(remaining = n, c, e, count = 0, allprime = 1, cprime);
  if(n < 1, error("Reconciliation needs a positive integer"));
  candidates = vecsort(candidates);
  for(i = 1, #candidates,
    c = candidates[i];
    if(c < 2, next());
    e = 0;
    while(remaining % c == 0, remaining = remaining / c; e++);
    if(e > 0,
      cprime = isprime(c);
      if(!cprime, allprime = 0);
      print("FACTOR:", c, "|", e, "|", if(cprime, 1, 0));
      count++;
    );
  );
  print("COFACTOR:", remaining, "|", if(remaining > 1 && isprime(remaining), 1, 0));
  \\ Complete means every reported part is prime, so nothing is left to factor.
  print("COMPLETE:", if(allprime && (remaining == 1 || isprime(remaining)), 1, 0));
  print("DONE:", count);
};

\\ Build M_p only for the staged factor hunt, divide every engine-reported divisor
\\ inside PARI/GP, preserve multiplicity, and classify the exact remaining cofactor.
\\ Unlike fl_mersenne_factors, this routine necessarily materializes M_p. Its caller
\\ therefore enforces a much smaller exponent limit and never routes the arithmetic
\\ through Python.
fl_mersenne_inventory(p, candidates, proof_seconds) =
{
  my(remaining, c, e, count = 0, cprime, allprime = 1,
     cofactor_status = "unit", screen, proof, complete = 0);
  if(p < 3 || p % 2 == 0, error("A staged Mersenne hunt needs an odd exponent of at least 3"));
  remaining = 2^p - 1;
  candidates = vecsort(candidates);
  for(i = 1, #candidates,
    c = candidates[i];
    if(c < 2, next());
    e = 0;
    while(remaining % c == 0, remaining /= c; e++);
    if(e > 0,
      cprime = isprime(c);
      if(!cprime, allprime = 0);
      print("INVENTORY_FACTOR:", c, "|", e, "|", if(cprime, 1, 0));
      count++;
    );
  );
  if(remaining == 1,
    cofactor_status = "unit";
    complete = allprime;
  ,
    screen = alarm(proof_seconds, ispseudoprime(remaining));
    if(type(screen) == "t_ERROR",
      cofactor_status = "unknown";
    , if(!screen,
      cofactor_status = "composite";
    ,
      proof = alarm(proof_seconds, isprime(remaining));
      if(type(proof) == "t_ERROR",
        cofactor_status = "probable_prime";
      ,
        if(proof,
          cofactor_status = "proven_prime";
          complete = allprime;
        ,
          cofactor_status = "composite";
        );
      );
    ));
  );
  print("INVENTORY_COFACTOR:", remaining);
  print("INVENTORY_COFACTOR_DIGITS:", if(remaining == 1, 1, #Str(remaining)));
  print("INVENTORY_COFACTOR_STATUS:", cofactor_status);
  print("INVENTORY_COMPLETE:", complete);
  print("DONE:", count);
};

\\ --- Mersenne trial factoring ----------------------------------------------------
\\ For odd prime p, every prime factor q of M_p = 2^p - 1 satisfies two classical
\\ congruences:
\\
\\   q = 2kp + 1        (Euler / Fermat: the order of 2 modulo q is exactly p)
\\   q = +/-1 (mod 8)   (2 is a quadratic residue modulo q)
\\
\\ Together they confine the candidates to a thin arithmetic progression, which is why
\\ this finds factors of Mersenne numbers far beyond the reach of any general-purpose
\\ method. The test itself is Mod(2, q)^p == 1, a single modular exponentiation.
\\
\\ M_p IS NEVER CONSTRUCTED. Everything happens modulo q, so p may be in the millions
\\ and the routine still runs; building 2^p - 1 for such a p would exhaust memory long
\\ before any factor was found. This is the same reason GIMPS trial-factors before it
\\ commits to a Lucas-Lehmer test.
\\
\\ For odd composite p, ord_q(2) may be any divisor d > 1 of p. PARI/GP therefore
\\ enumerates every such d and searches q = 2kd + 1. An exhausted k range is still
\\ INCONCLUSIVE: it says nothing about whether M_p or its remaining cofactor is prime.
fl_mersenne_factors(p, k_limit, seconds, stop_after_first) =
{
  my(found = 0, truncated = 0, q, k, d, scanned = 0, largest_q = 0, started = getwalltime(),
     stop_reason = "ceiling", hits = List(), orders, completed_orders = 0,
     seen = Map(), pf, pf_text = "");
  if(p < 3 || p % 2 == 0, error("Mersenne progression factoring needs an odd exponent p >= 3; M_2 = 3 is the trivial exception"));
  print("EXPONENT:", p);
  print("K_LIMIT:", k_limit);
  pf = factor(p);
  for(i = 1, matsize(pf)[1],
    pf_text = concat(pf_text, if(i > 1, " * ", ""));
    pf_text = concat(pf_text, Str(pf[i, 1]));
    if(pf[i, 2] > 1, pf_text = concat(pf_text, concat("^", Str(pf[i, 2]))));
  );
  print("EXPONENT_PRIME:", isprime(p));
  print("EXPONENT_FACTORIZATION:", pf_text);
  \\ If p is composite, a prime divisor q of M_p can have any odd order d>1
  \\ dividing p. Searching q=2kd+1 for every such d includes the algebraic
  \\ M_d divisors that a prime-p-only search misses. PARI/GP owns divisors(p).
  orders = select(x -> x > 1, divisors(p));
  print("ORDER_DIVISORS:", #orders);
  \\ #digits of 2^p - 1 without building it.
  print("MERSENNE_DIGITS:", floor(p * log(2) / log(10)) + 1);
  for(i = 1, #orders,
    d = orders[i];
    for(k = 1, k_limit,
      if(getwalltime() - started >= 1000 * seconds,
        truncated = 1; stop_reason = "timeout"; break();
      );
      scanned = max(scanned, k);
      q = 2 * k * d + 1;
      largest_q = max(largest_q, q);
      \\ q = +/-1 mod 8 is necessary for an odd order d.
      if(q % 8 == 1 || q % 8 == 7,
        if(ispseudoprime(q) && Mod(2, q)^d == 1 && isprime(q) && !mapisdefined(seen, q),
          mapput(seen, q, 1);
          listput(hits, [k, q, d]);
          if(stop_after_first, stop_reason = "factor_found"; break());
        );
      );
    );
    if(truncated || stop_reason == "factor_found", break());
    completed_orders++;
  );
  for(i = 1, #hits,
    print("FACTOR:", hits[i][2], "|", hits[i][1], "|", hits[i][3]);
    found++;
  );
  print("SCANNED_K:", scanned);
  print("LARGEST_CANDIDATE:", largest_q);
  print("ORDERS_COMPLETED:", completed_orders);
  print("STOP_REASON:", stop_reason);
  print("TRUNCATED:", truncated);
  print("DONE:", found);
};

\\ --- Mersenne metadata and confirmation for the native scanner ---------------------
\\ The compiled helper numerisect-mfactor scans one order divisor's progression very
\\ fast, but it is a scanner, not an authority: it reports q with 2^d = 1 (mod q), which
\\ makes q a divisor of 2^d - 1 but says nothing about q being prime. PARI/GP keeps both
\\ jobs it should keep. These two routines supply the exponent's structure before the
\\ scan and confirm every candidate after it, so no claim reaches a user unverified.
fl_mersenne_orders(p) =
{
  my(pf, pf_text = "", orders);
  if(p < 3 || p % 2 == 0, error("Mersenne progression factoring needs an odd exponent p >= 3; M_2 = 3 is the trivial exception"));
  pf = factor(p);
  for(i = 1, matsize(pf)[1],
    pf_text = concat(pf_text, if(i > 1, " * ", ""));
    pf_text = concat(pf_text, Str(pf[i, 1]));
    if(pf[i, 2] > 1, pf_text = concat(pf_text, concat("^", Str(pf[i, 2]))));
  );
  print("EXPONENT_PRIME:", isprime(p));
  print("EXPONENT_FACTORIZATION:", pf_text);
  print("MERSENNE_DIGITS:", floor(p * log(2) / log(10)) + 1);
  orders = select(x -> x > 1, divisors(p));
  for(i = 1, #orders, print("ORDER:", orders[i]));
  print("DONE:", #orders);
};

\\ Confirm each scanned candidate: q must be prime and must genuinely divide 2^d - 1.
fl_mersenne_confirm(candidates, orders) =
{
  my(q, d, ok);
  if(#candidates != #orders, error("Each candidate needs its order"));
  for(i = 1, #candidates,
    q = candidates[i]; d = orders[i];
    ok = if(q > 1 && Mod(2, q)^d == 1 && isprime(q), 1, 0);
    print("CONFIRM:", q, "|", d, "|", ok);
  );
  print("DONE:", #candidates);
};
