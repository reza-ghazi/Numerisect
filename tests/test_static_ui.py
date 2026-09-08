import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
INDEX = (ROOT / "numerisect" / "static" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "numerisect" / "static" / "app.js").read_text(encoding="utf-8")
RUNNER = (ROOT / "run.sh").read_text(encoding="utf-8")


API_REFERENCE = (ROOT / "docs" / "reference" / "api.md").read_text(encoding="utf-8")


def test_every_documented_endpoint_states_its_purpose():
    """An endpoint table with a blank Purpose column tells the reader nothing.

    151 of the 208 rows shipped empty, so the reference listed routes without
    saying what any of them did.
    """

    rows = re.findall(
        r"^\| `(?:GET|POST|DELETE)` \| `([^`]+)` \| (.*) \|$", API_REFERENCE, re.M
    )
    assert len(rows) > 200, f"the endpoint table shrank unexpectedly: {len(rows)} rows"
    blank = [route for route, purpose in rows if not purpose.strip()]
    assert not blank, f"endpoints documented with no purpose: {blank}"


def test_api_reference_table_rows_are_well_formed():
    """An unescaped pipe silently splits a row into extra columns.

    The l-zeros row contained |L| and rendered as a broken table.
    """

    broken = [
        line
        for line in API_REFERENCE.splitlines()
        if line.startswith("| `") and len(re.findall(r"(?<!\\)\|", line)) != 4
    ]
    assert not broken, f"table rows with unescaped pipes: {broken}"


def test_api_reference_uses_the_names_the_interface_shows():
    """A reader moving between the app and the reference must see one vocabulary."""

    for name in ("Pell", "Carmichael", "Goldbach", "Chebotarev", "Pocklington"):
        assert name in API_REFERENCE, f"the API reference never mentions {name}"


def _form_headings() -> dict[str, str]:
    """Each tool's <h2>, which is exactly what the navigation button displays."""

    pairs = re.findall(
        r'<form id="([a-z0-9-]+-form)"[^>]*>.*?<h2>(.*?)</h2>', INDEX, re.S
    )
    return {form: re.sub(r"\s+", " ", heading).strip() for form, heading in pairs}


def test_navigation_labels_are_unique():
    """Two tools sharing a label are indistinguishable in the sidebar and the picker.

    The two prime-race tools, one animated and one analytic, both read "Race the
    reduced residue classes" until they were given distinct names.
    """

    headings = _form_headings()
    duplicates = {h for h in headings.values() if list(headings.values()).count(h) > 1}
    assert not duplicates, f"navigation labels shared by more than one tool: {duplicates}"


def test_navigation_labels_carry_the_recognised_name():
    """A tool must be findable by the name it is known by, not only by what it does.

    The navigation button shows the <h2>, so a heading that describes the operation
    without naming the subject hides the tool from anyone scanning for it. "Solve
    x^2 - dy^2 = 1" gave no hint that it was Pell's equation.
    """

    labels = " | ".join(_form_headings().values())
    for name in (
        "Pell", "Continued fractions", "Miller\u2013Rabin", "Goldbach", "Carmichael",
        "Bateman\u2013Horn", "Hardy\u2013Littlewood", "Chebotarev", "Dirichlet",
        "Dedekind", "Sierpi\u0144ski", "Pocklington", "Proth", "Eisenstein",
        "Chinese remainder", "SQUFOF", "Primorials", "Maier", "Chebyshev",
    ):
        assert name in labels, f"no navigation label mentions {name}"


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
    assert '/assets/styles.css?v=20260907-named-tools' in INDEX
    assert '/assets/app.js?v=20260907-named-tools' in INDEX
    assert '/assets/favicon.svg?v=20260907-named-tools' in INDEX
    assert '--app-dir "$project_dir"' in RUNNER
    assert '?ui=20260907-named-tools#primes/prime-check' in RUNNER
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


def test_apex_redirect_keeps_the_documentation_host_canonical():
    redirect = (ROOT / "hosting" / "apex" / ".htaccess").read_text(encoding="utf-8")
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "https://docs.numerisect.com%{REQUEST_URI}" in redirect
    assert "[R=301,L,NE]" in redirect
    assert "site_url: https://docs.numerisect.com/" in config


def test_the_documentation_site_carries_no_analytics():
    """Numerisect is offline-first; its documentation does not track readers."""

    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    for tracker in ("google_analytics", "gtag", "analytics:", "googletagmanager"):
        assert tracker not in config, f"the documentation site must not carry {tracker}"
