\\ Numerisect application-infrastructure helpers for PARI/GP.
\\
\\ Python validates batch-import syntax and parses the tagged protocol; the
\\ expansion of ranges and polynomial families, and the verification of
\\ catalogue factors, happen here.

ws_expand(idx, f, a, b, cap, maxdigits) =
{
  my(v);
  if(b < a, error("Range end must not precede its start"));
  if(b - a + 1 > cap, error("Range exceeds the configured expansion cap"));
  for(n = a, b,
    v = f(n);
    if(type(v) != "t_INT", error("Family values must be integers"));
    if(sizedigit(v) > maxdigits, error("Family value exceeds the digit limit"));
    print("ITEM:", idx, "|", v);
  );
  print("EXPANDED:", idx, "|", b - a + 1);
};

ws_verify_factors(n, factors) =
{
  my(product = 1);
  if(n == 0, error("Catalogue verification needs a nonzero integer"));
  for(i = 1, #factors,
    if(factors[i] == 0, error("Catalogue factors must be nonzero"));
    product *= factors[i];
    print("FACTOR:", factors[i], "|", isprime(factors[i]), "|", n % factors[i] == 0);
  );
  print("PRODUCT_MATCH:", product == n);
  print("COFACTOR:", if(n % product == 0, n / product, 0));
  print("DONE:", #factors);
};
