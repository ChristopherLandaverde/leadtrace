# DESIGN — LeadTrace

`Design tokens · Nov 2026 · FOCO brand applied to a CLI and its repo assets`

Every visual surface for LeadTrace takes its values from this file: terminal
output, the social preview, and any future docs page. Nothing is hard-coded
anywhere else.

## Type

| Role | Family | Weight | Used for |
|---|---|---|---|
| narrative | Inter | 400 / 500 | headings, explanatory sentences |
| evidence | IBM Plex Mono | 400 / 500 | labels, metadata, statuses, numbers, field names |

The sans/mono split is the signature. Inter is a declared choice, not a
default; keep it whitelisted in design-lint configs. Where Plex Mono lacks a
glyph (`□`) or draws it poorly (`✓` at display sizes), fall back to Inter for that glyph only.

## Color

| Token | Value | Use |
|---|---|---|
| `ink` | `#1e2327` | all text and rules (light mode) |
| `paper` | `#f7f7f5` | background (light mode) |
| `ink-muted` | `#5b636a` | metadata lines |
| `rule` | `#d9dcdf` | thin rules, 1 px |
| `status-broken` | `#b42318` | `×` only |
| `status-verified` | `#1a7f37` | `✓` only |

Dark mode inverts `ink` and `paper`. Color appears only as status, never as
decoration. In the terminal, status color is ANSI red/green, only on a TTY,
and never when `NO_COLOR` is set.

## Glyphs

`□ OBSERVED` · `↓ TRACED` · `× BROKEN` · `+ REPAIRED` · `✓ VERIFIED`, plus
`→` for direction and `↗` for outbound links. These are the only
iconography: no emoji, no icon libraries, no illustration. LeadTrace reports
and never repairs, so `+ REPAIRED` is unused here.

On terminals that cannot encode them, the glyphs fall back to ASCII:
`□ -` `↓ v` `× x` `✓ +` `→ ->`.

## Layout

Documentation style: small mono label, large heading, numbered steps, thin
rules, generous whitespace.

Terminal records follow one shape:

```
LEADTRACE / <COMMAND>
<scope> · <UTC timestamp> · synthetic lead, test data only

□ OBSERVED   <what was sent>
↓ TRACED     <the path followed>

✓ <check>    <evidence>
× <check>    expected <value>, got <value>

× BROKEN     <n> of <n> checks failed
```

## Banned

Gradients, glows, purple accents, emoji, large rounded icons above headings,
decorative shadows, and shadcn's default theme.
