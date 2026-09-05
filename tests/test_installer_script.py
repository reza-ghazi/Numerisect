from pathlib import Path


ROOT = Path(__file__).parents[1]
INSTALLER = (ROOT / "install.sh").read_text(encoding="utf-8")
MODE = (ROOT / "install.sh").stat().st_mode


def test_installer_is_executable_and_versioned():
    assert MODE & 0o111
    assert 'version="$(awk -F\'"\'' in INSTALLER
    assert 'releases/$version' in INSTALLER
    assert 'ln -sfn "releases/$version" "$prefix/current"' in INSTALLER
    assert 'printf \'%s\\n\' "$version" > "$release_dir/VERSION"' in INSTALLER


def test_installer_is_cross_platform_and_checks_dependencies():
    assert 'Linux or Windows WSL' in INSTALLER
    assert 'macOS' in INSTALLER
    assert 'dnf install -y' in INSTALLER
    assert 'apt-get install -y' in INSTALLER
    assert 'pacman -Sy' in INSTALLER
    assert 'brew install' in INSTALLER
    assert 'python3-venv' in INSTALLER
    assert 'gmp-devel mpfr-devel flint-devel' in INSTALLER
    assert 'libgmp-dev libmpfr-dev libflint-dev' in INSTALLER
    assert 'pkg-config --exists' in INSTALLER


def test_installer_preserves_shared_state_and_managed_engine_setup():
    assert 'NUMERISECT_STATE_DIR' in INSTALLER
    assert 'NUMERISECT_OUTPUT_DIR' in INSTALLER
    assert 'numerisect.__version__' in INSTALLER
    assert 'state/tools' in INSTALLER or 'Native engines are checked' in INSTALLER
    assert 'python3 -m venv' in INSTALLER or ' -m venv ' in INSTALLER
    assert 'python" -m pip install "$release_dir"' in INSTALLER
