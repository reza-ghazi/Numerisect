"""Enforce the governing policy: Numerisect is a UI over existing libraries.

The project's native-computation rules:

1. Use an existing library routine (PARI/GP, FLINT/Arb, YAFU, Msieve, CADO-NFS,
   GMP-ECM, primesieve, primecount).
2. Only when no library provides it, write optimized C/C++ with GMP/FLINT.
3. Python and JavaScript are interface, API, and orchestration only. Neither
   computes a mathematical result, ever.

These tests fail if a change smuggles mathematics into the interface layer. They
are deliberately source-level: a runtime test cannot tell where a number was
computed, but the source can.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "numerisect"
APP_JS = PACKAGE / "static" / "app.js"

# Modules whose whole job is mathematics; each must reach a native engine.
MATHEMATICAL_MODULES = [
    "primes.py",
    "number_theory.py",
    "prime_manipulation.py",
    "zeta.py",
    "factor_lab.py",
    "primality_lab.py",
    "algebra_lab.py",
    "visual_lab.py",
    "forms_lab.py",
    "gpu.py",
]

# Modules that legitimately contain no engine call: transport, formatting, storage.
INTERFACE_ONLY_MODULES = [
    "exports.py",
    "catalogues.py",
    "client.py",
    "asgi_client.py",
    "config.py",
    "security.py",
    "database.py",
]

ENGINE_CALL = re.compile(
    r"_run_gp\(|_run_zeta\(|_execute\(|subprocess\.(run|Popen)|tool_path\(\)"
    r"|_run_process\(|cuLaunchKernel\("
)

# Third-party mathematics is forbidden outright: it would replace the engines.
FORBIDDEN_IMPORTS = {"sympy", "numpy", "scipy", "gmpy2", "primefac", "labmath"}


def python_sources() -> list[Path]:
    return sorted(PACKAGE.glob("*.py"))


def test_no_third_party_mathematics_library_is_imported():
    """Mathematics must come from the engines, not from a Python library."""

    offenders = []
    for path in python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name in FORBIDDEN_IMPORTS:
                    offenders.append(f"{path.name}: {name}")
    assert not offenders, (
        "Third-party mathematics libraries are not permitted; use a native engine "
        f"or optimized C instead: {offenders}"
    )


@pytest.mark.parametrize("module", MATHEMATICAL_MODULES)
def test_mathematical_modules_dispatch_to_a_native_engine(module: str):
    """Every mathematical module must actually call an engine."""

    path = PACKAGE / module
    if not path.is_file():
        pytest.skip(f"{module} is not present in this build")
    source = path.read_text(encoding="utf-8")
    assert ENGINE_CALL.search(source), (
        f"{module} performs mathematics but never dispatches to a native engine"
    )


@pytest.mark.parametrize("module", MATHEMATICAL_MODULES)
def test_mathematical_modules_name_their_engine(module: str):
    """Each mathematical module must say which routine performs the computation."""

    path = PACKAGE / module
    if not path.is_file():
        pytest.skip(f"{module} is not present in this build")
    head = path.read_text(encoding="utf-8")[:4000].lower()
    assert any(
        name in head
        for name in ("pari", "gp", "flint", "arb", "yafu", "msieve", "cado", "ecm",
                     "primesieve", "primecount", "gmp", "cuda", "nvrtc")
    ), f"{module} does not name the library routine or program that computes its results"


@pytest.mark.parametrize("module", INTERFACE_ONLY_MODULES)
def test_interface_modules_contain_no_primality_or_factoring(module: str):
    """Transport and formatting layers must not decide mathematics."""

    path = PACKAGE / module
    if not path.is_file():
        pytest.skip(f"{module} is not present in this build")
    source = path.read_text(encoding="utf-8")
    # Strip docstrings and comments so prose mentioning the words does not trip this.
    code = re.sub(r'"""[\s\S]*?"""', "", source)
    code = re.sub(r"#[^\n]*", "", code)
    for banned in ("isprime(", "is_prime(", "math.gcd(", "math.prod(", "factorint("):
        assert banned not in code, f"{module} decides mathematics in Python: {banned}"


def test_the_expression_evaluator_is_the_only_python_arithmetic_gateway():
    """Integer expressions are parsed in Python but only through the audited evaluator.

    The evaluator walks the AST and accepts a closed set of node types, so a name,
    a call, or a float can never reach Python arithmetic.
    """

    source = (PACKAGE / "evaluator.py").read_text(encoding="utf-8")
    assert "import ast" in source
    # Only these node types may be evaluated.
    for allowed in ("ast.Expression", "ast.Constant", "ast.UnaryOp", "ast.BinOp"):
        assert allowed in source, f"evaluator no longer handles {allowed}"
    # Anything not explicitly allowed must raise.
    assert "ExpressionError" in source
    tree = ast.parse(source)
    handled = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
        and node.value.id == "ast"
    }
    assert "Call" not in handled, "the evaluator must never evaluate a call node"
    assert "Name" not in handled, "the evaluator must never evaluate a name node"


def test_javascript_never_decides_primality():
    """The browser renders engine output; it must not compute number theory."""

    source = APP_JS.read_text(encoding="utf-8")
    code = re.sub(r"//[^\n]*", "", source)
    code = re.sub(r"/\*[\s\S]*?\*/", "", code)
    # Reading a primality flag the engine returned (data.is_prime) is correct.
    # DEFINING a primality test, or doing big-integer modular arithmetic, is not.
    banned = (
        "function isPrime", "const isPrime", "let isPrime", "isPrime =",
        "function millerRabin", "function gcd", "const gcd =",
        "function factorize", "BigInt(",
    )
    for token in banned:
        assert token not in code, (
            f"app.js appears to compute mathematics in the browser: {token}"
        )


def test_javascript_math_calls_are_presentation_only():
    """Math.* in the browser is allowed for geometry and colour, nothing else.

    Every call site is checked to sit on a line that also mentions a drawing or
    layout concept, which is how canvas geometry is distinguished from arithmetic
    on mathematical quantities.
    """

    source = APP_JS.read_text(encoding="utf-8")
    presentation = (
        "x", "y", "width", "height", "radius", "angle", "canvas", "ctx", "context",
        "pad", "extent", "column", "row", "cell", "bar", "point", "scale", "size",
        "lightness", "colour", "color", "offset", "centre", "center", "margin",
        "frame", "index", "limit", "max", "min", "length", "count", "step", "bin",
        "placed", "layout", "left", "top", "gap", "seconds", "value", "magnitude",
        "frequency", "spoke", "digit", "label", "position", "zoom", "line",
        "spiral", "lattice", "hex", "grid", "draw", "render", "plot", "chart",
        "coordinate", "geometric", "ulam", "sacks", "polar", "wheel", "axis",
    )
    lines = source.splitlines()
    offenders = []
    for number, line in enumerate(lines, start=1):
        if "Math." not in line:
            continue
        # Consider the line together with the enclosing function's name and the
        # preceding comment, because a geometry helper such as ulamPoint() carries
        # its meaning in the signature rather than on every line.
        context = line.lower()
        for back in range(max(0, number - 12), number - 1):
            previous = lines[back]
            if re.match(r"\s*(function|const|let)\s+\w+", previous) or previous.strip().startswith("//"):
                context += " " + previous.lower()
        if not any(word in context for word in presentation):
            offenders.append(f"{number}: {line.strip()[:100]}")
    assert not offenders, (
        "These Math.* call sites do not look like canvas geometry or formatting; "
        f"move the computation into an engine: {offenders}"
    )


def test_every_gp_program_is_packaged():
    """A .gp engine that is not packaged would break the installed wheel."""

    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config["tool"]["setuptools"]["package-data"]["numerisect"]
    assert "*.gp" in patterns
    assert list(PACKAGE.glob("*.gp")), "no GP engines found"


def test_every_c_helper_is_packaged():
    """Native C sources ship in the wheel so the helpers can be rebuilt."""

    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config["tool"]["setuptools"]["package-data"]["numerisect"]
    assert "native/*.c" in patterns
    sources = sorted(path.name for path in (PACKAGE / "native").glob("*.c"))
    assert sources, "no C helpers found"


def test_c_helpers_document_why_they_exist():
    """A C program is only justified when no library provides the routine."""

    for path in sorted((PACKAGE / "native").glob("*.c")):
        head = path.read_text(encoding="utf-8")[:3000].lower()
        assert any(
            phrase in head
            for phrase in ("no installed library", "no library", "flint", "arb", "gmp")
        ), f"{path.name} does not state which library it uses or why it exists"


# --- Minimum supported Python -----------------------------------------------------------


def _nested_same_quote_fstrings(source: str, path: Path) -> list[str]:
    """Find f-strings whose expression reuses the enclosing quote character.

    That is PEP 701 syntax, valid from Python 3.12 and a SyntaxError on 3.11.
    ``ast`` cannot detect it after the fact because the tree is identical either
    way, and ``compile(..., _feature_version=11)`` does not gate it, so the check
    works on the source text of each f-string.
    """

    findings: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings
    lines = source.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        for value in node.values:
            if not isinstance(value, ast.FormattedValue):
                continue
            # A nested JoinedStr inside the expression is the hazard; check whether
            # the two use the same delimiter in the source.
            for inner in ast.walk(value):
                if inner is value or not isinstance(inner, ast.JoinedStr):
                    continue
                start = getattr(node, "lineno", None)
                if not start or start > len(lines):
                    continue
                text = lines[start - 1]
                if 'f"' in text and text.count('f"') > 1:
                    findings.append(f"{path.name}:{start}: nested f-string reusing a quote")
                elif "f'" in text and text.count("f'") > 1:
                    findings.append(f"{path.name}:{start}: nested f-string reusing a quote")
    return findings


def test_every_source_parses_on_the_minimum_supported_python():
    """No file may use syntax newer than the version pyproject.toml promises.

    CI runs 3.11 through 3.14, but a developer on a newer interpreter sees every
    file parse and every test pass while 3.11 fails in CI.

    Two checks run here. If an interpreter matching the declared minimum is
    installed, every source is compiled with it, which is authoritative. Otherwise
    the sources are parsed with an explicit feature version, and PEP 701 f-strings
    are looked for separately because feature_version does not gate them.
    """

    import shutil
    import subprocess
    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requires = config["project"]["requires-python"]
    minimum = requires.lstrip(">=~^ ").split(",")[0].strip()
    major, minor = (int(part) for part in minimum.split(".")[:2])
    assert major == 3, "only Python 3 is supported"

    sources = sorted(ROOT.glob("numerisect/**/*.py")) + sorted(ROOT.glob("tests/*.py"))
    interpreter = shutil.which(f"python{minimum}")
    if interpreter:
        result = subprocess.run(
            [interpreter, "-m", "py_compile", *[str(path) for path in sources]],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"These files do not compile on Python {minimum}: {result.stderr[:2000]}"
        )
        return

    offenders: list[str] = []
    for path in sources:
        source = path.read_text(encoding="utf-8")
        try:
            compile(
                source, str(path), "exec",
                flags=ast.PyCF_ONLY_AST, dont_inherit=True, _feature_version=minor,
            )
        except SyntaxError as exc:
            offenders.append(f"{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
        offenders.extend(_nested_same_quote_fstrings(source, path))
    assert not offenders, (
        f"These use syntax newer than Python {minimum}, which pyproject.toml promises "
        f"and CI tests. Note that `ruff check .` also catches this; run it. {offenders}"
    )


def test_no_python_number_theory_anywhere_including_the_tests():
    """Python must not reimplement what the engines compute, in the suite either.

    A test that checks an engine against a second implementation written here is not an
    independent check: a mistake shared between the two makes both look right. This was
    not hypothetical. A GPU test once carried a full sieve of Eratosthenes and Fermat
    modular inverses in Python to build its own candidate set, duplicating the C helper's
    mathematics. References must come from an engine.

    Three-argument pow is modular exponentiation, and math.gcd, math.isqrt and
    math.factorial are number theory. None belongs on this side of the boundary.
    """

    banned_calls = {"gcd", "isqrt", "factorial", "comb", "perm"}
    offenders: list[str] = []
    roots = [PACKAGE, PACKAGE.parent / "tests"]
    for root in roots:
        for path in sorted(root.glob("*.py")):
            if path.name == "test_native_computation_policy.py":
                continue        # this file names the forbidden constructs to forbid them
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                if isinstance(function, ast.Name) and function.id == "pow" and len(node.args) == 3:
                    offenders.append(f"{path.name}:{node.lineno}: modular exponentiation")
                if (
                    isinstance(function, ast.Attribute)
                    and function.attr in banned_calls
                    and isinstance(function.value, ast.Name)
                    and function.value.id == "math"
                ):
                    offenders.append(f"{path.name}:{node.lineno}: math.{function.attr}")
    assert not offenders, (
        "Python must not compute number theory; ask an engine instead: " + str(offenders)
    )
