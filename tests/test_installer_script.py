import os
import subprocess
from pathlib import Path

import pytest

from numerisect.installer import ENGINE_SOURCES, load_engine_manifest

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
    assert 'Windows WSL' in INSTALLER
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
    assert 'not installed automatically' in INSTALLER
    assert 'python3 -m venv' in INSTALLER or ' -m venv ' in INSTALLER
    assert 'python" -m pip install "$release_dir"' in INSTALLER
    assert 'LICENSE NOTICE.md README.md THIRD_PARTY_LICENSES.md' in INSTALLER


def test_installer_requires_confirmation_and_does_not_upgrade_pip():
    assert '--yes' in INSTALLER
    assert 'confirm_system_changes' in INSTALLER
    assert 'Packages: %s' in INSTALLER
    assert 'Administrative privileges required: %s' in INSTALLER
    assert 'pip install --upgrade pip' not in INSTALLER


def test_installer_resolves_checkout_when_called_elsewhere(tmp_path):
    result = subprocess.run(
        [str(ROOT / 'install.sh'), '--check', '--no-system-deps'],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode:
        pytest.skip(f'Host lacks optional native prerequisites: {result.stderr.strip()}')
    assert 'Numerisect 0.6.0 prerequisites are available' in result.stdout


def test_installer_rejects_unsupported_operating_system(tmp_path):
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    fake_uname = fake_bin / 'uname'
    fake_uname.write_text('#!/bin/sh\nprintf Haiku\\n\n', encoding='utf-8')
    fake_uname.chmod(0o755)
    environment = os.environ.copy()
    environment['PATH'] = f'{fake_bin}:{environment["PATH"]}'
    result = subprocess.run(
        [str(ROOT / 'install.sh'), '--check'],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert 'Unsupported operating system: Haiku' in result.stderr


def test_installer_refuses_unconfirmed_system_changes(tmp_path):
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    fake_pkg_config = fake_bin / 'pkg-config'
    fake_pkg_config.write_text('#!/bin/sh\nexit 1\n', encoding='utf-8')
    fake_pkg_config.chmod(0o755)
    environment = os.environ.copy()
    environment['PATH'] = f'{fake_bin}:{environment["PATH"]}'
    result = subprocess.run(
        [str(ROOT / 'install.sh'), '--prefix', str(tmp_path / 'application')],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert 'Package manager:' in result.stdout
    assert 'Packages:' in result.stdout
    assert 'requires confirmation' in result.stderr


def test_engine_manifest_is_complete_and_immutable():
    sources = load_engine_manifest()
    assert sources == ENGINE_SOURCES
    assert set(sources) == {
        "PARI/GP",
        "GMP-ECM",
        "Msieve",
        "YAFU",
        "CADO-NFS",
        "GGNFS lattice sievers",
        "FLINT/Zeta",
        "primesieve",
        "primecount",
    }
    assert all(len(source.revision) == 40 for source in sources.values())
    assert all(source.repository.startswith('https://') for source in sources.values())
