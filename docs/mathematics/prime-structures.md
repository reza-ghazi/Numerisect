# Prime structures

Primality is one yes-or-no property. Prime *structure* asks what else a proven prime does:
how its digits behave, how it sits beside other primes, how it factors in a larger ring,
or what period its reciprocal has. These questions use different mathematics, and a
prime may belong to many classes at once.

Numerisect proves the input prime before applying proof-oriented classifications. Digital
operations, recurrences, modular orders, norms and every further primality decision are
performed in PARI/GP. Python only validates, invokes GP and parses complete tagged output.

## Families, properties and sequences are different things

A **formula family** specifies candidates, such as Mersenne numbers \(2^p-1\), Proth
numbers \(k2^n+1\), or repunits \((b^n-1)/(b-1)\). Membership in the family need not
imply primality.

A **property class** starts with a prime and asks a second exact question. A safe prime
\(q\) has \((q-1)/2\) prime; a Sophie Germain prime \(p\) has \(2p+1\) prime; a
Wieferich prime satisfies

\[
2^{p-1}\equiv1\pmod{p^2}.
\]

A **sequence class** asks whether the prime occurs in a defined recurrence or established
catalogue. Exact recurrences can often settle membership. An open-ended or finite
catalogue cannot prove non-membership beyond its known boundary, so the correct result is
inconclusive.

This distinction explains the three-way classifier contract: match, definite non-match,
or inconclusive. See the [complete 56-class table](../PRIME_CLASSIFICATION.md).

## Prime neighbors, tuples and the two meanings of “k-prime”

Twin, cousin and sexy primes have a prime partner at distance 2, 4 and 6 respectively.
A prime triplet or quadruplet occupies an admissible pattern such as
\(\{0,2,6\}\) or \(\{0,2,6,8\}\). More generally, offsets
\(H=\{h_1,\ldots,h_k\}\) form a prime \(k\)-tuple at \(n\) when every \(n+h_i\) is
prime.

“k-prime” also has a separate standard meaning: an integer \(n\) with exactly \(k\)
prime factors counted with multiplicity, \(\Omega(n)=k\). Thus semiprimes are 2-primes in
that terminology. Numerisect keeps the operations separate:

- **Prime tuples** searches offset patterns among primes.
- **Compare \(\omega(n)\) and \(\Omega(n)\)** studies distinct and repeated prime-factor
  counts of general integers.

Admissibility is necessary for a tuple pattern to recur: for every prime \(\ell\), the
offsets must not cover all residue classes modulo \(\ell\). It is not a proof of any
future tuple. Hardy–Littlewood estimates are therefore labelled predictions, while every
reported tuple member is tested individually.

## Decimal structure depends on the base

Circular, palindromic, emirp, truncatable, digitally delicate and non-insertable primes
refer to a numeral representation, not to the abstract integer alone. Unless a tool says
otherwise, Numerisect uses base 10.

For example, 197 is circular in base 10 because 197, 971 and 719 are prime. Rotations
that introduce a leading zero are interpreted as integers after rotation, whereas a
left-truncatable definition may explicitly reject embedded leading-zero cases. The exact
convention is part of the class definition; changing it changes the class.

The **absolute-prime** search groups a decimal rotation orbit once. In this application
that historical tool name means circular primes; it is not a claim that “absolute prime”
has one universally standardized definition.

## Reciprocal periods and full-reptend primes

Let \(p\) be prime and let the base \(b\) be coprime to \(p\). The repeating-period
length of \(1/p\) in base \(b\) is

\[
\operatorname{ord}_p(b)
=\min\{k>0:b^k\equiv1\pmod p\}.
\]

Lagrange's theorem gives \(\operatorname{ord}_p(b)\mid p-1\). The maximum possible
period is therefore \(p-1\), attained exactly when \(b\) is a primitive root modulo
\(p\). In base 10, such a prime is called full reptend. For \(p=7\), the order of 10 is
6 and

\[
\frac17=0.\overline{142857}.
\]

Primes dividing the base are the terminating exceptions: \(1/2=0.5\) and \(1/5=0.2\)
in base 10. Numerisect reports period zero rather than forcing them into the repeating
case.

Computing the exact order generally requires factoring \(p-1\). That factorization, not
long division, can dominate a large analysis. The native reciprocal engine streams a
complete finite expansion or one full repetend directly to the report; the 100,000-digit
browser limit is only a preview cap. See [Reciprocals of primes](../PRIME_RECIPROCALS.md).

## Gaussian and Eisenstein primes

The Gaussian integers \(\mathbb Z[i]\) use the norm

\[
N(a+bi)=a^2+b^2.
\]

If both coordinates are nonzero, \(a+bi\) is Gaussian prime exactly when
\(a^2+b^2\) is an ordinary rational prime. On an axis, \(a\) or \(bi\) is Gaussian
prime exactly when the nonzero absolute coordinate is a rational prime congruent to 3
modulo 4. A rational prime \(p\equiv1\pmod4\) splits because it is a sum of two squares;
\(p\equiv3\pmod4\) remains prime in \(\mathbb Z[i]\); and 2 ramifies.

For the Eisenstein integers \(\mathbb Z[\omega]\), where
\(\omega^2+\omega+1=0\), the norm is

\[
N(a+b\omega)=a^2-ab+b^2.
\]

Away from the three unit axes, primality is decided by whether this norm is a rational
prime. A rational prime \(p\equiv1\pmod3\) splits, \(p\equiv2\pmod3\) remains prime,
and 3 ramifies. These are statements about irreducibility in different rings: the same
rational integer can behave differently after the coefficient ring is enlarged.

PARI/GP computes the norm and the exact axis criterion. JavaScript only maps the returned
lattice points to screen coordinates.

## Perfect numbers and Mersenne primes

A positive integer is perfect when the sum of its proper divisors equals itself, or
equivalently when \(\sigma(n)=2n\). The Euclid–Euler theorem classifies every even
perfect number:

\[
n=2^{p-1}(2^p-1),
\]

where \(2^p-1\) is prime. Numerisect therefore proves the Mersenne factor before calling
the constructed integer perfect. It makes no claim about odd perfect numbers; whether
any exist remains open.

For odd prime \(p\), every prime divisor \(q\) of \(M_p=2^p-1\) has

\[
q=2kp+1,\qquad q\equiv\pm1\pmod8.
\]

The mod-8 condition retains two of the four odd residue classes—one half of the
\(q=2kp+1\) progression. Testing \(2^p\equiv1\pmod q\) proves divisibility without
constructing \(M_p\). Exhausting a finite \(k\)-range proves only that no divisor was
found in that range; Lucas–Lehmer answers the separate primality question. See
[Mersenne numbers](../MERSENNE.md).

The case \(p=2\) gives \(M_2=3\) and is the trivial exception to that divisor form.

## Where this appears in Numerisect

| Topic | Tool | Native operation |
|---|---|---|
| 56 overlapping classes | **Classify a prime** | `prime_classifier.gp`; PARI `isprime`, recurrences, congruences and guarded searches |
| Decimal rotations | **Find circular primes** | `prime_structures.gp`; rigorous primality of every rotation |
| Prime constellations | **Prime tuples**, classifier | PARI `forprime`/`isprime`; primesieve for eligible 64-bit tuple counts |
| Factor multiplicity | **Compare ω(n) and Ω(n)** | PARI `factor` and exact exponent sums |
| Reciprocal periods | **Analyze 1/p**, **Full-reptend primes** | PARI `znorder`, `znprimroot`, `isprime` |
| Gaussian primes | **Check a + bi**, **Find Gaussian primes** | PARI exact norm and rational primality |
| Eisenstein primes | **Eisenstein primes a + bω** | PARI exact norm/axis criterion |
| Even perfect numbers | **Generate even perfect numbers** | PARI `isprime` and Euclid–Euler construction |
| Mersenne divisors | **Mersenne trial factoring** | PARI `ispseudoprime`, modular powering and exact divisibility congruence |

## References

- G. H. Hardy and E. M. Wright, *An Introduction to the Theory of Numbers*, sections on
  periodic decimals, primitive roots and sums of two squares.
- K. Ireland and M. Rosen, *A Classical Introduction to Modern Number Theory*, chapters
  on Gaussian and Eisenstein integers.
- P. Ribenboim, *The New Book of Prime Number Records*, chapters on special prime forms,
  decimal properties and prime constellations.
- L. E. Dickson, *History of the Theory of Numbers*, volume I, for Euclid–Euler perfect
  numbers and classical special-prime results.
- R. Crandall and C. Pomerance, *Prime Numbers: A Computational Perspective*, for
  computational primality, orders and Mersenne-number methods.
