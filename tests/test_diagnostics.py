from numerisect.diagnostics import system_diagnostics
from numerisect.installer import ENGINE_SOURCES


def test_diagnostics_are_complete_and_sanitized():
    result = system_diagnostics()
    assert len(result["rows"]) == len(ENGINE_SOURCES)
    assert result["metrics"]["Logical CPUs"]
    assert "/home/reza" not in str(result)
    assert all(len(row) == 5 for row in result["rows"])
