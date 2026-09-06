import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
INDEX = (ROOT / "numerisect" / "static" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "numerisect" / "static" / "app.js").read_text(encoding="utf-8")
RUNNER = (ROOT / "run.sh").read_text(encoding="utf-8")


def test_every_prime_tool_belongs_to_exactly_one_navigation_section():
    grid = INDEX.split('id="prime-page-grid"', 1)[1].split(
        'id="prime-result-panel"', 1
    )[0]
    html_forms = re.findall(r'<form id="([^"]+-form)"', grid)
    page_catalogue = APP.split("const primeSections = {", 1)[1].split(
        "const primeTools", 1
    )[0]
    categorized_forms = re.findall(r"'([^']+-form)'", page_catalogue)

    assert len(html_forms) == len(set(html_forms)) == 38
    assert len(categorized_forms) == len(set(categorized_forms)) == 38
    assert set(categorized_forms) == set(html_forms)


def test_prime_tools_use_one_operation_per_route():
    assert 'id="prime-tool-navigation"' in INDEX
    assert 'id="prime-tool-search"' in INDEX
    assert 'id="prime-tool-select"' in INDEX
    assert 'class="prime-page-tabs"' not in INDEX
    assert "form.classList.toggle('prime-page-hidden', form.id !== selected.formId)" in APP
    assert "`#primes/prime-check`" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_prime_results_are_placed_below_the_submitted_form():
    assert "form.insertAdjacentElement('afterend', panel)" in APP
    assert "showPrimeResult(title(data), data, type, form)" in APP
    assert "placePrimeResult(form);" in APP
    assert "Result saved automatically to output/${data.output_file}" in APP


def test_interface_assets_are_cache_busted():
    assert '/assets/styles.css?v=20260905-workstation' in INDEX
    assert '/assets/app.js?v=20260905-workstation' in INDEX
    assert '--app-dir "$project_dir"' in RUNNER
    assert '?ui=20260905-workstation#primes/prime-check' in RUNNER
    assert '"$browser_open" "$ui_url"' in RUNNER
    assert 'NUMERISECT_NO_BROWSER' in RUNNER


def test_browser_bootstraps_local_request_protection():
    assert "await api('/api/session')" in APP
    assert "X-Numerisect-Token" in APP
    assert "window.confirm" in APP
    assert "body: JSON.stringify({ confirm: true })" in APP
