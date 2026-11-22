# PLAN — browser form audit

| # | Task | Files | Verify | Status |
|---|---|---|---|---|
| 1 | Fixture site: clean form (native POST), fetch() form, redirect that strips gclid, form with a broken hidden input | `tests/browser_site/*.html`, `tests/browser_site/server.py` | serve + curl each page | done |
| 2 | Acceptance tests A1–A6, A8 (skip if Playwright or Chrome missing) | `tests/test_browser_audit.py` | tests fail before impl | done |
| 3 | Extract shared HubSpot poll + compare from `audit_lead` | `leadtrace/audit.py` | existing 9 tests pass (A7) | done |
| 4 | Browser driver: landing URL, fill, capture POST, parse body | `leadtrace/browser.py` | A1–A3, A5 | done |
| 5 | `audit_browser` wiring + report checks | `leadtrace/audit.py` | A1–A5 | done |
| 6 | CLI flags `--mode browser`, `--selector`, `--form-field`, `--submit`, `--browser-path`; exit 2 on missing extra | `leadtrace/cli.py` | A6, `leadtrace audit -h` | done |
| 7 | Optional extra + version 0.2.0 | `pyproject.toml`, `leadtrace/__init__.py` | `pip install '.[browser]'` | done |
| 8 | CI job that installs Chrome + Playwright and runs browser tests | `.github/workflows/ci.yml` | YAML parses; core matrix unchanged | done |
| 9 | README section, FOCO brand gate | `README.md` | ship gate 1–6 | done |
| 10 | Independent review by a different model | — | findings addressed | in review |
