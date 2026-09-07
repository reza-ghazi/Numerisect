"""Numerisect command-line interface; computation remains in native engines."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from .asgi_client import METHODS, LocalApiClient
from .config import (
    DATABASE_PATH,
    DEFAULT_PRETEST_LEVEL,
    ensure_state_dirs,
    prepend_managed_tools_to_path,
)
from .database import Database
from .evaluator import evaluate_integer
from .jobs import JobManager
from .number_theory import character_symbols, chinese_remainder, perfect_power
from .primes import nth_prime, nth_prime_near, primality_result


def _emit(value: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in {"certificate_data"}:
                print(f"{key}: {item}")
    else:
        print(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="numerisect",
        description="Native-engine integer factorization and number-theory workbench",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON where supported")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="start the loopback web application")

    factor = commands.add_parser("factor", help="queue a factorization and wait for it")
    factor.add_argument("expression")
    factor.add_argument("--engine", default="auto", choices=[
        "auto", "yafu", "hybrid", "cado", "msieve", "cross_verify",
        "pari_trial", "yafu_rho", "yafu_pm1", "yafu_pp1", "yafu_ecm",
        "yafu_siqs", "yafu_nfs",
    ])
    factor.add_argument("--threads", type=int, default=os.cpu_count() or 1)
    factor.add_argument("--pretest", type=int, default=DEFAULT_PRETEST_LEVEL)
    factor.add_argument("--trial-bound", type=int, default=100_000)

    prime = commands.add_parser("prime", help="test one integer")
    prime.add_argument("number", type=int)
    prime.add_argument("--fast", action="store_true")
    prime.add_argument("--certificate", action="store_true")

    nth = commands.add_parser("nth-prime", help="calculate the globally indexed nth prime")
    nth.add_argument("index", type=int)

    near = commands.add_parser("near-prime", help="find the nth prime before or after n")
    near.add_argument("number", type=int)
    near.add_argument("index", type=int)
    near.add_argument("--direction", choices=["before", "after"], default="after")

    symbols = commands.add_parser("symbols", help="evaluate Legendre/Jacobi/Kronecker symbols")
    symbols.add_argument("a")
    symbols.add_argument("n")

    crt = commands.add_parser("crt", help="solve residue:modulus pairs")
    crt.add_argument("pairs", nargs="+", metavar="A:M")

    power = commands.add_parser("perfect-power", help="find maximal n=a^k decomposition")
    power.add_argument("number")

    api = commands.add_parser(
        "api", help="call any HTTP route in-process (complete CLI/API parity)"
    )
    api.add_argument("method", choices=[m.lower() for m in METHODS] + list(METHODS))
    api.add_argument("path", help="route path, for example /api/primes/check")
    api.add_argument("--data", help="JSON request body")
    api.add_argument("--data-file", help="file containing the JSON request body")
    api.add_argument(
        "--param", action="append", default=[], metavar="KEY=VALUE",
        help="query parameter; repeatable",
    )

    routes = commands.add_parser("routes", help="list every available API route")
    routes.add_argument("--filter", default="", help="only show paths containing this text")
    return parser


def _api(args: argparse.Namespace) -> dict[str, Any]:
    """Run one in-process API call and return its decoded result."""

    if args.data and args.data_file:
        raise ValueError("Use either --data or --data-file, not both")
    body: Any = None
    if args.data_file:
        body = json.loads(Path(args.data_file).read_text(encoding="utf-8"))
    elif args.data:
        body = json.loads(args.data)
    params: dict[str, str] = {}
    for item in args.param:
        if "=" not in item:
            raise ValueError(f"Query parameter '{item}' must be KEY=VALUE")
        key, value = item.split("=", 1)
        params[key] = value
    ensure_state_dirs()
    prepend_managed_tools_to_path()
    client = LocalApiClient()
    response = client.request(args.method, args.path, data=body, params=params or None)
    try:
        payload = response.json()
    except ValueError:
        payload = {"text": response.text}
    if not response.ok:
        raise RuntimeError(
            f"HTTP {response.status}: {payload.get('detail', payload) if isinstance(payload, dict) else payload}"
        )
    return payload if isinstance(payload, dict) else {"result": payload}


def _routes(args: argparse.Namespace) -> dict[str, Any]:
    """List the application's routes."""

    listing = LocalApiClient().routes()
    if args.filter:
        listing = [row for row in listing if args.filter in row["path"]]
    return {"count": len(listing), "routes": listing}


def _factor(args: argparse.Namespace) -> dict[str, Any]:
    if not 1 <= args.threads <= 256:
        raise ValueError("Threads must be between 1 and 256")
    ensure_state_dirs()
    prepend_managed_tools_to_path()
    database = Database(DATABASE_PATH)
    manager = JobManager(database)
    job = manager.create(
        expression=args.expression,
        number=evaluate_integer(args.expression),
        requested_backend=args.engine,
        threads=args.threads,
        pretest_level=args.pretest,
        trial_bound=args.trial_bound,
        cado_parameter_size=None,
    )
    try:
        while job["status"] in {"queued", "running", "cancelling"}:
            time.sleep(0.2)
            job = database.get_job(job["id"]) or job
    except KeyboardInterrupt:
        manager.cancel(job["id"])
        raise
    finally:
        manager.shutdown()
    return {
        "id": job["id"], "status": job["status"], "number": job["number"],
        "strategy": job["selected_backend"], "factors": job["factors"],
        "error": job.get("error"), "report": job.get("result_path"),
    }


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    try:
        if args.command in {None, "serve"}:
            from .main import run

            run()
            return
        if args.command == "api":
            result = _api(args)
        elif args.command == "routes":
            result = _routes(args)
        elif args.command == "factor":
            result = _factor(args)
        elif args.command == "prime":
            if args.fast and args.certificate:
                raise ValueError("Certificates require rigorous mode")
            result = primality_result(
                args.number,
                mode="fast" if args.fast else "proven",
                certificate=args.certificate,
            )
        elif args.command == "nth-prime":
            result = {"index": args.index, "prime": str(nth_prime(args.index)), "engine": "PARI/GP"}
        elif args.command == "near-prime":
            result = {
                "start": str(args.number), "index": args.index,
                "direction": args.direction,
                "prime": str(nth_prime_near(args.number, args.index, args.direction)),
                "engine": "PARI/GP",
            }
        elif args.command == "symbols":
            result = character_symbols(args.a, args.n)
        elif args.command == "crt":
            split = [pair.split(":", 1) for pair in args.pairs]
            if any(len(pair) != 2 for pair in split):
                raise ValueError("Every CRT equation must use residue:modulus syntax")
            result = chinese_remainder([pair[0] for pair in split], [pair[1] for pair in split])
        elif args.command == "perfect-power":
            result = perfect_power(args.number)
        else:
            parser.error("Unknown command")
            return
        _emit(result, args.json)
        if isinstance(result, dict) and result.get("status") == "failed":
            raise SystemExit(2)
    except (RuntimeError, ValueError) as exc:
        print(f"numerisect: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
