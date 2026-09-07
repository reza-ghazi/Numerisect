import getpass
from pathlib import Path

from numerisect.diagnostics import system_diagnostics
from numerisect.installer import ENGINE_SOURCES


def test_diagnostics_are_complete_and_sanitized():
    result = system_diagnostics()
    assert len(result["rows"]) == len(ENGINE_SOURCES)
    assert result["metrics"]["Logical CPUs"]
    # The report must never carry the home directory or the user's name, whoever
    # runs it. Checking the real values keeps this honest on any machine.
    rendered = str(result)
    assert str(Path.home()) not in rendered
    assert getpass.getuser() not in rendered
    assert all(len(row) == 5 for row in result["rows"])
