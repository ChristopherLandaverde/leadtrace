"""Run a single synthetic lead through ingestion and HubSpot reconciliation."""

import json
import math
import time
from datetime import datetime
from urllib.parse import urlsplit

from .client import inject_lead
from .generator import generate_synthetic_lead

HUBSPOT_SEARCH = "https://api.hubapi.com/crm/v3/objects/contacts/search"
FIELDS = (
    "ft_source", "ft_medium", "ft_campaign", "original_conversion_id",
    "gclid", "fbclid",
)


def audit_lead(
    url, access_token, *, mode="webhook", properties=None,
    max_latency_minutes=120, wait_seconds=120, poll_seconds=5,
):
    """Dispatch once and poll CRM visibility within a bounded time window."""
    endpoint = urlsplit(url)
    if not endpoint.hostname or endpoint.username is not None or not (
        endpoint.scheme == "https"
        or (endpoint.scheme == "http" and endpoint.hostname in {"localhost", "127.0.0.1", "::1"})
    ):
        raise ValueError("Use an HTTPS webhook or a loopback HTTP test endpoint.")
    for value, label in (
        (max_latency_minutes, "SLA"), (wait_seconds, "wait"), (poll_seconds, "poll interval"),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{label} must be positive and finite.")
    if not access_token:
        raise ValueError("Set HUBSPOT_ACCESS_TOKEN to a contact-read token.")
    if mode not in {"webhook", "sgtm"}:
        raise ValueError("Mode must be webhook or sgtm.")

    properties = properties or {}
    if set(properties) - set(FIELDS):
        raise ValueError("Property mappings must use canonical attribution field names.")
    mapping = {field: properties.get(field, field) for field in FIELDS}
    names = ["email", "createdate", *mapping.values()]
    if len(set(names)) != len(names) or not all(name.isidentifier() for name in names):
        raise ValueError("Use distinct HubSpot internal property names.")

    lead = generate_synthetic_lead(campaign="audit_test")
    payload = lead.to_form_payload()
    capi = lead.to_capi_payload()
    sent_at = time.time()
    deadline = time.monotonic() + wait_seconds
    receipt = inject_lead(url, payload, follow_redirects=False)
    report = {"token": lead.token, "email": lead.email, "passed": False, "checks": {}}
    checks = report["checks"]
    checks["injection"] = {"passed": receipt.status_code in (200, 201), "http_status": receipt.status_code}
    if not checks["injection"]["passed"]:
        return report

    if mode == "sgtm":
        try:
            event = json.loads(receipt.response_body)["capi_event"]
        except (ValueError, KeyError, TypeError):
            event = {}
        event = event if isinstance(event, dict) else {}
        user_data = event.get("user_data")
        user_data = user_data if isinstance(user_data, dict) else {}
        checks["capi_handshake"] = {
            "passed": (
                event.get("event_id") == capi["event_id"]
                and user_data.get("em") == capi["user_data"]["em"]
                and user_data.get("ph") == capi["user_data"]["ph"]
            )
        }

    query = {
        "filterGroups": [{"filters": [
            {"propertyName": "email", "operator": "EQ", "value": lead.email}
        ]}],
        "properties": names,
        "limit": 2,
    }
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            checks["destination_lookup"] = {"passed": False, "reason": "Contact lookup timed out."}
            return report
        search = inject_lead(
            HUBSPOT_SEARCH, query, headers={"Authorization": f"Bearer {access_token}"},
            timeout=min(10, remaining), follow_redirects=False,
        )
        if search.status_code == 200:
            try:
                results = json.loads(search.response_body)["results"]
                if not isinstance(results, list):
                    raise ValueError("Expected a results list.")
                if results:
                    if len(results) != 1:
                        checks["destination_lookup"] = {"passed": False, "reason": "Multiple contacts matched."}
                        return report
                    record = results[0]["properties"]
                    if not isinstance(record, dict):
                        raise ValueError("Expected a properties object.")
                    break
            except (KeyError, TypeError, ValueError):
                checks["destination_lookup"] = {"passed": False, "reason": "Invalid HubSpot response."}
                return report
        elif search.status_code not in {0, 429, 500, 502, 503, 504}:
            checks["destination_lookup"] = {"passed": False, "http_status": search.status_code}
            return report
        time.sleep(max(0, min(poll_seconds, deadline - time.monotonic())))

    checks["destination_lookup"] = {"passed": record.get("email") == lead.email}
    for field, property_name in mapping.items():
        actual = record.get(property_name)
        checks[field] = {"passed": actual == payload[field], "expected": payload[field], "actual": actual}
    latency = None
    try:
        created = datetime.fromisoformat(record["createdate"].replace("Z", "+00:00"))
        if created.utcoffset() is not None:
            latency = (created.timestamp() - sent_at) / 60
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        pass
    checks["sync_latency"] = {
        "passed": latency is not None and 0 <= latency <= max_latency_minutes,
        "minutes": latency,
        "sla_minutes": max_latency_minutes,
    }
    report["passed"] = all(check["passed"] for check in checks.values())
    return report
