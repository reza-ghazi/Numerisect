# How this was built

Numerisect was designed and directed by its author, and much of the code was written
with AI assistance under that direction and review. This section says so plainly, because
the commit history records it and a reader is entitled to know how a piece of software
came to exist.

**What that meant in practice.** The architecture is the part that matters here, and it
is a human decision: Numerisect is a user interface over existing number-theory
libraries, not a reimplementation of them. A computation uses a library routine first, an
optimized C program with GMP or FLINT only where no library provides one, and never
Python or JavaScript. That constraint shaped every feature, was written into
[the contributing guide](contributing.md), and is enforced by
`tests/test_native_computation_policy.py` rather than left to good intentions.

The same applies to the project's other commitments: that a result is labelled proven,
probable or inconclusive and never blurred; that an exhausted search is never reported as
a negative answer; that the application stays offline unless explicitly told otherwise;
and that where the engines cannot answer, the gap is reported rather than approximated.

**What the assistance contributed** was throughput and breadth: writing and testing the
compiled helpers, wiring routes and interface, composing PARI/GP programs, and drafting
documentation, all reviewed against the policy above.

**What review means here.** Every mathematical claim in this repository is checked
against a native engine rather than asserted. The test suite cites published constants
with their sources, the documentation names the library routine behind each operation,
and `POST /api/verify/self-test` asks each installed engine questions whose answers are
published values, so a miscompiled build is caught before its output is trusted. Where
independent implementations of the same quantity exist, Numerisect runs several and
reports disagreement rather than choosing between them.

Correctness here does not rest on who or what typed a line. It rests on the engines doing
the mathematics, on results being labelled by their actual strength, and on the checks
being reproducible by anyone who clones the repository.
