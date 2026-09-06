#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -Eeuo pipefail

# Install Numerisect from this source checkout into a user-owned, versioned tree.
# Native engines are optional and are installed only after explicit action in the UI.

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"

version="$(awk -F'"' '/^version = / { print $2; exit }' "$project_dir/pyproject.toml")"
if [[ -z "$version" || ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]]; then
  echo "Could not determine a valid version from $project_dir/pyproject.toml" >&2
  exit 1
fi

prefix="${NUMERISECT_INSTALL_DIR:-${HOME}/.local/share/numerisect}"
install_system_deps=1
assume_yes=0
force=0
check_only=0
host_os="$(uname -s)"
host_arch="$(uname -m)"

case "$host_os" in
  Linux)
    if [[ -r /proc/version ]] && grep -qi microsoft /proc/version; then
      platform_label="Windows WSL"
    else
      platform_label="Linux"
    fi
    ;;
  Darwin) platform_label="macOS" ;;
  *)
    echo "Unsupported operating system: $host_os. Supported installer hosts are Linux, Windows WSL, and macOS." >&2
    exit 1
    ;;
esac

case "$host_arch" in
  x86_64|amd64) architecture_label="x86-64" ;;
  arm64|aarch64) architecture_label="ARM64" ;;
  *)
    echo "Unsupported architecture: $host_arch. Supported installer architectures are x86-64 and ARM64." >&2
    exit 1
    ;;
esac

usage() {
  printf '%s\n' \
    "Usage: ./install.sh [--prefix DIR] [--no-system-deps] [--yes] [--force] [--check]" \
    "  --prefix DIR       Install under DIR (default: ~/.local/share/numerisect)" \
    "  --no-system-deps   Never invoke a system package manager" \
    "  --yes              Confirm displayed system-package changes noninteractively" \
    "  --force            Replace this version directory after preserving a backup" \
    "  --check            Check prerequisites and version consistency only"
}

while (($#)); do
  case "$1" in
    --prefix)
      [[ $# -ge 2 ]] || { echo "--prefix requires a directory" >&2; exit 2; }
      prefix="$2"
      shift 2
      ;;
    --no-system-deps) install_system_deps=0; shift ;;
    --yes) assume_yes=1; shift ;;
    --force) force=1; shift ;;
    --check) check_only=1; install_system_deps=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$prefix" in
  /|"$project_dir"|"$project_dir"/*)
    echo "Choose an installation prefix outside the source checkout: $prefix" >&2
    exit 2
    ;;
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

package_version="$("$python_command" -c 'import pathlib,re,sys; text=pathlib.Path(sys.argv[1]).read_text(); print(re.search(r"^version = \"([^\"]+)\"", text, re.M).group(1))' "$project_dir/pyproject.toml")"
module_version="$(PYTHONPATH="$project_dir" "$python_command" -c 'import numerisect; print(numerisect.__version__)')"
if [[ "$package_version" != "$version" || "$module_version" != "$version" ]]; then
  echo "Version mismatch: pyproject.toml=$package_version, numerisect.__version__=$module_version" >&2
  exit 1
fi

libtool_command="libtoolize"
if [[ "$host_os" == Darwin ]]; then
  libtool_command="glibtoolize"
fi

declare -a missing_commands=()
for command in git make cc cmake pkg-config autoconf automake "$libtool_command"; do
  command -v "$command" >/dev/null 2>&1 || missing_commands+=("$command")
done

declare -a missing_libraries=()
for module in gmp mpfr flint; do
  if ! command -v pkg-config >/dev/null 2>&1 || ! pkg-config --exists "$module"; then
    missing_libraries+=("$module")
  fi
done

detect_package_manager() {
  if command -v dnf >/dev/null 2>&1; then package_manager="dnf"
  elif command -v apt-get >/dev/null 2>&1; then package_manager="apt-get"
  elif command -v pacman >/dev/null 2>&1; then package_manager="pacman"
  elif command -v brew >/dev/null 2>&1; then package_manager="brew"
  else package_manager=""
  fi
}

confirm_system_changes() {
  local answer=""
  if ((assume_yes)); then return 0; fi
  if [[ ! -t 0 ]]; then
    echo "System-package installation requires confirmation. Re-run interactively or pass --yes." >&2
    return 1
  fi
  read -r -p "Install the packages shown above? [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" || "$answer" == "yes" || "$answer" == "YES" ]]
}

install_system_packages() {
  detect_package_manager
  if [[ -z "$package_manager" ]]; then
    echo "No supported package manager was found; install the prerequisites documented in docs/INSTALLATION.md." >&2
    return 1
  fi

  local requires_admin="yes"
  local -a packages=()
  case "$package_manager" in
    dnf) packages=(git make gcc gcc-c++ cmake pkgconf-pkg-config gmp-devel mpfr-devel flint-devel autoconf automake libtool) ;;
    apt-get) packages=(git make gcc g++ cmake pkg-config python3-venv libgmp-dev libmpfr-dev libflint-dev autoconf automake libtool) ;;
    pacman) packages=(git make gcc cmake pkgconf python gmp mpfr flint autoconf automake libtool) ;;
    brew)
      packages=(git make cmake pkg-config gmp mpfr flint autoconf automake libtool)
      requires_admin="no"
      ;;
  esac

  printf 'Package manager: %s\nAdministrative privileges required: %s\nPackages: %s\n' \
    "$package_manager" "$requires_admin" "${packages[*]}"
  confirm_system_changes || { echo "System-package installation was not approved." >&2; return 1; }

  local -a privilege=()
  if [[ "$requires_admin" == yes && "${EUID:-$(id -u)}" -ne 0 ]]; then
    command -v sudo >/dev/null 2>&1 || { echo "sudo is required for $package_manager." >&2; return 1; }
    privilege=(sudo)
  fi
  case "$package_manager" in
    dnf) "${privilege[@]}" dnf install -y "${packages[@]}" ;;
    apt-get)
      "${privilege[@]}" apt-get update
      "${privilege[@]}" apt-get install -y "${packages[@]}"
      ;;
    pacman) "${privilege[@]}" pacman -Sy --needed --noconfirm "${packages[@]}" ;;
    brew) brew install "${packages[@]}" ;;
  esac
}

if ((${#missing_commands[@]} || ${#missing_libraries[@]})); then
  ((${#missing_commands[@]})) && echo "Missing system commands: ${missing_commands[*]}"
  ((${#missing_libraries[@]})) && echo "Missing system libraries: ${missing_libraries[*]}"
  if ((install_system_deps)); then
    install_system_packages
  else
    echo "System dependency installation is disabled; no system changes were made." >&2
  fi
fi

declare -a missing_after=()
for command in git make cc cmake pkg-config autoconf automake "$libtool_command"; do
  command -v "$command" >/dev/null 2>&1 || missing_after+=("$command")
done
declare -a missing_libraries_after=()
for module in gmp mpfr flint; do
  if ! command -v pkg-config >/dev/null 2>&1 || ! pkg-config --exists "$module"; then
    missing_libraries_after+=("$module")
  fi
done
if ((${#missing_after[@]} || ${#missing_libraries_after[@]})); then
  ((${#missing_after[@]})) && echo "Missing required system commands: ${missing_after[*]}" >&2
  ((${#missing_libraries_after[@]})) && echo "Missing required system libraries: ${missing_libraries_after[*]}" >&2
  exit 1
fi

if ((check_only)); then
  echo "Numerisect $version prerequisites are available on $platform_label ($architecture_label)."
  echo "Install prefix: $prefix"
  exit 0
fi

release_dir="$prefix/releases/$version"
if [[ -e "$release_dir" ]]; then
  if ((force)); then
    backup_dir="$prefix/releases/$version.backup.$(date +%Y%m%d%H%M%S)"
    mv -- "$release_dir" "$backup_dir"
    echo "Existing release preserved at $backup_dir"
  else
    echo "Release $version already exists at $release_dir; use --force to preserve and replace it." >&2
    exit 1
  fi
fi

mkdir -p "$prefix/releases" "$prefix/state" "$prefix/output" "$prefix/bin" "$release_dir"
touch "$release_dir/.install-incomplete"

for item in LICENSE NOTICE.md README.md THIRD_PARTY_LICENSES.md pyproject.toml run.sh; do
  [[ -e "$project_dir/$item" ]] && cp -a "$project_dir/$item" "$release_dir/$item"
done
for directory in numerisect docs scripts; do
  [[ -d "$project_dir/$directory" ]] && cp -a "$project_dir/$directory" "$release_dir/$directory"
done

if ! "$python_command" -m venv "$release_dir/.venv"; then
  echo "Could not create the virtual environment. Partial installation remains marked at $release_dir." >&2
  exit 1
fi
if ! "$release_dir/.venv/bin/python" -m pip install "$release_dir"; then
  echo "Python dependency installation failed. Partial installation remains marked at $release_dir." >&2
  exit 1
fi

printf '%s\n' "$version" > "$release_dir/VERSION"
printf '%s\n' \
  "Numerisect $version" \
  "Installed: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "Source revision: $(git -C "$project_dir" rev-parse HEAD 2>/dev/null || printf 'source archive')" \
  > "$release_dir/INSTALLATION.txt"

rm -- "$release_dir/.install-incomplete"
ln -sfn "releases/$version" "$prefix/current"
cat > "$prefix/bin/numerisect" <<'EOF'
#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
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
echo "Optional native engines are not installed automatically. Review them in the application before starting a pinned source build."
