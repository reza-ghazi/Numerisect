"""Static contracts for the supported-host compatibility workflow."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "platform-compatibility.yml").read_text(
    encoding="utf-8"
)


def test_supported_ci_hosts_are_real_github_runner_targets():
    for runner in ("ubuntu-24.04-arm", "macos-15", "macos-15-intel", "windows-2025"):
        assert runner in WORKFLOW


def test_wsl_job_uses_a_pinned_action_and_real_ubuntu_distribution():
    assert "Vampire/setup-wsl@d1da7f2c0322a5ee4f24975344f67fc0f5baf364" in WORKFLOW
    assert "distribution: Ubuntu-24.04" in WORKFLOW
    assert "wsl-version: 1" in WORKFLOW
    assert "grep -qi microsoft /proc/version" in WORKFLOW


def test_every_platform_runs_tests_and_exercises_the_installer():
    assert WORKFLOW.count("Run complete native test suite") == 2
    assert WORKFLOW.count("Exercise versioned user installation") == 2
    assert WORKFLOW.count("./install.sh --check") == 2


def test_every_platform_installs_the_built_distribution_rather_than_the_checkout():
    """A platform job that installs `.` tests the source tree, not what users get.

    The decision recorded in the roadmap is that each platform installs the published
    artifact. So each job builds the distribution and installs the wheel into a fresh
    environment; `pip install '.[test,dev]'` must not come back.
    """

    assert "python -m build" in WORKFLOW
    assert WORKFLOW.count("numerisect-*.whl)[test,dev]") == 2
    assert "pip install '.[test,dev]'" not in WORKFLOW
    assert WORKFLOW.count("scripts/check_installed_distribution.py") == 2


def test_the_installed_distribution_check_refuses_a_checkout_import():
    """The check is the thing that makes the installation claim mean anything.

    A smoke test run with the checkout as working directory imports the checkout, so
    this asserts the script still contains the guard that catches exactly that.
    """

    script = (ROOT / "scripts" / "check_installed_distribution.py").read_text(encoding="utf-8")
    assert "not an installed distribution" in script
    assert "site-packages" in script
    assert "CHECKOUT in location.parents" in script
    quality = (ROOT / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    assert "scripts/check_installed_distribution.py" in quality
    assert "pari-gp" in quality          # the check computes, so the engine must be there
