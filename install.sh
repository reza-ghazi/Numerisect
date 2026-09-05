#!/usr/bin/env bash
set -euo pipefail

# Install Numerisect from this source checkout into a user-owned, versioned tree.
# System package installation is intentionally explicit and distro-aware; native
# engines are built by Numerisect on first start under the shared state directory.

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
version="$(awk -F'"' '/^version = / { print $2; exit }' "$project_dir/pyproject.toml")"
if [[ -z "$version" || ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]]; then
  echo "Could not determine a valid version from pyproject.toml" >&2
  exit 1
fi

prefix="${NUMERISECT_INSTALL_DIR:-$HOME/.local/share/numerisect}"
install_system_deps=1
force=0
check_only=0
host_os="$(uname -s)"
case "$host_os" in
  Linux) platform_label="Linux or Windows WSL" ;;
  Darwin) platform_label="macOS" ;;
  *) echo "Unsupported host OS: $host_os. Use Linux, Windows WSL, or macOS." >&2; exit 1 ;;
esac

usage() {
  printf '%s\n' \
    "Usage: ./install.sh [--prefix DIR] [--no-system-deps] [--force] [--check]" \
    "  --prefix DIR       Install under DIR (default: ~/.local/share/numerisect)" \
    "  --no-system-deps   Check system prerequisites without invoking a package manager" \
    "  --force            Rebuild this version directory if it already exists" \
    "  --check            Check prerequisites and version consistency only"
}

while (($#)); do
  case "$1" in
    --prefix)
      [[ $# -ge 2 ]] || { echo "--prefix requires a directory" >&2; exit 2; }
      prefix="$2"; shift 2 ;;
    --no-system-deps) install_system_deps=0; shift ;;
    --force) force=1; shift ;;
    --check) check_only=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$prefix" in
  /|"$project_dir"|"$project_dir"/*)
    echo "Choose an installation prefix outside the source checkout: $prefix" >&2
    exit 2 ;;
esac

python_command="$(command -v python3 || true)"
if [[ -z "$python_command" ]]; then
  echo "Python 3 is required. Install Python 3.11 or newer and retry." >&2
  exit 1
fi
"$python_command" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required")
PY

package_version="$($python_command -c 'import pathlib,re; text=pathlib.Path("pyproject.toml").read_text(); print(re.search(r"^version = \"([^\"]+)\"", text, re.M).group(1))' 2>/dev/null || true)"
if [[ "$package_version" != "$version" ]]; then
  echo "Version mismatch between installer and pyproject.toml" >&2
  exit 1
fi
module_version="$($python_command -c 'import numerisect; print(numerisect.__version__)' 2>/dev/null || true)"
if [[ "$module_version" != "$version" ]]; then
  echo "Version mismatch between pyproject.toml ($version) and numerisect.__version__ ($module_version)" >&2
  exit 1
fi

libtool_command="libtoolize"
if [[ "$host_os" == Darwin ]] && command -v glibtoolize >/dev/null 2>&1; then
  libtool_command="glibtoolize"
fi

declare -a missing_commands=()
for command in git make cc cmake pkg-config autoconf automake "$libtool_command"; do
  command -v "$command" >/dev/null 2>&1 || missing_commands+=("$command")
done

declare -a missing_libraries=()
for module in gmp mpfr flint; do
  if ! pkg-config --exists "$module" >/dev/null 2>&1; then
    missing_libraries+=("$module")
  fi
done

install_system_packages() {
  local manager=""
  if command -v dnf >/dev/null 2>&1; then manager=dnf
  elif command -v apt-get >/dev/null 2>&1; then manager=apt-get
  elif command -v pacman >/dev/null 2>&1; then manager=pacman
  elif command -v brew >/dev/null 2>&1; then manager=brew
  fi
  if [[ -z "$manager" ]]; then
    echo "No supported package manager found; cannot install missing system libraries." >&2
    return 1
  fi
  local sudo_command=()
  if [[ "$manager" != brew && "${EUID:-$(id -u)}" -ne 0 ]]; then
    command -v sudo >/dev/null 2>&1 || { echo "sudo is required to install system packages" >&2; return 1; }
    sudo_command=(sudo)
  fi
  case "$manager" in
    dnf)
      "${sudo_command[@]}" dnf install -y git make gcc gcc-c++ cmake pkgconf-pkg-config \
        gmp-devel mpfr-devel flint-devel autoconf automake libtool ;;
    apt-get)
      "${sudo_command[@]}" apt-get update
      "${sudo_command[@]}" apt-get install -y git make gcc g++ cmake pkg-config \
        python3-venv libgmp-dev libmpfr-dev libflint-dev autoconf automake libtool ;;
    pacman)
      "${sudo_command[@]}" pacman -Sy --needed --noconfirm git make gcc cmake pkgconf \
        python gmp mpfr flint autoconf automake libtool ;;
    brew)
      brew install git make cmake pkg-config gmp mpfr flint autoconf automake libtool ;;
  esac
}

if ((${#missing_commands[@]} || ${#missing_libraries[@]})); then
  ((${#missing_commands[@]})) && echo "Missing system commands: ${missing_commands[*]}"
  ((${#missing_libraries[@]})) && echo "Missing system libraries: ${missing_libraries[*]}"
  if ((install_system_deps)); then
    install_system_packages
  else
    echo "System dependency installation disabled (--no-system-deps)." >&2
  fi
fi

missing_after=()
for command in git make cc cmake pkg-config autoconf automake "$libtool_command"; do
  command -v "$command" >/dev/null 2>&1 || missing_after+=("$command")
done
missing_libraries_after=()
for module in gmp mpfr flint; do
  pkg-config --exists "$module" >/dev/null 2>&1 || missing_libraries_after+=("$module")
done
if ((${#missing_after[@]} || ${#missing_libraries_after[@]})); then
  echo "Missing required system commands: ${missing_after[*]}" >&2
  ((${#missing_libraries_after[@]})) && echo "Missing required system libraries: ${missing_libraries_after[*]}" >&2
  exit 1
fi

if ((check_only)); then
  echo "Numerisect $version prerequisites are available on $platform_label."
  echo "Install prefix: $prefix"
  exit 0
fi

release_dir="$prefix/releases/$version"
if [[ -e "$release_dir" ]]; then
  if ((force)); then
    backup_dir="$prefix/releases/$version.backup.$(date +%Y%m%d%H%M%S)"
    mv -- "$release_dir" "$backup_dir"
    echo "Existing release moved to $backup_dir"
  else
    echo "Release $version is already installed at $release_dir; use --force to replace it." >&2
    exit 1
  fi
fi

mkdir -p "$prefix/releases" "$prefix/state" "$prefix/output" "$prefix/bin"
mkdir -p "$release_dir"

for item in LICENSE README.md pyproject.toml run.sh; do
  cp -a "$project_dir/$item" "$release_dir/$item"
done
for directory in numerisect static native docs; do
  cp -a "$project_dir/$directory" "$release_dir/$directory"
done

"$python_command" -m venv "$release_dir/.venv"
"$release_dir/.venv/bin/python" -m pip install --upgrade pip
"$release_dir/.venv/bin/python" -m pip install "$release_dir"

printf '%s\n' "$version" > "$release_dir/VERSION"
printf '%s\n' \
  "Numerisect $version" \
  "Installed: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "Source: $project_dir" > "$release_dir/INSTALLATION.txt"

ln -sfn "releases/$version" "$prefix/current"
cat > "$prefix/bin/numerisect" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
install_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export NUMERISECT_STATE_DIR="$install_root/state"
export NUMERISECT_OUTPUT_DIR="$install_root/output"
exec "$install_root/current/run.sh" "$@"
EOF
chmod 0755 "$prefix/bin/numerisect"

echo "Installed Numerisect $version at $release_dir"
echo "Current release: $prefix/current"
echo "Launcher: $prefix/bin/numerisect"
echo "Add $prefix/bin to PATH to run 'numerisect'."
echo "Native engines are checked and installed on the first application start."
