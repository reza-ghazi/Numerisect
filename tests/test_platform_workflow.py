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
