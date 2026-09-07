\\ Numerisect primality laboratory for PARI/GP.
\\
\\ Every test, proof, certificate, witness search, and special-form search in
\\ this file executes inside PARI/GP.  Python validates requests, launches gp,
\\ and parses the tagged protocol; JavaScript only renders the results.
\\
\\ Conventions: verdict flags are 1 (yes/pass/proven prime), 0 (no/fail/proven
\\ composite) and -1 (inconclusive: time budget exhausted or search bound hit).
\\ Every entry point prints a DONE: marker as its final line.

pl_ms() = getabstime();

\\ Run a closure under a time budget; returns [status, value] with status 0 on timeout.
pl_budget(seconds, closure) =
{
  my(result = alarm(seconds, closure()));
  if(type(result) == "t_ERROR", [0, 0], [1, result]);
};

\\ Strong (Miller–Rabin) test with the complete squaring chain.  Returns
\\ [pass, s, d, chain] where chain lists the successive residues.
pl_strong_chain(n, a) =
{
  my(s = valuation(n - 1, 2), d = (n - 1) >> s, x, chain = List(), pass = 0);
  x = lift(Mod(a, n)^d); listput(chain, x);
  if(x == 1 || x == n - 1, pass = 1);
  for(i = 1, s - 1,
    if(pass, break());
    x = x^2 % n; listput(chain, x);
    if(x == n - 1, pass = 1);
    if(x == 1, break());
  );
  [pass, s, d, Vec(chain)];
};

\\ Lucas sequence terms [U_m, V_m] modulo N through a 2x2 matrix power.
pl_lucas_uv(P, Q, m, N) =
{
  my(R = (Mod(1, N) * [P, -Q; 1, 0])^m);
  [lift(R[2, 1]), lift(2 * R[1, 1] - P * R[2, 1])];
};

\\ Selfridge method A: the first D in 5, -7, 9, -11, ... with (D/n) = -1.
\\ Returns [D, P, Q] or [0, 0, 0] when n is a perfect square (no such D exists).
pl_selfridge(n) =
{
  my(D = 5, sign = 1);
  if(issquare(n), return([0, 0, 0]));
  while(kronecker(D, n) != -1,
    if(gcd(abs(D), n) > 1 && gcd(abs(D), n) < n, return([D, 1, (1 - D) / 4]));
    sign = -sign; D = sign * (abs(D) + 2);
  );
  [D, 1, (1 - D) / 4];
};

\\ Lucas probable-prime tests with parameters (P, Q); returns
\\ [lucas_pass, strong_pass, D, jacobi, r_index, V_check].
pl_lucas_tests_core(n, P, Q) =
{
  my(D = P^2 - 4 * Q, jac = kronecker(D, n), delta, uv, s, d, x, strong = 0, r_index = -1, vcheck);
  delta = n - jac;
  uv = pl_lucas_uv(P, Q, delta, n);
  vcheck = if(jac == -1, uv[2] == lift(Mod(2 * Q, n)), uv[2] == 2);
  s = valuation(delta, 2); d = delta >> s;
  x = pl_lucas_uv(P, Q, d, n);
  if(x[1] == 0, strong = 1; r_index = 0);
  if(!strong,
    for(r = 0, s - 1,
      x = pl_lucas_uv(P, Q, d << r, n);
      if(x[2] == 0, strong = 1; r_index = r; break());
    );
  );
  [uv[1] == 0, strong, D, jac, r_index, vcheck];
};

\\ Quadratic Frobenius probable-prime test with respect to x^2 - Px + Q.
\\ Returns 1 when x^n is congruent to the Frobenius image of x modulo (n, f).
pl_frobenius(n, P, Q) =
{
  my(D = P^2 - 4 * Q, jac = kronecker(D, n), F);
  if(gcd(n, 2 * Q * D) != 1, return(0));
  F = Mod(1, n) * (x^2 - P * x + Q);
  if(jac == -1, Mod(x, F)^n == Mod(P - x, F), Mod(x, F)^n == Mod(x, F));
};

pl_chain_text(chain) =
{
  my(s = "");
  for(i = 1, #chain, s = concat(concat(s, if(i == 1, "", ",")), Str(chain[i])));
  s;
};

\\ ---------------------------------------------------------------------------
\\ Item 21: comparison laboratory.
\\ ---------------------------------------------------------------------------
pl_compare(n, bases, budget) =
{
  if(n < 2, error("Primality comparison requires an integer at least 2"));
  my(t0, a, g, ok, chain, sel, D, P, Q, lt, fr, proofs = 0, composite = 0,
     inconclusive = 0, r, even = (n % 2 == 0));
  print("N:", n); print("DIGITS:", #digits(n));
  if(even,
    print("TEST:Even input|", if(n == 2, "pass", "fail"), "|n mod 2 = 0|0|proof");
    if(n == 2, proofs = 1, composite = 1);
  );
  for(i = 1, #bases,
    a = bases[i] % n;
    if(a == 0,
      print("TEST:Fermat|skipped|a=", bases[i], " is 0 modulo n|0|probable");
      next();
    );
    g = gcd(a, n);
    if(g > 1,
      print("TEST:Fermat|fail|a=", bases[i], " shares factor gcd=", g, "|0|probable");
      composite = 1; next();
    );
    t0 = pl_ms(); ok = Mod(a, n)^(n - 1) == 1;
    print("TEST:Fermat|", if(ok, "pass", "fail"), "|a=", bases[i], "; a^(n-1) mod n = ",
          lift(Mod(a, n)^(n - 1)), "|", pl_ms() - t0, "|probable");
    if(!ok, composite = 1);
    if(!even,
      t0 = pl_ms(); r = lift(Mod(a, n)^((n - 1) / 2));
      ok = r == kronecker(a, n) % n;
      print("TEST:Solovay-Strassen|", if(ok, "pass", "fail"), "|a=", bases[i], "; a^((n-1)/2) mod n = ",
            r, "; Jacobi (a/n) = ", kronecker(a, n), "|", pl_ms() - t0, "|probable");
      if(!ok, composite = 1);
      t0 = pl_ms(); chain = pl_strong_chain(n, a);
      print("TEST:Miller-Rabin|", if(chain[1], "pass", "fail"), "|a=", bases[i], "; n-1 = 2^", chain[2],
            " * ", chain[3], "; chain ", pl_chain_text(chain[4]), "|", pl_ms() - t0, "|probable");
      if(!chain[1], composite = 1);
    );
  );
  if(!even && n > 2,
    sel = pl_selfridge(n);
    if(sel[1] == 0,
      print("TEST:Lucas (Selfridge)|fail|n is a perfect square|0|probable");
      print("TEST:Strong Lucas|fail|n is a perfect square|0|probable");
      print("TEST:Frobenius|fail|n is a perfect square|0|probable");
      composite = 1;
    ,
      D = sel[1]; P = sel[2]; Q = sel[3];
      if(gcd(n, 2 * Q * D) != 1 && gcd(n, 2 * Q * D) < n,
        print("TEST:Lucas (Selfridge)|fail|gcd(n, 2QD) = ", gcd(n, 2 * Q * D), "|0|probable");
        print("TEST:Strong Lucas|fail|gcd(n, 2QD) = ", gcd(n, 2 * Q * D), "|0|probable");
        print("TEST:Frobenius|fail|gcd(n, 2QD) = ", gcd(n, 2 * Q * D), "|0|probable");
        composite = 1;
      ,
        t0 = pl_ms(); lt = pl_lucas_tests_core(n, P, Q);
        print("TEST:Lucas (Selfridge)|", if(lt[1], "pass", "fail"), "|D=", D, "; P=", P, "; Q=", Q,
              "; U(n+1) = 0 mod n: ", if(lt[1], "yes", "no"), "|", pl_ms() - t0, "|probable");
        print("TEST:Strong Lucas|", if(lt[2], "pass", "fail"), "|D=", D, "; P=", P, "; Q=", Q,
              if(lt[2], concat("; index r = ", Str(lt[5])), ""), "|0|probable");
        if(!lt[1], composite = 1); if(!lt[2], composite = 1);
        t0 = pl_ms(); fr = pl_frobenius(n, P, Q);
        print("TEST:Frobenius|", if(fr, "pass", "fail"), "|f(x) = x^2 - ", P, "x + (", Q,
              "); x^n = ", if(D == 0, "x", "P - x"), " mod (n, f)|", pl_ms() - t0, "|probable");
        if(!fr, composite = 1);
      );
    );
  );
  t0 = pl_ms(); ok = ispseudoprime(n);
  print("TEST:Baillie-PSW|", if(ok, "pass", "fail"), "|PARI ispseudoprime (strong base 2 + strong Lucas)|",
        pl_ms() - t0, "|probable");
  if(!ok, composite = 1);
  t0 = pl_ms(); r = pl_budget(budget, () -> isprime(n, 2));
  if(r[1] == 0,
    print("TEST:APR-CL|inconclusive|time budget ", budget, " s exhausted|", pl_ms() - t0, "|proof"); inconclusive = 1;
  ,
    print("TEST:APR-CL|", if(r[2], "pass", "fail"), "|Adleman-Pomerance-Rumely-Cohen-Lenstra|", pl_ms() - t0, "|proof");
    if(r[2], proofs = 1, composite = 1);
  );
  t0 = pl_ms(); r = pl_budget(budget, () -> isprime(n, 3));
  if(r[1] == 0,
    print("TEST:ECPP|inconclusive|time budget ", budget, " s exhausted|", pl_ms() - t0, "|proof"); inconclusive = 1;
  ,
    print("TEST:ECPP|", if(r[2], "pass", "fail"), "|Atkin-Morain elliptic-curve proof|", pl_ms() - t0, "|proof");
    if(r[2], proofs = 1, composite = 1);
  );
  if(proofs && composite, error("Inconsistent primality verdicts"));
  print("PROVEN:", if(proofs, 1, if(composite, 0, -1)));
  print("DONE:1");
};

\\ ---------------------------------------------------------------------------
\\ Item 22: deterministic Miller–Rabin with published sufficient witness sets.
\\ ---------------------------------------------------------------------------
pl_deterministic_mr(n) =
{
  if(n < 2, error("Deterministic Miller-Rabin requires an integer at least 2"));
  my(bounds = [[2047, 1], [1373653, 2], [25326001, 3], [3215031751, 4],
               [2152302898747, 5], [3474749660383, 6], [341550071728321, 7],
               [3825123056546413051, 9], [318665857834031151167461, 12],
               [3317044064679887385961981, 13]],
     count = 0, bound = 0, set, chain, all_pass = 1, verdict);
  print("N:", n);
  for(i = 1, #bounds, if(n < bounds[i][1], count = bounds[i][2]; bound = bounds[i][1]; break()));
  if(count == 0,
    print("SET_AVAILABLE:0"); print("PROVEN:-1"); print("DONE:1"); return();
  );
  set = primes(count);
  print("SET_AVAILABLE:1"); print("BOUND:", bound); print("SET_SIZE:", count);
  for(i = 1, count, print("BASE:", set[i]));
  if(n == 2, print("WITNESS:2|pass|n = 2 is the even prime"); print("PROVEN:1"); print("DONE:1"); return());
  if(n % 2 == 0, print("WITNESS:2|fail|n is even"); print("PROVEN:0"); print("DONE:1"); return());
  for(i = 1, count,
    if(set[i] % n == 0,
      print("WITNESS:", set[i], "|pass|n equals the prime base ", set[i]); next();
    );
    chain = pl_strong_chain(n, set[i]);
    print("WITNESS:", set[i], "|", if(chain[1], "pass", "fail"), "|n-1 = 2^", chain[2], " * ", chain[3],
          "; chain ", pl_chain_text(chain[4]));
    if(!chain[1], all_pass = 0; verdict = set[i]);
  );
  print("PROVEN:", all_pass);
  print("CROSSCHECK:", isprime(n));
  print("DONE:1");
};

\\ ---------------------------------------------------------------------------
\\ Item 23: Pocklington N-1 proofs with explicit certificates.
\\ ---------------------------------------------------------------------------
pl_pocklington(n, budget, witness_limit) =
{
  if(n < 3, error("Pocklington proofs require an integer at least 3"));
  my(f, rows, F = 1, R, selected = List(), found, a, g, r, all_proven = 1, cert = List(), pf);
  print("N:", n);
  if(n % 2 == 0, print("PROVEN:0"); print("REASON:even"); print("DONE:1"); return());
  r = pl_budget(budget, () -> factor(n - 1));
  if(r[1] == 0, print("FACTOR_STATUS:timeout"); print("PROVEN:-1"); print("DONE:1"); return());
  f = r[2]; print("FACTOR_STATUS:complete");
  rows = vecsort(vector(matsize(f)[1], i, [f[i, 1], f[i, 2]]), (u, v) -> sign(v[1] - u[1]));
  for(i = 1, #rows,
    if((F + 1)^2 > n, break());
    F *= rows[i][1]^rows[i][2]; listput(selected, rows[i]);
  );
  R = (n - 1) / F;
  print("FACTORED_PART:", F); print("COFACTOR:", R); print("BOUND_OK:", (F + 1)^2 > n);
  print("COPRIME:", gcd(F, R) == 1);
  for(i = 1, #selected,
    my(p = selected[i][1], e = selected[i][2]);
    pf = pl_budget(budget, () -> isprime(p));
    if(pf[1] == 0 || pf[2] == 0, all_proven = 0);
    found = 0;
    for(b = 2, witness_limit,
      a = Mod(b, n);
      if(a^(n - 1) != 1,
        print("FERMAT_WITNESS:", b); print("PROVEN:0"); print("DONE:1"); return();
      );
      g = gcd(lift(a^((n - 1) / p)) - 1, n);
      if(g == 1, found = b; break());
      if(g > 1 && g < n,
        print("FACTOR_FOUND:", g); print("PROVEN:0"); print("DONE:1"); return();
      );
    );
    print("WITNESS:", p, "|", e, "|", found, "|", if(pf[1] == 0, -1, pf[2]));
    if(found, listput(cert, [p, e, found]), all_proven = 0);
  );
  if(all_proven,
    print("CERT:[", n, ",", F, ",", Vec(cert), "]");
    r = pl_budget(budget, () -> primecertisvalid(primecert(n, 1)));
    print("PARI_N_MINUS_1:", if(r[1] == 0, -1, r[2]));
    print("PROVEN:1");
  ,
    print("PROVEN:-1");
  );
  print("DONE:1");
};

pl_verify_pocklington(cert) =
{
  if(type(cert) != "t_VEC" || #cert != 3, error("A Pocklington certificate is [N, F, [[p, e, a], ...]]"));
  my(n = cert[1], F = cert[2], parts = cert[3], product = 1, valid = 1, ok, a);
  if(type(n) != "t_INT" || type(F) != "t_INT" || type(parts) != "t_VEC", error("Invalid certificate fields"));
  print("N:", n);
  ok = n > 2 && n % 2 == 1; print("CHECK:N is odd and at least 3|", ok); valid = valid && ok;
  for(i = 1, #parts,
    if(type(parts[i]) != "t_VEC" || #parts[i] != 3, error("Invalid certificate entry"));
    product *= parts[i][1]^parts[i][2];
  );
  ok = product == F; print("CHECK:Product of p^e equals F|", ok); valid = valid && ok;
  ok = F > 0 && (n - 1) % F == 0; print("CHECK:F divides N-1|", ok); valid = valid && ok;
  ok = ok && gcd(F, (n - 1) / F) == 1; print("CHECK:gcd(F, (N-1)/F) = 1|", ok); valid = valid && ok;
  ok = (F + 1)^2 > n; print("CHECK:(F+1)^2 > N|", ok); valid = valid && ok;
  for(i = 1, #parts,
    my(p = parts[i][1], w = parts[i][3]);
    ok = isprime(p); print("CHECK:p = ", p, " is prime|", ok); valid = valid && ok;
    a = Mod(w, n);
    ok = a^(n - 1) == 1; print("CHECK:", w, "^(N-1) = 1 mod N|", ok); valid = valid && ok;
    ok = gcd(lift(a^((n - 1) / p)) - 1, n) == 1;
    print("CHECK:gcd(", w, "^((N-1)/", p, ") - 1, N) = 1|", ok); valid = valid && ok;
  );
  print("VALID:", valid); print("DONE:1");
};

\\ ---------------------------------------------------------------------------
\\ Item 24: Pratt certificates (recursive tree with shared nodes).
\\ ---------------------------------------------------------------------------
pl_pratt_node(n, parent, depth, max_nodes, budget, ~state) =
{
  my(id, g, f, r, child, ok = 1, entry);
  if(mapisdefined(state[1], n), return(mapget(state[1], n)));
  if(state[2] >= max_nodes, state[3] = 1; return(0));
  state[2]++; id = state[2]; mapput(state[1], n, id);
  if(n == 2,
    print("NODE:", id, "|", parent, "|2|1|", depth, "|1");
    listput(state[4], [2, 1, []]);
    return(id);
  );
  if(!ispseudoprime(n), print("NODE:", id, "|", parent, "|", n, "|0|", depth, "|0"); state[5] = 1; return(id));
  r = pl_budget(budget, () -> factor(n - 1));
  if(r[1] == 0, print("NODE:", id, "|", parent, "|", n, "|0|", depth, "|-1"); state[3] = 1; return(id));
  f = r[2]; g = lift(znprimroot(n));
  for(i = 1, matsize(f)[1], if(Mod(g, n)^((n - 1) / f[i, 1]) == 1, ok = 0));
  if(Mod(g, n)^(n - 1) != 1, ok = 0);
  print("NODE:", id, "|", parent, "|", n, "|", g, "|", depth, "|", ok);
  entry = vector(matsize(f)[1], i, [f[i, 1], f[i, 2]]);
  listput(state[4], [n, g, entry]);
  for(i = 1, matsize(f)[1],
    child = pl_pratt_node(f[i, 1], id, depth + 1, max_nodes, budget, ~state);
    print("EDGE:", id, "|", f[i, 1], "|", f[i, 2], "|", child);
  );
  id;
};

pl_pratt(n, max_nodes, budget) =
{
  if(n < 2, error("Pratt certificates require an integer at least 2"));
  my(state = [Map(), 0, 0, List(), 0], root);
  print("N:", n);
  root = pl_pratt_node(n, 0, 0, max_nodes, budget, ~state);
  print("NODES:", state[2]); print("TRUNCATED:", state[3]);
  if(state[5], print("PROVEN:0"), if(state[3], print("PROVEN:-1"),
    print("CERT:", Vec(state[4])); print("PROVEN:1")));
  print("DONE:", state[2]);
};

pl_verify_pratt(cert) =
{
  if(type(cert) != "t_VEC" || #cert == 0, error("A Pratt certificate is a vector of [p, g, [[q, e], ...]] nodes"));
  my(known = Map(), valid = 1, ok, n, g, parts, product);
  for(i = 1, #cert, if(type(cert[i]) != "t_VEC" || #cert[i] != 3, error("Invalid Pratt node")); mapput(known, cert[i][1], 1));
  mapput(known, 2, 1);
  print("N:", cert[1][1]);
  for(i = 1, #cert,
    n = cert[i][1]; g = cert[i][2]; parts = cert[i][3];
    if(n == 2, print("CHECK:2 is prime|1"); next());
    product = 1; for(j = 1, #parts, product *= parts[j][1]^parts[j][2]);
    ok = product == n - 1; print("CHECK:", n, ": product of q^e equals n-1|", ok); valid = valid && ok;
    ok = gcd(g, n) == 1 && Mod(g, n)^(n - 1) == 1; print("CHECK:", n, ": g^(n-1) = 1 mod n|", ok); valid = valid && ok;
    for(j = 1, #parts,
      ok = Mod(g, n)^((n - 1) / parts[j][1]) != 1;
      print("CHECK:", n, ": g^((n-1)/", parts[j][1], ") differs from 1|", ok); valid = valid && ok;
      ok = mapisdefined(known, parts[j][1]);
      print("CHECK:", n, ": factor ", parts[j][1], " is certified|", ok); valid = valid && ok;
    );
  );
  print("VALID:", valid); print("DONE:1");
};

\\ ---------------------------------------------------------------------------
\\ Items 27 and 33: Proth and generalized Proth numbers k*b^n + 1.
\\ ---------------------------------------------------------------------------
pl_proth_core(k, n, b, witness_limit) =
{
  my(N = k * b^n + 1, primes_b, a, g, found, cert = List(), status = -1, r);
  if(k >= b^n, return([N, -1, [], 0]));
  if(b == 2,
    for(c = 2, witness_limit,
      if(kronecker(c, N) != -1, next());
      r = Mod(c, N)^((N - 1) / 2);
      status = r == -1;
      return([N, status, [[2, c]], 1]);
    );
    return([N, -1, [], 1]);
  );
  primes_b = factor(b)[, 1]~;
  for(i = 1, #primes_b,
    found = 0;
    for(c = 2, witness_limit,
      a = Mod(c, N);
      if(a^(N - 1) != 1, return([N, 0, [], 1]));
      g = gcd(lift(a^((N - 1) / primes_b[i])) - 1, N);
      if(g == 1, found = c; break());
      if(g > 1 && g < N, return([N, 0, [], 1]));
    );
    if(!found, return([N, -1, [], 1]));
    listput(cert, [primes_b[i], found]);
  );
  [N, 1, Vec(cert), 1];
};

pl_proth(k, n, b, witness_limit, budget) =
{
  if(k < 1 || n < 1 || b < 2, error("Require k >= 1, n >= 1 and base b >= 2"));
  my(v, res, r);
  if(b == 2 && k % 2 == 0, v = valuation(k, 2); k /= 2^v; n += v; print("NORMALIZED:", k, "|", n));
  res = pl_proth_core(k, n, b, witness_limit);
  print("N:", res[1]); print("DIGITS:", #digits(res[1]));
  print("PROTH_CONDITION:", res[4]);
  for(i = 1, #res[3], print("WITNESS:", res[3][i][1], "|", res[3][i][2]));
  if(res[2] == 1, print("CERT:[", k, ",", n, ",", b, ",", res[3], "]"));
  print("PROVEN:", res[2]);
  r = pl_budget(budget, () -> isprime(res[1]));
  print("CROSSCHECK:", if(r[1] == 0, -1, r[2]));
  if(r[1] == 1 && res[2] >= 0 && r[2] != res[2], error("Proth verdict disagrees with isprime"));
  print("DONE:1");
};

pl_proth_search(k, b, n_start, n_end, limit, witness_limit, budget) =
{
  if(k < 1 || b < 2 || n_start < 1 || n_end < n_start, error("Invalid generalized Proth search range"));
  my(found = 0, truncated = 0, N, res, r, status, method, inconclusive = 0);
  for(n = n_start, n_end,
    N = k * b^n + 1;
    if(!ispseudoprime(N), next());
    if(k < b^n,
      r = pl_budget(budget, () -> pl_proth_core(k, n, b, witness_limit));
      if(r[1] == 0, status = -1, status = r[2][2]); method = "proth";
    ,
      r = pl_budget(budget, () -> isprime(N));
      status = if(r[1] == 0, -1, r[2]); method = "isprime";
    );
    if(status == -1, inconclusive++);
    if(status != 0,
      if(found >= limit, truncated = 1; break());
      print("PROTH:", n, "|", #digits(N), "|", status, "|", method, "|", if(#digits(N) <= 20000, N, 0));
      found++;
    );
  );
  print("INCONCLUSIVE:", inconclusive); print("TRUNCATED:", truncated); print("DONE:", found);
};

\\ ---------------------------------------------------------------------------
\\ Item 28: Lucas-sequence tests, Morrison N+1 proofs, and Lucas–Lehmer–Riesel.
\\ ---------------------------------------------------------------------------
pl_lucas_lehmer_riesel(k, m, N) =
{
  my(P = 3, u);
  while(!(kronecker(P - 2, N) == 1 && kronecker(P + 2, N) == -1), P++; if(P > 10000, return([0, -1])));
  u = pl_lucas_uv(P, 1, k, N)[2];
  for(i = 1, m - 2, u = (u^2 - 2) % N);
  [P, u == 0];
};

pl_lucas_tests(n, P, Q, selfridge, budget, witness_limit) =
{
  if(n < 3 || n % 2 == 0, error("Lucas tests require an odd integer at least 3"));
  my(sel, D, g, lt, f, rows, F = 1, R, r, ok, jac, cert = List(), all_ok = 1, kk, mm, llr, v, uv, wit);
  print("N:", n);
  if(selfridge,
    sel = pl_selfridge(n);
    if(sel[1] == 0, print("SQUARE:1"); print("PROVEN:0"); print("DONE:1"); return());
    P = sel[2]; Q = sel[3];
  );
  D = P^2 - 4 * Q; jac = kronecker(D, n);
  if(D == 0, error("The Lucas discriminant P^2 - 4Q must be nonzero"));
  print("PARAMS:", P, "|", Q, "|", D, "|", jac);
  g = gcd(n, 2 * Q * D);
  print("GCD_2QD:", g);
  if(g > 1,
    if(g < n, print("FACTOR_FOUND:", g); print("PROVEN:0"));
    if(g == n, print("PROVEN:-1"));
    print("DONE:1"); return();
  );
  lt = pl_lucas_tests_core(n, P, Q);
  print("LUCAS_PRP:", lt[1]); print("STRONG_LUCAS:", lt[2]); print("STRONG_INDEX:", lt[5]);
  print("V_CHECK:", lt[6]);
  print("FROBENIUS:", pl_frobenius(n, P, Q));
  if(!lt[1] || !lt[2], print("PROVEN:0"); print("DONE:1"); return());
  \\ Lucas–Lehmer–Riesel when n + 1 = k * 2^m with odd k < 2^m and m >= 2.
  v = valuation(n + 1, 2); kk = (n + 1) >> v;
  if(v >= 2 && kk < 2^v,
    llr = pl_lucas_lehmer_riesel(kk, v, n);
    print("LLR:", kk, "|", v, "|", llr[1], "|", llr[2]);
    if(llr[2] == 0, print("PROVEN:0"); print("DONE:1"); return());
  );
  \\ Morrison N+1 proof: requires (D/n) = -1 and a factored part F with (F-1)^2 > n.
  if(jac != -1, print("NPLUS1:-1"); print("PROVEN:", if(v >= 2 && kk < 2^v, llr[2], -1)); print("DONE:1"); return());
  r = pl_budget(budget, () -> factor(n + 1));
  if(r[1] == 0, print("NPLUS1:-1"); print("PROVEN:", if(v >= 2 && kk < 2^v, llr[2], -1)); print("DONE:1"); return());
  f = r[2];
  rows = vecsort(vector(matsize(f)[1], i, [f[i, 1], f[i, 2]]), (u, w) -> sign(w[1] - u[1]));
  for(i = 1, #rows, if((F - 1)^2 > n, break()); F *= rows[i][1]^rows[i][2]);
  R = (n + 1) / F;
  print("NPLUS1_F:", F); print("NPLUS1_R:", R); print("NPLUS1_BOUND:", (F - 1)^2 > n);
  if((F - 1)^2 <= n, print("NPLUS1:-1"); print("PROVEN:", if(v >= 2 && kk < 2^v, llr[2], -1)); print("DONE:1"); return());
  for(i = 1, #rows,
    my(p = rows[i][1]);
    if(F % p != 0, next());
    wit = 0;
    for(j = 0, witness_limit,
      my(PP = P + 2 * j, QQ = (PP^2 - D) / 4);
      if(gcd(n, 2 * QQ * D) != 1, next());
      uv = pl_lucas_uv(PP, QQ, n + 1, n);
      if(uv[1] != 0, print("PROVEN:0"); print("DONE:1"); return());
      if(gcd(pl_lucas_uv(PP, QQ, (n + 1) / p, n)[1], n) == 1, wit = [PP, QQ]; break());
    );
    ok = isprime(p);
    print("NPLUS1_WITNESS:", p, "|", rows[i][2], "|", if(wit == 0, 0, wit[1]), "|", if(wit == 0, 0, wit[2]), "|", ok);
    if(wit == 0 || !ok, all_ok = 0, listput(cert, [p, rows[i][2], wit[1], wit[2]]));
  );
  if(all_ok, print("CERT:[", n, ",", F, ",", Vec(cert), "]"); print("NPLUS1:1"); print("PROVEN:1"),
    print("NPLUS1:-1"); print("PROVEN:", if(v >= 2 && kk < 2^v, llr[2], -1)));
  print("DONE:1");
};

\\ ---------------------------------------------------------------------------
\\ Item 29: probable-prime taxonomy.
\\ ---------------------------------------------------------------------------
pl_taxonomy(n, bases, P, Q, selfridge, budget) =
{
  if(n < 3 || n % 2 == 0, error("Pseudoprime taxonomy applies to odd integers at least 3"));
  my(r, prime_status, a, chain, sel, D, lt, ok);
  print("N:", n);
  r = pl_budget(budget, () -> isprime(n));
  prime_status = if(r[1] == 0, -1, r[2]);
  print("PRIME:", prime_status);
  for(i = 1, #bases,
    a = bases[i] % n;
    if(a == 0 || gcd(a, n) > 1,
      print("TAX:Fermat|a=", bases[i], "|0|gcd(a, n) > 1");
      print("TAX:Euler|a=", bases[i], "|0|gcd(a, n) > 1");
      print("TAX:Strong|a=", bases[i], "|0|gcd(a, n) > 1");
      next();
    );
    ok = Mod(a, n)^(n - 1) == 1;
    print("TAX:Fermat|a=", bases[i], "|", ok, "|a^(n-1) = 1 mod n");
    ok = lift(Mod(a, n)^((n - 1) / 2)) == kronecker(a, n) % n;
    print("TAX:Euler|a=", bases[i], "|", ok, "|a^((n-1)/2) = (a/n) mod n");
    chain = pl_strong_chain(n, a);
    print("TAX:Strong|a=", bases[i], "|", chain[1], "|n-1 = 2^", chain[2], " * ", chain[3], "; chain ", pl_chain_text(chain[4]));
  );
  if(selfridge,
    sel = pl_selfridge(n)
  ,
    if(P^2 - 4 * Q == 0, error("The Lucas discriminant P^2 - 4Q must be nonzero"));
    sel = [P^2 - 4 * Q, P, Q]
  );
  if(sel[1] == 0,
    print("TAX:Lucas|Selfridge|0|n is a perfect square");
    print("TAX:Strong Lucas|Selfridge|0|n is a perfect square");
    print("TAX:Frobenius|Selfridge|0|n is a perfect square");
  ,
    D = sel[1]; P = sel[2]; Q = sel[3];
    if(gcd(n, 2 * Q * D) != 1,
      print("TAX:Lucas|P=", P, "; Q=", Q, "|0|gcd(n, 2QD) > 1");
      print("TAX:Strong Lucas|P=", P, "; Q=", Q, "|0|gcd(n, 2QD) > 1");
      print("TAX:Frobenius|P=", P, "; Q=", Q, "|0|gcd(n, 2QD) > 1");
    ,
      lt = pl_lucas_tests_core(n, P, Q);
      print("TAX:Lucas|P=", P, "; Q=", Q, "; D=", D, "|", lt[1], "|U(n - (D/n)) = 0 mod n");
      print("TAX:Strong Lucas|P=", P, "; Q=", Q, "; D=", D, "|", lt[2], "|U(d) = 0 or V(d 2^r) = 0 mod n");
      print("TAX:Frobenius|P=", P, "; Q=", Q, "; D=", D, "|", pl_frobenius(n, P, Q), "|x^n = Frobenius image mod (n, x^2 - Px + Q)");
    );
  );
  print("TAX:Baillie-PSW|PARI ispseudoprime|", ispseudoprime(n), "|strong base 2 and strong Lucas");
  print("DONE:1");
};

\\ ---------------------------------------------------------------------------
\\ Item 30: Carmichael-number analysis and Chernick construction.
\\ ---------------------------------------------------------------------------
pl_carmichael(n, base_limit, budget) =
{
  if(n < 3, error("Carmichael analysis requires an integer at least 3"));
  my(r, f, squarefree = 1, korselt = 1, composite, liars = 1, lambda, cyc, passes = 0, fails = 0,
     tested = 0, upper, phi);
  print("N:", n);
  r = pl_budget(budget, () -> factor(n));
  if(r[1] == 0, print("FACTOR_STATUS:timeout"); print("CARMICHAEL:-1"); print("DONE:1"); return());
  f = r[2]; print("FACTOR_STATUS:complete");
  composite = matsize(f)[1] > 1 || f[1, 2] > 1;
  for(i = 1, matsize(f)[1],
    print("FACTOR:", f[i, 1], "|", f[i, 2], "|", (n - 1) % (f[i, 1] - 1));
    if(f[i, 2] > 1, squarefree = 0);
    if((n - 1) % (f[i, 1] - 1), korselt = 0);
    liars *= gcd(f[i, 1] - 1, n - 1);
  );
  \\ lambda(n) is the largest invariant factor of (Z/nZ)^*, supplied by PARI znstar;
  \\ the factorization computed above is reused so it is not recomputed.
  cyc = znstar([n, f])[2];
  lambda = if(#cyc == 0, 1, cyc[1]);
  phi = eulerphi(n);
  print("COMPOSITE:", composite); print("SQUAREFREE:", squarefree); print("KORSELT:", korselt);
  print("ODD:", n % 2); print("PRIME_FACTORS:", matsize(f)[1]);
  print("CARMICHAEL:", composite && squarefree && korselt && n % 2 == 1);
  print("LAMBDA:", lambda); print("LAMBDA_DIVIDES:", (n - 1) % lambda == 0);
  print("FERMAT_LIARS:", if(composite, liars, phi)); print("TOTIENT:", phi);
  upper = min(n - 1, base_limit);
  for(a = 2, upper,
    if(gcd(a, n) != 1, next());
    tested++;
    if(Mod(a, n)^(n - 1) == 1, passes++, fails++);
  );
  print("BASES_TESTED:", tested); print("BASES_PASSED:", passes); print("BASES_FAILED:", fails);
  print("EXHAUSTIVE:", upper >= n - 1);
  print("DONE:1");
};

pl_chernick(k_start, k_end, limit) =
{
  if(k_start < 1 || k_end < k_start, error("Invalid Chernick parameter range"));
  my(found = 0, truncated = 0, p1, p2, p3, m);
  for(k = k_start, k_end,
    p1 = 6 * k + 1; if(!isprime(p1), next());
    p2 = 12 * k + 1; if(!isprime(p2), next());
    p3 = 18 * k + 1; if(!isprime(p3), next());
    if(found >= limit, truncated = 1; break());
    m = p1 * p2 * p3;
    print("CHERNICK:", k, "|", p1, "|", p2, "|", p3, "|", m, "|",
          (m - 1) % (p1 - 1) == 0 && (m - 1) % (p2 - 1) == 0 && (m - 1) % (p3 - 1) == 0);
    found++;
  );
  print("TRUNCATED:", truncated); print("DONE:", found);
};

\\ ---------------------------------------------------------------------------
\\ Item 36: generalized repunit primes (b^n - 1)/(b - 1).
\\ ---------------------------------------------------------------------------
pl_repunit(b, n_start, n_end, limit, budget) =
{
  if(b < 2 || n_start < 1 || n_end < n_start, error("Invalid generalized repunit search"));
  my(found = 0, truncated = 0, inconclusive = 0, value, r, status, tested = 0);
  for(n = n_start, n_end,
    if(n < 2 || !isprime(n), next());
    value = (b^n - 1) / (b - 1); tested++;
    if(!ispseudoprime(value), next());
    r = pl_budget(budget, () -> isprime(value));
    status = if(r[1] == 0, -1, r[2]);
    if(status == -1, inconclusive++);
    if(status != 0,
      if(found >= limit, truncated = 1; break());
      print("REPUNIT:", n, "|", #digits(value), "|", status, "|", if(#digits(value) <= 20000, value, 0));
      found++;
    );
  );
  print("TESTED:", tested); print("INCONCLUSIVE:", inconclusive); print("TRUNCATED:", truncated);
  print("DONE:", found);
};

\\ ---------------------------------------------------------------------------
\\ Item 37: Sierpiński/Riesel explorer and exact covering-set verification.
\\ ---------------------------------------------------------------------------
pl_sierpinski_search(k, kind, n_max, budget) =
{
  if(k < 1 || n_max < 1 || (kind != 1 && kind != -1), error("Invalid Sierpinski/Riesel search"));
  my(N, r, tested = 0);
  print("K:", k);
  for(n = 1, n_max,
    N = k * 2^n + kind; tested++;
    if(N < 2 || !ispseudoprime(N), next());
    r = pl_budget(budget, () -> isprime(N));
    if(r[1] == 0,
      print("PROBABLE:", n); print("STATUS:probable"); print("TESTED:", tested); print("DONE:1"); return();
    );
    if(r[2],
      print("FOUND:", n, "|", #digits(N), "|", if(#digits(N) <= 20000, N, 0));
      print("STATUS:found"); print("TESTED:", tested); print("DONE:1"); return();
    );
  );
  print("STATUS:exhausted"); print("TESTED:", tested); print("DONE:1");
};

pl_covering_set(k, kind, period, candidates) =
{
  if(k < 1 || period < 1 || (kind != 1 && kind != -1), error("Invalid covering-set request"));
  my(set = candidates, covered = 1, hit, N, used = Map(), periodic = 1);
  if(#set == 0, set = factor(2^period - 1)[, 1]~);
  for(i = 1, #set,
    if(!isprime(set[i]), error("Covering-set members must be proven primes"));
    if(Mod(2, set[i])^period != 1, periodic = 0; print("NOT_PERIODIC:", set[i]));
  );
  print("PERIOD:", period); print("PERIODIC:", periodic);
  for(i = 1, #set, print("CANDIDATE:", set[i]));
  for(n = 0, period - 1,
    N = k * 2^n + kind; hit = 0;
    for(i = 1, #set, if(N % set[i] == 0, hit = set[i]; mapput(used, set[i], 1); break()));
    print("COVER:", n, "|", hit);
    if(hit == 0, covered = 0);
  );
  print("COVERED:", covered && periodic);
  print("SIZE_CONDITION:", k * 2 + kind > vecmax(set));
  my(keys = Vec(used)); keys = vecsort(keys);
  for(i = 1, #keys, print("USED:", keys[i]));
  print("DONE:", period);
};

\\ ---------------------------------------------------------------------------
\\ Item 40: bi-twin chains and digit prime ladders.
\\ ---------------------------------------------------------------------------
pl_bitwin(start, finish, min_length, limit) =
{
  if(start < 2 || finish < start || min_length < 1, error("Invalid bi-twin search"));
  my(found = 0, truncated = 0, len, c, members, m);
  forstep(n = start + (start % 2), finish, 2,
    if(n % 4 == 0 && isprime(n / 2 - 1) && isprime(n / 2 + 1), next());
    len = 0; c = n;
    while(isprime(c - 1) && isprime(c + 1), len++; c *= 2);
    if(len >= min_length,
      if(found >= limit, truncated = 1; break());
      members = ""; m = n;
      for(i = 1, len, members = concat(concat(members, if(i == 1, "", " ")), concat(concat(Str(m - 1), "/"), Str(m + 1))); m *= 2);
      print("BITWIN:", n, "|", len, "|", members); found++;
    );
  );
  print("TRUNCATED:", truncated); print("DONE:", found);
};

pl_prime_ladder(a, b, max_steps) =
{
  if(a < 2 || b < 2 || !isprime(a) || !isprime(b), error("Prime ladders need two proven primes"));
  if(#digits(a) != #digits(b), error("Both primes must have the same number of digits"));
  my(width = #digits(a), parent = Map(), frontier = List([a]), next_frontier, steps = 0, found = a == b,
     digs, cand, path, cur);
  mapput(parent, a, 0);
  while(!found && #frontier && steps < max_steps,
    next_frontier = List(); steps++;
    for(i = 1, #frontier,
      cur = frontier[i]; digs = digits(cur);
      for(pos = 1, width,
        for(dgt = 0, 9,
          if(dgt == digs[pos] || (pos == 1 && dgt == 0), next());
          cand = cur + (dgt - digs[pos]) * 10^(width - pos);
          if(mapisdefined(parent, cand) || !isprime(cand), next());
          mapput(parent, cand, cur); listput(next_frontier, cand);
          if(cand == b, found = 1; break(3));
        );
      );
    );
    frontier = next_frontier;
  );
  print("VISITED:", #parent);
  if(found,
    path = List(); cur = b;
    while(cur != 0, listput(path, cur); cur = mapget(parent, cur));
    for(i = 1, #path, print("RUNG:", i - 1, "|", path[#path + 1 - i]));
    print("STATUS:found"); print("DONE:", #path);
  ,
    print("STATUS:", if(#frontier == 0, "none", "bound")); print("DONE:0");
  );
};

\\ ---------------------------------------------------------------------------
\\ Items 42 and 43: constrained and Gordon strong primes with proofs.
\\ ---------------------------------------------------------------------------
pl_emit_certificate(p, budget) =
{
  my(r = pl_budget(budget, () -> primecert(p)));
  if(r[1] == 0 || r[2] == 0, print("CERT_STATUS:-1"); return());
  print("CERT_STATUS:", primecertisvalid(r[2]));
  print("CERTBEGIN"); print(primecertexport(r[2])); print("CERTEND");
  print("CERTDATABEGIN"); print(r[2]); print("CERTDATAEND");
};

pl_next_in_class(c, modulus, residue) = c + ((residue - c) % modulus);

\\ Map a raw random draw into the lower half of [2^(bits-1), 2^bits - 1] so that a
\\ CSPRNG seed supplied by the caller never has to be scaled outside PARI/GP.
pl_seed_start(bits, seed) = 2^(bits - 1) + (abs(seed) % 2^(bits - 2));

pl_constrained_prime(bits, modulus, residue, kind, seeds, certificate, budget, candidate_limit) =
{
  if(bits < 8 || modulus < 1 || residue < 0 || residue >= modulus, error("Invalid constrained-prime request"));
  my(lower = 2^(bits - 1), upper = 2^bits - 1, c, q, tested = 0, r, s, t, rr, p0, j, step, found = 0);
  if(kind == 0,
    c = pl_next_in_class(pl_seed_start(bits, seeds[1]), modulus, residue);
    while(c <= upper && tested < candidate_limit,
      tested++;
      if(ispseudoprime(c),
        r = pl_budget(budget, () -> isprime(c));
        if(r[1] == 0, print("CANDIDATE:", c); print("STATUS:probable"); print("TESTED:", tested); print("DONE:1"); return());
        if(r[2], found = c; break());
      );
      c += modulus;
    );
  );
  if(kind == 1,
    c = pl_next_in_class(pl_seed_start(bits, seeds[1]), modulus, residue);
    if(c % 2 == 0, c += modulus);
    while(c <= upper && tested < candidate_limit,
      tested++;
      if(c % 2 == 1 && ispseudoprime(c) && ispseudoprime((c - 1) / 2),
        q = (c - 1) / 2;
        r = pl_budget(budget, () -> isprime(c) && isprime(q));
        if(r[1] == 0, print("CANDIDATE:", c); print("STATUS:probable"); print("TESTED:", tested); print("DONE:1"); return());
        if(r[2], found = c; print("Q:", q); break());
      );
      c += modulus;
    );
  );
  if(kind == 2,
    \\ Gordon's algorithm: s, t proven primes; r = 2it + 1 prime; p0 = 2(s^(r-2) mod r)s - 1; p = p0 + 2jrs.
    my(half = (bits - 24) \ 2);
    s = nextprime(max(2^(half - 1), abs(seeds[1]) % 2^half)); while(!isprime(s), s = nextprime(s + 1));
    t = nextprime(max(2^(half - 1), abs(seeds[2]) % 2^half)); while(!isprime(t), t = nextprime(t + 1));
    if(s == t, t = nextprime(t + 1); while(!isprime(t), t = nextprime(t + 1)));
    rr = 0;
    for(i = 1, 100000, if(isprime(2 * i * t + 1), rr = 2 * i * t + 1; break()));
    if(rr == 0, print("STATUS:exhausted"); print("TESTED:", tested); print("DONE:1"); return());
    p0 = 2 * lift(Mod(s, rr)^(rr - 2)) * s - 1; step = 2 * rr * s;
    j = max(0, (lower - p0 + step - 1) \ step);
    if(gcd(step, modulus) != 1 && modulus > 1, error("The residue condition is incompatible with Gordon's step 2rs"));
    if(modulus > 1, j += lift(Mod((residue - p0 - j * step) / step, modulus)));
    c = p0 + j * step;
    print("S:", s); print("T:", t); print("R:", rr);
    while(c <= upper && tested < candidate_limit,
      tested++;
      if(ispseudoprime(c),
        r = pl_budget(budget, () -> isprime(c));
        if(r[1] == 0, print("CANDIDATE:", c); print("STATUS:probable"); print("TESTED:", tested); print("DONE:1"); return());
        if(r[2], found = c; break());
      );
      c += step * max(1, modulus);
    );
  );
  if(found == 0, print("STATUS:", if(tested >= candidate_limit, "bound", "exhausted")); print("TESTED:", tested); print("DONE:1"); return());
  print("PRIME:", found); print("BITS:", #binary(found)); print("RESIDUE_OK:", found % modulus == residue);
  print("STATUS:proven"); print("TESTED:", tested);
  if(certificate, pl_emit_certificate(found, budget));
  print("DONE:1");
};

\\ ---------------------------------------------------------------------------
\\ Item 130: structured proof steps for the educational viewer.
\\ ---------------------------------------------------------------------------
pl_lucas_lehmer_steps(p, show_limit) =
{
  if(p < 2 || !isprime(p), error("The Mersenne exponent must be prime"));
  my(M = 2^p - 1, s = 4);
  print("N:", M);
  if(p == 2, s = 0);
  for(i = 1, p - 2,
    s = (s^2 - 2) % M;
    if(i <= show_limit || i == p - 2, print("STEP:", i, "|", if(#digits(s) <= 5000, s, 0)));
  );
  print("ITERATIONS:", max(p - 2, 0));
  print("SHOWN:", min(max(p - 2, 0), show_limit)); print("PROVEN:", s == 0); print("DONE:1");
};

pl_ecpp_steps(n, budget) =
{
  if(n < 2, error("ECPP certificates require an integer at least 2"));
  my(r = pl_budget(budget, () -> primecert(n)), c, N, t, s, a, P, b, m, q, D);
  print("N:", n);
  if(r[1] == 0, print("PROVEN:-1"); print("DONE:0"); return());
  c = r[2];
  if(c == 0, print("PROVEN:0"); print("DONE:0"); return());
  if(type(c) == "t_INT", print("SMALL:1"); print("PROVEN:", isprime(c)); print("DONE:0"); return());
  for(i = 1, #c,
    N = c[i][1]; t = c[i][2]; s = c[i][3]; a = c[i][4]; P = c[i][5];
    m = N + 1 - t; q = m / s; D = coredisc(t^2 - 4 * N);
    b = (P[2]^2 - P[1]^3 - a * P[1]) % N;
    print("ECPP:", i, "|", N, "|", t, "|", s, "|", a, "|", b, "|", P[1], "|", P[2], "|", m, "|", q, "|", D);
  );
  print("VALID:", primecertisvalid(c)); print("PROVEN:", primecertisvalid(c)); print("DONE:", #c);
};
