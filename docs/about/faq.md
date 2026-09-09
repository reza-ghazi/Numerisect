# Frequently asked questions

## About results

### Numerisect says "probable prime". Is my number prime?

Probably, but that has not been proven. It passed Baillie–PSW, which no composite is
known to pass, but no proof exists that none can. Run the rigorous test for a proof, and
export a certificate if you want independent verification.

[:octicons-arrow-right-24: Proven and probable](../concepts/proven-and-probable.md)

### The factorization found no factor. Is my number prime?

**No, that does not follow.** A factoring method that finds nothing has found nothing. It
has not established primality. Use a primality test, which answers a different question.

### Why does one class say "inconclusive" instead of "no"?

Because the search hit its bound before settling the question. For some classes, such as
Mills, Wilson or Fortunate primes, "inconclusive" is the only honest answer any feasible
computation can give. Treating it as "no" would be a false claim.

### Eight methods agree on π(x). How confident should I be?

Quite confident, with one important qualification. Six outputs are distinct algorithms
inside primecount; primesieve and PARI/GP supply two separate codebases. Agreement across
all three implementations is meaningful evidence, while the six primecount modes are not
six independent votes.

If they ever disagree, Numerisect reports every value and refuses to pick a winner. A
majority of implementations sharing a bug is exactly what a vote would hide.

### Why are plot values not certified when evaluations are?

Evaluation returns a rigorous enclosure: an interval guaranteed to contain the true
value. Drawing a curve needs one number per pixel, so Numerisect uses each enclosure's
midpoint. The shape is faithful, the individual values are not certified, and every plot
says so.

## About performance

### Why is my factorization taking so long?

Factoring difficulty grows very fast with size, and thread count does not rescue it.
A 60-digit semiprime is routine; a 200-digit one is a research project. Ask the strategy
adviser before starting: if your number has a special form, SNFS may make it far cheaper.

### Should I change the CADO threshold?

Only with a measurement. `POST /api/factor-lab/tune` runs YAFU's own tuning to find where
SIQS stops beating NFS on your hardware and suggests a value. Numerisect never changes
the setting itself.

### Why is only one job running?

`NUMERISECT_MAX_PARALLEL_JOBS` defaults to 1, because these engines already use every
core you give them. Running two halves the threads available to each.

## About privacy and safety

### Why do `/api/jobs` or `/api/setup` sometimes return 403 in the terminal?

Numerisect creates a new local-session token whenever its server starts. A browser tab
left open across a restart can keep polling with the old token, and the security layer
correctly rejects those requests. Close obsolete tabs or reload the active page. If the
log subsequently shows `200 OK`, the current session is healthy and no mathematical
engine failed. See the [localhost security model](../SECURITY_MODEL.md) if 403 responses
continue from a freshly loaded, sole tab.

### Does Numerisect send anything anywhere?

Not during calculations. There is no telemetry, no analytics and no update check. Three
outbound paths exist, all off by default: building engines from pinned sources after your
confirmation, optional catalogue lookups behind a two-key opt-in, and distributed
CADO-NFS.

This documentation site carries no analytics either.

### Can I expose it on my network?

You should not. The loopback binding is the security boundary, and the API can start
processes and read local files. For a remote machine, use an SSH tunnel.

### Is the prime generator safe for cryptographic keys?

**No.** It is labelled experimental and is not audited cryptographic software. Use a
vetted library for keys.

### Is distributed CADO-NFS safe on my LAN?

Read the trust model first. Verified from CADO's own source: clients do not authenticate
to its server at all, and an IP whitelist is the only access control. Anyone reaching the
port from a whitelisted address can submit relations. Run it only across machines you
control on a network you trust.

[:octicons-arrow-right-24: Distributed CADO-NFS](../DISTRIBUTED.md)

## About the project

### Why does Python compute nothing?

Because the mathematics belongs in libraries written by specialists and optimized over
decades. Reimplementing it would be slower and less trustworthy. Python validates input,
launches engines, parses results and serves HTTP. The rule is enforced by the test suite,
not just documented.

### Why write any C at all?

Only where no installed library provides a routine. Three programs qualify: the FLINT/Arb
zeta driver, SQUFOF (absent from every installed engine), and prime enumeration above
\(2^{64}\), which primesieve refuses outright and PARI handles single-threaded and slowly.

### An engine is missing. What breaks?

Only the features needing it, and they say so rather than substituting a weaker method.
PARI/GP and FLINT cover most of the application.

### How do I know my engines are built correctly?

Run the self-test. It asks each engine questions whose answers are published constants,
with citations, and reports any mismatch. A wrong answer there means you should not trust
that engine until you know why.

### Can I use it from a script or notebook?

Yes. Every route is reachable from the command line with `numerisect api`, and
`numerisect/client.py` is a standard-library client that works in Jupyter and SageMath.
Examples for five languages are in `examples/`.

### Is it finished?

It is an experimental pre-release. The roadmap ledger records exactly what is
implemented, what is partial with the specific gap named, and what was declined with the
reasoning.

[:octicons-arrow-right-24: Roadmap status](../ROADMAP_STATUS.md)
