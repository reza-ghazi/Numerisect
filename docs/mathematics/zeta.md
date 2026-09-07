# The Riemann zeta function and L-functions

This page covers the analytic core of Numerisect: the definition and Euler product of
\(\zeta(s)\), its continuation and functional equation, the trivial and nontrivial
zeros, the Riemann hypothesis and what it is equivalent to, the computational
machinery of Hardy's \(Z\) function, Gram points, \(N(T)\), \(S(T)\) and the Turing
method, the Riemann–Siegel formula, the explicit formula linking zeros to \(\psi(x)\)
and \(\pi(x)\), the statistics of zero spacings and the GUE connection, Dirichlet
characters and \(L\)-functions with the generalised Riemann hypothesis, Dedekind zeta
functions, and finally the ball arithmetic that lets Numerisect say *certified* about
some of these results and only *exploratory* about others. The tools are documented in
[Riemann zeta tools](../RIEMANN_ZETA.md) and [the zeta lab](../ZETA_LAB.md).

!!! warning "Certified and exploratory are not synonyms"
    Numerisect uses those two words in a technical sense, and this page uses them the
    same way. **Certified** means a rigorous Arb ball enclosure, or a decision that
    could only be reached because an enclosure excluded zero. **Exploratory** means a
    number that is probably right and proves nothing — a truncated sum, a histogram
    bin, a plot sample taken from enclosure midpoints, or any PARI floating-point
    output. The last section explains why the distinction is real and not decorative.

## Definition and Euler product

For \(\mathrm{Re}\,s > 1\),

\[
\zeta(s) = \sum_{n=1}^{\infty} \frac{1}{n^s}
= \prod_{p \text{ prime}} \left(1 - \frac{1}{p^s}\right)^{-1}.
\]

The identity is Euler's, and expanding each factor as a geometric series and
multiplying out is exactly the statement that every integer factors into primes in
one way. That is the whole reason a function of a complex variable has anything to
say about primes: **the Euler product is unique factorization written analytically.**

Taking logarithms of the product and differentiating gives

\[
-\frac{\zeta'(s)}{\zeta(s)} = \sum_{n=1}^{\infty} \frac{\Lambda(n)}{n^s},
\]

which is the bridge used in every proof of the prime number theorem and the source of
the explicit formula below.

**In Numerisect.** *Euler-product comparison* (`POST /api/zeta/euler-product`)
evaluates the truncated product over primes from FLINT's `n_primes_t` sieve with
`acb_pow`, compares it against `acb_dirichlet_zeta`, and reports the deviation and a
rigorous truncation bound — the half-plane condition \(\mathrm{Re}\,s > 1\) is
checked as a ball comparison, so a request that cannot be decided is refused rather
than answered. Every partial value, deviation and bound on that page is **certified**.

## Continuation, the functional equation, and the zeros

\(\zeta\) continues to a meromorphic function on all of \(\mathbb{C}\), analytic
except for a **simple pole at \(s = 1\) with residue 1**. The continuation is
governed by the completed function

\[
\xi(s) = \tfrac{1}{2}\, s (s - 1)\, \pi^{-s/2}\, \Gamma\!\left(\tfrac{s}{2}\right) \zeta(s),
\]

which is entire and satisfies the **functional equation**

\[
\xi(s) = \xi(1 - s).
\]

Unwinding gives the asymmetric form

\[
\zeta(s) = 2^s \pi^{s-1} \sin\!\left(\frac{\pi s}{2}\right) \Gamma(1 - s)\, \zeta(1-s).
\]

Two families of zeros follow.

- **Trivial zeros** at \(s = -2, -4, -6, \ldots\), forced by the poles of
  \(\Gamma(s/2)\) in the completed function; equivalently by the sine factor.
- **Nontrivial zeros**, all lying in the **critical strip**
  \(0 < \mathrm{Re}\,s < 1\). The functional equation makes them symmetric about
  \(s \mapsto 1 - s\), and \(\overline{\zeta(\bar s)} = \zeta(s)\) makes them
  symmetric about the real axis, so they come in quadruples \(\rho, \bar\rho,
  1-\rho, 1-\bar\rho\) unless \(\mathrm{Re}\,\rho = 1/2\), when the quadruple
  degenerates to a pair.

The line \(\mathrm{Re}\,s = 1/2\) is the **critical line**, the axis of that
symmetry. The first few nontrivial zeros have ordinates
\(14.134725141\ldots\), \(21.022039639\ldots\), \(25.010857580\ldots\).

**In Numerisect.** *Evaluate \(\zeta(s)\)* (`POST /api/zeta/evaluate`, `acb_zeta`)
returns rigorous enclosures for real part, imaginary part, magnitude and argument, and
rejects \(s = 1\). *Completed xi and Dirichlet eta*
(`POST /api/zeta/xi-eta`) use `acb_dirichlet_xi` and `acb_dirichlet_eta`. *Functional
equation* (`POST /api/zeta/functional-equation`) evaluates both sides
**independently** in FLINT/Arb and reports the equation as verified **only when the
two complex balls overlap** — which is a genuine check, not a restatement.
*Stieltjes constants* (`POST /api/zeta/stieltjes`, `acb_dirichlet_stieltjes`) give
rigorous enclosures for the \(\gamma_n\) in the Laurent expansion at \(s = 1\).

## The Riemann hypothesis

**Conjecture (Riemann, 1859).** Every nontrivial zero of \(\zeta\) satisfies
\(\mathrm{Re}\,\rho = \tfrac{1}{2}\).

This is a conjecture. Numerisect never states it, or anything derived from it, as a
theorem.

What is proved: infinitely many zeros lie on the critical line (Hardy, 1914); a
positive proportion do (Selberg), and at least two fifths do (Conrey, 1989); the
first \(3 \times 10^{12}\) zeros by ordinate do, verified rigorously by Platt and
Trudgian (2021). None of that is evidence about the rest, in the strict sense that
none of it constrains the zeros above the computed height.

### What RH is equivalent to

The reason RH is *the* problem in prime number theory is that it is exactly a
statement about the error term in the prime number theorem. The following are
equivalent to RH:

\[
\psi(x) = x + O\!\left(\sqrt{x}\,\log^2 x\right),
\qquad
\pi(x) = \mathrm{li}(x) + O\!\left(\sqrt{x}\,\log x\right).
\]

Schoenfeld made the second explicit: RH is equivalent to
\(|\pi(x) - \mathrm{li}(x)| < \dfrac{\sqrt x \log x}{8\pi}\) for all \(x \ge 2657\).

Unconditionally, all that is known is the de la Vallée Poussin form, coming from a
zero-free region just left of \(\mathrm{Re}\,s = 1\):
\(\psi(x) = x + O\!\left(x\,e^{-c\sqrt{\log x}}\right)\), which is very much weaker.
The general principle is that a zero at \(\mathrm{Re}\,\rho = \sigma\) contributes a
term of size \(x^{\sigma}\) to the error, so the supremum of the real parts of the
zeros **is** the exponent in the error term. RH says that supremum is \(1/2\), the
smallest it can be.

Two equivalents outside analysis are worth knowing because Numerisect computes both
sides of them: \(M(x) = O(x^{1/2 + \varepsilon})\) for the Mertens function, and the
same for the summatory Liouville function — see
[the modular page](modular.md#summatory-functions), which also records that the
stronger *Mertens conjecture* \(|M(x)| < \sqrt x\) is false.

## Hardy's \(Z\) function and the geometry of the critical line

To find zeros on the critical line one wants a **real** function whose sign changes
are the zeros. That is Hardy's \(Z\):

\[
Z(t) = e^{i\theta(t)}\, \zeta\!\left(\tfrac{1}{2} + it\right),
\qquad
\theta(t) = \arg \Gamma\!\left(\tfrac{1}{4} + \tfrac{it}{2}\right) - \tfrac{t}{2}\log \pi .
\]

The Riemann–Siegel theta function \(\theta\) is chosen precisely so that the phase
cancels: \(Z(t)\) is real for real \(t\), and \(|Z(t)| = |\zeta(1/2 + it)|\). A sign
change of \(Z\) between two points is therefore a zero of \(\zeta\) on the critical
line, of odd order, in that interval.

### Gram points and Gram's law

\(\theta\) is increasing for \(t\) large, so \(\theta(t) = n\pi\) has a unique
solution \(g_n\), the \(n\)-th **Gram point**; \(g_0 = 17.8455995404\ldots\). Since
the leading behaviour of \(Z\) is dominated by its first term \(2\cos\theta(t)\),
one expects \(Z(g_n)\) to alternate in sign with \(n\):

**Gram's law (an empirical rule, not a theorem).** \((-1)^n Z(g_n) > 0\).

It usually holds, and it fails infinitely often. Its **first failure is at
\(n = 126\)**, where \(g_{126} = 282.4547208234621746\ldots\) and
\(Z(g_{126}) = -0.0276294988571999\ldots\) although 126 is even. When Gram's law
holds on a stretch, each Gram interval \([g_n, g_{n+1})\) contains exactly one zero
and counting is trivial; the failures are exactly where a rigorous count needs more
than the rule. A **Gram block** is a maximal run \([g_n, g_{n+k})\) with good
endpoints and \(k-1\) bad interior points, and it is the unit in which exceptions
are organised.

**In Numerisect.** *Gram point* (`POST /api/zeta/gram`, `acb_dirichlet_gram_point`)
gives one \(g_n\) as a rigorous enclosure. *Gram blocks and exceptions*
(`POST /api/zeta/gram-blocks`) scans an index range with `acb_dirichlet_gram_point`
and `acb_dirichlet_hardy_z`. Every verdict is **certified**: a Gram point is called
*good* or *bad* only when the enclosure of \((-1)^n Z(g_n)\) strictly excludes zero,
and otherwise it is reported as **inconclusive**. Scanning indices 120–131 reports
exactly one exception and one Gram block, \(n = 125\) of length 2 with pattern
`gbg`.

### Counting zeros: \(N(T)\), \(S(T)\), and Turing's method

Let \(N(T)\) be the number of zeros with \(0 < \mathrm{Im}\,\rho \le T\).

**Theorem (Riemann–von Mangoldt).**

\[
N(T) = \frac{\theta(T)}{\pi} + 1 + S(T),
\qquad
S(T) = \frac{1}{\pi}\arg \zeta\!\left(\tfrac{1}{2} + iT\right),
\]

where the argument is by continuous variation from \(2\) to \(2 + iT\) to
\(1/2 + iT\). Expanding \(\theta\),

\[
N(T) = \frac{T}{2\pi}\log\frac{T}{2\pi e} + \frac{7}{8} + S(T) + O(1/T).
\]

So the smooth part \(\theta(T)/\pi + 1\) is known exactly and everything difficult is
in \(S(T)\). Unconditionally \(S(T) = O(\log T)\), and in practice \(S(T)\) is
usually small — it stays between \(-1\) and \(1\) for a very long way — but it is
known to be unbounded, and a single unnoticed excursion would mean a missed zero.

!!! note "Why the smooth term is not a count"
    \(\theta(T)/\pi + 1\) is the **main term** of Riemann–von Mangoldt, and rounding
    it is a guess. Numerisect labels the smooth count exploratory wherever it appears
    — including the \(\theta(T,\chi)/\pi\) count on the \(L\)-zeros page — and never
    prints it as the number of zeros.

**Turing's method** turns this into a rigorous count. The key is not a bound on
\(S(T)\) pointwise but on its **average**: explicit bounds on
\(\int_{T_1}^{T_2} S(t)\,dt\) constrain how many zeros can hide, and combining that
with the number of sign changes actually observed pins \(N(T)\) to a unique integer.
FLINT implements this in `acb_dirichlet_zeta_nzeros`.

**In Numerisect.** *Count zeros through \(T\)* (`POST /api/zeta/count`) succeeds
**only** when FLINT isolates a unique integer; otherwise it reports `inconclusive`
and asks for higher precision or a different endpoint, rather than rounding. This is
**certified**. *Zero-counting remainder \(S(T)\)*
(`POST /api/zeta/backlund-s`) reports `acb_dirichlet_backlund_s`,
`acb_dirichlet_backlund_s_bound`, `acb_dirichlet_zeta_nzeros` and
`acb_dirichlet_hardy_theta`; the values are certified, but the **plotted \(S(T)\)
trace is exploratory**, because a plot shows enclosure midpoints.
*Consecutive zeros* (`POST /api/zeta/zeros`, `acb_dirichlet_hardy_z_zeros`) returns
rigorous intervals for consecutive zeros, each printed with its radius.
`N(100) = 29` is one of the pinned test values.

!!! warning "A sign-change count is a lower bound"
    Certified sign changes on a finite grid prove that at least that many zeros of
    odd order lie in the range. A coarse grid can step over a closely spaced pair.
    Raising the resolution raises the bound; nothing claims completeness.

## The Riemann–Siegel formula

Evaluating \(\zeta(1/2 + it)\) by the defining series is impossible (it does not
converge) and by Euler–Maclaurin is expensive at large \(t\). The Riemann–Siegel
formula, found by Siegel in Riemann's unpublished notes and published in 1932, gives
\(Z(t)\) in \(O(\sqrt t)\) terms:

\[
Z(t) = 2 \sum_{n=1}^{\nu} \frac{\cos\bigl(\theta(t) - t \log n\bigr)}{\sqrt n}
\; + \; R(t),
\qquad \nu = \left\lfloor \sqrt{\tfrac{t}{2\pi}} \right\rfloor .
\]

The first part is the **main sum**: a truncated Dirichlet series with the phase
folded in, of length \(\nu \approx \sqrt{t/2\pi}\). The remainder has an asymptotic
expansion in **correction terms**

\[
R(t) \sim (-1)^{\nu - 1} \left(\frac{t}{2\pi}\right)^{-1/4}
\sum_{k \ge 0} C_k(p)\left(\frac{t}{2\pi}\right)^{-k/2},
\qquad
p = \sqrt{\tfrac{t}{2\pi}} - \nu ,
\]

where each \(C_k\) is an explicit combination of derivatives of a fixed function of
the fractional part \(p\). \(C_0\) alone already gives several digits; the series is
asymptotic, so adding terms helps up to a point and then stops helping.

!!! warning "An asymptotic expansion with the remainder dropped is not a certification"
    [Riemann zeta tools](../RIEMANN_ZETA.md) records that the imported research
    prototype contained an incomplete custom approximation described as
    Riemann–Siegel, and that Numerisect does not expose that claim. Dropping the
    omitted remainder of an asymptotic formula is not a proof. What Numerisect
    exposes instead is `acb_dirichlet_zeta_rs`, which **folds a rigorous remainder
    bound into the returned ball**, together with `acb_dirichlet_zeta_rs_bound` and
    an independent `acb_dirichlet_zeta` evaluation. Every Riemann–Siegel row is
    therefore certified.

**In Numerisect.** *Riemann–Siegel remainder* (`POST /api/zeta/riemann-siegel`), with
\(t \ge 10\) and \(0 \le K \le 20\) correction terms.

## The explicit formula

This is the theorem that makes zeta a statement about primes rather than a curiosity.

**Theorem (von Mangoldt's explicit formula).** For \(x > 1\) not a prime power,

\[
\psi(x) = x \;-\; \sum_{\rho} \frac{x^{\rho}}{\rho} \;-\; \log 2\pi
\;-\; \tfrac{1}{2}\log\!\left(1 - x^{-2}\right),
\]

the sum being over nontrivial zeros, taken symmetrically in \(\rho\) and \(\bar\rho\).

Read the terms. \(x\) is the main term — this alone is the prime number theorem. The
final two are small and explicit (they come from the pole and the trivial zeros). The
sum over zeros is the **entire** fluctuation of the primes about their average: each
zero \(\rho = \beta + i\gamma\) contributes an oscillation of amplitude
\(x^{\beta}/|\rho|\) and frequency \(\gamma\) in \(\log x\). The zeros are the
frequencies of the primes.

Riemann's original version is for the counting function. With
\(J(x) = \sum_{k \ge 1} \pi(x^{1/k})/k\),

\[
J(x) = \mathrm{li}(x) - \sum_{\rho} \mathrm{li}\!\left(x^{\rho}\right) - \log 2
+ \int_x^{\infty} \frac{dt}{t(t^2 - 1)\log t},
\qquad
\pi(x) = \sum_{n \ge 1} \frac{\mu(n)}{n} J\!\left(x^{1/n}\right).
\]

The Möbius coefficients strip out the contribution of prime squares, cubes and higher
powers — the same inversion that produces Riemann's \(R(x)\) on
[the distribution page](distribution.md).

### What "prime reconstruction from zeros" means

Truncating the sum at the first \(N\) zeros gives an approximation to \(\psi(x)\) or
\(\pi(x)\) that oscillates around the true step function and sharpens as \(N\) grows;
the jumps at prime powers emerge from the interference of the terms. It is a striking
demonstration and it is **not** a computation of \(\pi(x)\): the discarded tail is not
bounded, so the result is an estimate, always.

!!! example "π(100) from 200 zeros"
    ```bash
    curl -sX POST 127.0.0.1:8765/api/zeta/explicit-prime-count \
      -H 'X-Numerisect-Token: <token>' -H 'content-type: application/json' \
      -d '{"bound":"100","zeros":200,"precision":30,"threads":8}'
    ```
    The response reports the exact \(\pi(100) = 25\) from `primecount` alongside a
    convergence table at \(N = 1, 2, 4, 8, \ldots\) zeros. The estimate walks toward
    25; it never becomes a certification. The one piece that **is** bounded
    rigorously is the tail integral, enclosed in
    \(\left[0,\; \log\!\left(\frac{x^2}{x^2-1}\right) / (2\log x)\right]\).

**In Numerisect.** *Reconstruct \(\pi(x)\) from zeros*
(`POST /api/zeta/explicit-prime-count`) uses `acb_dirichlet_hardy_z_zeros` for the
zeros, `acb_hypgeom_ei` for \(\mathrm{li}(x^\rho)\), `arb_hypgeom_li` for the
principal term, `n_moebius_mu` for the weights, and `primecount` for the exact value.
*Rebuild Chebyshev \(\psi(x)\)* (`POST /api/zeta/chebyshev-psi`) sums \(x^\rho/\rho\)
with `acb_exp` and `acb_div` and computes the exact \(\psi(x)\) from FLINT's
`n_primes_t` sieve with `arb_log_ui`; \(\psi(10) = 3\log 2 + 2\log 3 + \log 5 +
\log 7 = 7.8320141805054689907\ldots\). Both estimates are **exploratory**, by
construction. Limits: 5000 zeros in a sum, \(x \le 10^7\) for exact \(\psi\),
\(x \le 10^{12}\) for \(\pi(x)\).

## Zero statistics and the GUE connection

The zeros thin out logarithmically: near height \(T\) the average gap is
\(2\pi/\log(T/2\pi)\). To compare spacings at different heights they are
**unfolded** — rescaled to unit mean — using \(\theta\):
\(\tilde\gamma_n = \theta(\gamma_n)/\pi\), so that consecutive differences
\(\delta_n = \tilde\gamma_{n+1} - \tilde\gamma_n\) have mean 1.

**Conjecture (Montgomery's pair correlation, 1973).** For the unfolded zeros,

\[
\frac{1}{N}\#\{(n, m) : \alpha \le \tilde\gamma_n - \tilde\gamma_m \le \beta \}
\;\longrightarrow\;
\int_{\alpha}^{\beta}\left(1 - \left(\frac{\sin \pi u}{\pi u}\right)^2\right) du
\;+\; \delta(\alpha, \beta).
\]

Montgomery proved this for test functions of restricted support, assuming RH; the
general statement is conjectural. The famous part is the recognition, in conversation
with Freeman Dyson, that \(1 - (\sin \pi u / \pi u)^2\) is exactly the pair
correlation of eigenvalues of large random Hermitian matrices from the **Gaussian
Unitary Ensemble**. The zeros repel each other like eigenvalues of a random matrix,
which is the main evidence for the Hilbert–Pólya idea that the zeros are the spectrum
of some self-adjoint operator.

Odlyzko's computations — at heights up to the \(10^{20}\)-th zero and beyond — match
the GUE predictions to remarkable accuracy, and also expose the slow convergence:
lower-height statistics deviate visibly, and the agreement improves with height.

!!! warning "Histogram bins are exploratory"
    Zero ordinates are certified; **binned statistics computed from them are not**.
    A histogram is a finite sample of a limiting distribution, and Numerisect labels
    every bin on the spacing and pair-correlation pages exploratory.

**In Numerisect.** *Zero-spacing histogram* (`POST /api/zeta/zero-spacing`) uses
`acb_dirichlet_hardy_z_zeros`, unfolds with `acb_dirichlet_hardy_theta`, and draws
the GUE surmise with `arb_hypgeom_erf`. *Pair correlation*
(`POST /api/zeta/pair-correlation`) computes the same unfolding and the
\(1 - (\sin \pi u/\pi u)^2\) curve with `arb_sin`. Up to 20 000 zeros per run.

## Dirichlet characters and L-functions

A **Dirichlet character** modulo \(q\) is a homomorphism
\(\chi : (\mathbb{Z}/q\mathbb{Z})^\times \to \mathbb{C}^\times\), extended to
\(\mathbb{Z}\) by \(\chi(n) = 0\) when \(\gcd(n, q) > 1\). There are \(\varphi(q)\)
of them, forming a group isomorphic to \((\mathbb{Z}/q\mathbb{Z})^\times\) itself.
A character is **primitive** when it does not factor through a smaller modulus; the
least such modulus is its **conductor**. \(\chi\) is **even** or **odd** according as
\(\chi(-1) = +1\) or \(-1\), and **real** when it takes only values \(0, \pm 1\) — the
real primitive characters are exactly the Kronecker symbols
\(\left(\frac{D}{\cdot}\right)\) of fundamental discriminants, which is where
[quadratic fields](quadratic-forms.md) re-enter.

The associated **Dirichlet \(L\)-function** is

\[
L(s, \chi) = \sum_{n \ge 1} \frac{\chi(n)}{n^s}
= \prod_p \left(1 - \frac{\chi(p)}{p^s}\right)^{-1},
\qquad \mathrm{Re}\,s > 1,
\]

continuing to an entire function for \(\chi\) non-principal. For primitive \(\chi\)
of conductor \(q\) there is a functional equation relating \(L(s,\chi)\) to
\(L(1-s, \bar\chi)\), with a **root number** \(\varepsilon(\chi)\) built from the
Gauss sum \(\tau(\chi) = \sum_{a} \chi(a) e^{2\pi i a/q}\) and satisfying
\(|\varepsilon(\chi)| = 1\).

Dirichlet's theorem on primes in progressions is exactly the statement
\(L(1, \chi) \ne 0\) for non-principal \(\chi\), which is why the theorem on
[the distribution page](distribution.md) belongs to this circle of ideas.

**Conjecture (generalised Riemann hypothesis, GRH).** Every nontrivial zero of every
Dirichlet \(L\)-function lies on \(\mathrm{Re}\,s = 1/2\).

GRH is a conjecture. It matters operationally: PARI's `quadclassunit` and `bnfinit`
assume it for their generator bounds, and Numerisect therefore marks class numbers
that could not be certified with `bnfcertify` as conditional on GRH — see
[the algebra laboratory](../ALGEBRA_LAB.md).

**In Numerisect.** *Dirichlet character table* (`POST /api/zeta/characters`) uses
`dirichlet_group_init`, `dirichlet_char_next`, `dirichlet_conductor_char`,
`dirichlet_parity_char` and `dirichlet_order_char`; modulus up to 100 000.
*Evaluate \(L(s,\chi)\)* (`POST /api/zeta/l-function`) computes with
`acb_dirichlet_l`, **cross-checked against an independent
`acb_dirichlet_l_hurwitz` evaluation**, and reports the root number and Gauss sum;
every value is certified. \(L(1, \chi_{-4}) = \pi/4 =
0.78539816339744830961566\ldots\).

*Critical-line zeros of \(L(s,\chi)\)* (`POST /api/zeta/l-zeros`) searches a grid for
sign changes of \(Z(t, \chi)\), and here the certification is precise: a bracket
counts **only** when the enclosures of \(Z\) at both endpoints are strictly of
opposite sign, which proves a critical-line zero of odd order inside. For
\(\chi_4(3, \cdot)\), the real primitive odd character of conductor 4, searching
\(0.5 \le t \le 30\) on a 400-point grid certifies ten sign changes against a smooth
\(\theta(T,\chi)/\pi\) count of 9.497; the first zero is at
\(t = 6.020948904697596654\ldots\).

!!! note "Complex characters have no real \(Z\)"
    Hardy's \(Z(t, \chi)\) is real-valued only for real characters. For a complex
    character such as \(\chi_5(2, \cdot)\) the page switches to
    `MODE: magnitude-minima` and reports minima of \(|L(\frac12 + it, \chi)|\), which
    are explicitly **exploratory indicators** and not certified zeros.

## Dedekind zeta functions

For a number field \(K\),

\[
\zeta_K(s) = \sum_{\mathfrak{a}} \frac{1}{N(\mathfrak{a})^s}
= \prod_{\mathfrak{p}} \left(1 - \frac{1}{N(\mathfrak{p})^s}\right)^{-1},
\]

summed over nonzero integral ideals. It generalises \(\zeta\) (which is
\(\zeta_{\mathbb{Q}}\)) and has a **simple pole at \(s = 1\)** whose residue is given
by the analytic class number formula

\[
\mathop{\mathrm{Res}}_{s=1} \zeta_K(s)
= \frac{2^{r_1} (2\pi)^{r_2}\, h\, R}{w \sqrt{|d_K|}},
\]

with \(r_1, r_2\) the real and complex places, \(h\) the class number, \(R\) the
regulator, \(w\) the number of roots of unity, \(d_K\) the discriminant. The
extended Riemann hypothesis is the corresponding conjecture for \(\zeta_K\).

For abelian \(K\), \(\zeta_K\) factors into Dirichlet \(L\)-functions. The cleanest
case is \(K = \mathbb{Q}(i)\), where \(\zeta_K(s) = \zeta(s)\, L(s, \chi_{-4})\), so
the zero set of \(\zeta_K\) is the **union** of the zeta ordinates and the
\(\chi_{-4}\) ordinates: \(6.0209\ldots, 10.2437\ldots, 12.9880\ldots,
14.1347\ldots\) — the fourth of which is the first zeta zero.

!!! warning "The Dedekind page is entirely exploratory"
    FLINT/Arb has no Dedekind zeta implementation, so this is the one zeta operation
    that leaves the C helper and runs in PARI/GP (`zeta_fields.gp`). PARI computes at
    a requested `realprecision` and returns floating-point numbers **with no rigorous
    error bound**. These are high-precision numerics, not Arb balls, and every value
    on that page is labelled exploratory — including the zero ordinates.

**In Numerisect.** *Dedekind zeta* (`POST /api/zeta/dedekind`) uses PARI `nfinit`,
`polcyclo`, `lfuncreate`, `lfuncheckfeq`, `lfun`, `lfunrootres`, `lfunzeros` and
`bnfinit`. For \(\mathbb{Q}(i)\) it reports degree 2, signature \((0,1)\),
discriminant \(-4\), \(\zeta_K(2) = 1.50670300992298503088\ldots\) and residue
\(\pi/4\), and with `class_data` enabled compares the residue against the class
number formula. `lfuncheckfeq` returns the base-2 logarithm of the
functional-equation error, so a large negative value means the \(L\)-function object
is internally consistent. Bounds: degree \(\le 8\), \(|d_K| \le 10^{12}\),
`lfunzeros` height \(\le 200\), `realprecision` 20–200 digits.

## Ball arithmetic: what "certified" buys you

Floating-point arithmetic gives a number with no attached claim. Round-off
accumulates, cancellation destroys digits silently, and a computed value near zero may
be zero, may be tiny, or may be pure error — nothing in the result distinguishes those
cases. For deciding whether a function **changes sign**, which is the entire business
of counting zeros, that is fatal.

**Ball arithmetic** (also called midpoint–radius interval arithmetic) carries a
radius through every operation. A value is represented as \([m \pm r]\), meaning a
rigorous **enclosure**: the true value is guaranteed to lie in that interval. Each
operation returns an enclosure of the true result of that operation applied to
anything in the input enclosures. Radii grow, sometimes fast — that is honest, and the
remedy is to raise the working precision and recompute — but they never lie. This is
what FLINT/Arb implements (Johansson, *Arb: efficient arbitrary-precision
midpoint-radius interval arithmetic*, IEEE Trans. Computers 66, 2017).

The practical consequences in Numerisect:

- **A sign is certified when the enclosure excludes zero.** \([0.3 \pm 0.01]\) is
  positive, certainly. \([0.003 \pm 0.01]\) has an unknown sign, and Numerisect
  reports **inconclusive** rather than guessing. Every Gram's-law verdict works this
  way.
- **A zero ordinate is an interval, not a number.** `acb_dirichlet_hardy_z_zeros`
  returns an interval provably containing exactly one zero, printed with its radius.
- **A count is certified when a unique integer is isolated.** If the enclosure of
  \(N(T)\) straddles two integers, the answer is `inconclusive` and the tool asks for
  more precision. It never rounds.
- **A verification is real when both sides are computed independently.** The
  functional-equation page evaluates each side separately and reports success only if
  the balls overlap.

### Why plot samples are exploratory

A chart is a finite set of points. Even when each point is computed in Arb, drawing
it discards the radius and shows a midpoint, and nothing is known about the function
between two adjacent pixels. So:

- **certified**: zero intervals, \(N(T)\) from the Turing method, \(S(T)\),
  \(\theta(T)\), Gram points and \(Z(g_n)\), Riemann–Siegel rows, Euler-product
  values and bounds, \(L(s,\chi)\) values, sign-change brackets;
- **exploratory**: the critical-line plot, the Argand trace, the complex heatmap, the
  \(S(T)\) trace, every histogram and pair-correlation bin, every truncated
  explicit-formula estimate, and all PARI output on the Dedekind page.

!!! note "A curve that looks like it misses zero"
    A critical-line plot that appears to stay away from the axis between two samples
    proves nothing about that gap. If you want a statement about an interval, use the
    zero-isolation or sign-change tools, which return enclosures. The plot endpoints
    exist to suggest where to look, and their reports say so.

## Where this appears in Numerisect

| Topic | Tool (route) | Engine routine | Status |
|---|---|---|---|
| \(\zeta(s)\), magnitude, argument | Evaluate (`/api/zeta/evaluate`) | `acb_zeta` | certified |
| Euler product versus \(\zeta\) | Euler product (`/api/zeta/euler-product`) | `acb_pow` over `n_primes_t`, `_acb_dirichlet_euler_product_real_ui` | certified |
| \(\xi\), \(\eta\), continuation | Xi/eta (`/api/zeta/xi-eta`) | `acb_dirichlet_xi`, `acb_dirichlet_eta` | certified |
| Functional equation, both sides independently | Functional equation (`/api/zeta/functional-equation`) | two FLINT/Arb evaluations, balls compared | certified |
| \(\gamma_n\) at \(s=1\) | Stieltjes (`/api/zeta/stieltjes`) | `acb_dirichlet_stieltjes` | certified |
| \(Z(t)\) on the critical line | Hardy \(Z\) (`/api/zeta/hardy`) | `acb_dirichlet_hardy_z` | certified |
| Gram points | Gram (`/api/zeta/gram`) | `acb_dirichlet_gram_point` | certified |
| Gram's law, exceptions, blocks | Gram blocks (`/api/zeta/gram-blocks`) | `acb_dirichlet_gram_point`, `acb_dirichlet_hardy_z` | certified, else inconclusive |
| Consecutive zero intervals | Zeros (`/api/zeta/zeros`) | `acb_dirichlet_hardy_z_zeros` | certified |
| \(N(T)\) by the Turing method | Count (`/api/zeta/count`) | `acb_dirichlet_zeta_nzeros` | certified, else inconclusive |
| \(S(T)\) and its bound | Backlund \(S\) (`/api/zeta/backlund-s`) | `acb_dirichlet_backlund_s`, `..._bound`, `acb_dirichlet_hardy_theta` | values certified, trace exploratory |
| Riemann–Siegel main sum and corrections | Riemann–Siegel (`/api/zeta/riemann-siegel`) | `acb_dirichlet_zeta_rs`, `acb_dirichlet_zeta_rs_bound`, `acb_dirichlet_zeta` | certified |
| \(\pi(x)\) from the explicit formula | Explicit prime count (`/api/zeta/explicit-prime-count`) | `acb_dirichlet_hardy_z_zeros`, `acb_hypgeom_ei`, `arb_hypgeom_li`, `n_moebius_mu`, `primecount` | exploratory |
| \(\psi(x)\) from zeros | Chebyshev \(\psi\) (`/api/zeta/chebyshev-psi`) | `acb_exp`, `acb_div`, `n_primes_t`, `arb_log_ui` | exploratory |
| Unfolded spacings against GUE | Zero spacing (`/api/zeta/zero-spacing`) | `acb_dirichlet_hardy_theta`, `arb_hypgeom_erf` | exploratory |
| Montgomery pair correlation | Pair correlation (`/api/zeta/pair-correlation`) | `acb_dirichlet_hardy_theta`, `arb_sin` | exploratory |
| Character tables, conductor, parity, order | Characters (`/api/zeta/characters`) | `dirichlet_group_init`, `dirichlet_char_next`, `dirichlet_conductor_char`, `dirichlet_parity_char`, `dirichlet_order_char` | certified |
| \(L(s,\chi)\), root number, Gauss sum | \(L\)-function (`/api/zeta/l-function`) | `acb_dirichlet_l`, `acb_dirichlet_l_hurwitz`, `acb_dirichlet_root_number`, `acb_dirichlet_gauss_sum` | certified |
| Critical-line zeros of \(L(s,\chi)\) | \(L\)-zeros (`/api/zeta/l-zeros`) | `acb_dirichlet_hardy_z`, `acb_dirichlet_hardy_theta`, `acb_dirichlet_l` | brackets certified; smooth count and magnitude minima exploratory |
| \(\zeta_K\), residue, class number formula | Dedekind (`/api/zeta/dedekind`) | PARI `nfinit`, `lfuncreate`, `lfuncheckfeq`, `lfun`, `lfunrootres`, `lfunzeros`, `bnfinit` | exploratory (PARI floating point) |
| Critical-line, Argand and heatmap plots | `/api/zeta/line`, `/api/zeta/heatmap` | parallel `acb_zeta` samples | exploratory (midpoints) |

## References

- H. M. Edwards, *Riemann's Zeta Function*, Academic Press (1974; Dover reprint) —
  the explicit formula, the Riemann–Siegel formula (Ch. 7), Gram points and the
  computational history. The best first book on this page's subject.
- E. C. Titchmarsh, *The Theory of the Riemann Zeta-Function*, 2nd ed. revised by
  D. R. Heath-Brown, Oxford (1986) — the standard analytic reference: functional
  equation, \(N(T)\) and \(S(T)\), zero-density and mean-value theorems.
- H. Iwaniec and E. Kowalski, *Analytic Number Theory*, AMS Colloquium Publications 53
  — Chapters 5 and 10 on general \(L\)-functions, characters, and GRH.
- H. L. Montgomery, "The pair correlation of zeros of the zeta function",
  *Proc. Sympos. Pure Math.* **24** (1973).
- A. M. Odlyzko, "On the distribution of spacings between zeros of the zeta
  function", *Math. Comp.* **48** (1987), and the subsequent large-height
  computations.
- C. L. Siegel, "Über Riemanns Nachlaß zur analytischen Zahlentheorie" (1932) — the
  Riemann–Siegel formula as recovered from Riemann's notes.
- A. M. Turing, "Some calculations of the Riemann zeta-function",
  *Proc. London Math. Soc.* (1953) — the method behind rigorous zero counts.
- D. J. Platt and T. S. Trudgian, "The Riemann hypothesis is true up to
  \(3 \cdot 10^{12}\)", *Bull. London Math. Soc.* **53** (2021).
- L. Schoenfeld, "Sharper bounds for the Chebyshev functions \(\theta(x)\) and
  \(\psi(x)\), II", *Math. Comp.* **30** (1976) — the explicit RH-equivalent bound.
- F. Johansson, "Arb: efficient arbitrary-precision midpoint-radius interval
  arithmetic", *IEEE Trans. Computers* **66** (2017) — the ball arithmetic every
  certified value on this page rests on.
- [FLINT/Arb `acb_dirichlet` documentation](https://flintlib.org/doc/acb_dirichlet.html).
- Numerisect: [Riemann zeta tools](../RIEMANN_ZETA.md),
  [zeta lab](../ZETA_LAB.md), [verification](../VERIFICATION.md).
