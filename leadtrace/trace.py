"""Render LeadTrace results as a FOCO trace record for the terminal.

Glyphs are the only iconography. Color appears only as status (red for ×,
green for ✓), only on a TTY, and never when NO_COLOR is set.
"""

import os
import sys
from datetime import datetime, timezone

ASCII = {"□": "-", "↓": "v", "×": "x", "✓": "+", "→": "->", "…": "...", "·": "-"}
RED, GREEN, RESET = "\033[31m", "\033[32m", "\033[0m"
LABEL = 13  # width of "□ OBSERVED   "
NAME = 24


def _color(stream):
    return stream.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def _safe(text, stream):
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
        return text
    except (UnicodeEncodeError, LookupError):
        for glyph, plain in ASCII.items():
            text = text.replace(glyph, plain)
        return text.encode(encoding, errors="replace").decode(encoding)


def _short(value, width=48):
    text = "(missing)" if value is None else ('""' if value == "" else str(value))
    return text if len(text) <= width else text[: width - 1] + "…"


def status(passed, stream=None):
    stream = stream or sys.stdout
    glyph = "✓" if passed else "×"
    if _color(stream):
        return f"{GREEN if passed else RED}{glyph}{RESET}"
    return glyph


def _detail(name, check):
    if "reason" in check:
        return check["reason"]
    if name == "landing":
        if check.get("missing"):
            return "dropped on the way: " + ", ".join(check["missing"])
        return "5/5 tracking params on the URL at submit"
    if name == "form_capture":
        bits = [f"POST {_short(check.get('submit_url'), 40)} · HTTP {check.get('http_status')}"]
        for field, diff in (check.get("mismatched") or {}).items():
            bits.append(f"{field}: expected {_short(diff['expected'], 24)}, got {_short(diff['actual'], 24)}")
        if check.get("other_posts"):
            bits.append(f"{len(check['other_posts'])} other POST(s) ignored")
        return " · ".join(bits)
    if name == "sync_latency":
        minutes = check.get("minutes")
        shown = "unknown" if minutes is None else f"{minutes:.1f} min"
        return f"{shown} (SLA {check.get('sla_minutes'):g} min)"
    if name == "injection":
        return f"HTTP {check.get('http_status')}"
    if name == "capi_handshake":
        return "event_id and hashed em/ph match" if check["passed"] else "event_id or hashed em/ph differ"
    if name == "destination_lookup":
        return f"HTTP {check['http_status']}" if "http_status" in check else "one contact, exact email"
    if "expected" in check:
        if check["passed"]:
            return _short(check["actual"])
        return f"expected {_short(check['expected'], 30)}, got {_short(check['actual'], 30)}"
    return ""


def header(title, meta, stream=None):
    stream = stream or sys.stdout
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(_safe(f"LEADTRACE / {title}", stream), file=stream)
    print(_safe(f"{meta} · {stamp} · synthetic lead, test data only", stream), file=stream)
    print(file=stream)


def row(label, text, stream=None):
    stream = stream or sys.stdout
    print(_safe(f"{label:<{LABEL}}{text}", stream), file=stream)


def verdict(passed, text, stream=None):
    stream = stream or sys.stdout
    print(file=stream)
    label = "VERIFIED" if passed else "BROKEN"
    print(_safe(f"{status(passed, stream)} {label:<{LABEL - 2}}{text}", stream), file=stream)


def render_audit(report, mode, stream=None):
    stream = stream or sys.stdout
    path = {
        "webhook": "POST to endpoint → HubSpot contact search",
        "sgtm": "POST to endpoint → CAPI receipt → HubSpot contact search",
        "browser": "landing page → form POST → HubSpot contact search",
    }[mode]
    header("AUDIT", f"{mode} mode", stream)
    row("□ OBSERVED", f"lead {_short(report['token'], 40)}", stream)
    row("", report["email"], stream)
    row("↓ TRACED", path, stream)
    print(file=stream)
    checks = report["checks"]
    for name, check in checks.items():
        line = f"{status(check['passed'], stream)} {name:<{NAME}}{_detail(name, check)}"
        print(_safe(line, stream), file=stream)
    failed = sum(not check["passed"] for check in checks.values())
    if report["passed"]:
        verdict(True, f"{len(checks)} of {len(checks)} checks passed", stream)
    else:
        verdict(False, f"{failed} of {len(checks)} checks failed", stream)
