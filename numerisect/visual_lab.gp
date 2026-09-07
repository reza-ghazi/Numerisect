\\ Numerisect visualization and education engine for PARI/GP.
\\
\\ Every number that the browser draws comes from this file: prime
\\ indicators, highlight membership, Eisenstein-prime classification,
\\ residue-class counts, gap records, prime-race running counts, and the
\\ exact step traces of the classical sieves.  Python validates requests and
\\ parses the tagged protocol; JavaScript only maps integers to canvas
\\ coordinates and colours.
\\
\\ Library routines used (nothing here re-implements them):
\\   vl_spiral            forprime, isprime, issquare  (primesieve enumerates
\\                        the unhighlighted 64-bit case from Python instead)
\\   vl_eisenstein_lattice isprime, sqrtint
\\   vl_modular_wheel     isprime, gcd, eulerphi
\\   vl_residue_heatmap   forprime, isprime, gcd
\\   vl_gap_timeline      forprime, isprime, log
\\   vl_prime_race        forprime, isprime, gcd
\\   vl_sieve_trace       primes, primepi (used only to VERIFY the trace)
\\
\\ vl_sieve_trace is the one deliberate exception to "always call the library
\\ routine": the sieves of Eratosthenes, segmented Eratosthenes, Sundaram and
\\ Atkin are executed step by step because the algorithms themselves are the
\\ subject of the animation.  Those traces are educational and bounded
\\ (n <= 5,000); every other tool here, and all real enumeration in the
\\ application, goes through primesieve or PARI's forprime/isprime.  Each
\\ trace is checked against PARI's own primes(primepi(n)) table before it is
\\ reported at all.

vl_join(values) = strjoin(vector(#values, i, Str(values[i])), "|");

\\ ---------------------------------------------------------------------------
\\ Prime spirals (Ulam, Sacks, polar): prime list with highlight membership.
\\ mode 0: no highlight; mode 1: residue class p = residue (mod modulus);
\\ mode 2: values of the quadratic a*k^2 + b*k + c for some integer k.
\\ ---------------------------------------------------------------------------
vl_polynomial_value(p, a, b, c) =
{
  my(D, s);
  if(a == 0,
    if(b == 0, return(p == c));
    return((p - c) % abs(b) == 0);
  );
  D = b^2 - 4*a*(c - p);
  if(D < 0 || !issquare(D, &s), return(0));
  ((-b + s) % (2*abs(a)) == 0) || ((-b - s) % (2*abs(a)) == 0);
};

vl_spiral(start, count, mode, a, b, c, modulus, residue) =
{
  if(start < 1, error("The spiral must start at a positive integer"));
  if(count < 1 || count > 1000000, error("The spiral may cover 1 to 1,000,000 integers"));
  if(mode < 0 || mode > 2, error("Unknown highlight mode"));
  if(mode == 1 && (modulus < 2 || residue < 0 || residue >= modulus),
    error("The residue class must satisfy 0 <= residue < modulus with modulus >= 2"));
  my(finish = start + count - 1, found = 0, highlighted = 0, h);
  forprime(p = max(2, start), finish,
    if(!isprime(p), next());
    h = 0;
    if(mode == 1, h = (p % modulus == residue));
    if(mode == 2, h = vl_polynomial_value(p, a, b, c));
    print("PRIME:", p, "|", h);
    found++; highlighted += h;
  );
  print("PRIME_COUNT:", found);
  print("HIGHLIGHT_COUNT:", highlighted);
  print("DONE:", found);
};

\\ ---------------------------------------------------------------------------
\\ Eisenstein primes a + b*omega with norm a^2 - a*b + b^2 <= norm_bound.
\\ Same criterion as nt_eisenstein: the norm is a rational prime, or the
\\ element is an associate of a rational prime q = 2 (mod 3).
\\ kind 1: split (norm = 1 mod 3), 2: inert associate (norm q^2), 3: ramified (norm 3).
\\ ---------------------------------------------------------------------------
vl_eisenstein_lattice(norm_bound, result_limit) =
{
  if(norm_bound < 2 || norm_bound > 200000, error("The norm bound must be between 2 and 200,000"));
  if(result_limit < 1, error("The result limit must be positive"));
  my(B = sqrtint((4 * norm_bound) \ 3) + 1, found = 0, truncated = 0, kinds = vector(3),
     norm, axis, q, kind);
  for(a = -B, B,
    for(b = -B, B,
      norm = a^2 - a*b + b^2;
      if(norm > norm_bound || norm < 2, next());
      axis = (a == 0 || b == 0 || a == b);
      q = abs(if(a, a, b));
      if(isprime(norm),
        kind = if(norm == 3, 3, 1);
      ,
        if(!(axis && isprime(q) && q % 3 == 2), next());
        kind = 2;
      );
      if(found >= result_limit, truncated = 1; break(2));
      print("EPOINT:", a, "|", b, "|", norm, "|", kind);
      found++; kinds[kind]++;
    );
  );
  print("COUNT:", found);
  for(k = 1, 3, print("KIND:", k, "|", kinds[k]));
  print("TRUNCATED:", truncated);
  print("DONE:", found);
};

\\ ---------------------------------------------------------------------------
\\ Residue-class heatmap: prime counts per residue class per interval bin.
\\ ---------------------------------------------------------------------------
vl_residue_heatmap(start, finish, modulus, bins) =
{
  if(start < 1 || start > finish, error("The range must satisfy 1 <= start <= end"));
  if(finish - start >= 10000000, error("The heatmap range may span at most 10,000,000 integers"));
  if(modulus < 2 || modulus > 360, error("The modulus must be between 2 and 360"));
  if(bins < 1 || bins > 200, error("Request between 1 and 200 bins"));
  my(span = finish - start + 1, width = ceil(span / bins), nb = ceil(span / width),
     M = matrix(nb, modulus), total = 0, maximum = 0, lo, hi, row);
  forprime(p = max(2, start), finish,
    if(!isprime(p), next());
    M[(p - start) \ width + 1, p % modulus + 1]++;
    total++;
  );
  for(i = 1, nb,
    lo = start + (i - 1) * width; hi = min(finish, lo + width - 1);
    row = vector(modulus, j, M[i, j]);
    maximum = max(maximum, vecmax(row));
    print("BIN:", i - 1, "|", lo, "|", hi, "|", vl_join(row));
  );
  for(r = 0, modulus - 1,
    print("RESIDUE:", r, "|", gcd(r, modulus) == 1, "|", sum(i = 1, nb, M[i, r + 1]));
  );
  print("PRIME_COUNT:", total);
  print("MAX_CELL:", maximum);
  print("BIN_COUNT:", nb);
  print("DONE:", nb);
};

\\ ---------------------------------------------------------------------------
\\ Prime-gap timeline with record (maximal within the scan) gaps and merits.
\\ ---------------------------------------------------------------------------
vl_gap_timeline(start, finish, result_limit) =
{
  if(start < 1 || start > finish, error("The range must satisfy 1 <= start <= end"));
  if(finish - start >= 10000000, error("The timeline range may span at most 10,000,000 integers"));
  if(result_limit < 1, error("The result limit must be positive"));
  my(prev = 0, record = 0, count = 0, shown = 0, truncated = 0, g, first = 0, last = 0,
     maxgap = 0, maxat = 0, records = 0);
  forprime(p = max(2, start), finish,
    if(!isprime(p), next());
    if(!first, first = p);
    if(prev,
      g = p - prev;
      if(shown < result_limit, print("GAP:", prev, "|", g); shown++, truncated = 1);
      count++;
      if(g > maxgap, maxgap = g; maxat = prev);
      if(g > record,
        record = g; records++;
        print("RECORD:", prev, "|", p, "|", g, "|", Strprintf("%.6f", g / log(prev)));
      );
    );
    prev = p; last = p;
  );
  print("FIRST:", first);
  print("LAST:", last);
  print("GAP_COUNT:", count);
  print("SHOWN:", shown);
  print("RECORD_COUNT:", records);
  print("MAX_GAP:", maxgap);
  print("MAX_GAP_AT:", maxat);
  print("TRUNCATED:", truncated);
  print("DONE:", count);
};

\\ ---------------------------------------------------------------------------
\\ Prime race: running counts of primes in each reduced residue class modulo
\\ q at successive checkpoints, plus every exact lead change.
\\ ---------------------------------------------------------------------------
vl_prime_race(start, finish, modulus, checkpoints, event_limit) =
{
  if(start < 1 || start > finish, error("The range must satisfy 1 <= start <= end"));
  if(finish - start >= 10000000, error("The race range may span at most 10,000,000 integers"));
  if(modulus < 2 || modulus > 360, error("The modulus must be between 2 and 360"));
  if(checkpoints < 1 || checkpoints > 1000, error("Request between 1 and 1,000 checkpoints"));
  if(event_limit < 1, error("The event limit must be positive"));
  my(classes = select(r -> gcd(r, modulus) == 1, [0..modulus - 1]), index = vector(modulus),
     counts, leader = -1, leadcount = 0, events = 0, truncated = 0, k = 1, span = finish - start,
     checkpoint, c, total = 0);
  for(i = 1, #classes, index[classes[i] + 1] = i);
  counts = vector(#classes);
  print("CLASSES:", vl_join(classes));
  checkpoint = start + (k * span) \ checkpoints;
  forprime(p = max(2, start), finish,
    if(!isprime(p), next());
    while(k <= checkpoints && p > checkpoint,
      print("CHECK:", checkpoint, "|", if(leader > 0, classes[leader], -1), "|", vl_join(counts));
      k++; checkpoint = start + (k * span) \ checkpoints;
    );
    c = index[p % modulus + 1];
    if(c == 0, next());
    counts[c]++; total++;
    if(c == leader, leadcount++,
      if(counts[c] > leadcount,
        leader = c; leadcount = counts[c]; events++;
        if(events <= event_limit, print("LEAD:", p, "|", classes[c]), truncated = 1);
      );
    );
  );
  while(k <= checkpoints,
    print("CHECK:", checkpoint, "|", if(leader > 0, classes[leader], -1), "|", vl_join(counts));
    k++; checkpoint = start + (k * span) \ checkpoints;
  );
  for(i = 1, #classes, print("FINAL:", classes[i], "|", counts[i]));
  print("LEADER:", if(leader > 0, classes[leader], -1));
  print("MAX_COUNT:", if(#counts, vecmax(counts), 0));
  print("PRIME_COUNT:", total);
  print("EVENT_COUNT:", events);
  print("EVENT_TRUNCATED:", truncated);
  print("DONE:", checkpoints);
};

\\ ---------------------------------------------------------------------------
\\ Sieve step traces.  STEP:kind|value|a|b|flag
\\   1 select prime (value)                 2 strike composite value by prime a (flag = already struck)
\\   3 survivor declared prime (value)      4 Sundaram strike of 2m+1 = value via i=a, j=b (flag = already struck)
\\   5/6/7 Atkin toggle by 4x^2+y^2 / 3x^2+y^2 / 3x^2-y^2 with x=a, y=b (flag = new state)
\\   8 Atkin square-multiple elimination of value by r^2 with r=a (flag = was marked)
\\   9 segment boundary [value, a]
\\ ---------------------------------------------------------------------------
vl_step(kind, value, a, b, flag) = print("STEP:", kind, "|", value, "|", a, "|", b, "|", flag);

vl_trace_eratosthenes(n) =
{
  my(marked = vector(n), steps = 0, found = List());
  for(p = 2, sqrtint(n),
    if(marked[p], next());
    vl_step(1, p, 0, 0, 0); steps++; listput(found, p);
    forstep(m = p^2, n, p,
      vl_step(2, m, p, 0, marked[m]); steps++; marked[m] = 1;
    );
  );
  for(q = max(2, sqrtint(n) + 1), n,
    if(!marked[q], vl_step(3, q, 0, 0, 0); steps++; listput(found, q));
  );
  [steps, Vec(found)];
};

vl_trace_segmented(n, segment) =
{
  my(limit = sqrtint(n), base = List(), marked = vector(max(limit, 1)), steps = 0,
     found = List(), lo, hi, seg, first, p);
  for(q = 2, limit,
    if(marked[q], next());
    vl_step(1, q, 0, 0, 0); steps++; listput(base, q); listput(found, q);
    forstep(m = q^2, limit, q, vl_step(2, m, q, 0, marked[m]); steps++; marked[m] = 1);
  );
  lo = max(2, limit + 1);
  while(lo <= n,
    hi = min(n, lo + segment - 1);
    vl_step(9, lo, hi, 0, 0); steps++;
    seg = vector(hi - lo + 1);
    for(i = 1, #base,
      p = base[i]; first = max(p^2, ((lo + p - 1) \ p) * p);
      forstep(m = first, hi, p,
        vl_step(2, m, p, 0, seg[m - lo + 1]); steps++; seg[m - lo + 1] = 1;
      );
    );
    for(m = lo, hi, if(!seg[m - lo + 1], vl_step(3, m, 0, 0, 0); steps++; listput(found, m)));
    lo = hi + 1;
  );
  [steps, Vec(found)];
};

vl_trace_sundaram(n) =
{
  my(k = (n - 1) \ 2, marked = vector(max(k, 1)), steps = 0, found = List(), m);
  vl_step(1, 2, 0, 0, 0); steps++; listput(found, 2);
  for(i = 1, k,
    if(2*i + 2*i*i > k, break);
    for(j = i, k,
      m = i + j + 2*i*j; if(m > k, break);
      vl_step(4, 2*m + 1, i, j, marked[m]); steps++; marked[m] = 1;
    );
  );
  for(m = 1, k, if(!marked[m], vl_step(3, 2*m + 1, 0, 0, 0); steps++; listput(found, 2*m + 1)));
  [steps, Vec(found)];
};

vl_trace_atkin(n) =
{
  my(sieve = vector(n), steps = 0, found = List(), v, r, root = sqrtint(n));
  if(n >= 2, vl_step(1, 2, 0, 0, 0); steps++; listput(found, 2));
  if(n >= 3, vl_step(1, 3, 0, 0, 0); steps++; listput(found, 3));
  for(x = 1, root,
    for(y = 1, root,
      v = 4*x^2 + y^2; r = v % 12;
      if(v <= n && (r == 1 || r == 5),
        sieve[v] = !sieve[v]; vl_step(5, v, x, y, sieve[v]); steps++);
      v = 3*x^2 + y^2; r = v % 12;
      if(v <= n && r == 7,
        sieve[v] = !sieve[v]; vl_step(6, v, x, y, sieve[v]); steps++);
      v = 3*x^2 - y^2; r = v % 12;
      if(x > y && v <= n && r == 11,
        sieve[v] = !sieve[v]; vl_step(7, v, x, y, sieve[v]); steps++);
    );
  );
  for(q = 5, root,
    if(!sieve[q], next());
    forstep(m = q^2, n, q^2, vl_step(8, m, q, 0, sieve[m]); steps++; sieve[m] = 0);
  );
  for(q = 5, n, if(sieve[q], vl_step(3, q, 0, 0, 0); steps++; listput(found, q)));
  [steps, Vec(found)];
};

vl_sieve_trace(kind, n, segment) =
{
  if(n < 2 || n > 5000, error("Sieve traces cover n between 2 and 5,000"));
  if(kind < 0 || kind > 3, error("Unknown sieve kind"));
  if(segment < 0 || segment > n, error("The segment size must be between 1 and n"));
  \\ segment 0 asks the engine for the default block size ceil(sqrt(n)).
  if(segment == 0, segment = sqrtint(n) + 1);
  my(result, expected = primes(primepi(n)));
  result = if(kind == 0, vl_trace_eratosthenes(n),
           if(kind == 1, vl_trace_segmented(n, segment),
           if(kind == 2, vl_trace_sundaram(n), vl_trace_atkin(n))));
  if(result[2] != expected, error("The sieve trace disagrees with PARI's prime table"));
  for(i = 1, #result[2], print("PRIME:", result[2][i]));
  print("SEGMENT:", segment);
  print("STEP_COUNT:", result[1]);
  print("PRIME_COUNT:", #result[2]);
  print("VERIFIED:1");
  print("DONE:", result[1]);
};

\\ ---------------------------------------------------------------------------
\\ Interactive modular wheel with an arbitrary base.  The Prime Structures
\\ wheel (ps_modular_wheel) always starts at 0 and caps the base at 360 and the
\\ maximum at 20,000; this variant accepts any base up to 10,000, an arbitrary
\\ start, and up to 200,000 consecutive values, and additionally reports the
\\ per-spoke prime counts and Euler totient so the browser never counts.
\\ ---------------------------------------------------------------------------
vl_modular_wheel(modulus, start, count) =
{
  if(modulus < 2 || modulus > 10000, error("The wheel base must be between 2 and 10,000"));
  if(start < 0, error("The wheel must start at a nonnegative integer"));
  if(count < 1 || count > 200000, error("The wheel may cover 1 to 200,000 integers"));
  my(finish = start + count - 1, primes = 0, coprimes = 0, spokes = vector(modulus),
     rings = 0, r, p, c);
  for(value = start, finish,
    r = value % modulus; p = isprime(value); c = (gcd(value, modulus) == 1);
    rings = (value - start) \ modulus;
    print("CELL:", value, "|", r, "|", rings, "|", p, "|", c);
    primes += p; coprimes += c;
    if(p, spokes[r + 1]++);
  );
  for(r = 0, modulus - 1,
    print("SPOKE:", r, "|", gcd(r, modulus) == 1, "|", spokes[r + 1]);
  );
  print("LOADED_SPOKES:", sum(r = 1, modulus, spokes[r] > 0));
  print("TOTIENT:", eulerphi(modulus));
  print("RING_COUNT:", rings + 1);
  print("CELL_COUNT:", count);
  print("PRIME_COUNT:", primes);
  print("COPRIME_COUNT:", coprimes);
  print("DONE:", count);
};
