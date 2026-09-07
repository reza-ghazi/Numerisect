"""Declarative engine adapter interface (roadmap item 142).

An :class:`EngineAdapter` describes how Numerisect launches one native factoring
tool: the executable name, how to probe its version, how to build the argument
array for a request, how to map output lines to progress phases, and how to
parse factors from its output.  The built-in engines (YAFU, Msieve, CADO-NFS, and
PARI/GP bounded trial division) are registered through the same interface so
that ``GET /api/adapters`` can describe them, while their execution path in
``jobs.py`` is unchanged.

Optional user adapters are loaded from ``STATE_DIR/adapters/*.toml``.  They are
purely declarative: argument templates are arrays with a fixed placeholder
vocabulary, the factor parser is a regular expression with named groups, and
nothing in the file is ever executed through a shell or ``eval``.
"""

from __future__ import annotations

import re
import shutil
import string
import subprocess
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ADAPTERS_DIR
from .engines import parse_cado_factors, parse_msieve_factors, parse_yafu_factors

ADAPTER_NAME = re.compile(r"[a-z][a-z0-9_-]{0,39}")
PLACEHOLDER = re.compile(r"[a-z][a-z0-9_]{0,31}")
BASE_PLACEHOLDERS = frozenset(
    {"number", "threads", "workdir", "trial_bound", "pretest_level", "parameter_file"}
)
KIND_LABELS = {
    "P": "prime",
    "PRP": "probable_prime",
    "C": "composite",
    "U": "unknown",
}
MAX_PATTERN_LENGTH = 500
MAX_TEMPLATE_LENGTH = 400
MAX_ADAPTER_FILE_BYTES = 64_000

FactorParser = Callable[[str, int], list[dict[str, object]]]


class AdapterError(ValueError):
    """Raised when an adapter definition is invalid."""


class _StrictFormatter(string.Formatter):
    """``str.format`` that rejects attribute/index access and unknown fields."""

    def __init__(self, allowed: frozenset[str]):
        super().__init__()
        self.allowed = allowed

    def get_field(self, field_name: str, args: Any, kwargs: Any) -> Any:  # noqa: D401
        if not PLACEHOLDER.fullmatch(field_name) or field_name not in self.allowed:
            raise AdapterError(f"Unknown adapter placeholder: {{{field_name}}}")
        return kwargs[field_name], field_name

    def format_field(self, value: Any, format_spec: str) -> str:
        if format_spec:
            raise AdapterError("Adapter placeholders do not accept format specifications")
        return str(value)


@dataclass(frozen=True)
class EngineAdapter:
    """One native engine described declaratively.

    Attributes:
        name: Registry key (``[a-z][a-z0-9_-]*``).
        command: Bare executable name resolved with ``shutil.which``.
        version_args: Arguments that print the engine version.
        arguments: Argument templates; placeholders are ``{number}``, ``{threads}``,
            ``{workdir}``, ``{trial_bound}``, ``{pretest_level}``, ``{parameter_file}``
            and any key of ``defaults``.
        stdin_template: Optional standard-input template using the same placeholders.
        factor_pattern: Regular expression with a named ``value`` group and optional
            ``kind`` (P/PRP/C/U) and ``digits`` groups, applied per output line.
        kind_map: Mapping from the ``kind`` group text to a factor status.
        phases: ``(needle, label, progress)`` triples matched case-insensitively.
        defaults: Extra placeholder values supplied by the adapter file.
        description: Free text shown in the API.
        builtin: Whether this adapter describes a bundled engine.
        parser: Optional Python parser used by built-in adapters.
    """

    name: str
    command: str
    version_args: tuple[str, ...] = ()
    arguments: tuple[str, ...] = ()
    stdin_template: str | None = None
    factor_pattern: str | None = None
    kind_map: dict[str, str] = field(default_factory=lambda: dict(KIND_LABELS))
    phases: tuple[tuple[str, str, int], ...] = ()
    defaults: dict[str, str] = field(default_factory=dict)
    description: str = ""
    builtin: bool = False
    parser: FactorParser | None = None

    def executable(self) -> str | None:
        """Return the resolved executable path, or ``None`` when absent."""

        return shutil.which(self.command)

    def version_command(self) -> list[str]:
        """Return the argument array that prints the engine version."""

        return [self.command, *self.version_args]

    def probe_version(self, timeout: float = 5.0) -> str | None:
        """Run the version probe and return its first non-empty output line."""

        path = self.executable()
        if not path or not self.version_args:
            return None
        try:
            result = subprocess.run(
                [path, *self.version_args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        for line in result.stdout.splitlines():
            if line.strip():
                return line.strip()[:200]
        return None

    def _placeholders(self, request: dict[str, Any]) -> dict[str, str]:
        values = {key: str(value) for key, value in self.defaults.items()}
        values.update({key: str(value) for key, value in request.items() if value is not None})
        return values

    def build_command(self, request: dict[str, Any]) -> list[str]:
        """Build the argument array for one request (never a shell string)."""

        values = self._placeholders(request)
        formatter = _StrictFormatter(frozenset(values))
        return [self.command, *(formatter.format(template, **values) for template in self.arguments)]

    def build_stdin(self, request: dict[str, Any]) -> str | None:
        """Render the standard-input template, if any."""

        if self.stdin_template is None:
            return None
        values = self._placeholders(request)
        return _StrictFormatter(frozenset(values)).format(self.stdin_template, **values)

    def phase_for_line(self, line: str) -> tuple[str, int] | None:
        """Map an output line to a ``(label, progress)`` phase."""

        lower = line.lower()
        for needle, label, progress in self.phases:
            if needle.lower() in lower:
                return label, progress
        return None

    def parse_factors(self, output: str, target: int) -> list[dict[str, object]]:
        """Parse factor records from the engine output.

        Records have ``value``, ``digits``, and ``status`` keys.  Built-in adapters
        delegate to the reviewed parsers in ``engines.py``; declarative adapters
        apply ``factor_pattern`` to every line.
        """

        if self.parser is not None:
            return self.parser(output, target)
        if not self.factor_pattern:
            return []
        pattern = re.compile(self.factor_pattern)
        records: list[dict[str, object]] = []
        for raw_line in output.replace("\r", "\n").splitlines():
            match = pattern.search(raw_line.strip())
            if not match:
                continue
            groups = match.groupdict()
            value = groups.get("value")
            if not value or not re.fullmatch(r"-?\d+", value):
                continue
            kind = (groups.get("kind") or "U").upper()
            status = self.kind_map.get(kind, "unknown")
            records.append(
                {"value": value, "digits": len(value.lstrip("-")), "status": status}
            )
        return records

    def describe(self) -> dict[str, object]:
        """Return a path-free public description."""

        return {
            "name": self.name,
            "command": self.command,
            "available": bool(self.executable()),
            "builtin": self.builtin,
            "description": self.description,
            "arguments": list(self.arguments),
            "uses_stdin": self.stdin_template is not None,
            "placeholders": sorted(BASE_PLACEHOLDERS | set(self.defaults)),
            "phases": [list(phase) for phase in self.phases],
            "declarative_parser": self.factor_pattern is not None,
        }


def _cado_parser(output: str, target: int) -> list[dict[str, object]]:
    return parse_cado_factors(output, target)


def _yafu_parser(output: str, _: int) -> list[dict[str, object]]:
    return parse_yafu_factors(output)


def _msieve_parser(output: str, _: int) -> list[dict[str, object]]:
    return parse_msieve_factors(output)


def _pari_trial_parser(output: str, _: int) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in output.splitlines():
        if not line.startswith("NTRIAL:"):
            continue
        fields = line.removeprefix("NTRIAL:").split("|")
        if len(fields) != 3 or not all(re.fullmatch(r"\d+", item) for item in fields):
            continue
        value, exponent, proven = fields
        records.extend(
            {
                "value": value,
                "digits": len(value),
                "status": "prime" if proven == "1" else "composite",
            }
            for _ in range(int(exponent))
        )
    return records


BUILTIN_ADAPTERS: tuple[EngineAdapter, ...] = (
    EngineAdapter(
        name="yafu",
        command="yafu",
        version_args=("-v",),
        arguments=("-threads", "{threads}", "-terse"),
        stdin_template="factor({number})\nquit\n",
        phases=(
            ("trial", "Trial division", 8),
            ("rho:", "Pollard rho", 18),
            ("pm1:", "Pollard p−1", 24),
            ("pp1:", "Williams p+1", 28),
            ("ecm:", "Elliptic-curve pretest", 35),
            ("starting siqs", "Self-initializing quadratic sieve", 55),
        ),
        description="YAFU automatic pipeline (trial, rho, p±1, ECM, SIQS, NFS).",
        builtin=True,
        parser=_yafu_parser,
    ),
    EngineAdapter(
        name="msieve",
        command="msieve",
        version_args=("-h",),
        arguments=("-v", "-t", "{threads}", "{number}"),
        phases=(
            ("polynomial selection", "NFS polynomial selection", 18),
            ("lattice sieving", "NFS lattice sieving", 55),
            ("linear algebra", "Linear algebra", 88),
            ("square root", "Square-root phase", 96),
        ),
        description="Msieve MPQS/NFS with its own primality labels.",
        builtin=True,
        parser=_msieve_parser,
    ),
    EngineAdapter(
        name="cado",
        command="cado-nfs.py",
        version_args=("--help",),
        arguments=(
            "-p", "{parameter_file}", "{number}", "-t", "{threads}", "--workdir", "{workdir}",
        ),
        phases=(
            ("polynomial selection", "NFS polynomial selection", 18),
            ("lattice sieving", "NFS lattice sieving", 55),
            ("filtering", "Filtering relations", 75),
            ("linear algebra", "Linear algebra", 88),
            ("square root", "Square-root phase", 96),
        ),
        description="CADO-NFS general number field sieve.",
        builtin=True,
        parser=_cado_parser,
    ),
    EngineAdapter(
        name="pari_trial",
        command="gp",
        version_args=("--version-short",),
        arguments=("-fq",),
        stdin_template=(
            "f=factor({number},{trial_bound}+1);for(i=1,matsize(f)[1],"
            'print("NTRIAL:",f[i,1],"|",f[i,2],"|",isprime(f[i,1])));'
            'print("NTRIAL_DONE:",matsize(f)[1]);quit\n'
        ),
        description="PARI/GP bounded trial division with isprime labels.",
        builtin=True,
        parser=_pari_trial_parser,
    ),
)


def _require_str_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AdapterError(f"Adapter field '{label}' must be a list of strings")
    for item in value:
        if len(item) > MAX_TEMPLATE_LENGTH or any(ord(ch) < 32 and ch != "\n" for ch in item):
            raise AdapterError(f"Adapter field '{label}' contains an invalid entry")
    return tuple(value)


def adapter_from_mapping(data: dict[str, Any]) -> EngineAdapter:
    """Validate a decoded TOML mapping and build a declarative adapter.

    Raises:
        AdapterError: When a field is missing, malformed, or unsafe.
    """

    name = data.get("name")
    if not isinstance(name, str) or not ADAPTER_NAME.fullmatch(name):
        raise AdapterError("Adapter 'name' must match [a-z][a-z0-9_-]{0,39}")
    if any(name == builtin.name for builtin in BUILTIN_ADAPTERS):
        raise AdapterError(f"Adapter name '{name}' is reserved for a built-in engine")
    command = data.get("command")
    if (
        not isinstance(command, str)
        or not command
        or "/" in command
        or "\\" in command
        or any(ch.isspace() for ch in command)
    ):
        raise AdapterError("Adapter 'command' must be a bare executable name")
    pattern = data.get("factor_pattern")
    if not isinstance(pattern, str) or not 1 <= len(pattern) <= MAX_PATTERN_LENGTH:
        raise AdapterError("Adapter 'factor_pattern' must be a regular expression (≤500 chars)")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise AdapterError(f"Adapter 'factor_pattern' is invalid: {exc}") from exc
    if "value" not in compiled.groupindex:
        raise AdapterError("Adapter 'factor_pattern' needs a named group (?P<value>...)")
    defaults_raw = data.get("defaults", {})
    if not isinstance(defaults_raw, dict):
        raise AdapterError("Adapter 'defaults' must be a table")
    defaults: dict[str, str] = {}
    for key, value in defaults_raw.items():
        if not PLACEHOLDER.fullmatch(str(key)) or key in BASE_PLACEHOLDERS:
            raise AdapterError(f"Adapter default '{key}' is not a valid placeholder name")
        if not isinstance(value, (str, int)) or len(str(value)) > MAX_TEMPLATE_LENGTH:
            raise AdapterError(f"Adapter default '{key}' must be a short string or integer")
        defaults[str(key)] = str(value)
    kind_map_raw = data.get("kind_map", dict(KIND_LABELS))
    if not isinstance(kind_map_raw, dict) or any(
        not isinstance(k, str) or v not in {"prime", "probable_prime", "composite", "unknown"}
        for k, v in kind_map_raw.items()
    ):
        raise AdapterError("Adapter 'kind_map' must map text to prime/probable_prime/composite/unknown")
    phases_raw = data.get("phases", [])
    phases: list[tuple[str, str, int]] = []
    if not isinstance(phases_raw, list) or len(phases_raw) > 32:
        raise AdapterError("Adapter 'phases' must be a list of at most 32 entries")
    for item in phases_raw:
        if (
            not isinstance(item, list)
            or len(item) != 3
            or not isinstance(item[0], str)
            or not isinstance(item[1], str)
            or not isinstance(item[2], int)
            or not 0 <= item[2] <= 100
        ):
            raise AdapterError("Each adapter phase must be [needle, label, progress 0–100]")
        phases.append((item[0], item[1], item[2]))
    stdin_template = data.get("stdin")
    if stdin_template is not None and (
        not isinstance(stdin_template, str) or len(stdin_template) > 4000
    ):
        raise AdapterError("Adapter 'stdin' must be a string of at most 4,000 characters")
    description = data.get("description", "")
    if not isinstance(description, str) or len(description) > 500:
        raise AdapterError("Adapter 'description' must be a string of at most 500 characters")
    adapter = EngineAdapter(
        name=name,
        command=command,
        version_args=_require_str_list(data.get("version_args", []), "version_args"),
        arguments=_require_str_list(data.get("arguments", []), "arguments"),
        stdin_template=stdin_template,
        factor_pattern=pattern,
        kind_map={str(k).upper(): str(v) for k, v in kind_map_raw.items()},
        phases=tuple(phases),
        defaults=defaults,
        description=description,
        builtin=False,
    )
    # Render once with dummy values so unknown placeholders fail at load time.
    probe = {
        "number": "1", "threads": "1", "workdir": "w", "trial_bound": "1",
        "pretest_level": "1", "parameter_file": "p",
    }
    adapter.build_command(probe)
    adapter.build_stdin(probe)
    return adapter


def load_user_adapters(directory: Path = ADAPTERS_DIR) -> tuple[list[EngineAdapter], list[str]]:
    """Load ``*.toml`` adapters from ``directory``.

    Returns:
        ``(adapters, problems)`` where ``problems`` lists rejected files with reasons
        (file names only, never absolute paths).
    """

    adapters: list[EngineAdapter] = []
    problems: list[str] = []
    if not directory.is_dir():
        return adapters, problems
    for path in sorted(directory.glob("*.toml")):
        try:
            if path.stat().st_size > MAX_ADAPTER_FILE_BYTES:
                raise AdapterError("adapter file exceeds 64 kB")
            with path.open("rb") as handle:
                data = tomllib.load(handle)
            adapter = adapter_from_mapping(data)
        except (OSError, tomllib.TOMLDecodeError, AdapterError) as exc:
            problems.append(f"{path.name}: {exc}")
            continue
        if any(existing.name == adapter.name for existing in adapters):
            problems.append(f"{path.name}: duplicate adapter name '{adapter.name}'")
            continue
        adapters.append(adapter)
    return adapters, problems


class AdapterRegistry:
    """Registry of built-in and user adapters."""

    def __init__(self, directory: Path = ADAPTERS_DIR):
        self.directory = directory
        self._builtin = {adapter.name: adapter for adapter in BUILTIN_ADAPTERS}
        self._user: dict[str, EngineAdapter] = {}
        self.problems: list[str] = []
        self.reload()

    def reload(self) -> None:
        """Re-read user adapters from disk."""

        adapters, problems = load_user_adapters(self.directory)
        self._user = {adapter.name: adapter for adapter in adapters}
        self.problems = problems

    def get(self, name: str) -> EngineAdapter | None:
        return self._builtin.get(name) or self._user.get(name)

    def all(self) -> list[EngineAdapter]:
        return [*self._builtin.values(), *self._user.values()]

    def describe(self, probe_versions: bool = False) -> dict[str, object]:
        items = []
        for adapter in self.all():
            entry = adapter.describe()
            if probe_versions:
                entry["version"] = adapter.probe_version()
            items.append(entry)
        return {
            "adapters": items,
            "problems": list(self.problems),
            "note": (
                "Built-in adapters describe the bundled engines; user adapters are "
                "declarative TOML files (argument arrays and output regexes only)."
            ),
        }


REGISTRY = AdapterRegistry()
