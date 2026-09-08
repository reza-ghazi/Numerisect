\\ SPDX-License-Identifier: GPL-3.0-or-later
\\
\\ RSA Factoring Challenge support.  PARI/GP performs every calculation here; the
\\ Python side only validates arguments, renders them into one call, and parses the
\\ tagged output.
\\
\\ WHY THIS EXISTS
\\ --------------
\\ Numerisect can already factor an RSA number: it is an ordinary semiprime and the
\\ automatic pipeline routes it to CADO-NFS.  What was missing is knowing *which*
\\ number you are holding and what attempting it would cost.  This program answers
\\ both, and it re-derives every catalogue claim rather than trusting the table.
\\
\\ NOTHING IS TRUSTED
\\ ------------------
\\ A transcribed constant is an unverified claim.  rc_report proves the value is
\\ composite, recomputes its digit and bit length, and where factors are supplied
\\ checks that p * q reproduces the value exactly and that both factors are prime.
\\ A catalogue entry that fails any of these is reported as failing, not as a fact.
\\
\\ THE COST ESTIMATE IS A HEURISTIC, AND IS LABELLED ONE
\\ ----------------------------------------------------
\\ The general number field sieve has conjectured complexity
\\
\\     L_N[1/3, c] = exp( (c + o(1)) (ln N)^(1/3) (ln ln N)^(2/3) ),  c = (64/9)^(1/3)
\\
\\ There is no proof of this running time, and the o(1) is not bounded, so the number
\\ produced here is an order-of-magnitude planning figure and never a prediction.  It
\\ is anchored on a published measurement rather than an abstract constant: the
\\ RSA-250 factorization, which Boudot, Gaudry, Guillevic, Heninger, Thome and Zimmermann
\\ reported in 2020 as approximately 2700 core-years on Intel Xeon Gold 6130 cores.
\\ Scaling that anchor by the ratio of L values gives the estimate below.

rc_l_gnfs(n) =
{
  my(c = (64/9)^(1/3), ln_n = log(n));
  exp(c * ln_n^(1/3) * log(ln_n)^(2/3));
};

\\ Effort for n, in core-years, scaled from the measured RSA-250 anchor.
rc_core_years(n, anchor, anchor_years) =
{
  if(n <= 1 || anchor <= 1, return(-1.0));
  anchor_years * rc_l_gnfs(n) / rc_l_gnfs(anchor);
};

\\ n            the value to report on
\\ p, q         claimed factors, or 0 when the entry is open
\\ prove        1 to demand a primality *proof* of each factor, 0 for Baillie-PSW
\\ cores        cores available on this machine, for the wall-clock estimate
\\ anchor       the RSA-250 value
\\ anchor_years the published core-years for that anchor
\\ seconds      budget for the optional primality proofs
rc_report(n, p, q, prove, cores, anchor, anchor_years, seconds) =
{
  my(proven = -1, pp = -1, qq = -1, product = -1, years, wall);
  if(n < 2, error("The RSA challenge value must be at least 2"));
  print("DIGITS:", #Str(n));
  print("BITS:", #binary(n));
  \\ A failed Miller-Rabin round is a proof of compositeness, so this is not a guess.
  print("COMPOSITE:", if(ispseudoprime(n), 0, 1));
  if(p > 0 && q > 0,
    product = if(p * q == n, 1, 0);
    print("PRODUCT:", product);
    print("P_DIGITS:", #Str(p));
    print("Q_DIGITS:", #Str(q));
    if(prove == 1,
      pp = alarm(seconds, isprime(p));
      qq = alarm(seconds, isprime(q));
      if(type(pp) == "t_ERROR" || type(qq) == "t_ERROR",
        print("FACTOR_PRIMALITY:inconclusive"); proven = -1;
      ,
        print("FACTOR_PRIMALITY:proven");
        proven = if(pp && qq, 1, 0);
      );
    ,
      pp = ispseudoprime(p); qq = ispseudoprime(q);
      print("FACTOR_PRIMALITY:probable");
      proven = 0;
    );
    print("P_PRIME:", if(pp === 1 || pp == 1, 1, 0));
    print("Q_PRIME:", if(qq === 1 || qq == 1, 1, 0));
    print("PROVEN:", proven);
  ,
    print("PRODUCT:-1");
    print("FACTOR_PRIMALITY:not-applicable");
    print("PROVEN:-1");
  );
  years = rc_core_years(n, anchor, anchor_years);
  print("L_VALUE:", rc_l_gnfs(n));
  print("CORE_YEARS:", years);
  wall = if(cores > 0, years / cores, -1.0);
  print("WALL_YEARS:", wall);
  print("CORES:", cores);
  print("DONE:1");
};
