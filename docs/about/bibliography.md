# Bibliography

Sources for the mathematics Numerisect implements, and for the engines it uses. Where a
documentation page states a bound, a constant or a named theorem, it cites from this
list.

## General references

- R. Crandall and C. Pomerance. *Prime Numbers: A Computational Perspective*, 2nd edition.
  Springer. The standard reference for computational prime number theory, covering
  pseudoprimes, primality proving and every factoring method here.
- H. Cohen. *A Course in Computational Algebraic Number Theory*. Springer. Algorithms for
  number fields, quadratic forms, class groups and modular arithmetic.
- H. Riesel. *Prime Numbers and Computer Methods for Factorization*. Birkhäuser.
- D. E. Knuth. *The Art of Computer Programming*, volume 2, *Seminumerical Algorithms*.
  Addison-Wesley.
- G. H. Hardy and E. M. Wright. *An Introduction to the Theory of Numbers*. Oxford.
- H. L. Montgomery and R. C. Vaughan. *Multiplicative Number Theory I: Classical Theory*.
  Cambridge.
- H. Iwaniec and E. Kowalski. *Analytic Number Theory*. American Mathematical Society.

## Primality

- R. Baillie and S. S. Wagstaff, Jr. "Lucas pseudoprimes". *Mathematics of Computation*.
- C. Pomerance, J. L. Selfridge and S. S. Wagstaff, Jr. "The pseudoprimes to
  \(25 \cdot 10^9\)". *Mathematics of Computation*.
- G. Miller. "Riemann's hypothesis and tests for primality". *Journal of Computer and
  System Sciences*.
- M. Rabin. "Probabilistic algorithm for testing primality". *Journal of Number Theory*.
- G. Jaeschke. "On strong pseudoprimes to several bases". *Mathematics of Computation*.
- J. Sorenson and J. Webster. "Strong pseudoprimes to twelve prime bases". *Mathematics of
  Computation*.
- H. C. Pocklington. "The determination of the prime or composite nature of large numbers
  by Fermat's theorem". *Proceedings of the Cambridge Philosophical Society*.
- V. Pratt. "Every prime has a succinct certificate". *SIAM Journal on Computing*.
- L. M. Adleman, C. Pomerance and R. S. Rumely. "On distinguishing prime numbers from
  composite numbers". *Annals of Mathematics*. The basis of APR-CL.
- A. O. L. Atkin and F. Morain. "Elliptic curves and primality proving". *Mathematics of
  Computation*. The basis of ECPP.

## Factorization

- J. M. Pollard. "A Monte Carlo method for factorization". *BIT*.
- J. M. Pollard. "Theorems on factorization and primality testing". *Proceedings of the
  Cambridge Philosophical Society*. The p−1 method.
- R. P. Brent. "An improved Monte Carlo factorization algorithm". *BIT*.
- H. C. Williams. "A \(p+1\) method of factoring". *Mathematics of Computation*.
- H. W. Lenstra, Jr. "Factoring integers with elliptic curves". *Annals of Mathematics*.
- C. Pomerance. "The quadratic sieve factoring algorithm". *Advances in Cryptology,
  EUROCRYPT '84*.
- A. K. Lenstra and H. W. Lenstra, Jr., editors. *The Development of the Number Field
  Sieve*. Springer Lecture Notes in Mathematics 1554.
- J. E. Gower and S. S. Wagstaff, Jr. "Square form factorization". *Mathematics of
  Computation*. The reference implementation notes for SQUFOF.
- D. Shanks. "Analysis and improvement of the continued fraction method of factorization".
  Unpublished manuscript, described in the Gower–Wagstaff paper above.

## Distribution of primes

- J. B. Rosser and L. Schoenfeld. "Approximate formulas for some functions of prime
  numbers". *Illinois Journal of Mathematics*.
- P. Dusart. "Estimates of some functions over primes without R.H." and "The \(k\)th prime
  is greater than \(k(\ln k + \ln\ln k - 1)\) for \(k \ge 2\)". *Mathematics of Computation*.
- J. E. Littlewood. "Sur la distribution des nombres premiers". *Comptes Rendus*. The sign
  of \(\pi(x) - \mathrm{li}(x)\) changes infinitely often.
- G. H. Hardy and J. E. Littlewood. "Some problems of 'Partitio numerorum' III: On the
  expression of a number as a sum of primes". *Acta Mathematica*.
- P. T. Bateman and R. A. Horn. "A heuristic asymptotic formula concerning the
  distribution of prime numbers". *Mathematics of Computation*.
- M. Rubinstein and P. Sarnak. "Chebyshev's bias". *Experimental Mathematics*.
- A. Granville. "Harald Cramér and the distribution of prime numbers". *Scandinavian
  Actuarial Journal*.
- T. R. Nicely. Computational work on prime gaps and maximal gaps.
- A. Odlyzko. Tables and papers on zeros of the zeta function.

## Prime counting

- J. C. Lagarias, V. S. Miller and A. M. Odlyzko. "Computing \(\pi(x)\): the
  Meissel–Lehmer method". *Mathematics of Computation*.
- M. Deléglise and J. Rivat. "Computing \(\pi(x)\): the Meissel, Lehmer, Lagarias, Miller,
  Odlyzko method". *Mathematics of Computation*.
- X. Gourdon. "Computation of \(\pi(x)\): improvements to the Meissel, Lehmer, Lagarias,
  Miller, Odlyzko, Deléglise and Rivat method". Available from the primecount project.

## Analytic number theory and zeta

- B. Riemann. "Ueber die Anzahl der Primzahlen unter einer gegebenen Grösse".
- H. M. Edwards. *Riemann's Zeta Function*. Dover.
- E. C. Titchmarsh, revised by D. R. Heath-Brown. *The Theory of the Riemann Zeta
  Function*. Oxford.
- A. M. Turing. "Some calculations of the Riemann zeta-function". *Proceedings of the
  London Mathematical Society*. The zero-counting method.
- H. L. Montgomery. "The pair correlation of zeros of the zeta function". *Analytic Number
  Theory, Proceedings of Symposia in Pure Mathematics*.

## Quadratic forms

- D. A. Buell. *Binary Quadratic Forms: Classical Theory and Modern Computations*.
  Springer.
- J. H. Conway. *The Sensual (Quadratic) Form*. Mathematical Association of America.
- D. A. Cox. *Primes of the Form \(x^2 + ny^2\)*. Wiley.

## Software

- The PARI Group. *PARI/GP*. <https://pari.math.u-bordeaux.fr/>
- F. Johansson. "Arb: efficient arbitrary-precision midpoint-radius interval arithmetic".
  *IEEE Transactions on Computers*. <https://flintlib.org/>
- B. Buhrow. *YAFU*. <https://github.com/bbuhrow/yafu>
- J. Papadopoulos. *Msieve*. <https://sourceforge.net/projects/msieve/>
- P. Zimmermann and others. *GMP-ECM*. <https://gitlab.inria.fr/zimmerma/ecm>
- The CADO-NFS Development Team. *CADO-NFS*. <https://cado-nfs.gitlabpages.inria.fr/>
- K. Walisch. *primesieve*. <https://github.com/kimwalisch/primesieve>
- K. Walisch. *primecount*. <https://github.com/kimwalisch/primecount>
- T. Granlund and the GMP development team. *The GNU Multiple Precision Arithmetic
  Library*. <https://gmplib.org/>

## Reference data

- The On-Line Encyclopedia of Integer Sequences. <https://oeis.org/> Sequences cited in
  the documentation include A002386 and A005250 (maximal prime gaps) and A005180.

!!! note "On citation practice"

    Where a documentation page states a numerical bound or a named result, it cites the
    source so you can check the claim rather than take Numerisect's word for it. Where an
    attribution is uncertain, the page describes the result without inventing a date.
