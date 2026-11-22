"""Model Context Protocol (MCP) Server for leadtrace."""
import json
import sys
from typing import Dict, Any
from .generator import generate_synthetic_lead
from .client import inject_lead
from .verifier import verify_lead_parity

TOOLS = [
    {
        "name": "generate_synthetic_lead",
        "description": "Generates a deterministic synthetic lead with traceable first-touch UTM tokens, click IDs, and normalized/hashed PII for CAPI/sGTM and CRM testing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "default": "google_ads"},
                "medium": {"type": "string", "default": "cpc"},
                "campaign": {"type": "string", "default": "q4_synthetic_audit"},
                "prefix": {"type": "string", "default": "foco_test"}
            }
        }
    },
    {
        "name": "inject_synthetic_lead",
        "description": "Submits a synthetic lead payload to an HTTP webhook, sGTM container, or form endpoint with dry-run support.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "format": {"type": "string", "enum": ["form", "capi", "raw"], "default": "form"},
                "dry_run": {"type": "boolean", "default": True}
            },
            "required": ["url"]
        }
    },
    {
        "name": "verify_crm_parity",
        "description": "Verifies whether a destination CRM record (HubSpot/Salesforce) preserved first-touch parameters and adheres to sync SLAs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expected_lead": {"type": "object"},
                "destination_record": {"type": "object"},
                "max_latency_minutes": {"type": "number", "default": 120.0}
            },
            "required": ["expected_lead", "destination_record"]
        }
    }
]

def handle_rpc_request(request: Dict[str, Any]) -> Dict[str, Any]:
    method = request.get("method")
    req_id = request.get("id")

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "generate_synthetic_lead":
            lead = generate_synthetic_lead(
                source=args.get("source", "google_ads"),
                medium=args.get("medium", "cpc"),
                campaign=args.get("campaign", "q4_synthetic_audit"),
                prefix=args.get("prefix", "foco_test")
            )
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(lead.to_dict(), indent=2)}]}}

        elif tool_name == "inject_synthetic_lead":
            lead = generate_synthetic_lead()
            fmt = args.get("format", "form")
            payload = lead.to_capi_payload() if fmt == "capi" else (lead.to_form_payload() if fmt == "form" else lead.to_dict())
            res = inject_lead(url=args.get("url", "dry-run"), payload=payload, dry_run=args.get("dry_run", True))
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps({"success": res.success, "status_code": res.status_code, "is_dry_run": res.is_dry_run}, indent=2)}]}}

        elif tool_name == "verify_crm_parity":
            res = verify_lead_parity(args.get("expected_lead", {}), args.get("destination_record", {}), args.get("max_latency_minutes", 120.0))
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps({"passed": res.passed, "latency_minutes": res.latency_minutes, "errors": [d.__dict__ for d in res.errors], "warnings": [d.__dict__ for d in res.warnings]}, indent=2)}]}}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method {tool_name} not found"}}

    return {"jsonrpc": "2.0", "id": req_id, "result": {}}

def run_mcp_server():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_rpc_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}}) + "\n")
            sys.stdout.flush()
