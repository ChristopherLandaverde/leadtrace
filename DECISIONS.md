# DECISIONS — browser form audit

Decided without approval. Each one is reversible on this branch.

- **Target: browser form audit.** No target was given, and the answer to the options was "no preference". This was the recommended option and the gap the README already admitted to.
- **Playwright as an optional extra (`leadtrace[browser]`), imported lazily.** The core package keeps zero runtime dependencies. *Yellow: a dependency outside the stdlib-only stack.*
- **Stacked on `brand/foco-pass` (PR #1), not `main`.** Both change README.md. Stacking avoids a merge conflict. Merge #1 first.
- **`original_conversion_id` compared with the value the form submitted.** The page creates that ID, so LeadTrace cannot know it in advance. If the form submits none, the check fails.
- **The HubSpot wait window starts after the form POST, not before navigation.** Browser steps can take up to 30 s, and that time should not come out of the search window. The SLA latency still runs from before navigation.
- **The audit keeps going to HubSpot when `form_capture` has mismatches.** It stops only when no POST was captured. Seeing what the CRM holds is useful evidence even when the form is broken.
- **New CI job `browser` (Playwright + Chromium).** The existing 3.9–3.12 matrix is unchanged, and there the browser tests skip. *Yellow: CI config change. It adds coverage and suppresses nothing.*
- **Fixed 30 s browser step timeout, no flag.** Boring default. Add a flag if a real page needs one.
- **Built inline instead of one subagent per task.** About 600 lines across 10 small tasks. Handing each task to a cold subagent would have cost more than it saved. Review still went to a different model.
- **Version bumped to 0.2.0.** New mode, no breaking changes.

## After independent review (Sonnet, 0 blockers, 5 should-fix, 5 nits)

- **#1 Form POST identified by the synthetic email in its body**, not as "first POST". Beacons go into `other_posts`. Test: A9.
- **#2 `submit_url` reported, not enforced.** Many real forms post to a third party (HubSpot Forms API, Zapier), so a same-domain rule would produce false failures. The URL is in the report for a human to judge.
- **#3 URL read at submit time, after `networkidle` (max 5 s).** Test: A10.
- **#4 Requests to literal private, link-local, reserved, or multicast IPs blocked.** Hostnames are not resolved, which keeps it boring and still covers the metadata endpoint. Blocked URLs are reported.
- **#5 Form response awaited through events with a bounded poll.** There is no blocking `request.response()` call.
- **#6 `text/plain` parsed as JSON first. #7 Empty canonical name no longer masks a filled alias. #8 Install hint only on a missing import, launch failure gets its own hint. #9 Tests added for flags, encodings, and the missing email field. #10 `--no-sandbox` only when running as root.**
- **Re-check: redirects bypassed the IP guard.** Every navigation hop is now checked. A blocked hop stops the run before the form is touched (test: `test_redirect_to_private_ip_stops`). Limit, also in the README: Playwright cannot intercept redirect hops, so the hop itself is still sent once.
- **Reviewer nit kept as a known limit:** a third-party beacon that carries the synthetic email *and* all 5 tracking values would be taken as the form. `submit_url` and `other_posts` are in the report so this is visible.

## Brand pass 2: trace output, DESIGN.md, social preview (2026-11-22)

- **`audit --format auto` is the default:** a trace record on a TTY, JSON when piped. Scripts and CI that parse the JSON keep working, and people at a terminal get the record. `--format json|trace` forces one.
- **`verify` now reports unknown latency as unknown.** It used to report `0.0`, which showed as a false `✓`. `ParityResult.latency_minutes` is `None` when a timestamp is missing, so the MCP tool returns `null` there too.
- **Token values not given by the brand skill were chosen and need checking against the focosys.io DESIGN.md:** `paper #f7f7f5`, `ink-muted #5b636a`, `rule #d9dcdf`, `status-broken #b42318`, `status-verified #1a7f37`.
- **Plex Mono lacks `□`, and its `✓` reads as `V` at display size.** Inter is used for those two glyphs in the preview image.
- **ASCII fallback for terminals that cannot encode the glyphs** (Windows cp1252): `□ -` `↓ v` `× x` `✓ +`.
- **The README example is real output** from the local test site, not hand-written.
