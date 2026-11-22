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
