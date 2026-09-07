\\ Numerisect Dedekind-zeta and number-field L-function engine for PARI/GP.
\\
\\ PARI/GP owns every computation here.  The field is built with nfinit (bnfinit
\\ when class-group data is requested), the L-function object with lfuncreate,
\\ the functional-equation self-test with lfuncheckfeq, values with lfun, poles
\\ and residues with lfunrootres, and critical-line ordinates with lfunzeros.
\\ Python only validates the request, launches gp, and parses the tagged output.
\\
\\ PARI works with floating-point numbers at a requested realprecision.  Its
\\ results are NOT Arb ball enclosures and carry no rigorous error bound, so the
\\ Python layer labels every value produced here as PARI-precision output.

zf_field_polynomial(kind, parameter) =
{
  \\ kind 0 = quadratic field Q(sqrt(parameter)), kind 1 = cyclotomic field Q(zeta_parameter).
  if(kind == 0,
    if(parameter == 0 || parameter == 1, error("the quadratic radicand must differ from 0 and 1"));
    if(!issquarefree(parameter), error("the quadratic radicand must be squarefree"));
    return(x^2 - parameter);
  );
  if(kind == 1,
    if(parameter < 3, error("the cyclotomic index must be at least 3"));
    return(polcyclo(parameter));
  );
  error("unknown field family");
};

zf_dedekind(pol, sr, si, tmax, zero_limit, max_degree, max_disc, want_class) =
{
  my(nf, lf, s, value, rootres, poles, zeros, found, shown, bnf);
  if(poldegree(pol) < 1, error("the defining polynomial must be nonconstant"));
  if(poldegree(pol) > max_degree, error("the field degree exceeds the configured bound"));
  if(!polisirreducible(pol), error("the defining polynomial must be irreducible over Q"));
  nf = nfinit(pol);
  if(abs(nf.disc) > max_disc, error("the field discriminant exceeds the configured bound"));
  print("POLYNOMIAL:", nf.pol);
  print("DEGREE:", poldegree(nf.pol));
  print("SIGNATURE:", nf.sign[1], "|", nf.sign[2]);
  print("DISCRIMINANT:", nf.disc);
  lf = lfuncreate(nf);
  \\ lfuncheckfeq returns the base-2 logarithm of the functional-equation error.
  print("FEQ:", lfuncheckfeq(lf));
  if(sr == 1 && si == 0, error("s = 1 is the simple pole of every Dedekind zeta function"));
  s = sr + si*I;
  value = lfun(lf, s);
  print("LVALUE:", real(value), "|", imag(value));
  rootres = lfunrootres(lf);
  poles = rootres[1];
  for(i = 1, #poles, print("POLE:", poles[i][1], "|", polcoef(poles[i][2], -1)));
  print("POLECOUNT:", #poles);
  if(want_class,
    bnf = bnfinit(pol, 1);
    print("CLASSNUMBER:", bnf.no);
    print("REGULATOR:", bnf.reg);
    print("TORSION:", bnf.tu[1]);
    print("CNF_RESIDUE:", 2^bnf.sign[1] * (2*Pi)^bnf.sign[2] * bnf.no * bnf.reg / (bnf.tu[1] * sqrt(abs(bnf.disc))));
  );
  zeros = lfunzeros(lf, tmax);
  found = #zeros;
  shown = min(found, zero_limit);
  for(i = 1, shown, print("ZERO:", i, "|", zeros[i]));
  print("ZEROCOUNT:", found);
  print("TRUNCATED:", if(found > zero_limit, 1, 0));
  print("DONE:", shown);
};
