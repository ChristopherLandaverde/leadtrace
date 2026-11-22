import argparse
import json
import os
from .audit import audit_lead
from .browser import BrowserUnavailable
import sys
from pathlib import Path
from .generator import generate_synthetic_lead
from .client import inject_lead
from .verifier import verify_lead_parity
from .mcp import run_mcp_server
from . import trace

def main():
    parser = argparse.ArgumentParser(prog="leadtrace", description="LeadTrace: send a synthetic lead and verify the CRM kept its original attribution.")
    sub = parser.add_subparsers(dest="command", required=True)

    gen_p = sub.add_parser("generate", help="Generate a tokenized synthetic lead")
    gen_p.add_argument("--source", default="google_ads")
    gen_p.add_argument("--medium", default="cpc")
    gen_p.add_argument("--campaign", default="q4_synthetic_audit")
    gen_p.add_argument("--prefix", default="foco_test")
    gen_p.add_argument("--format", choices=["dict", "form", "capi"], default="dict")
    gen_p.add_argument("--out")

    inj_p = sub.add_parser("inject", help="Inject synthetic lead to endpoint")
    inj_p.add_argument("url")
    inj_p.add_argument("--source", default="google_ads")
    inj_p.add_argument("--medium", default="cpc")
    inj_p.add_argument("--campaign", default="q4_synthetic_audit")
    inj_p.add_argument("--format", choices=["form", "capi", "raw"], default="form")
    inj_p.add_argument("--dry-run", action="store_true")

    ver_p = sub.add_parser("verify", help="Reconcile expected lead against CRM record")
    ver_p.add_argument("--expected", required=True)
    ver_p.add_argument("--actual", required=True)
    ver_p.add_argument("--max-latency", type=float, default=120.0)

    audit_p = sub.add_parser("audit", help="Inject a synthetic lead and reconcile HubSpot")
    audit_p.add_argument("url")
    audit_p.add_argument("--mode", choices=["webhook", "sgtm", "browser"], default="webhook",
                         help="browser: open URL as a landing page and submit its real form")
    audit_p.add_argument("--property", action="append", default=[], metavar="FIELD=INTERNAL_NAME")
    audit_p.add_argument("--max-latency", type=float, default=120)
    audit_p.add_argument("--wait-seconds", type=float, default=120)
    audit_p.add_argument("--poll-seconds", type=float, default=5)
    audit_p.add_argument("--selector", action="append", default=[], metavar="FIELD=CSS",
                         help="browser mode: CSS selector for email, firstname, lastname, phone, or company")
    audit_p.add_argument("--form-field", action="append", default=[], metavar="FIELD=NAME",
                         help="browser mode: name the form submits a tracking field under")
    audit_p.add_argument("--submit", default="[type=submit]", metavar="CSS",
                         help="browser mode: submit control selector")
    audit_p.add_argument("--format", choices=["auto", "json", "trace"], default="auto",
                         help="auto: trace record on a terminal, JSON when piped (default)")
    audit_p.add_argument("--browser-path", default=os.environ.get("LEADTRACE_BROWSER"),
                         help="browser mode: Chrome/Chromium binary (default: $LEADTRACE_BROWSER or Playwright's)")

    sub.add_parser("mcp", help="Run MCP stdio server for Claude/Cursor agents")

    args = parser.parse_args()

    if args.command == "generate":
        lead = generate_synthetic_lead(source=args.source, medium=args.medium, campaign=args.campaign, prefix=args.prefix)
        payload = lead.to_form_payload() if args.format == "form" else (lead.to_capi_payload() if args.format == "capi" else lead.to_dict())
        out_str = json.dumps(payload, indent=2)
        if args.out:
            Path(args.out).write_text(out_str, encoding="utf-8")
            print(trace._safe(f"✓ Synthetic lead written to {args.out}", sys.stdout))
        else:
            print(out_str)
        sys.exit(0)

    elif args.command == "inject":
        lead = generate_synthetic_lead(source=args.source, medium=args.medium, campaign=args.campaign)
        payload = lead.to_capi_payload() if args.format == "capi" else (lead.to_form_payload() if args.format == "form" else lead.to_dict())
        trace.header("INJECT", f"{args.format} payload" + (" · dry run" if args.dry_run else ""))
        trace.row("□ OBSERVED", f"lead {lead.token}")
        trace.row("↓ TRACED", f"POST → {args.url}")
        res = inject_lead(url=args.url, payload=payload, dry_run=args.dry_run)
        detail = f"HTTP {res.status_code}" + (f" · {res.error_message}" if res.error_message else "")
        if res.is_dry_run:
            trace.verdict(True, "dry run · nothing sent")
        else:
            trace.verdict(res.success, ("endpoint accepted the lead · " if res.success
                                        else "endpoint rejected the lead · ") + detail)
        sys.exit(0 if res.success else 1)

    elif args.command == "verify":
        expected = json.loads(Path(args.expected).read_text(encoding="utf-8"))
        actual = json.loads(Path(args.actual).read_text(encoding="utf-8"))
        res = verify_lead_parity(expected, actual, max_latency_minutes=args.max_latency)
        trace.header("VERIFY", "offline fixture comparison")
        trace.row("□ OBSERVED", f"expected {args.expected}")
        trace.row("↓ TRACED", f"actual   {args.actual}")
        print()
        latency = res.latency_minutes
        if latency is None:
            mark, shown = "□", "unknown · no timestamp in one of the records"
        else:
            mark, shown = trace.status(latency <= args.max_latency), f"{latency:.1f} min"
        print(trace._safe(f"{mark} {'sync_latency':<{trace.NAME}}{shown} (SLA {args.max_latency:g} min)", sys.stdout))
        for issue in res.errors:
            if issue.field == "sync_latency":
                continue  # already shown above
            print(trace._safe(f"{trace.status(False)} {issue.field:<{trace.NAME}}{issue.description}", sys.stdout))
        for issue in res.warnings:
            print(trace._safe(f"□ {issue.field:<{trace.NAME}}warning · {issue.description}", sys.stdout))
        if res.passed and not res.warnings:
            print(trace._safe(f"{trace.status(True)} {'first_touch_fields':<{trace.NAME}}every value and click ID matches",
                              sys.stdout))
        trace.verdict(res.passed, "first-touch values and click IDs match" if res.passed
                      else f"{len(res.errors)} error(s), {len(res.warnings)} warning(s)")
        sys.exit(0 if res.passed else 1)

    elif args.command == "audit":
        try:
            pairs = {}
            for flag in ("property", "selector", "form_field"):
                items = getattr(args, flag)
                if any("=" not in item for item in items):
                    raise ValueError(f"--{flag.replace('_', '-')} takes KEY=VALUE.")
                pairs[flag] = dict(item.split("=", 1) for item in items)
            report = audit_lead(
                args.url, os.environ.get("HUBSPOT_ACCESS_TOKEN"), mode=args.mode,
                properties=pairs["property"], max_latency_minutes=args.max_latency,
                wait_seconds=args.wait_seconds, poll_seconds=args.poll_seconds,
                selectors=pairs["selector"], form_fields=pairs["form_field"],
                submit=args.submit, browser_path=args.browser_path,
            )
        except ValueError as exc:
            audit_p.error(str(exc))
        except BrowserUnavailable as exc:
            print(f"× {exc}", file=sys.stderr)
            sys.exit(2)
        use_trace = args.format == "trace" or (args.format == "auto" and sys.stdout.isatty())
        if use_trace:
            try:
                trace.render_audit(report, args.mode)
            except Exception:  # never lose a finished audit to a rendering bug
                print(json.dumps(report, indent=2))
        else:
            print(json.dumps(report, indent=2))
        sys.exit(0 if report["passed"] else 1)

    elif args.command == "mcp":
        run_mcp_server()

if __name__ == "__main__":
    main()
