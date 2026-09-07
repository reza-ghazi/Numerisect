# Inconclusive results

An inconclusive result means the question was not settled. It is not a negative answer,
and Numerisect never presents it as one. This page explains where inconclusive results
come from and what to do with them.

## The distinction

Three outcomes are possible for most questions Numerisect asks:

| Outcome | Meaning |
|---|---|
| **Yes** | The property holds, with the strength stated. |
| **No** | The property definitely does not hold. |
| **Inconclusive** | Not determined within the budget or bound applied. |

Tools that collapse the third into the second are the reason people mistrust
computational number theory. A search that ran out of time has found nothing; it has not
shown there is nothing to find.

## Where inconclusive results arise

**Time budgets.** Every engine call carries a timeout. The 56-class prime classifier
gives each class its own budget, and a class that exceeds it is listed separately from
classes that definitely do not match.

**Documented search bounds.** Many properties are only decidable by search. Sierpiński
and Riesel candidate testing, covering-set verification, sociable-number cycles,
record-number families and special-form recognition all carry documented caps. Reaching a
cap is reported with the cap.

**Open questions.** Some classes in the catalogue are not decidable at all with current
knowledge. Mills, Wilson, Wolstenholme, Higgs, cluster and Fortunate primes are the usual
examples. For these, "inconclusive" is often the only honest answer that exists.

**Method limits.** SQUFOF exhausting its iteration limit says nothing about primality.
An ECM campaign completing its curves without a split says nothing about whether a factor
of that size exists. Both report inconclusive with a suggestion of what to change.

**Missing external data.** A catalogue with no entry for your number means the catalogue
does not know.

## How to act on one

Every inconclusive result states the bound that was reached. That tells you the lever:

- A **timeout** means raise the time budget, or accept that this class is expensive.
- A **search cap** means raise the cap, if the runtime is acceptable to you.
- An **iteration limit** in SQUFOF means raise it or move to SIQS.
- An **ECM campaign** that found nothing means raise \(B_1\) or the curve count, or move
  to SIQS or NFS.
- An **open question** means no amount of computation will settle it here.

!!! warning "The mistake to avoid"

    Do not read "no factor found" as "the number is prime". Use a primality test for
    that question. They are different questions and Numerisect answers them separately.

## How it is enforced

Every engine program ends its output with a completion marker, and every count it reports
is checked against the number of records parsed. A run killed by a timeout produces no
marker, and Numerisect raises an error rather than returning an empty successful result.
A partial run therefore cannot be mistaken for a completed search that found nothing.

Searches that stop at a cap set an explicit truncation flag alongside the results, so a
truncated list is never mistaken for a complete one.

[:octicons-arrow-right-24: Proven and probable](proven-and-probable.md)
