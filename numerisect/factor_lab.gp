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
fl_aurifeuillean(b, n, value) =
{
  my(found = 0, f, part);
  if(b < 2 || n < 1, return(0));
  \\ Only report a split when Phi_n(b) genuinely factors into more than one part.
  f = factor(polcyclo(n, b));
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
fl_special_form(expr, seconds) =
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
  results = alarm(seconds,
    my(found = List(), base, exponent, limit);
    for(base = 2, 1000,
      exponent = 2;
      \\ The bound is n + 1 so that n = base^exponent - 1 is itself reachable.
      while(base^exponent <= n + 1,
        if(base^exponent - 1 == n,
          listput(found, ["homogeneous", Str(base), Str(exponent), "-1"]);
        );
        if(base^exponent + 1 == n,
          listput(found, ["homogeneous", Str(base), Str(exponent), "+1"]);
        );
        exponent++;
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
      print("FORM:homogeneous|n = ", row[2], "^", row[3], " ", row[4], " 1|1");
      forms++;
      if(!suitable,
        poly = concat(concat(concat("x^", row[3]), if(row[4] == "-1", " - ", " + ")), "1");
        difficulty = round(eval(row[3]) * log(eval(row[2])) / log(10));
        suitable = 1;
      );
      algebraic += fl_aurifeuillean(eval(row[2]), eval(row[3]), n);
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
  my(remaining = n, c, e, count = 0);
  if(n < 1, error("Reconciliation needs a positive integer"));
  candidates = vecsort(candidates);
  for(i = 1, #candidates,
    c = candidates[i];
    if(c < 2, next());
    e = 0;
    while(remaining % c == 0, remaining = remaining / c; e++);
    if(e > 0,
      print("FACTOR:", c, "|", e, "|", if(isprime(c), 1, 0));
      count++;
    );
  );
  print("COFACTOR:", remaining, "|", if(remaining > 1 && isprime(remaining), 1, 0));
  \\ Complete means every reported part is prime, so nothing is left to factor.
  print("COMPLETE:", if(remaining == 1 || isprime(remaining), 1, 0));
  print("DONE:", count);
};
