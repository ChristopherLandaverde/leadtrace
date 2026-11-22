# SPEC — browser form audit (`leadtrace audit --mode browser`)

`Build spec · Nov 2026 · LeadTrace v0.2.0 · assumptions and limits`

> **Reading taken.** Christopher started `/foco-build` without naming a target
> and answered "no preference" to the options. This build takes the
> recommended option: the browser-form gap that the README already admits
> to. Nothing in it is irreversible. It ships on a branch as a draft PR.

## Problem

The current `audit` posts JSON straight to the webhook. That skips the
browser. It cannot see a redirect that strips `utm_*` or `gclid`, or a
hidden input that never gets populated. Those are the most common places
where first-touch attribution breaks before the CRM ever sees it. Today
the README tells users to run a separate browser test by hand.

## User and decision

A RevOps or MarTech engineer is about to trust a "paid vs organic" report
built on HubSpot first-touch fields. They want to know one thing: "If a
click from a Google ad lands on this page and fills in this form, does
HubSpot keep the source, medium, campaign, and click IDs?"

## Scope

`leadtrace audit LANDING_URL --mode browser` does the following:

1. Builds a landing URL from the synthetic lead:
   `utm_source`, `utm_medium`, `utm_campaign`, `gclid`, `fbclid`.
2. Opens it in headless Chromium through Playwright, which follows
   redirects. Check `landing`: the final URL must still carry all 5
   params. The check reports `final_url` and any params that are missing.
3. Fills visible fields (`email`, `firstname`, `lastname`, `phone`,
   `company`). The default selector is `[name=<field>]`. Override with
   `--selector FIELD=CSS`. Clicks `--submit` (default
   `[type=submit]`).
4. Captures the first POST request after the click. Check `form_capture`:
   the body must carry each tracking value. It accepts the canonical name
   or the `utm_*` alias, and `--form-field FIELD=NAME` overrides the name.
   It parses urlencoded and JSON bodies. Any other encoding fails with a
   named reason.
5. Polls HubSpot exactly as `webhook` mode does. It compares the 5 URL
   fields to the values the URL carried. It compares
   `original_conversion_id` to the value the form submitted, because the
   page creates that value and LeadTrace does not. If the form submitted
   none, that check fails.
6. Uses the same JSON report, exit codes, SLA, and wait/poll flags as the
   other modes.

Playwright is an optional extra: `pip install 'leadtrace[browser]'`. The
browser binary comes from `--browser-path`, from `LEADTRACE_BROWSER`, or
from Playwright's default. The core package keeps zero runtime
dependencies.

## Out of scope

- Multi-step forms, iframes (including embedded HubSpot forms), CAPTCHAs,
  and consent banners. A consent banner that blocks the form is reported
  as a fill/submit failure, not handled.
- Multipart bodies
- Meta delivery and Salesforce, as before
- Any write to HubSpot by LeadTrace itself. The form under test does the
  write, against the user's test portal.

## Acceptance criteria (runnable)

All tests run against a local `http.server` fixture site with headless
Chrome. HubSpot is mocked and no live credentials are used.

| # | Check | Test |
|---|---|---|
| A1 | A clean form passes every check, exit 0 | `test_browser_audit.BrowserAudit.test_clean_form_passes` |
| A2 | A redirect that drops `gclid` fails `landing` and names `gclid` | `test_redirect_strips_param` |
| A3 | A form whose hidden `utm_campaign` stays empty fails `form_capture` on `ft_campaign` | `test_hidden_input_not_populated` |
| A4 | HubSpot overwriting `ft_source` fails `ft_source` and shows expected and actual values | `test_crm_overwrite_detected` |
| A5 | `original_conversion_id` is compared to the submitted value, not the generated one | `test_conversion_id_from_form` |
| A6 | Without Playwright installed, the CLI exits 2 with an install hint | `test_missing_playwright_message` |
| A7 | Existing webhook and sgtm tests still pass with no changes | `python -m unittest` |
| A8 | Non-HTTPS non-loopback URLs are rejected in browser mode | `test_rejects_plain_http` |

## Assumptions → how each is verified

- The fixture site's JS-populated hidden inputs behave like a real landing
  page script. Verified by A1/A3 running real Chrome, not a DOM stub.
- `page.expect_request` catches both native form posts and `fetch()`
  submits. Verified by a fixture that uses each.
- HubSpot search behaves the same whatever the ingestion path. The
  polling code is shared, not copied, and A7 covers it.

## Decided alone / brought back

Decided alone (logged in DECISIONS.md): flag names, alias table, the
optional-extra packaging, and the CI job layout.
Brought back: merging, releasing to PyPI, and any run against a real
portal.
