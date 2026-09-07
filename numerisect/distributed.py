# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated parameters for distributed CADO-NFS sieving.

Numerisect writes no networking of its own here. CADO-NFS already implements a
work-unit server and clients; this module validates the parameters the user
supplies and hands them to CADO as an argument array. Every value below is a
CADO parameter name, documented in CADO's own parameter files.

READ THE TRUST MODEL BEFORE ENABLING THIS. It was verified against CADO-NFS
3.0.0's own source (``scripts/cadofactor/api_server.py``):

* **Clients do not authenticate to the server.** There is no password, token, or
  client credential anywhere in CADO's client or server. ``cado-nfs-client.py``
  offers ``--certsha1``, which authenticates the *server to the client*, not the
  other way round.
* **The server's only access control is an IP whitelist**
  (``api_limit_remote_addr``). Any host whose address matches the whitelist may
  request work units and POST results to ``/upload``.
* CADO fails closed: with no whitelist configured, every address is blocked.

The consequence is that anyone who can reach the server port from a whitelisted
address can submit relations. IP addresses are forgeable on an untrusted network,
and a compromised whitelisted host can feed the computation bad data. The damage
is bounded rather than silent: CADO validates relations during filtering, and
Numerisect independently verifies that the returned factors multiply back to the
input before a job is marked complete, so a poisoned run fails rather than
producing a wrong answer that is accepted.

Run this only across machines you control, on a network you trust.
"""

from __future__ import annotations

import ipaddress
import re
import shutil
from pathlib import Path
from typing import Any

# CADO parameter names this module is willing to set. Anything outside this set
# is rejected rather than passed through, so a request cannot reach arbitrary
# CADO internals.
SERVER_PARAMETERS = ("server.address", "server.port", "server.whitelist", "server.ssl")
SLAVE_PARAMETERS = ("slaves.nrclients", "slaves.hostnames", "slaves.scriptpath")

HOSTNAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")
MIN_PORT = 1024
MAX_PORT = 65535
MAX_CLIENTS = 1024
MAX_WHITELIST_ENTRIES = 64
MAX_HOSTNAMES = 128

LOOPBACK_ONLY = ("127.0.0.1", "localhost", "::1")


class DistributedConfigurationError(ValueError):
    """Raised when a distributed configuration is unsafe or malformed."""


def _validate_whitelist(entries: list[str]) -> list[str]:
    """Validate whitelist entries as addresses or CIDR networks.

    Args:
        entries: Addresses or CIDR blocks, as CADO's ``server.whitelist`` accepts.

    Returns:
        The normalised entries.

    Raises:
        DistributedConfigurationError: If empty, oversized, malformed, or so broad
            that it would accept the entire internet.
    """

    if not entries:
        raise DistributedConfigurationError(
            "A whitelist is required. Distributed CADO authenticates clients only by "
            "IP address, so an absent whitelist means the run is either fully blocked "
            "or fully open depending on configuration."
        )
    if len(entries) > MAX_WHITELIST_ENTRIES:
        raise DistributedConfigurationError(
            f"List at most {MAX_WHITELIST_ENTRIES} whitelist entries"
        )
    normalised: list[str] = []
    for raw in entries:
        entry = str(raw).strip()
        if not entry:
            continue
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError as exc:
            raise DistributedConfigurationError(
                f"'{entry}' is not an IP address or CIDR network"
            ) from exc
        # Refuse a whitelist that admits the whole internet. CADO would accept it.
        if network.prefixlen == 0:
            raise DistributedConfigurationError(
                f"'{entry}' whitelists every address on the internet; name the worker "
                "machines or their subnet instead"
            )
        if network.is_global and network.num_addresses > 256:
            raise DistributedConfigurationError(
                f"'{entry}' is a public range covering {network.num_addresses} addresses. "
                "Distributed CADO has no client authentication; list individual hosts or "
                "a private subnet."
            )
        normalised.append(str(network))
    if not normalised:
        raise DistributedConfigurationError("The whitelist contained no usable entries")
    return normalised


def _validate_hostnames(entries: list[str]) -> list[str]:
    """Validate worker hostnames CADO will start clients on over SSH."""

    if len(entries) > MAX_HOSTNAMES:
        raise DistributedConfigurationError(f"List at most {MAX_HOSTNAMES} hostnames")
    names: list[str] = []
    for raw in entries:
        name = str(raw).strip()
        if not name:
            continue
        if not HOSTNAME.match(name):
            try:
                ipaddress.ip_address(name)
            except ValueError as exc:
                raise DistributedConfigurationError(
                    f"'{name}' is not a valid hostname or IP address"
                ) from exc
        names.append(name)
    return names


def validate_configuration(
    *,
    address: str,
    port: int,
    whitelist: list[str],
    ssl: bool,
    clients: int,
    hostnames: list[str] | None = None,
    script_path: str | None = None,
    client_threads: int | None = None,
) -> dict[str, Any]:
    """Validate a distributed configuration and describe its exposure.

    Args:
        address: Interface CADO's work-unit server binds. ``127.0.0.1`` keeps the
            server local, which is the only configuration that exposes nothing.
        port: TCP port for the work-unit server.
        whitelist: Addresses or CIDR networks permitted to fetch work and post
            results. Required, because it is CADO's only client access control.
        ssl: Whether CADO serves over TLS. Clients pin the certificate with
            ``--certsha1``; this authenticates the server, not the client.
        clients: Number of client processes CADO starts.
        hostnames: Worker hosts CADO starts clients on. Empty means local only.
        script_path: Directory holding ``cado-nfs-client.py`` on the workers.
        client_threads: Threads per client process.

    Returns:
        ``{"parameters": [...], "exposure": {...}, "warnings": [...]}`` where
        ``parameters`` are ``key=value`` strings for CADO's command line.

    Raises:
        DistributedConfigurationError: If the configuration is malformed or unsafe.
    """

    if not shutil.which("cado-nfs.py"):
        raise DistributedConfigurationError("CADO-NFS is not installed")
    if not MIN_PORT <= int(port) <= MAX_PORT:
        raise DistributedConfigurationError(
            f"The server port must be between {MIN_PORT} and {MAX_PORT}"
        )
    if not 1 <= int(clients) <= MAX_CLIENTS:
        raise DistributedConfigurationError(f"Run between 1 and {MAX_CLIENTS} clients")

    address = str(address).strip()
    if not address:
        raise DistributedConfigurationError("A server address is required")
    if address not in LOOPBACK_ONLY:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            if not HOSTNAME.match(address):
                raise DistributedConfigurationError(
                    f"'{address}' is not a valid address or hostname"
                ) from None
            parsed = None
        if parsed is not None and parsed.is_global:
            raise DistributedConfigurationError(
                f"Refusing to bind the work-unit server to the public address {address}. "
                "CADO has no client authentication; bind a private interface and reach it "
                "over a VPN or SSH tunnel."
            )

    entries = _validate_whitelist(whitelist)
    names = _validate_hostnames(hostnames or [])
    if names and not script_path:
        raise DistributedConfigurationError(
            "Remote workers need slaves.scriptpath, the directory holding "
            "cado-nfs-client.py on those machines"
        )
    if script_path is not None:
        candidate = str(script_path).strip()
        if candidate and not candidate.startswith("/"):
            raise DistributedConfigurationError(
                "slaves.scriptpath must be an absolute path on the worker machines"
            )
        script_path = candidate or None
    if client_threads is not None and not 1 <= int(client_threads) <= 256:
        raise DistributedConfigurationError("Client threads must be between 1 and 256")

    local_only = address in LOOPBACK_ONLY and not names
    warnings: list[str] = []
    if not ssl:
        warnings.append(
            "TLS is disabled, so work units and relations travel in clear text and "
            "clients cannot verify which server they are talking to."
        )
    if not local_only:
        warnings.append(
            "Clients do not authenticate to the CADO server. Any host matching the "
            "whitelist can request work and post relations."
        )
    if any(ipaddress.ip_network(entry).num_addresses > 1 for entry in entries):
        warnings.append(
            "The whitelist contains a subnet rather than individual hosts, so every "
            "machine on it may join the computation."
        )

    parameters = [
        f"server.address={address}",
        f"server.port={int(port)}",
        f"server.whitelist={','.join(entries)}",
        f"server.ssl={'yes' if ssl else 'no'}",
        f"slaves.nrclients={int(clients)}",
    ]
    # slaves.hostnames must always be set. CADO only defaults it to "localhost" when
    # it is using its own default parameter file; Numerisect always passes -p, so
    # without this CADO starts a bare server and polls for work units forever.
    parameters.append(f"slaves.hostnames={','.join(names) if names else 'localhost'}")
    if script_path:
        parameters.append(f"slaves.scriptpath={script_path}")

    return {
        "parameters": parameters,
        "client_threads": int(client_threads) if client_threads else None,
        "exposure": {
            "local_only": local_only,
            "bind_address": address,
            "port": int(port),
            "tls": bool(ssl),
            "whitelist": entries,
            "worker_hosts": names,
            "client_authentication": "none (CADO authenticates clients by IP only)",
        },
        "warnings": warnings,
    }


def describe_trust_model() -> dict[str, Any]:
    """Return the distributed trust model for the interface and diagnostics.

    Stated as verified facts about CADO-NFS, not as reassurance.
    """

    return {
        "client_authentication": "none",
        "server_authentication": "optional TLS with certificate pinning (--certsha1)",
        "access_control": "IP whitelist only (server.whitelist)",
        "default_when_unset": "CADO blocks every address when no whitelist is given",
        "risk": (
            "Any host matching the whitelist can request work units and post relations. "
            "IP addresses are forgeable on an untrusted network."
        ),
        "mitigation": (
            "CADO validates relations during filtering, and Numerisect verifies that the "
            "returned factors multiply back to the input before completing a job, so a "
            "poisoned run fails rather than yielding an accepted wrong answer."
        ),
        "recommendation": (
            "Run only across machines you control on a trusted network. To involve a "
            "remote machine, prefer an SSH tunnel or VPN and keep the server bound to a "
            "private interface."
        ),
    }


def client_command(
    server_url: str, certsha1: str | None = None, threads: int | None = None
) -> list[str]:
    """Build the command a worker runs to join a computation.

    This is shown to the user so they can start workers themselves; Numerisect
    does not reach out to other machines.

    Args:
        server_url: The server URL CADO logged when it started.
        certsha1: The server certificate hash CADO logged, when TLS is enabled.
        threads: Threads for this client.

    Returns:
        The argument array for ``cado-nfs-client.py``.
    """

    command = ["cado-nfs-client.py", f"--server={server_url}"]
    if certsha1:
        command.append(f"--certsha1={certsha1}")
    if threads:
        command.append(f"--override=('threads', '{int(threads)}')")
    return command


def find_client_script() -> Path | None:
    """Locate ``cado-nfs-client.py`` so the worker instructions can name it."""

    found = shutil.which("cado-nfs-client.py")
    return Path(found) if found else None
