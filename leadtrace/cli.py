import argparse
import json
import os
from .audit import audit_lead
import sys
from pathlib import Path
from .generator import generate_synthetic_lead
from .client import inject_lead
from .verifier import verify_lead_parity
from .mcp import run_mcp_server

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
    audit_p.add_argument("--mode", choices=["webhook", "sgtm"], default="webhook")
    audit_p.add_argument("--property", action="append", default=[], metavar="FIELD=INTERNAL_NAME")
    audit_p.add_argument("--max-latency", type=float, default=120)
    audit_p.add_argument("--wait-seconds", type=float, default=120)
    audit_p.add_argument("--poll-seconds", type=float, default=5)

    sub.add_parser("mcp", help="Run MCP stdio server for Claude/Cursor agents")

    args = parser.parse_args()

    if args.command == "generate":
        lead = generate_synthetic_lead(source=args.source, medium=args.medium, campaign=args.campaign, prefix=args.prefix)
        payload = lead.to_form_payload() if args.format == "form" else (lead.to_capi_payload() if args.format == "capi" else lead.to_dict())
        out_str = json.dumps(payload, indent=2)
        if args.out:
            Path(args.out).write_text(out_str, encoding="utf-8")
            print(f"✓ Synthetic lead written to {args.out}")
        else:
            print(out_str)
        sys.exit(0)

    elif args.command == "inject":
        lead = generate_synthetic_lead(source=args.source, medium=args.medium, campaign=args.campaign)
        payload = lead.to_capi_payload() if args.format == "capi" else (lead.to_form_payload() if args.format == "form" else lead.to_dict())
        print("=" * 60)
        print("LEADTRACE / INJECT")
        print(f"Target: {args.url} (dry_run={args.dry_run})")
        print(f"Token:  {lead.token}")
        print("=" * 60)
        res = inject_lead(url=args.url, payload=payload, dry_run=args.dry_run)
        print(f"{'✓' if res.success else '×'} HTTP {res.status_code}")
        sys.exit(0 if res.success else 1)

    elif args.command == "verify":
        expected = json.loads(Path(args.expected).read_text(encoding="utf-8"))
        actual = json.loads(Path(args.actual).read_text(encoding="utf-8"))
        res = verify_lead_parity(expected, actual, max_latency_minutes=args.max_latency)
        print("=" * 60)
        print("LEADTRACE / VERIFY")
        print(f"Sync latency: {res.latency_minutes:.1f} min (SLA: {args.max_latency} min)")
        print("=" * 60)
        if res.passed:
            print("✓ VERIFIED: every first-touch value and click ID matches the original lead.")
            sys.exit(0)
        else:
            print(f"× BROKEN: {len(res.errors)} error(s), {len(res.warnings)} warning(s)")
            for err in res.errors:
                print(f"  × {err.field}: {err.description}")
            sys.exit(1)

    elif args.command == "audit":
        try:
            properties = dict(item.split("=", 1) for item in args.property)
            report = audit_lead(
                args.url, os.environ.get("HUBSPOT_ACCESS_TOKEN"), mode=args.mode,
                properties=properties, max_latency_minutes=args.max_latency,
                wait_seconds=args.wait_seconds, poll_seconds=args.poll_seconds,
            )
        except ValueError as exc:
            audit_p.error(str(exc))
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["passed"] else 1)

    elif args.command == "mcp":
        run_mcp_server()

if __name__ == "__main__":
    main()
