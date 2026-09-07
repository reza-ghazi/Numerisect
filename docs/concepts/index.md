# Concepts

These pages explain how Numerisect thinks. They are worth reading before the feature
guides, because they set the vocabulary the rest of the documentation uses.

<div class="grid cards" markdown>

-   **Proven, probable, inconclusive**

    ---

    The four labels attached to every result, why the distinction is enforced, and what
    each costs. **Start here.**

    [:octicons-arrow-right-24: Read](proven-and-probable.md)

-   **Inconclusive results**

    ---

    Why an exhausted search is never reported as a negative answer, and how to act on one.

    [:octicons-arrow-right-24: Read](inconclusive.md)

-   **The engines**

    ---

    What each native engine is, what it is good at, and when Numerisect reaches for it.

    [:octicons-arrow-right-24: Read](engines.md)

-   **Architecture**

    ---

    How a request becomes an engine invocation, and why Python and JavaScript compute
    nothing.

    [:octicons-arrow-right-24: Read](architecture.md)

-   **Security and privacy**

    ---

    Loopback binding, the session token, what never leaves the machine, and the two
    outbound paths that exist.

    [:octicons-arrow-right-24: Read](security.md)

</div>

## The one-paragraph version

Numerisect is a user interface over existing number-theory libraries. A computation uses
a library routine first; an optimized C program with GMP or FLINT only when no library
provides one; and never Python or JavaScript. Results are labelled by strength, and a
search that hits a bound is inconclusive rather than negative. Everything runs locally
unless you explicitly enable one of two outbound features.
