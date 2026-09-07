# Binary quadratic forms, continued fractions and quadratic fields

This page covers the classical theory that Gauss built and that two factoring
algorithms still run on: binary quadratic forms and their discriminants, reduction
and equivalence, the class group and the class number, continued fractions and their
exact periodicity for quadratic irrationals, Pell's equation and the fundamental unit
of a real quadratic field, representation of integers by forms, and the arithmetic of
quadratic fields — splitting, inertia and ramification. It closes with the link that
makes all of this a factoring subject: SQUFOF walks a cycle of forms hunting for an
ambiguous one, and CFRAC builds congruences of squares out of the convergents of
\(\sqrt{N}\). The implementing tools are documented in
[the forms laboratory](../FORMS_LAB.md) and
[the factorization laboratory](../FACTOR_LAB.md).

## Binary quadratic forms

A **binary quadratic form** is

\[
f(x, y) = a x^2 + b xy + c y^2, \qquad a, b, c \in \mathbb{Z},
\]

written \((a, b, c)\). Its **discriminant** is

\[
D = b^2 - 4ac .
\]

Because \(b^2 \equiv b \pmod 2\), any \(D\) arising this way satisfies
\(D \equiv 0\) or \(1 \pmod 4\), and conversely every such \(D \ne 0\) is the
discriminant of some form. \(D \equiv 0, 1 \pmod 4\) is therefore the definition of a
**discriminant**, and it is exactly the condition Numerisect checks on the tools that
take \(D\) directly.

A **square** discriminant is excluded: the form then factors into two linear forms
over \(\mathbb{Q}\) and the theory degenerates. A form is **primitive** when
\(\gcd(a, b, c) = 1\); the class group is built from primitive forms.

### Definite and indefinite

The sign of \(D\) governs everything, because \(4a f(x,y) = (2ax + by)^2 - D y^2\).

- **\(D < 0\): definite.** \(f\) takes values of one sign only, positive when
  \(a > 0\). Only positive definite forms are considered (a negative definite form is
  just \(-f\)), so \(a > 0\) is required.
- **\(D > 0\): indefinite.** \(f\) takes both signs.

That single sign difference produces the two distinct reduction theories below, and
it is why every Numerisect forms report states which case it is in.

### Equivalence and reduction

\(\mathrm{SL}_2(\mathbb{Z})\) acts on forms by substitution: for
\(\begin{pmatrix} \alpha & \beta \\ \gamma & \delta \end{pmatrix}\) of determinant 1,
send \(f(x,y) \mapsto f(\alpha x + \beta y,\; \gamma x + \delta y)\). This preserves
the discriminant and preserves the set of integers represented, so it is the right
notion of sameness. Two forms in the same orbit are **properly equivalent**.

**Reduction for \(D < 0\).** A positive definite form is reduced when

\[
|b| \le a \le c, \qquad\text{and } b \ge 0 \text{ whenever } |b| = a \text{ or } a = c .
\]

**Every class contains exactly one reduced form.** Reduction is a finite algorithm —
alternately normalise \(b\) into \((-a, a]\) and swap \((a,b,c) \mapsto (c,-b,a)\)
when \(a > c\) — and it terminates because \(a\) strictly decreases at each swap.
Since a reduced form has \(a \le \sqrt{|D|/3}\), there are only finitely many.

**Reduction for \(D > 0\).** There is no unique fixed point. A form is reduced when

\[
\left|\sqrt{D} - 2|a|\right| < b < \sqrt{D},
\]

and the reduction operator permutes the reduced forms of a class in a **cycle**.
Each class is therefore a periodic cycle of reduced forms rather than a single
representative, and every question about the class — is it principal? is it
ambiguous? — becomes a walk around that cycle.

!!! note "Why the indefinite case is harder, and more useful"
    The cycle is a nuisance for bookkeeping and the entire point for factoring.
    SQUFOF exists because the principal cycle of an indefinite discriminant can be
    walked cheaply and something factorable can be found in it. Numerisect walks the
    cycle with single-step `qfbred(f, 1)`, and an exhausted cycle cap reads
    `inconclusive` rather than `no`.

**In Numerisect.** *Reduce a form* (`POST /api/forms/reduce`) gives the reduced form,
the step-by-step trace, and the \(\mathrm{SL}_2(\mathbb{Z})\) matrix from
`qfbredsl2` with `matdet` confirming determinant 1. PARI's `Qfb` performs the
discriminant validity check and refuses a negative definite form, since PARI
represents only \(a > 0\).

## The class group

### Composition

Gauss's composition takes two primitive forms of the same discriminant to a third,
and — this is the substance — it descends to a well-defined operation on proper
equivalence classes. Under it, the classes of primitive forms of discriminant \(D\)
form a **finite abelian group**, the **form class group** \(\mathrm{Cl}(D)\):

- the identity is the class of the **principal form**,
  \((1, 0, -D/4)\) when \(D \equiv 0\), and \((1, 1, (1-D)/4)\) when
  \(D \equiv 1 \pmod 4\);
- the inverse of \((a, b, c)\) is \((a, -b, c)\).

Its order \(h(D)\) is the **class number**.

Bhargava's reinterpretation of composition via \(2 \times 2 \times 2\) cubes is the
modern way to see why the operation is natural rather than a formula pulled out of
the air, but the classical Dirichlet "united forms" construction is what algorithms
implement.

### Ambiguous classes and genus theory

A class equals its own inverse exactly when it contains a form with
\((a, b, c) \sim (a, -b, c)\). Concretely, a form is **ambiguous** when
\(a \mid b\) or \(a = c\): in the first case the substitution
\((x, y) \mapsto (x - (b/a)y,\, y)\) and in the second \((x,y) \mapsto (-y, x)\)
carries \((a,b,c)\) to \((a,-b,c)\).

The ambiguous classes are precisely the 2-torsion of \(\mathrm{Cl}(D)\). Genus theory
computes their number: if the discriminant has \(t\) prime discriminant factors then
there are \(2^{t-1}\) genera, and the principal genus is the subgroup of squares.
This is what connects 2-torsion to factorization — an ambiguous form of discriminant
\(4N\) essentially *is* a factorization of \(N\) — and it is the reason the section
on SQUFOF below is in this page and not somewhere else.

### Why the class number matters

\(h(D)\) measures the failure of unique factorization in the corresponding quadratic
order. \(h = 1\) means every ideal is principal and factorization into irreducibles
is unique. For imaginary quadratic **fields**, the complete list of class number one
is the nine Heegner discriminants

\[
-3,\; -4,\; -7,\; -8,\; -11,\; -19,\; -43,\; -67,\; -163,
\]

a fact conjectured by Gauss, proved by Heegner and independently by Baker and Stark.
\(D = -163\) is the largest, and it is why \(e^{\pi\sqrt{163}}\) is so close to an
integer.

Class numbers grow: for \(D < 0\), \(h(D)\) is roughly of size \(\sqrt{|D|}\) up to
logarithmic factors, made precise by Dirichlet's class number formula and the
Brauer–Siegel theorem — the latter, notoriously, with an ineffective constant.

!!! warning "Class numbers can be conditional"
    PARI's `quadclassunit` and `bnfinit` use a bound on the generators that assumes
    the **generalized Riemann hypothesis**. Numerisect says so in the report, and
    certifies with `bnfcertify` where the budget allows; an exhausted budget makes
    the certification `inconclusive`, which means the class number stands **only**
    under GRH. It is never presented as unconditional when it is not.

**In Numerisect.** *Compose and exponentiate* (`POST /api/forms/compose`) uses
`qfbcomp`, `qfbcompraw`, `qfbpow` and `qfbpowraw`, with `qfbprimeform(D, 1)` giving
the principal form, and reports principality and class order. *Class number and class
group* (`POST /api/forms/class-group`) cross-checks Shanks' `qfbclassno` against
`quadclassunit` — a disagreement is raised as an engine error, never returned — and
adds the Hurwitz class number `qfbhclassno` for \(D < 0\) and the norm of the
fundamental unit from `quadunit` for \(D > 0\). *Enumerate reduced forms*
(`POST /api/forms/reduced-forms`) lists the reduced forms class by class and flags
every ambiguous one, and separately those whose \(|a|\) is a perfect square.

Verified reference values from `tests/test_forms_lab.py`: \(h(-23) = 3\) with class
group \(\mathbb{Z}/3\) generated by \(\mathrm{Qfb}(2,1,3)\); \(h(-163) = 1\);
\(D = -47\) has 5 reduced forms with principal form \(\mathrm{Qfb}(1,1,12)\).

## Continued fractions

Every real \(\alpha\) has a continued fraction expansion

\[
\alpha = a_0 + \cfrac{1}{a_1 + \cfrac{1}{a_2 + \cdots}} = [a_0; a_1, a_2, \ldots],
\qquad a_0 = \lfloor \alpha \rfloor,\ a_i \ge 1 \text{ for } i \ge 1,
\]

produced by \(\alpha_{n+1} = 1/(\alpha_n - a_n)\).

### Three classification theorems

- **Finite \(\iff\) rational.** The expansion terminates exactly when \(\alpha \in
  \mathbb{Q}\); the algorithm is then the Euclidean algorithm on numerator and
  denominator, and the partial quotients are its quotients.
- **Eventually periodic \(\iff\) quadratic irrational** (Euler one way, **Lagrange**
  the other). This is the theorem that makes continued fractions an arithmetic tool
  rather than an approximation trick.
- **Purely periodic \(\iff\) reduced quadratic irrational** (Galois): \(\alpha > 1\)
  and its conjugate lies in \((-1, 0)\).

### Convergents are the best approximations

The convergents \(p_n/q_n = [a_0; a_1, \ldots, a_n]\) satisfy the recurrences
\(p_n = a_n p_{n-1} + p_{n-2}\), \(q_n = a_n q_{n-1} + q_{n-2}\), and

\[
\left|\alpha - \frac{p_n}{q_n}\right| < \frac{1}{q_n q_{n+1}} \le \frac{1}{q_n^2}.
\]

More strongly, \(p_n/q_n\) is a **best approximation of the second kind**:
\(|q_n\alpha - p_n| < |q\alpha - p|\) for every \(q < q_{n+1}\) and every \(p\). The
converse is Legendre's: if \(|\alpha - p/q| < 1/(2q^2)\) then \(p/q\) is a convergent.
So "the good rational approximations" and "the convergents" are the same set, which
is why continued fractions and not decimal truncation are the tool of choice here.

### The expansion of \(\sqrt{d}\)

For a positive non-square \(d\) the expansion has the distinctive shape

\[
\sqrt{d} = [\,a_0; \overline{a_1, a_2, \ldots, a_{L-1}, 2a_0}\,],
\]

periodic from the first term after \(a_0\), ending each period in \(2a_0\), and with
the head \([a_1, \ldots, a_{L-1}]\) **palindromic**. For \(d = 13\) this is
\([3; \overline{1,1,1,1,6}]\), period length 5, palindromic head \(1,1,1,1\).

!!! warning "Floating point cannot give you this"
    PARI's `contfrac` takes a `t_REAL`, so its tail is unreliable and it reports no
    period at all: at the default 38 digits `contfrac(sqrt(13))` ends in a spurious
    `7`. Numerisect therefore runs the classical exact \((P, Q)\) recursion in
    integer arithmetic with `sqrtint`, detects the period by **state repetition**
    rather than by guessing, and cross-checks its emitted prefix term by term against
    `contfrac` at raised precision. A disagreement is an engine error, not a result.

**In Numerisect.** *Continued fractions* (`POST /api/forms/continued-fraction`)
accepts a rational \(p/q\) or a quadratic irrational \((p + \sqrt d)/q\) and returns
the partial quotients, the convergents from `contfracpnqn`, the preperiod and period,
a palindromic-head flag (marked not applicable for surds other than \(\sqrt d\)), and
the best rational approximation below a denominator bound from `bestappr`. A quotient
limit too small to close the period reports the period as `inconclusive` with
`complete: false` — it never reports a shorter period. Because \(q_n\) grows at least
as fast as the Fibonacci numbers, a convergent quickly outgrows anything a JSON response
should carry: values wider than the requested preview are abbreviated with their exact
first and last twelve digits and their exact digit count, and every convergent is written
at full length to a separate export file.

## Pell's equation and the fundamental unit

**Theorem (Lagrange).** For \(d\) a positive non-square, \(x^2 - dy^2 = 1\) has
infinitely many integer solutions, and they are the powers of a least positive one,
the **fundamental solution**.

The connection to continued fractions is exact. Let \(L\) be the period length of
\(\sqrt d\). Then \(p_{n}^2 - d q_{n}^2 = \pm 1\) precisely at \(n = kL - 1\), and:

- if \(L\) is **even**, \(p_{L-1}^2 - d q_{L-1}^2 = +1\) and the negative Pell
  equation \(x^2 - dy^2 = -1\) has **no** solution;
- if \(L\) is **odd**, \(p_{L-1}^2 - d q_{L-1}^2 = -1\), so the negative equation is
  solvable, and the fundamental solution of the \(+1\) equation is at \(n = 2L - 1\).

Algebraically this is the unit group of a real quadratic order. In
\(\mathbb{Z}[\sqrt d]\), the order of discriminant \(4d\), the norm form is
\(N(x + y\sqrt d) = x^2 - d y^2\), so Pell solutions are exactly the units of norm
\(+1\). By Dirichlet's unit theorem the unit group of a real quadratic order is
\(\{\pm 1\} \times \langle \varepsilon \rangle\) for a **fundamental unit**
\(\varepsilon\), and \(\log \varepsilon\) is the **regulator**.

Numerisect therefore solves Pell **from the unit, not by search**: `quadunit(4d)` is
\(\varepsilon\), and

- \(N(\varepsilon) = -1\): the negative equation is solvable with \(\varepsilon\)'s
  own coordinates, and the fundamental Pell solution is \(\varepsilon^2\). For
  \(d = 13\), \(\varepsilon = 18 + 5\sqrt{13}\) has norm \(-1\) and squaring gives
  \((649, 180)\).
- \(N(\varepsilon) = +1\): the negative equation is unsolvable and \(\varepsilon\) is
  already the fundamental Pell solution. For \(d = 3\), \(\varepsilon = 2 + \sqrt 3\)
  gives \((2, 1)\).

Every returned pair is verified as \(x^2 - dy^2 = 1\) inside PARI, and `bestappr`
independently confirms that the fundamental solution is the convergent of \(\sqrt d\)
at the end of its period — which is why \(\texttt{bestappr}(\sqrt{13}, 1000)\)
returns \(649/180\). `quadregulator(4d)` is the logarithm of the same unit.

Fundamental solutions grow violently with \(d\): for \(d = 61\) it is
\((1766319049,\ 226153980)\) with period 11, and for \(d = 1621\) it has hundreds of
digits. Numerisect caps each Pell solution at \(10^5\) decimal digits and returns at
most 100 of them.

**In Numerisect.** *Pell's equation* (`POST /api/forms/pell`) — `quadunit`, `norm`,
`quadregulator`, `quadgen`, `bestappr`, `issquare`. If `quadunit` exceeds its budget
the report says so and claims no solution.

The fundamental solution can be astronomically large before any power is taken. The
classical illustration is \(d = 61\), whose least solution is
\((1766319049,\ 226153980)\); a harder one is \(d = 1000099\), where \(x\) already has
1,128 decimal digits. No solution is ever dropped for being long: values wider than the
requested preview are abbreviated with their exact leading and trailing digits and their
exact digit count, and every solution is written at full length to a separate export
file, where each pair has been substituted back into \(x^2 - dy^2 = 1\).

## Representing integers by forms

Which integers does \(f\) represent? For the principal form of discriminant \(D\)
this is a question about norms of ideals, and in general it is decided modulo \(D\)
by genus theory plus a class-group condition.

The clean classical cases:

- **Sums of two squares** (Fermat). \(n = x^2 + y^2\) is solvable exactly when every
  prime \(\equiv 3 \pmod 4\) divides \(n\) to an even power. Jacobi's count is
  \(r_2(n) = 4\bigl(d_1(n) - d_3(n)\bigr)\), the difference of the number of
  divisors \(\equiv 1\) and \(\equiv 3 \pmod 4\), scaled by the four units of
  \(\mathbb{Z}[i]\).
- **\(x^2 + dy^2 = p\)** for prime \(p\): solvable exactly when \(-d\) is a quadratic
  residue mod \(p\) **and** the corresponding form class is principal. For \(d = 1, 2,
  3\) the class number is 1 so the residue condition alone decides it; for larger
  \(d\) it does not, and that is the historical origin of class field theory.

**Cornacchia's algorithm** solves \(x^2 + dy^2 = m\) directly, in essentially the
time of one Euclidean algorithm:

1. find \(r\) with \(r^2 \equiv -d \pmod m\), taking the root with \(m/2 < r < m\);
2. run the Euclidean algorithm on \((m, r)\), stopping at the first remainder
   \(b < \sqrt m\);
3. accept \((b, y)\) if \((m - b^2)/d\) is a perfect square \(y^2\).

It is the standard primitive in ECPP and in constructing curves with prescribed
complex multiplication, which is why Numerisect exposes it as a traced algorithm.

**In Numerisect.** *Represent an integer by a form* (`POST /api/forms/represent`)
uses `qfbsolve` with flag 1 for primitive solutions and flag 3 for all of them;
\(x^2 + 3y^2 = 1729\) returns 8 primitive solutions including \((23, -20)\) and
\((31, 16)\). *Cornacchia* (`POST /api/algebra/cornacchia`) runs the Euclidean
descent over every square divisor \(g^2\) of \(n\), verifies every representation
against \(x^2 + dy^2 = n\), and then compares the **complete solution set** with
`qfbsolve(Qfb(1,0,d), n, 3)` as a set, after closing both sides under the
automorphism group of the form (\(\{\pm 1\}\), plus the coordinate swap when
\(d = 1\), because \(x^2 + y^2\) has that extra symmetry). For prime \(n\) the
primitive representation is also checked against `qfbcornacchia`.
Representation counts \(r_2(n)\) and \(r_4(n)\) appear on the *extended arithmetic*
page (`POST /api/number-theory/arithmetic-functions`).

## Quadratic fields

Let \(d \ne 0, 1\) be squarefree and \(K = \mathbb{Q}(\sqrt d)\). Its ring of
integers is

\[
\mathcal{O}_K =
\begin{cases}
\mathbb{Z}\!\left[\frac{1 + \sqrt d}{2}\right], & d \equiv 1 \pmod 4, \quad D_K = d,\\
\mathbb{Z}[\sqrt d], & d \equiv 2, 3 \pmod 4, \quad D_K = 4d .
\end{cases}
\]

\(K\) is **imaginary** for \(d < 0\) and **real** for \(d > 0\); the unit group is
finite (just roots of unity) in the first case and rank one in the second, which is
the Pell dichotomy again.

### Splitting, inertia, ramification

A rational prime \(p\) generates an ideal \(p\mathcal{O}_K\) that factors in exactly
one of three ways, and the **Kronecker symbol decides which**:

| \(\left(\frac{D_K}{p}\right)\) | Behaviour | Factorization | \((e, f)\) |
|---|---|---|---|
| \(+1\) | **split** | \(p\mathcal{O}_K = \mathfrak{p}\bar{\mathfrak{p}}\), distinct | \((1, 1)\) twice |
| \(-1\) | **inert** | \(p\mathcal{O}_K\) is prime | \((1, 2)\) |
| \(0\) | **ramified** | \(p\mathcal{O}_K = \mathfrak{p}^2\) | \((2, 1)\) |

The ramified primes are exactly the divisors of \(D_K\), so there are finitely many.
In every case \(\sum_i e_i f_i = 2 = [K : \mathbb{Q}]\), the identity that
Numerisect's number-field page checks for general degrees.

The connection back to forms is the reason this section exists: for a fundamental
discriminant \(D\), the form class group \(\mathrm{Cl}(D)\) is isomorphic to the
ideal class group of \(\mathcal{O}_K\) (the **narrow** class group when \(D > 0\)),
under the map sending a form \((a, b, c)\) to the ideal
\(\bigl(a, \frac{-b + \sqrt D}{2}\bigr)\). "Which primes does \(x^2 + dy^2\)
represent" and "which primes split into principal ideals in
\(\mathbb{Q}(\sqrt{-d})\)" are the same question asked twice.

**In Numerisect.** *Quadratic integer rings* (`POST /api/algebra/quadratic-ring`)
reports \(\omega\), \(N(a + b\omega)\), \(\mathrm{Tr}(a + b\omega)\), unit and prime
status in the ring, roots of unity, the fundamental unit for real fields, the class
group, and the decomposition of a requested rational prime with an explicit generator
for each principal prime ideal — from `core`, `quaddisc`, `quadgen`, `norm`, `trace`,
`quadunit`, `quadclassunit`, `bnfinit`, `bnfcertify`, `kronecker`, `idealprimedec`,
`bnfisprincipal` and `nfbasistoalg`. The lighter *quadratic prime decomposition*
page (`POST /api/number-theory/quadratic-decomposition`,
`nt_quadratic_prime_decomposition`) gives the Kronecker symbol, the field
discriminant and the \((e, f, p^f)\) data from `nfinit` and `idealprimedec` alone.
For degrees above 2, *number fields* (`POST /api/algebra/number-field`) does the same
with `nfinit` and `idealprimedec` and checks \(\sum e_i f_i = n\).

## The link to factoring

### SQUFOF walks the principal cycle

Shanks' **square forms factorization** is a statement about indefinite forms. To
split \(N\), take the discriminant \(4kN\) for a small multiplier \(k\), start at the
principal form, and walk the principal cycle by repeated single-step reduction
looking for an **ambiguous** form. The leading coefficient of an ambiguous form in
that cycle exposes a factor of \(N\) — which is genus theory in action: an ambiguous
class is 2-torsion, and 2-torsion in a class group of discriminant \(4kN\) is
precisely a factorization of \(N\).

!!! example "Seeing the cycle SQUFOF searches"
    \(N = 1817 = 23 \times 79\), so \(D = 4N = 7268\). Enumerating the reduced forms
    of that discriminant gives a principal cycle of **28** forms containing
    \(\mathrm{Qfb}(23, 46, -56)\). Here \(23 \mid 46\), so the form is ambiguous, and
    23 is exactly the factor the C helper extracts.

    ```bash
    curl --cookie jar --header 'Content-Type: application/json' \
      --data '{"discriminant":"7268"}' \
      http://127.0.0.1:8765/api/forms/reduced-forms
    ```

The forms lab **shows** that cycle; it does not factor with it. The factoring
implementation is `numerisect/native/numerisect_squfof.c`, reached through
`POST /api/factor-lab/squfof` and available as the `squfof` job backend. It is
written in C because SQUFOF is absent from every installed engine — PARI implements
it internally inside `factorint` but exposes no `squfof()` in the GP language, and
`factorint` flag `4` disables it only together with Pollard–Brent rho. Inputs must
be below \(2^{62}\); above that the multiplier-scaled discriminant leaves the 64-bit
range and larger inputs are **rejected with a message**, not answered incorrectly. A
run that finds nothing reports `status: exhausted`, which is **inconclusive** and
never a claim that the input is prime. See
[the factorization laboratory](../FACTOR_LAB.md).

### CFRAC uses the convergents of \(\sqrt N\)

The continued fraction factorization method exploits that the convergents of
\(\sqrt N\) make

\[
Q_n = p_n^2 - N q_n^2
\]

small — bounded by \(2\sqrt N\) in absolute value — so \(p_n^2 \equiv Q_n \pmod N\)
with \(Q_n\) small enough to have a real chance of being smooth over a modest factor
base. Collecting enough smooth \(Q_n\) and combining them by linear algebra over
\(\mathbb{F}_2\) produces a congruence of squares \(x^2 \equiv y^2 \pmod N\), and
\(\gcd(x - y, N)\) then splits \(N\) with probability at least \(1/2\).

**Numerisect does not implement CFRAC as a factoring method,** and this is a
deliberate choice rather than an omission. The self-initializing quadratic sieve
finds smooth relations far faster than the continued-fraction recursion can supply
them, at every size, so Factor Lab routes those inputs to SIQS through YAFU. The
continued-fraction tools on this page are exposition of where the idea came from.

## Where this appears in Numerisect

| Topic | Tool (route) | Engine routine |
|---|---|---|
| Reduction, equivalence, the \(\mathrm{SL}_2\) matrix | Reduce a form (`/api/forms/reduce`) | `Qfb`, `qfbred`, `qfbred(f,1)`, `qfbredsl2`, `matdet`, `quaddisc`, `isfundamental` |
| Gauss composition, powers, principality, class order | Compose (`/api/forms/compose`) | `qfbcomp`, `qfbcompraw`, `qfbpow`, `qfbpowraw`, `qfbprimeform(D,1)` |
| Prime forms of a discriminant | Prime form (`/api/forms/prime-form`) | `qfbprimeform`, `qfbred`, `kronecker`, `isprime` |
| Class number, structure, generators, regulator | Class group (`/api/forms/class-group`) | `qfbclassno` cross-checked against `quadclassunit`; `qfbhclassno`; `quadunit` |
| Reduced-form enumeration, cycles, ambiguous forms | Reduced forms (`/api/forms/reduced-forms`) | `quadclassunit`, `qfbpow`, `qfbcomp`, `qfbred(f,1)`, `issquare` |
| Representation of an integer by a form | Represent (`/api/forms/represent`) | `qfbsolve` flags 1 and 3 |
| Expansion, period, convergents, best approximation | Continued fractions (`/api/forms/continued-fraction`) | exact \((P,Q)\) recursion with `sqrtint`, cross-checked against `contfrac`; `contfracpnqn`, `bestappr` |
| Fundamental solution, negative Pell, regulator | Pell (`/api/forms/pell`) | `quadunit`, `norm`, `quadregulator`, `quadgen`, `bestappr` |
| Cornacchia descent, \(x^2 + dy^2 = n\) | Cornacchia (`/api/algebra/cornacchia`) | `qfbsolve`, `qfbcornacchia`, `polrootsmod`, `issquare`, `sqrtint`, `fordiv` |
| \(r_2(n)\), \(r_4(n)\), difference of squares | Extended arithmetic (`/api/number-theory/arithmetic-functions`) | `nt_arithmetic` (PARI `divisors`, `qfbsolve`) |
| Quadratic ring, units, splitting, class group | Quadratic integer rings (`/api/algebra/quadratic-ring`) | `core`, `quaddisc`, `quadgen`, `quadunit`, `quadclassunit`, `bnfinit`, `bnfcertify`, `idealprimedec`, `bnfisprincipal` |
| Kronecker symbol and \((e, f)\) for one prime | Quadratic decomposition (`/api/number-theory/quadratic-decomposition`) | `nt_quadratic_prime_decomposition` (`nfinit`, `idealprimedec`, `kronecker`) |
| Higher-degree splitting and ramification | Number fields (`/api/algebra/number-field`) | `nfinit`, `idealprimedec`, `idealfactor`, `nfeltnorm`, `polgalois` |
| SQUFOF as a factoring method | Factor lab (`/api/factor-lab/squfof`) | `numerisect-squfof` (C with GMP), factors labelled by PARI `isprime` |
| Dedekind zeta of a quadratic field | Zeta lab (`/api/zeta/dedekind`) | PARI `nfinit`, `lfuncreate`, `lfun`, `lfunzeros`, `bnfinit` |

## References

- D. A. Buell, *Binary Quadratic Forms: Classical Theory and Modern Computations*,
  Springer (1989) — reduction in both signs, composition, cycles, genus theory, and
  the SQUFOF connection.
- D. A. Cox, *Primes of the Form \(x^2 + ny^2\)*, 2nd ed., Wiley — the arc from
  Fermat through Gauss's composition to class field theory.
- H. Cohen, *A Course in Computational Algebraic Number Theory*, Springer GTM 138 —
  §1.5.2 (Cornacchia), §5.2–5.4 (forms, class groups, SQUFOF), §5.7 (continued
  fractions and Pell), §4.8 and §6.2 (prime decomposition).
- R. Crandall and C. Pomerance, *Prime Numbers: A Computational Perspective*, 2nd ed.
  — §5.6 (SQUFOF), §6.1 (CFRAC and congruences of squares).
- C. F. Gauss, *Disquisitiones Arithmeticae* (1801) — Sections V and VI: the original
  theory of forms, composition, and genera.
- G. H. Hardy and E. M. Wright, *An Introduction to the Theory of Numbers*, 6th ed. —
  Chapters 10 and 11 (continued fractions), Chapters 12–15 (quadratic fields, sums of
  two squares).
- D. Shanks, "Class number, a theory of factorization, and genera",
  *Proc. Sympos. Pure Math.* **20** (1971) — SQUFOF and its class-group setting.
- [PARI/GP binary quadratic forms](https://pari.math.u-bordeaux.fr/dochtml/html-stable/Arithmetic_functions.html)
  and [general number fields](https://pari.math.u-bordeaux.fr/dochtml/html-stable/General_number_fields.html).
- Numerisect: [forms laboratory](../FORMS_LAB.md),
  [factorization laboratory](../FACTOR_LAB.md),
  [algebra laboratory](../ALGEBRA_LAB.md).
