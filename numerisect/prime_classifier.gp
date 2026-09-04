\\ Numerisect prime-classification engine for PARI/GP.
\\ All membership calculations in this file execute inside PARI/GP.

pc_yes(detail = "") = [1, detail];
pc_no() = [0, ""];
pc_unknown(reason) = [-1, reason];

pc_emit(id, result) =
{
  if (result[1] == 1,
    print("CLASS:", id, ":", result[2]),
    if (result[1] == -1, print("UNKNOWN:", id, ":", result[2]))
  );
};

pc_run(id, closure, seconds) =
{
  my(result = alarm(seconds, closure()));
  if (type(result) == "t_ERROR",
    print("UNKNOWN:", id, ":time budget exceeded"),
    pc_emit(id, result)
  );
};

pc_contains(values, value) = setsearch(Set(values), value) != 0;
pc_power_of_two(n) = n > 0 && n == 2^valuation(n, 2);

pc_next_prime(n) =
{
  my(q = nextprime(n));
  while (!isprime(q), q = nextprime(q + 1));
  q;
};

pc_previous_prime(n) =
{
  my(q = precprime(n));
  while (q >= 2 && !isprime(q), q = precprime(q - 1));
  q;
};

pc_balanced(p) =
{
  if (p == 2, return(pc_no()));
  my(lo = pc_previous_prime(p - 1), hi = pc_next_prime(p + 1));
  if (p - lo == hi - p, pc_yes(Str("neighbors ", lo, " and ", hi)), pc_no());
};

pc_chen(p) =
{
  my(q = p + 2);
  if (isprime(q), return(pc_yes(Str(q, " is prime"))));
  if (bigomega(q) == 2, pc_yes(Str(q, " is semiprime")), pc_no());
};

pc_circular(p) =
{
  my(d = digits(p), n = #digits(p));
  if (n == 1, return(pc_yes()));
  for (i = 1, n - 1,
    d = concat(d[2..n], d[1]);
    if (!isprime(fromdigits(d)), return(pc_no()));
  );
  pc_yes();
};

pc_cluster(p) =
{
  if (p == 2, return(pc_no()));
  if (p == 3, return(pc_yes()));
  if (p > 100000, return(pc_unknown("exact difference coverage is limited to p <= 100000")));
  my(pr = primes([2, p]), covered = vector((p - 3) \ 2, i, 0));
  for (i = 2, #pr,
    for (j = 1, i - 1,
      my(delta = pr[i] - pr[j]);
      if (delta % 2 == 0, covered[delta \ 2] = 1);
    );
  );
  if (vecmin(covered), pc_yes(), pc_no());
};

pc_pair(p, delta, lower_limit) =
{
  my(v = List());
  if (p > lower_limit && isprime(p - delta), listput(v, p - delta));
  if (isprime(p + delta), listput(v, p + delta));
  if (#v, pc_yes(Str("partners ", Vec(v))), pc_no());
};

pc_cuban(p) =
{
  my(a = 4 * p - 1, b = 4 * (p - 1));
  if (a % 3 == 0 && issquare(a \ 3), return(pc_yes("type 1")));
  if (b % 3 == 0 && issquare(b \ 3), return(pc_yes("type 2")));
  pc_no();
};

pc_n_times_2n(m) =
{
  if (m <= 0, return(0));
  my(t = valuation(m, 2), odd = m \ 2^t, n);
  for (s = 0, logint(t + 1, 2) + 1,
    n = odd * 2^s;
    if (n + s == t, return(n));
  );
  0;
};

pc_cullen(p) =
{
  my(n = pc_n_times_2n(p - 1));
  if (n, pc_yes(Str("n = ", n)), pc_no());
};

pc_delicate(p) =
{
  my(d = digits(p), old, q);
  for (i = 1, #d,
    old = d[i];
    for (replacement = 0, 9,
      if (replacement != old,
        d[i] = replacement; q = fromdigits(d);
        if (isprime(q), d[i] = old; return(pc_no()));
      );
    );
    d[i] = old;
  );
  pc_yes();
};

pc_dihedral(p) =
{
  my(d = digits(p), up = [0,1,2,-1,-1,5,-1,-1,8,-1]);
  my(mirror = [0,1,5,-1,-1,2,-1,-1,8,-1], u = 0, m = 0, um = 0, x);
  for (i = 1, #d, if (up[d[i] + 1] < 0 || mirror[d[i] + 1] < 0, return(pc_no())));
  for (i = 1, #d,
    x = d[#d - i + 1];
    u = 10 * u + up[x + 1];
    m = 10 * m + mirror[x + 1];
    um = 10 * um + up[mirror[d[i] + 1] + 1];
  );
  if (isprime(u) && isprime(m) && isprime(um), pc_yes(Str("transforms ", u, ", ", m, ", ", um)), pc_no());
};

pc_double_mersenne(p) =
{
  my(e, q);
  if (!pc_power_of_two(p + 1), return(pc_no()));
  e = valuation(p + 1, 2);
  if (!pc_power_of_two(e + 1), return(pc_no()));
  q = valuation(e + 1, 2);
  if (isprime(q), pc_yes(Str("exponent prime ", q)), pc_no());
};

pc_emirp(p) =
{
  my(r = fromdigits(Vecrev(digits(p))));
  if (r != p && isprime(r), pc_yes(Str("reverse ", r)), pc_no());
};

pc_factorial(p) =
{
  my(f = 1, n = 1);
  while (f <= p + 1,
    if (f == p - 1, return(pc_yes(Str(n, "! + 1"))));
    if (f == p + 1, return(pc_yes(Str(n, "! - 1"))));
    n++; f *= n;
  );
  pc_no();
};

pc_fermat(p) =
{
  my(e);
  if (!pc_power_of_two(p - 1), return(pc_no()));
  e = valuation(p - 1, 2);
  if (pc_power_of_two(e), pc_yes(Str("F_", valuation(e, 2))), pc_no());
};

pc_fibonacci(p) = if (issquare(5 * p^2 + 4) || issquare(5 * p^2 - 4), pc_yes(), pc_no());

pc_fortunate(p) =
{
  if (p > 1000, return(pc_unknown("exact Fortunate search is limited to candidate p <= 1000")));
  my(product = 1, q = 2, n = 0, following, fortunate);
  while (q < p,
    n++; product *= q;
    following = pc_next_prime(product + 2);
    fortunate = following - product;
    if (fortunate == p, return(pc_yes(Str("primorial index ", n))));
    q = pc_next_prime(q + 1);
  );
  pc_no();
};

pc_good(p) =
{
  if (p == 2, return(pc_no()));
  if (p > 1000000, return(pc_unknown("exact symmetric-prime comparison is limited to p <= 1000000")));
  my(lo = pc_previous_prime(p - 1), hi = pc_next_prime(p + 1));
  while (lo >= 2,
    if (p^2 <= lo * hi, return(pc_no()));
    if (lo == 2, return(pc_yes()));
    lo = pc_previous_prime(lo - 1); hi = pc_next_prime(hi + 1);
  );
  pc_no();
};

pc_happy(p) =
{
  my(n = p, seen = Set());
  while (n != 1,
    if (setsearch(seen, n), return(pc_no()));
    seen = setunion(seen, Set([n]));
    n = vecsum(vector(#digits(n), i, digits(n)[i]^2));
  );
  pc_yes();
};

pc_higgs(p) =
{
  if (p > 100000, return(pc_unknown("exact exponent-2 Higgs search is limited to p <= 100000")));
  if (p == 2, return(pc_yes("exponent 2")));
  my(product = 2, q = 3);
  while (q <= p,
    if (lift(Mod(product, q - 1)^2) == 0,
      if (q == p, return(pc_yes("exponent 2")));
      product *= q;
    );
    q = pc_next_prime(q + 1);
  );
  pc_no();
};

pc_left_right_truncatable(p) =
{
  my(d = digits(p));
  while (#d > 2,
    d = d[2..#d - 1];
    if (#d && !isprime(fromdigits(d)), return(pc_no()));
  );
  pc_yes();
};

pc_left_truncatable(p) =
{
  my(d = digits(p));
  for (i = 2, #d, if (d[i] == 0, return(pc_no())));
  while (#d > 1,
    d = d[2..#d];
    if (!isprime(fromdigits(d)), return(pc_no()));
  );
  pc_yes();
};

pc_lucas(p) = if (issquare(5 * p^2 + 20) || issquare(5 * p^2 - 20), pc_yes(), pc_no());

pc_mersenne(p) =
{
  if (pc_power_of_two(p + 1), pc_yes(Str("exponent ", valuation(p + 1, 2))), pc_no());
};

pc_mills(p) =
{
  my(values = [2,11,1361,2521008887,16022236204009818131831320183,
    4113101149215104800030529537915953170486139623539759933135949994882770404074832568499]);
  if (pc_contains(values, p), return(pc_yes()));
  if (p < values[#values], pc_no(), pc_unknown("membership beyond the tabulated Mills-prime sequence is not established"));
};

pc_minimal(p) =
{
  my(values = [2,3,5,7,11,19,41,61,89,409,449,499,881,991,6469,6949,9001,
    9049,9649,9949,60649,666649,946669,60000049,66000049,66600049]);
  if (pc_contains(values, p), pc_yes(), pc_no());
};

pc_motzkin(p) =
{
  if (p == 2, return(pc_yes("index 2")));
  my(a = 1, b = 1, c, n = 1);
  while (b < p,
    n++; c = ((2 * n + 1) * b + (3 * n - 3) * a) \ (n + 2);
    a = b; b = c;
  );
  if (b == p, pc_yes(Str("index ", n)), pc_no());
};

pc_non_insertable(p) =
{
  my(d = digits(p), n = #d, pow10 = 10, hi, lo, q);
  for (x = 0, 9, if (isprime(p * 10 + x), return(pc_no())));
  for (k = 1, n - 1,
    lo = p % pow10; hi = p \ pow10;
    for (x = 0, 9,
      q = hi * pow10 * 10 + x * pow10 + lo;
      if (isprime(q), return(pc_no()));
    );
    pow10 *= 10;
  );
  for (x = 1, 9, if (isprime(x * 10^n + p), return(pc_no())));
  pc_yes();
};

pc_nsw(p) =
{
  my(a = 1, b = 1, c, n = 1);
  while (b < p, c = 2 * b + a; a = b; b = c; n++);
  if (b == p && n >= 3 && n % 2, pc_yes(Str("index ", n)), pc_no());
};

pc_palindromic(p) = if (digits(p) == Vecrev(digits(p)), pc_yes(), pc_no());

pc_pell(p) =
{
  my(a = 0, b = 1, c, n = 1);
  while (b < p, c = 2 * b + a; a = b; b = c; n++);
  if (b == p, pc_yes(Str("index ", n)), pc_no());
};

pc_pell_lucas(p) =
{
  my(a = 1, b = 1, c, n = 1);
  while (b < p, c = 2 * b + a; a = b; b = c; n++);
  if (b == p && n >= 2, pc_yes(Str("half-companion index ", n)), pc_no());
};

pc_permutable(p) =
{
  my(values = [2,3,5,7,11,13,17,31,37,71,73,79,97,113,131,199,311,337,373,733,919,991]);
  if (pc_contains(values, p), return(pc_yes()));
  my(d = digits(p));
  if (vecmin(d) == 1 && vecmax(d) == 1, return(pc_yes("repunit")));
  if (p < (10^1031 - 1) \ 9, pc_no(), pc_unknown("non-repunit membership beyond the tabulated range is not established"));
};

pc_pierpont(p) =
{
  my(n = p - 1, u = valuation(n, 2)); n \= 2^u;
  my(v = valuation(n, 3)); n \= 3^v;
  if (n == 1, pc_yes(Str("u = ", u, ", v = ", v)), pc_no());
};

pc_pillai(p) =
{
  if (p > 200000, return(pc_unknown("exact factorial-residue search is limited to p <= 200000")));
  my(f = 1);
  for (n = 2, p - 1,
    f = (f * n) % p;
    if ((f + 1) % p == 0 && (p - 1) % n != 0, return(pc_yes(Str("n = ", n))));
  );
  pc_no();
};

pc_prime_quadruplet(p) =
{
  my(patterns = [[-8,-6,-2],[-6,-4,2],[-2,4,6],[2,6,8]], v = List());
  for (i = 1, #patterns,
    if (vecmin(vector(3, j, isprime(p + patterns[i][j]))), listput(v, vector(3, j, p + patterns[i][j])));
  );
  if (#v, pc_yes(Str("companions ", Vec(v))), pc_no());
};

pc_prime_triplet(p) =
{
  my(patterns = [[-6,-4],[-6,-2],[-4,2],[-2,4],[2,6],[4,6]], v = List());
  for (i = 1, #patterns,
    if (isprime(p + patterns[i][1]) && isprime(p + patterns[i][2]),
      listput(v, [p + patterns[i][1], p + patterns[i][2]]));
  );
  if (#v, pc_yes(Str("companions ", Vec(v))), pc_no());
};

pc_is_primorial(n) =
{
  if (n < 2, return(0));
  my(product = 1, q = 2);
  while (product < n, product *= q; if (product == n, return(q)); q = nextprime(q + 1));
  0;
};

pc_primorial(p) =
{
  if (p == 2, return(pc_yes("2")));
  my(q = pc_is_primorial(p - 1));
  if (q, return(pc_yes(Str(q, "# + 1"))));
  q = pc_is_primorial(p + 1);
  if (q, pc_yes(Str(q, "# - 1")), pc_no());
};

pc_proth(p) =
{
  my(k = p - 1, n = valuation(k, 2)); k \= 2^n;
  if (n > 0 && k % 2 && 2^n > k, pc_yes(Str("k = ", k, ", n = ", n)), pc_no());
};

pc_quartan(p) =
{
  my(solution = qfbsolve(Qfb(1, 0, 1), p), x, y);
  if (#solution != 2, return(pc_no()));
  if (issquare(abs(solution[1]), &x) && issquare(abs(solution[2]), &y),
    pc_yes(Str("", x, "^4 + ", y, "^4")), pc_no());
};

pc_repunit(p) =
{
  my(d = digits(p));
  if (vecmin(d) == 1 && vecmax(d) == 1, pc_yes(Str(#d, " digits")), pc_no());
};

pc_right_truncatable(p) =
{
  my(n = p);
  while (n >= 10, n \= 10; if (!isprime(n), return(pc_no())));
  pc_yes();
};

pc_strobogrammatic(p) =
{
  my(d = digits(p), up = [0,1,-1,-1,-1,-1,9,-1,8,6], n = 0, x);
  for (i = 1, #d,
    x = up[d[#d - i + 1] + 1]; if (x < 0, return(pc_no())); n = 10 * n + x;
  );
  if (n == p, pc_yes(), pc_no());
};

pc_strong(p) =
{
  if (p == 2, return(pc_no()));
  my(lo = pc_previous_prime(p - 1), hi = pc_next_prime(p + 1));
  if (2 * p > lo + hi, pc_yes(Str("neighbors ", lo, " and ", hi)), pc_no());
};

pc_superprime(p) =
{
  if (p > 10^12, return(pc_unknown("exact prime indexing is limited to p <= 10^12")));
  my(index = primepi(p));
  if (isprime(index), pc_yes(Str("prime index ", index)), pc_no());
};

pc_supersingular(p) =
{
  if (pc_contains([2,3,5,7,11,13,17,19,23,29,31,41,47,59,71], p), pc_yes(), pc_no());
};

pc_wagstaff(p) =
{
  my(n = 3 * p - 1);
  if (!pc_power_of_two(n), return(pc_no()));
  my(e = valuation(n, 2));
  if (e % 2 && isprime(e), pc_yes(Str("exponent ", e)), pc_no());
};

pc_wieferich(p) = if (lift(Mod(2, p^2)^(p - 1)) == 1, pc_yes("base 2"), pc_no());

pc_williams_for_base(p, b) =
{
  if ((p + 1) % (b - 1), return(0));
  my(q = (p + 1) \ (b - 1), n = 0);
  while (q % b == 0, q \= b; n++);
  if (q == 1 && n >= 1, n, 0);
};

pc_williams(p) =
{
  my(matches = List(), n);
  for (b = 3, 9, n = pc_williams_for_base(p, b); if (n, listput(matches, Str("base ", b, ", n = ", n))));
  if (#matches, pc_yes(Str(Vec(matches))), pc_no());
};

pc_wilson(p) =
{
  if (pc_contains([5,13,563], p), return(pc_yes()));
  if (p < 20000000000000, pc_no(), pc_unknown("membership above the published exhaustive bound is not established"));
};

pc_wolstenholme(p) =
{
  if (pc_contains([16843,2124679], p), return(pc_yes()));
  if (p < 1000000000, pc_no(), pc_unknown("membership above the published exhaustive bound is not established"));
};

pc_woodall(p) =
{
  my(n = pc_n_times_2n(p + 1));
  if (n, pc_yes(Str("n = ", n)), pc_no());
};

classify_prime(p, seconds = 2) =
{
  my(prime = isprime(p));
  print("PRIME:", prime);
  if (!prime, return());

  pc_run("balanced", ()->pc_balanced(p), seconds);
  pc_run("chen", ()->pc_chen(p), seconds);
  pc_run("circular", ()->pc_circular(p), seconds);
  pc_run("cluster", ()->pc_cluster(p), seconds);
  pc_run("cousin", ()->pc_pair(p, 4, 5), seconds);
  pc_run("cuban", ()->pc_cuban(p), seconds);
  pc_run("cullen", ()->pc_cullen(p), seconds);
  pc_run("delicate", ()->pc_delicate(p), seconds);
  pc_run("dihedral", ()->pc_dihedral(p), seconds);
  pc_run("double_mersenne", ()->pc_double_mersenne(p), seconds);
  pc_run("emirp", ()->pc_emirp(p), seconds);
  pc_emit("even", if (p == 2, pc_yes(), pc_no()));
  pc_run("factorial", ()->pc_factorial(p), seconds);
  pc_emit("fermat", pc_fermat(p));
  pc_emit("fibonacci", pc_fibonacci(p));
  pc_run("fortunate", ()->pc_fortunate(p), seconds);
  pc_run("good", ()->pc_good(p), seconds);
  pc_emit("happy", pc_happy(p));
  pc_run("higgs", ()->pc_higgs(p), seconds);
  pc_run("left_and_right_truncatable", ()->pc_left_right_truncatable(p), seconds);
  pc_run("left_truncatable", ()->pc_left_truncatable(p), seconds);
  pc_emit("lucas", pc_lucas(p));
  pc_emit("mersenne", pc_mersenne(p));
  pc_emit("mills", pc_mills(p));
  pc_emit("minimal", pc_minimal(p));
  pc_run("motzkin", ()->pc_motzkin(p), seconds);
  pc_run("non_insertable", ()->pc_non_insertable(p), seconds);
  pc_run("newman_shanks_williams", ()->pc_nsw(p), seconds);
  pc_emit("palindromic", pc_palindromic(p));
  pc_run("pell", ()->pc_pell(p), seconds);
  pc_run("pell_lucas", ()->pc_pell_lucas(p), seconds);
  pc_emit("permutable", pc_permutable(p));
  pc_emit("pierpont", pc_pierpont(p));
  pc_run("pillai", ()->pc_pillai(p), seconds);
  pc_run("prime_quadruplet", ()->pc_prime_quadruplet(p), seconds);
  pc_run("prime_triplet", ()->pc_prime_triplet(p), seconds);
  pc_run("primorial", ()->pc_primorial(p), seconds);
  pc_emit("proth", pc_proth(p));
  pc_emit("pythagorean", if ((p - 1) % 4 == 0, pc_yes(), pc_no()));
  pc_run("quartan", ()->pc_quartan(p), seconds);
  pc_emit("repunit", pc_repunit(p));
  pc_run("right_truncatable", ()->pc_right_truncatable(p), seconds);
  pc_run("safe", ()->if (p > 2 && isprime((p - 1) \ 2), pc_yes(Str("Sophie Germain partner ", (p - 1) \ 2)), pc_no()), seconds);
  pc_run("sexy", ()->pc_pair(p, 6, 7), seconds);
  pc_run("sophie_germain", ()->if (isprime(2 * p + 1), pc_yes(Str("safe partner ", 2 * p + 1)), pc_no()), seconds);
  pc_emit("strobogrammatic", pc_strobogrammatic(p));
  pc_run("strong", ()->pc_strong(p), seconds);
  pc_run("superprime", ()->pc_superprime(p), seconds);
  pc_emit("supersingular", pc_supersingular(p));
  pc_run("twin", ()->pc_pair(p, 2, 3), seconds);
  pc_emit("wagstaff", pc_wagstaff(p));
  pc_run("wieferich", ()->pc_wieferich(p), seconds);
  pc_emit("williams", pc_williams(p));
  pc_emit("wilson", pc_wilson(p));
  pc_emit("wolstenholme", pc_wolstenholme(p));
  pc_emit("woodall", pc_woodall(p));
};
