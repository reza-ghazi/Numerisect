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

    assert len(html_forms) == len(set(html_forms)) == 133
    assert len(categorized_forms) == len(set(categorized_forms)) == 133
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


def test_zeta_tools_use_individual_routes_and_local_results():
    grid = INDEX.split('id="zeta-page-grid"', 1)[1].split('id="zeta-result-panel"', 1)[0]
    forms = re.findall(r'<form id="(zeta-[^"]+-form)"', grid)
    catalogue = APP.split("const zetaSections = {", 1)[1].split("const zetaTools", 1)[0]
    categorized = re.findall(r"'(zeta-[^']+-form)'", catalogue)
    assert len(forms) == len(set(forms)) == 22
    assert set(forms) == set(categorized)
    assert "form.insertAdjacentElement('afterend', panel)" in APP


def test_interface_assets_are_cache_busted():
    assert '/assets/styles.css?v=20260907-arbitrary-digits' in INDEX
    assert '/assets/app.js?v=20260907-arbitrary-digits' in INDEX
    assert '/assets/favicon.svg?v=20260907-arbitrary-digits' in INDEX
    assert '--app-dir "$project_dir"' in RUNNER
    assert '?ui=20260907-arbitrary-digits#primes/prime-check' in RUNNER
    assert '"$browser_open" "$ui_url"' in RUNNER
    assert 'NUMERISECT_NO_BROWSER' in RUNNER


def test_browser_bootstraps_local_request_protection():
    assert "await api('/api/session')" in APP
    assert "X-Numerisect-Token" in APP
    assert "window.confirm" in APP
    assert "body: JSON.stringify({ confirm: true })" in APP


def test_system_diagnostics_are_a_first_class_local_workspace():
    assert 'data-view="diagnostic-view"' in INDEX
    assert 'id="run-diagnostics"' in INDEX
    assert "#diagnostics" in APP
    assert "Report saved automatically to output/${escapeHtml(data.output_file)}" in APP


# --- Documentation site ------------------------------------------------------------


def test_every_documentation_page_is_reachable_from_the_site_navigation():
    """A page in docs/ that is not in mkdocs.yml would be published but unlinked."""

    import re

    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    nav = config.split("nav:", 1)[1]
    listed = set(re.findall(r"([A-Za-z0-9_./-]+\.md)", nav))
    # ROADMAP_STATUS.md is deliberately excluded from the nav and linked inline.
    listed.update(re.findall(r"([A-Za-z0-9_./-]+\.md)", config.split("not_in_nav:", 1)[1].split("nav:", 1)[0]))
    on_disk = {
        str(path.relative_to(ROOT / "docs"))
        for path in (ROOT / "docs").rglob("*.md")
    }
    missing = sorted(on_disk - listed)
    assert not missing, f"These documentation pages are not in the site navigation: {missing}"


def test_the_site_declares_the_custom_domain():
    assert (ROOT / "docs" / "CNAME").read_text(encoding="utf-8").strip() == "docs.numerisect.com"


def test_the_documentation_site_carries_no_analytics():
    """Numerisect is offline-first; its documentation does not track readers."""

    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    for tracker in ("google_analytics", "gtag", "analytics:", "googletagmanager"):
        assert tracker not in config, f"the documentation site must not carry {tracker}"
