# Distributed CADO-NFS

The number field sieve parallelises across machines, and this is the one place where
more hardware lets you factor numbers a single machine cannot. CADO-NFS already
implements the whole mechanism: a work-unit server, clients that fetch work and post
relations, and the parameters that configure both. Numerisect validates those
parameters and hands them to CADO. **It adds no networking of its own.**

## Read the trust model first

These are verified facts about CADO-NFS 3.0.0, taken from its own
`scripts/cadofactor/api_server.py`, not reassurances:

| Question | Answer |
|---|---|
| How do clients prove who they are? | **They do not.** There is no password, token, or client credential anywhere in CADO's client or server. |
| How does the server decide who may join? | An IP whitelist only (`server.whitelist`, enforced in `api_limit_remote_addr`). |
| How does a client know it is talking to the right server? | Optionally, by pinning the server's TLS certificate with `--certsha1`. This authenticates the *server to the client*, not the reverse. |
| What happens with no whitelist? | CADO fails closed and blocks every address. |

The consequence: **anyone who can reach the server port from a whitelisted address can
request work units and post relations.** IP addresses are forgeable on an untrusted
network, and a compromised whitelisted host can feed the computation bad data.

The damage is bounded rather than silent. CADO validates relations during filtering, and
Numerisect independently checks that the returned factors multiply back to the input
before marking a job complete. A poisoned run therefore fails; it does not produce a
wrong answer that gets accepted.

**Run this only across machines you control, on a network you trust.** To involve a
machine elsewhere, put it on a VPN or use an SSH tunnel and keep the server bound to a
private interface.

`GET /api/distributed/trust-model` returns the table above at runtime.

## What Numerisect refuses

Validation rejects configurations CADO itself would accept:

- **No whitelist.** Required, because it is the only access control.
- **`0.0.0.0/0`.** Whitelisting the entire internet.
- **Broad public ranges.** A global range covering more than 256 addresses.
- **Binding a public address.** The work-unit server may not listen on a globally
  routable interface.
- **Remote workers without `slaves.scriptpath`.** CADO needs to know where
  `cado-nfs-client.py` lives on those machines.
- Ports below 1024, more than 1024 clients, malformed addresses or hostnames.

Anything outside the supported parameter set is rejected rather than passed through, so
a request cannot reach arbitrary CADO internals.

## Two-step approval

```text
POST /api/distributed/preview   validate and report exposure; starts nothing
POST /api/distributed/factor    queue the run; requires confirm_network
GET  /api/distributed/trust-model
```

`preview` performs no networking and starts nothing. It returns the exact CADO
parameters, an exposure summary, the warnings that apply, and the command a worker
would run. Read it before approving.

`factor` additionally requires `confirm_network: true`. A run that leaves this machine
also requires the process to have been started with `NUMERISECT_ALLOW_NETWORK=1`, the
same gate as every other outbound feature. A loopback-only run with no remote workers
needs only the per-request confirmation, because nothing leaves the machine.

## Parameters

| Field | CADO parameter | Meaning |
|---|---|---|
| `address` | `server.address` | Interface the work-unit server binds |
| `port` | `server.port` | Work-unit server port |
| `whitelist` | `server.whitelist` | Addresses or CIDR blocks permitted to join |
| `ssl` | `server.ssl` | Serve over TLS so clients can pin the certificate |
| `clients` | `slaves.nrclients` | Client processes CADO starts |
| `hostnames` | `slaves.hostnames` | Worker machines; empty means this machine only |
| `script_path` | `slaves.scriptpath` | Where `cado-nfs-client.py` lives on the workers |
| `client_threads` | `--client-threads` | Threads per client process |

## Starting workers

CADO logs the server URL and, with TLS on, the certificate hash:

```text
You can start additional cado-nfs-client.py scripts with parameters:
  --server=https://127.0.0.1:8791 --certsha1=6313d5f9...
```

Run that on each worker. Numerisect does not reach out to other machines; it shows you
the command. If you list `hostnames`, CADO starts the clients itself over SSH, which
requires key-based access and `slaves.scriptpath`.

Note that CADO adds the server host's own LAN address to the whitelist automatically so
that local clients can connect. A run you configured as loopback-only will show that
extra entry in its log.

## Two behaviours worth knowing

**`slaves.hostnames` is mandatory here.** CADO defaults it to `localhost` only when it
uses its own default parameter file. Numerisect always passes `-p` to select a parameter
set, so without an explicit value CADO starts a bare work-unit server, queues work units,
and polls for them forever with no client ever running. Numerisect always sets it. This
also affects ordinary non-distributed CADO jobs, and both paths now set it.

**Order matters on the command line.** CADO parses `key=value` options only when they are
contiguous with the integer being factored. Numerisect places every flag first and the
integer immediately before its assignments; interleaving them makes `cado-nfs.py` reject
the whole invocation.

## Testing without a second machine

A loopback run with several clients exercises the entire path: the work-unit server,
client registration, sieving, relation upload, filtering, linear algebra and the square
root. `tests/test_distributed.py` contains such a run, marked `slow` and deselected by
default. Run it with:

```bash
python -m pytest tests/test_distributed.py -m slow
```

It factors a 25-digit product of four primes through the job path and asserts the parts
multiply back to the input.
