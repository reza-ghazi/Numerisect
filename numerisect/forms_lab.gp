\\ Numerisect binary-quadratic-forms and continued-fraction laboratory for PARI/GP.
\\
\\ Two workbenches share this driver.  The first is the classical theory of binary
\\ quadratic forms: reduction, composition, exponentiation, prime forms, class numbers
\\ and class-group structure, enumeration of the reduced forms of a discriminant, and
\\ representation of an integer by a form.  The second is continued fractions: the
\\ expansion of a rational or a quadratic irrational, its convergents, the period of
\\ sqrt(d) and its palindromic structure, best rational approximations, and the
\\ fundamental solution of Pell's equation together with further solutions.
\\
\\ Python validates requests and parses the tagged protocol; every calculation is a
\\ PARI/GP routine call.  This file is a driver over PARI's own routines, not a
\\ reimplementation of them:
\\   fl_reduce           Qfb, qfbred, qfbred(.,1), qfbredsl2, matdet, quaddisc,
\\                       isfundamental, sqrtint, gcd
\\   fl_compose          qfbcomp, qfbcompraw, qfbpow, qfbpowraw, qfbprimeform, qfbred
\\   fl_primeform        qfbprimeform, qfbred, kronecker, isprime
\\   fl_class_group      qfbclassno, quadclassunit, qfbhclassno, quaddisc, isfundamental
\\   fl_reduced_forms    quadclassunit, qfbpow, qfbcomp, qfbred, qfbred(.,1), issquare
\\   fl_represent        qfbsolve, gcd
\\   fl_contfrac         contfrac, contfracpnqn, bestappr, sqrtint, issquare
\\   fl_pell             quadunit, quadregulator, norm, issquare, bestappr
\\
\\ Two computations have no library routine and are therefore built from PARI
\\ primitives, in the same spirit as the Hensel lift in algebra_lab.gp:
\\
\\   * The exact continued-fraction expansion of a quadratic irrational.  PARI's
\\     contfrac accepts a t_REAL and therefore returns a floating-point expansion whose
\\     tail is unreliable (contfrac(sqrt(13)) at 38 digits ends in a spurious 7).  The
\\     classical (P, Q) recursion below is exact integer arithmetic with sqrtint, it
\\     detects the period by state repetition rather than by guessing, and its emitted
\\     prefix is cross-checked term by term against contfrac at raised precision.
\\   * Enumeration of the reduced forms of a discriminant.  PARI exposes the class group
\\     (quadclassunit) and the reduction operators (qfbred, qfbred(.,1)) but no routine
\\     that lists reduced forms.  The enumeration below is therefore driven entirely by
\\     those routines: class representatives come from the quadclassunit generators
\\     through qfbpow/qfbcomp, and for a positive discriminant each class is expanded
\\     into its cycle by repeated single-step qfbred.
\\
\\ Every operation is bounded.  Exceeding a bound is reported as inconclusive
\\ (COMPLETE:0, or a -1 sentinel), never as a wrong or silently shortened answer.

fl_join(values) =
{
  my(s = "");
  for(i = 1, #values, s = concat(concat(s, if(i > 1, ",", "")), Str(values[i])));
  s;
};

\\ A discriminant is a nonzero integer congruent to 0 or 1 modulo 4.  A square
\\ discriminant makes the form reducible over Q, which PARI's Qfb rejects outright, so
\\ it is refused here with a mathematical explanation instead of an engine error.
fl_check_discriminant(d) =
{
  if(d == 0, error("A discriminant must be nonzero"));
  if(d % 4 > 1, error("A discriminant must be congruent to 0 or 1 modulo 4"));
  if(issquare(d), error("A square discriminant gives a degenerate, reducible form"));
};

fl_invariants(d) =
{
  my(fundamental = quaddisc(d));
  print("DISC:", d);
  print("DEFINITE:", if(d < 0, 1, 0));
  print("FUNDAMENTAL:", isfundamental(d));
  print("FIELD_DISC:", fundamental);
  print("CONDUCTOR:", sqrtint(d \ fundamental));
};

\\ Build the form, refusing the negative-definite case PARI does not implement.
fl_form(a, b, c) =
{
  my(d = b^2 - 4*a*c);
  fl_check_discriminant(d);
  if(d < 0 && a <= 0,
     error("A form of negative discriminant must have a > 0; PARI represents only positive definite forms"));
  Qfb(a, b, c);
};

fl_print_form(tag, f) = print(tag, ":", component(f, 1), "|", component(f, 2), "|", component(f, 3));

\\ A form is ambiguous when a divides b or a = c: the substitution (x, y) -> (x - (b/a)y, y)
\\ in the first case and (x, y) -> (-y, x) in the second carries (a, b, c) to (a, -b, c), so
\\ the class is its own inverse.  For a positive discriminant these are exactly the forms
\\ SQUFOF hunts for in the principal cycle, because an ambiguous form of discriminant 4N
\\ exposes a factor of N in its leading coefficient.
fl_ambiguous(f) =
{
  my(a = component(f, 1), b = component(f, 2), c = component(f, 3));
  if(b % a == 0 || a == c, 1, 0);
};

\\ ---------------------------------------------------------------- reduction
\\ qfbred performs the whole reduction; qfbred(f, 1) performs one step, which is what
\\ makes the trace possible.  qfbredsl2 supplies the SL(2, Z) matrix taking f to it.
fl_reduce(a, b, c, step_cap, cycle_cap) =
{
  my(f = fl_form(a, b, c), d = b^2 - 4*a*c, reduced, sl2, g, current, steps = List(),
     emitted, cycle = -1, previous);
  fl_invariants(d);
  print("CONTENT:", gcd(gcd(a, b), c));
  fl_print_form("INPUT", f);
  reduced = qfbred(f);
  fl_print_form("REDUCED", reduced);
  sl2 = qfbredsl2(f);
  g = sl2[2];
  print("MATRIX:", g[1, 1], "|", g[1, 2], "|", g[2, 1], "|", g[2, 2]);
  print("MATDET:", matdet(g));
  print("SL2_AGREES:", if(sl2[1] == reduced, 1, 0));
  current = f;
  for(i = 1, step_cap,
    previous = current;
    current = qfbred(current, 1);
    listput(steps, [component(current, 1), component(current, 2), component(current, 3)]);
    if(d < 0 && current == previous, break());
  );
  emitted = #steps;
  for(i = 1, emitted, print("STEP:", i, "|", steps[i][1], "|", steps[i][2], "|", steps[i][3]));
  if(d > 0,
    \\ Indefinite forms have a cycle of reduced forms rather than a single one; walk it
    \\ with single-step qfbred until the reduced starting point recurs.
    current = reduced; cycle = 0;
    for(i = 1, cycle_cap,
      current = qfbred(current, 1);
      if(current == reduced, cycle = i; break());
    );
    if(cycle == 0, cycle = -1);
  );
  print("CYCLE_LENGTH:", cycle);
  print("AMBIGUOUS:", fl_ambiguous(reduced));
  print("STEPS:", emitted);
  print("TRUNCATED:", if(emitted >= step_cap, 1, 0));
  print("DONE:", emitted);
};

\\ ---------------------------------------------------------------- composition
\\ Whether the class of a form is principal.  For a negative discriminant reduced forms
\\ are unique in their class, so a comparison settles it.  For a positive discriminant
\\ the principal class is a whole cycle, so the cycle is walked; an exhausted cap
\\ returns -1, which the report renders as inconclusive.
fl_is_principal(f, d, cycle_cap) =
{
  my(identity = qfbprimeform(d, 1), reduced = qfbred(f), current);
  if(d < 0, return(if(reduced == qfbred(identity), 1, 0)));
  current = qfbred(identity);
  if(current == reduced, return(1));
  for(i = 1, cycle_cap,
    current = qfbred(current, 1);
    if(current == reduced, return(1));
    if(current == qfbred(identity), return(0));
  );
  -1;
};

fl_compose(a1, b1, c1, a2, b2, c2, exponent, raw_cap, order_cap, cycle_cap) =
{
  my(f = fl_form(a1, b1, c1), g = fl_form(a2, b2, c2), d = b1^2 - 4*a1*c1,
     composed, power, raw_available, order = -1, current, identity);
  if(b2^2 - 4*a2*c2 != d, error("Both forms must have the same discriminant to be composed"));
  fl_invariants(d);
  fl_print_form("LEFT", f);
  fl_print_form("RIGHT", g);
  identity = qfbprimeform(d, 1);
  fl_print_form("PRINCIPAL", identity);
  composed = qfbcomp(f, g);
  fl_print_form("COMP", composed);
  fl_print_form("COMPRAW", qfbcompraw(f, g));
  power = qfbpow(f, exponent);
  fl_print_form("POW", power);
  raw_available = if(abs(exponent) <= raw_cap, 1, 0);
  print("POWRAW_AVAILABLE:", raw_available);
  if(raw_available, fl_print_form("POWRAW", qfbpowraw(f, exponent)));
  print("COMP_PRINCIPAL:", fl_is_principal(composed, d, cycle_cap));
  print("POW_PRINCIPAL:", fl_is_principal(power, d, cycle_cap));
  \\ Order of the class of the left form, by exponentiating with qfbpow until the
  \\ principal class recurs.  An exhausted cap reports -1.
  for(i = 1, order_cap,
    if(fl_is_principal(qfbpow(f, i), d, cycle_cap) == 1, order = i; break());
  );
  print("ORDER:", order);
  print("EXPONENT:", exponent);
  print("DONE:1");
};

\\ ---------------------------------------------------------------- prime forms
\\ qfbprimeform(d, p) is defined exactly when d is a square modulo 4p; PARI raises an
\\ error otherwise, which is caught and reported as "not represented".
fl_primeform(d, primes) =
{
  my(f, emitted = 0);
  fl_check_discriminant(d);
  fl_invariants(d);
  for(i = 1, #primes,
    my(p = primes[i], k = kronecker(d, p), reduced);
    f = iferr(qfbprimeform(d, p), E, 0);
    if(type(f) == "t_QFB",
      reduced = qfbred(f);
      print("PRIME:", p, "|form|", component(f, 1), "|", component(f, 2), "|", component(f, 3),
            "|", component(reduced, 1), "|", component(reduced, 2), "|", component(reduced, 3),
            "|", k, "|", isprime(p), "|", fl_ambiguous(reduced));
    ,
      print("PRIME:", p, "|none|0|0|0|0|0|0|", k, "|", isprime(p), "|0");
    );
    emitted++;
  );
  print("DONE:", emitted);
};

\\ ---------------------------------------------------------------- class group
fl_class_group(d, gen_cap) =
{
  my(h, structure, generators, emitted = 0);
  fl_check_discriminant(d);
  fl_invariants(d);
  h = qfbclassno(d);
  print("CLASSNO:", h);
  structure = quadclassunit(d);
  print("QCU_CLASSNO:", structure[1]);
  print("AGREE:", if(structure[1] == h, 1, 0));
  print("CYC:", if(#structure[2], fl_join(structure[2]), "trivial"));
  print("RANK:", #structure[2]);
  if(d > 0,
    print("REGULATOR:", structure[4]);
    print("FUNDAMENTAL_UNIT_NORM:", norm(quadunit(d)));
  ,
    print("HURWITZ:", qfbhclassno(-d));
  );
  generators = structure[3];
  for(i = 1, min(#generators, gen_cap),
    my(g = qfbred(generators[i]));
    print("GEN:", i, "|", component(g, 1), "|", component(g, 2), "|", component(g, 3),
          "|", structure[2][i], "|", fl_ambiguous(g));
    emitted++;
  );
  print("TRUNCATED:", if(#generators > gen_cap, 1, 0));
  print("DONE:", emitted);
};

\\ ---------------------------------------------------------------- enumeration
\\ Class representatives are the products of the quadclassunit generators raised to
\\ every exponent below their cyclic orders, formed with qfbpow and qfbcomp.  For a
\\ negative discriminant each class contains exactly one reduced form; for a positive
\\ discriminant each class is a cycle of reduced forms, expanded with single-step
\\ qfbred.  Class 1 is the principal class, and for a positive discriminant its cycle
\\ is the one SQUFOF walks.
fl_reduced_forms(d, form_cap, cycle_cap) =
{
  my(structure, cyc, gens, h, odometer, rep, forms = List(), classes = 0, complete = 1,
     principal_cycle = -1, ambiguous = 0, current, start, class_size);
  fl_check_discriminant(d);
  fl_invariants(d);
  h = qfbclassno(d);
  print("CLASSNO:", h);
  structure = quadclassunit(d);
  cyc = structure[2]; gens = structure[3];
  odometer = vector(#cyc, i, 0);
  for(index = 1, structure[1],
    rep = qfbprimeform(d, 1);
    for(i = 1, #cyc, rep = qfbcomp(rep, qfbpow(gens[i], odometer[i])));
    classes++;
    start = qfbred(rep);
    class_size = 0;
    current = start;
    while(1,
      class_size++;
      if(#forms >= form_cap, complete = 0; break());
      listput(forms, [classes, component(current, 1), component(current, 2),
                      component(current, 3), fl_ambiguous(current),
                      if(issquare(abs(component(current, 1))), 1, 0)]);
      if(fl_ambiguous(current), ambiguous++);
      if(d < 0, break());
      current = qfbred(current, 1);
      if(current == start, break());
      if(class_size >= cycle_cap, complete = 0; break());
    );
    if(index == 1, principal_cycle = if(complete || d < 0, class_size, -1));
    if(!complete, break());
    for(i = 1, #cyc,
      odometer[i]++;
      if(odometer[i] < cyc[i], break());
      odometer[i] = 0;
    );
  );
  for(i = 1, #forms,
    print("FORM:", forms[i][1], "|", forms[i][2], "|", forms[i][3], "|", forms[i][4],
          "|", forms[i][5], "|", forms[i][6]));
  print("CLASSES_SHOWN:", classes);
  print("PRINCIPAL_CYCLE:", principal_cycle);
  print("AMBIGUOUS:", ambiguous);
  print("COMPLETE:", complete);
  print("TRUNCATED:", if(complete, 0, 1));
  print("DONE:", #forms);
};

\\ ---------------------------------------------------------------- representation
\\ qfbsolve(Q, n, 1) returns every primitive solution up to the automorphism group of
\\ Q; flag 3 adds the imprimitive ones.  Each returned pair is substituted back into Q.
fl_represent(a, b, c, n, solution_cap) =
{
  my(f = fl_form(a, b, c), d = b^2 - 4*a*c, primitive, all, emitted = 0, value);
  if(n == 0, error("Choose a nonzero integer to represent"));
  fl_invariants(d);
  fl_print_form("FORM", f);
  print("TARGET:", n);
  primitive = qfbsolve(f, n, 1);
  all = qfbsolve(f, n, 3);
  for(i = 1, min(#all, solution_cap),
    my(x = all[i][1], y = all[i][2]);
    value = a*x^2 + b*x*y + c*y^2;
    if(value != n, error("Internal representation verification failed"));
    print("SOLUTION:", x, "|", y, "|", if(gcd(x, y) == 1, 1, 0), "|", value);
    emitted++;
  );
  print("PRIMITIVE_COUNT:", #primitive);
  print("TOTAL_COUNT:", #all);
  print("REPRESENTED:", if(#all, 1, 0));
  print("TRUNCATED:", if(#all > solution_cap, 1, 0));
  print("DONE:", emitted);
};

\\ ---------------------------------------------------------------- continued fractions
\\ Exact expansion of the quadratic irrational (p + sqrt(d))/q.  Scaling by |q| makes the
\\ state integral: (p + sqrt(d))/q = (p|q| + sqrt(d q^2))/(q|q|).  The state (P, Q) of the
\\ recursion determines the whole tail, so by Lagrange's theorem the expansion is periodic
\\ from the first repeated state; recording states finds the preperiod and the period
\\ exactly rather than guessing where a floating-point expansion starts to repeat.
\\ a_i = floor((P_i + sqrt(D))/Q_i) is exact because D is not a square, so sqrtint(D) may
\\ replace sqrt(D) inside the floor.  Returns [quotients, preperiod, period]; a period of
\\ -1 means the cap was reached first and the expansion is inconclusive.
fl_surd_expansion(p, q, d, quotient_cap) =
{
  my(D = d * q^2, root, P = p * abs(q), Q = q * abs(q), states = Map(),
     quotients = List(), key, a, index = 0);
  root = sqrtint(D);
  while(index < quotient_cap,
    key = Str(P, ",", Q);
    if(mapisdefined(states, key),
      my(preperiod = mapget(states, key) - 1);
      return([quotients, preperiod, index - preperiod]);
    );
    index++;
    mapput(states, key, index);
    a = if(Q > 0, (P + root) \ Q, -((P + root) \ (-Q)) - 1);
    listput(quotients, a);
    P = a*Q - P;
    Q = (D - P^2) / Q;
  );
  [quotients, -1, -1];
};

fl_palindromic(terms) =
{
  my(n = #terms);
  for(i = 1, n \ 2, if(terms[i] != terms[n + 1 - i], return(0)));
  1;
};

\\ Compare the exact expansion with PARI's own contfrac at raised precision.  Only a short
\\ safe prefix is compared: contfrac works on a t_REAL and its tail is unreliable, which is
\\ precisely why the exact recursion above exists.  Returns 1, 0, or -1 for not applicable.
fl_surd_crosscheck(p, q, d, quotients, count) =
{
  my(terms, n = min(count, #quotients));
  if(n < 2, return(-1));
  localprec(2*n + 64);
  terms = Vec(contfrac((p + sqrt(d)) / q, , n));
  n = min(#terms, n) - 1;
  if(n < 1, return(-1));
  for(i = 1, n, if(terms[i] != quotients[i], return(0)));
  1;
};

\\ mode 0: the rational p/q, expanded by PARI's contfrac.
\\ mode 1: the quadratic irrational (p + sqrt(d))/q, expanded exactly by the recursion
\\         above, unrolled through its period up to the cap, and cross-checked.
fl_contfrac(mode, p, q, d, quotient_cap, convergent_cap, appr_bound, check_terms) =
{
  my(quotients, preperiod = -1, period = -1, complete = 1, expansion, matrix, emitted,
     shown, crosscheck = -1, palindromic = -1, approx, target, base, unrolled);
  if(q == 0, error("The denominator must be nonzero"));
  print("MODE:", mode);
  if(mode == 0,
    if(p == 0 && q == 0, error("The rational must be well defined"));
    print("VALUE:", p, "/", q);
    quotients = Vec(contfrac(p / q));
    if(#quotients > quotient_cap, complete = 0);
    quotients = vector(min(#quotients, quotient_cap), i, quotients[i]);
    target = p / q;
  ,
    if(d <= 0, error("The radicand must be a positive integer"));
    if(issquare(d), error("The radicand must not be a perfect square: (p + sqrt(d))/q would be rational"));
    print("VALUE:(", p, "+sqrt(", d, "))/", q);
    expansion = fl_surd_expansion(p, q, d, quotient_cap);
    base = Vec(expansion[1]);
    preperiod = expansion[2]; period = expansion[3];
    if(period < 0,
      complete = 0; quotients = base;
    ,
      \\ Unroll the period so that convergents may run past its first repetition, which is
      \\ where the Pell solution of sqrt(d) appears.
      unrolled = List();
      for(i = 1, #base, listput(unrolled, base[i]));
      while(#unrolled < quotient_cap,
        listput(unrolled, base[preperiod + 1 + ((#unrolled - preperiod) % period)]));
      quotients = Vec(unrolled);
    );
    crosscheck = fl_surd_crosscheck(p, q, d, quotients, check_terms);
    \\ For sqrt(d) itself the period is [a_1, ..., a_{L-1}, 2*a_0] with a palindromic head.
    \\ The flag is reported only for that classical case.
    if(period > 0 && p == 0 && q == 1,
      palindromic = fl_palindromic(vector(period - 1, i, quotients[preperiod + i])));
    target = (p + sqrt(d)) / q;
  );
  emitted = #quotients;
  for(i = 1, emitted, print("QUOTIENT:", i - 1, "|", quotients[i]));
  print("QUOTIENTS:", emitted);
  print("PREPERIOD:", preperiod);
  print("PERIOD:", period);
  if(period > 0,
    print("PERIOD_TERMS:", fl_join(vector(period, i, quotients[preperiod + i]))));
  print("PALINDROMIC:", palindromic);
  print("CROSSCHECK:", crosscheck);
  shown = min(emitted, convergent_cap);
  if(shown > 0,
    matrix = contfracpnqn(vector(shown, i, quotients[i]), shown - 1);
    for(i = 1, shown, print("CONVERGENT:", i - 1, "|", matrix[1, i], "|", matrix[2, i]));
  );
  print("CONVERGENTS:", shown);
  if(mode == 0 && shown > 0 && shown == emitted,
    print("VERIFIED:", if(matrix[1, shown] / matrix[2, shown] == p / q, 1, 0)),
    print("VERIFIED:-1"));
  approx = bestappr(target, appr_bound);
  print("BESTAPPR:", numerator(approx), "|", denominator(approx), "|", appr_bound);
  print("COMPLETE:", complete);
  print("TRUNCATED:", if(complete, 0, 1));
  print("DONE:", emitted);
};

\\ ---------------------------------------------------------------- Pell
\\ The convergent of sqrt(d) at the end of the period is the fundamental solution, so
\\ bestappr with the solution's own denominator must return it.  Skipped, as -1, when the
\\ solution is too large for a floating-point cross-check to be worth its precision.
fl_pell_crosscheck(d, fx, fy, digit_limit) =
{
  if(#Str(fy) > digit_limit, return(-1));
  localprec(4 * #Str(fy) + 64);
  if(bestappr(sqrt(d), fy) == fx / fy, 1, 0);
};

\\ quadunit(4d) is the fundamental unit x + y*sqrt(d) of the order Z[sqrt(d)] of
\\ discriminant 4d, so it *is* the fundamental solution of x^2 - d*y^2 = norm(u).  When
\\ that norm is -1 the negative Pell equation is solvable and the fundamental solution of
\\ x^2 - d*y^2 = 1 is the square of the unit; when it is +1 the negative equation has no
\\ solution.  Powers of the fundamental solution give every further solution.
\\ quadregulator(4d) is the logarithm of the same unit.
fl_pell(d, solution_count, digit_cap, period_cap, check_digits, unit_seconds) =
{
  my(unit, nrm, x, y, fx, fy, current, step, emitted = 0, truncated = 0, expansion,
     period = -1, w);
  if(d < 2, error("Pell's equation needs an integer d of at least 2"));
  if(issquare(d), error("Pell's equation is degenerate when d is a perfect square"));
  print("D:", d);
  unit = alarm(unit_seconds, quadunit(4*d));
  if(type(unit) == "t_ERROR",
    print("AVAILABLE:0"); print("DONE:0"); return();
  );
  print("AVAILABLE:1");
  print("REGULATOR:", quadregulator(4*d));
  x = component(unit, 2); y = component(unit, 3);
  nrm = norm(unit);
  print("UNIT_X:", x); print("UNIT_Y:", y); print("UNIT_NORM:", nrm);
  print("NEGATIVE_SOLVABLE:", if(nrm == -1, 1, 0));
  w = quadgen(4*d);
  current = if(nrm == -1, unit^2, unit);
  fx = component(current, 2); fy = component(current, 3);
  if(fx^2 - d*fy^2 != 1, error("Internal Pell verification failed"));
  print("FUND_X:", fx); print("FUND_Y:", fy);
  expansion = fl_surd_expansion(0, 1, d, period_cap);
  period = expansion[3];
  print("CF_PERIOD:", period);
  print("CF_MATCH:", fl_pell_crosscheck(d, fx, fy, check_digits));
  step = fx + fy*w;
  current = step;
  for(k = 1, solution_count,
    my(sx = component(current, 2), sy = component(current, 3));
    if(#Str(sx) > digit_cap || #Str(sy) > digit_cap, truncated = 1; break());
    if(sx^2 - d*sy^2 != 1, error("Internal Pell verification failed"));
    print("SOLUTION:", k, "|", sx, "|", sy);
    emitted++;
    current = current * step;
  );
  print("VERIFIED:1");
  print("TRUNCATED:", truncated);
  print("DONE:", emitted);
};
