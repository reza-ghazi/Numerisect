#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve and deliberately update one native-engine source pin."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "numerisect" / "engine_manifest.toml"
sys.path.insert(0, str(ROOT))

from numerisect.installer import load_engine_manifest  # noqa: E402


def resolve_ref(repository: str, reference: str) -> str:
    """Resolve an upstream ref to its commit without checking out source."""

    result = subprocess.run(
        ["git", "ls-remote", repository, reference, f"{reference}^{{}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git ls-remote failed")
    revisions = [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
    if not revisions:
        raise RuntimeError(f"Upstream ref was not found: {reference}")
    return revisions[-1]


def update_manifest(name: str, reference: str, revision: str) -> None:
    """Update exactly one manifest block after displaying the resolved pin."""

    text = MANIFEST.read_text(encoding="utf-8")
    pattern = re.compile(
        rf'(\[\[engine\]\]\nname = "{re.escape(name)}".*?upstream_ref = ")[^"]+("\nrevision = ")[0-9a-f]{{40}}(")',
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"Could not locate a unique manifest block for {name}")
    replacement = f"{match.group(1)}{reference}{match.group(2)}{revision}{match.group(3)}"
    updated = text[: match.start()] + replacement + text[match.end() :]
    MANIFEST.write_text(updated, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve an official upstream ref and optionally update its reviewed pin."
    )
    parser.add_argument("--engine", required=True, help="Manifest engine name")
    parser.add_argument("--ref", required=True, help="Exact upstream tag or ref")
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the resolved revision; without this option the command is read-only",
    )
    arguments = parser.parse_args()
    sources = load_engine_manifest()
    if arguments.engine not in sources:
        parser.error(f"unknown engine {arguments.engine!r}")
    source = sources[arguments.engine]
    revision = resolve_ref(source.repository, arguments.ref)
    print(f"Engine: {source.name}")
    print(f"Current revision: {source.revision}")
    print(f"Resolved revision: {revision}")
    if arguments.write:
        update_manifest(source.name, arguments.ref, revision)
        load_engine_manifest()
        print(f"Updated: {MANIFEST}")
    else:
        print("No file changed. Re-run with --write after reviewing the upstream ref.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
