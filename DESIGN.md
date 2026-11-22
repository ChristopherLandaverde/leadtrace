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

Focosys family tokens, the same set as PipeTrace, OSRA and Rabbit:

| Token | Value | Use |
|---|---|---|
| `ink-primary` | `#10231F` | text, rules, logo tile, dark output boxes |
| `surface-paper` | `#F3F0E6` | backgrounds, stage boxes, text on ink |
| `surface-source` | `#EBE8DE` | input/source boxes in diagrams |
| `ink-muted` | `#426B5D` | metadata, mono detail text, section labels |
| `state-verified` | `#D7FF69` | `✓` and verified totals, only on `ink-primary` |

`state-verified` lime is only used on the dark ink, never on paper, because
it has no contrast there. The family has no red token, so `×` is drawn in
ink. In the terminal, status color is ANSI red/green, only on a TTY, and
never when `NO_COLOR` is set.

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
