# Changelog

`Changelog · Nov 2026 · what changed, by version`

## 0.2.0 · 2026-11-22

- `audit --mode browser` runs the landing page and the real form in headless Chromium. The new checks are `landing` (URL params kept at submit) and `form_capture` (the form POST carries every tracking value). Install with `pip install 'leadtrace[browser]'`.
- Every command prints a trace record on a terminal. `audit --format auto|json|trace` keeps JSON when output is piped.
- `verify` reports unknown sync latency as unknown instead of `0.0`. In that case `ParityResult.latency_minutes` and the MCP `verify_crm_parity` result are `null`.
- CI runs on Python 3.9–3.12 (`ubuntu-24.04`), plus a browser job.

## 0.1.0

- `audit` in webhook and sGTM modes, plus the offline `generate`, `inject`, `verify` and `mcp` commands.
