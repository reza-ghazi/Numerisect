# Glossary

Terms as Numerisect uses them. Where a word is used loosely elsewhere, the entry says so.

## Result strength

**Proven**
: A mathematical proof exists. Not a probability statement.

**Probable prime**
: An integer that passed a strong probabilistic test, almost always Baillie–PSW. Not a
proof. Numerisect never calls one prime without qualification.

**Inconclusive**
: The question was not settled within the budget or bound applied. **Not** a negative
result.

**Exploratory**
: Indicative rather than certified: a plot sample, an enclosure midpoint, or a value
predicted by a conjecture.

**Certified enclosure**
: An interval, produced by ball arithmetic, guaranteed to contain the true value. A proof
about a real number.

## Primality

**Fermat pseudoprime to base \(a\)**
: Composite \(n\) with \(a^{n-1} \equiv 1 \pmod n\).

**Carmichael number**
: Composite \(n\) that is a Fermat pseudoprime to every base coprime to \(n\). The
smallest is 561. Korselt's criterion characterises them.

**Strong pseudoprime**
: Composite passing the Miller–Rabin test for a given base. The smallest strong
pseudoprime to bases 2, 3, 5 and 7 is 3215031751.

**Strong liar**
: A base to which a composite is a strong pseudoprime. At most a quarter of bases are
strong liars for any odd composite above 9.

**BPSW**
: Baillie–PSW: a base-2 strong test combined with a Lucas test using Selfridge's
parameters. No counterexample is known; none is proven not to exist.

**Witness set**
: A fixed set of bases sufficient to decide primality deterministically below a proven
bound.

**Primality certificate**
: A structure allowing independent verification that a number is prime, typically a Pratt
tree or an ECPP certificate.

## Factoring

**Smooth**
: An integer whose prime factors are all below a bound \(B\). *Powersmooth* requires the
prime **powers** to be below \(B\).

**Cofactor**
: What remains after dividing out known factors. A composite cofactor is not a completed
factorization.

**Pretest**
: ECM run before a heavier method, to remove factors small enough that the heavier method
would waste effort on them. Measured in digits: "t20" means work sufficient to find most
20-digit factors.

**Ambiguous form**
: A binary quadratic form equal to its own inverse in the class group. Finding one during
SQUFOF yields a factor.

**Special form**
: An input with algebraic structure, such as \(a^n \pm 1\) or a cyclotomic value, which
SNFS can exploit for far less work than general NFS.

**Aurifeuillean factorization**
: An algebraic splitting of \(a^n \pm 1\) beyond the obvious cyclotomic factors.

## Distribution

**\(\pi(x)\)**
: The number of primes not exceeding \(x\).

**\(\mathrm{li}(x)\)**
: The logarithmic integral, a much better approximation to \(\pi(x)\) than \(x/\log x\).

**Merit**
: A prime gap divided by \(\log p\), measuring how large a gap is relative to the average
spacing there.

**Maximal gap**
: A gap larger than every gap before it.

**Admissible tuple**
: A pattern of offsets that does not cover every residue class modulo any prime, hence not
obstructed from occurring infinitely often.

**Singular series**
: The constant in the Hardy–Littlewood conjectured density for a tuple pattern.

## Analytic

**Critical line**
: \(\mathrm{Re}(s) = 1/2\), where the Riemann hypothesis asserts all nontrivial zeros lie.

**Hardy Z function**
: A real-valued function on the critical line with the same zeros as \(\zeta\), which is
why sign changes can locate them.

**Gram point**
: A point where the Riemann–Siegel theta function is a multiple of \(\pi\). Gram's law is
a tendency, not a theorem, and its exceptions are catalogued.

**Turing method**
: A rigorous technique for confirming a zero count through a given height.

**\(S(T)\)**
: The remainder in the zero-counting formula.

## Summatory functions and exceptional primes

**Mertens function \(M(x)\)**
: \(\sum_{n\le x}\mu(n)\). An exact integer sum; the conjecture that
  \(|M(x)|<\sqrt x\) is false.

**Hyperbola identity**
: \(\sum_{n\le x} M(x/n) = 1\), the recurrence that makes \(M(x)\) computable in about
  \(x^{2/3}\) operations instead of \(x\).

**Brun's constant**
: The limit of the sum of reciprocals over twin primes. Numerisect reports the exact
  truncated sum up to a stated bound, never an extrapolated constant.

**Fermat quotient**
: The residue \(A\) in \(a^{p-1}\equiv 1+Ap \pmod{p^2}\). \(A=0\) makes \(p\) a
  Wieferich prime to base \(a\); a small \(|A|\) is a near-miss.

**Wilson prime**
: A prime with \((p-1)!\equiv-1\pmod{p^2}\), strengthening Wilson's theorem. Only 5, 13
  and 563 are known.

**Wolstenholme prime**
: A prime with \(H_{p-1}\equiv0\pmod{p^3}\), one power beyond Wolstenholme's theorem.
  Only 16843 and 2124679 are known.

**Wall–Sun–Sun prime**
: A prime with \(p^2\mid F_{p-(5\mid p)}\). None is known.

**CFRAC**
: The continued-fraction factoring method: relations come from the convergents of
  \(\sqrt N\) rather than from a sieving interval.

**Coppersmith's method**
: Finds small roots of a polynomial modulo an *unknown* divisor, by lattice reduction.
  Its cost depends on how much of a factor is unknown rather than on the size of the
  modulus, which is why it reaches sizes no sieve does.

**Proven validity window**
: The bound within which Coppersmith's method is guaranteed to find a root,
  \(X \le \exp((\log B)^2/(\deg P\log N))\). Outside it, finding nothing says nothing.

**Square-free decomposition**
: The first stage of factoring a polynomial over \(\mathbb{F}_p\): separate repeated
  factors and record their multiplicities. The later stages assume a square-free input.

**Distinct-degree factorization**
: The second stage: split a square-free polynomial into blocks whose irreducible factors
  all share one degree.

**Equal-degree splitting**
: The third stage, by Cantor and Zassenhaus: divide a block into its irreducible factors
  of that one degree.

## Engines

**Tagged output**
: The `TAG:value` line protocol Numerisect uses to read engine results, ending in a
mandatory completion marker.

**Completion marker**
: The final line an engine prints. Its absence is an error, never an empty success.

**Work unit**
: A parcel of sieving work CADO-NFS hands to a client.

**Presieve**
: Removing multiples of small primes before applying an expensive test to the survivors.
