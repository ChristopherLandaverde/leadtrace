"""Run a single synthetic lead through ingestion and HubSpot reconciliation."""

import json
import math
import time
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from .client import inject_lead
from .generator import generate_synthetic_lead
from . import browser

HUBSPOT_SEARCH = "https://api.hubapi.com/crm/v3/objects/contacts/search"
FIELDS = (
    "ft_source", "ft_medium", "ft_campaign", "original_conversion_id",
    "gclid", "fbclid",
)


def _validate(url, access_token, mode, properties, numbers):
    endpoint = urlsplit(url)
    if not endpoint.hostname or endpoint.username is not None or not (
        endpoint.scheme == "https"
        or (endpoint.scheme == "http" and endpoint.hostname in {"localhost", "127.0.0.1", "::1"})
    ):
        raise ValueError("Use an HTTPS URL or a loopback HTTP test endpoint.")
    for value, label in numbers:
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{label} must be positive and finite.")
    if not access_token:
        raise ValueError("Set HUBSPOT_ACCESS_TOKEN to a contact-read token.")
    if mode not in {"webhook", "sgtm", "browser"}:
        raise ValueError("Mode must be webhook, sgtm, or browser.")
    if set(properties) - set(FIELDS):
        raise ValueError("Property mappings must use canonical attribution field names.")
    mapping = {field: properties.get(field, field) for field in FIELDS}
    names = ["email", "createdate", *mapping.values()]
    if len(set(names)) != len(names) or not all(name.isidentifier() for name in names):
        raise ValueError("Use distinct HubSpot internal property names.")
    return mapping, names


def _lookup(checks, email, names, access_token, deadline, poll_seconds):
    """Poll HubSpot search by exact email. Return the record, or None after recording a failure."""
    query = {
        "filterGroups": [{"filters": [
            {"propertyName": "email", "operator": "EQ", "value": email}
        ]}],
        "properties": names,
        "limit": 2,
    }
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            checks["destination_lookup"] = {"passed": False, "reason": "Contact lookup timed out."}
            return None
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
                        return None
                    record = results[0]["properties"]
                    if not isinstance(record, dict):
                        raise ValueError("Expected a properties object.")
                    checks["destination_lookup"] = {"passed": record.get("email") == email}
                    return record
            except (KeyError, TypeError, ValueError):
                checks["destination_lookup"] = {"passed": False, "reason": "Invalid HubSpot response."}
                return None
        elif search.status_code not in {0, 429, 500, 502, 503, 504}:
            checks["destination_lookup"] = {"passed": False, "http_status": search.status_code}
            return None
        time.sleep(max(0, min(poll_seconds, deadline - time.monotonic())))


def _compare(checks, record, mapping, expected, sent_at, max_latency_minutes):
    for field, property_name in mapping.items():
        if field in checks:
            continue
        actual = record.get(property_name)
        checks[field] = {"passed": actual == expected[field], "expected": expected[field], "actual": actual}
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


def _finish(report):
    report["passed"] = all(check["passed"] for check in report["checks"].values())
    return report


def audit_lead(
    url, access_token, *, mode="webhook", properties=None,
    max_latency_minutes=120, wait_seconds=120, poll_seconds=5,
    selectors=None, form_fields=None, submit="[type=submit]", browser_path=None,
):
    """Dispatch once and poll CRM visibility within a bounded time window.

    ``mode="browser"`` opens ``url`` as a landing page in headless Chromium,
    submits the real form, and needs the ``leadtrace[browser]`` extra.
    """
    mapping, names = _validate(url, access_token, mode, properties or {}, (
        (max_latency_minutes, "SLA"), (wait_seconds, "wait"), (poll_seconds, "poll interval"),
    ))
    if mode == "browser":
        return _audit_browser(
            url, access_token, mapping, names, max_latency_minutes, wait_seconds, poll_seconds,
            selectors or {}, form_fields or {}, submit, browser_path,
        )

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

    record = _lookup(checks, lead.email, names, access_token, deadline, poll_seconds)
    if record is None:
        return report
    _compare(checks, record, mapping, payload, sent_at, max_latency_minutes)
    return _finish(report)


def _audit_browser(
    url, access_token, mapping, names, max_latency_minutes, wait_seconds, poll_seconds,
    selectors, form_fields, submit, browser_path,
):
    form_keys = set(browser.URL_PARAMS) | {"original_conversion_id"}
    if set(selectors) - set(browser.VISIBLE_FIELDS):
        raise ValueError(f"Selectors must name one of: {', '.join(browser.VISIBLE_FIELDS)}.")
    if set(form_fields) - form_keys:
        raise ValueError(f"Form fields must name one of: {', '.join(sorted(form_keys))}.")

    lead = generate_synthetic_lead(campaign="audit_test")
    payload = lead.to_form_payload()
    report = {"token": lead.token, "email": lead.email, "passed": False, "checks": {}}
    checks = report["checks"]
    sent_at = time.time()
    result = browser.submit_form(
        browser.landing_url(url, payload), payload,
        selectors=selectors, submit=submit, browser_path=browser_path,
    )
    deadline = time.monotonic() + wait_seconds

    final_url = result["final_url"]
    if final_url is None:
        checks["landing"] = {"passed": False, "reason": result.get("error", "Page did not load.")}
        return report
    arrived = parse_qs(urlsplit(final_url).query, keep_blank_values=True)
    missing = [
        param for field, param in browser.URL_PARAMS.items()
        if arrived.get(param, [None])[0] != payload[field]
    ]
    checks["landing"] = {"passed": not missing, "final_url": final_url, "missing": missing}

    if "submitted" not in result or result.get("error"):
        checks["form_capture"] = {"passed": False, "reason": result.get("error", "No form POST captured.")}
        return report
    submitted = result["submitted"]

    def submitted_value(field):
        candidates = [form_fields[field]] if field in form_fields else [field, browser.URL_PARAMS.get(field)]
        return next((submitted[name] for name in candidates if name and name in submitted), None)

    mismatched = {}
    for field in browser.URL_PARAMS:
        actual = submitted_value(field)
        if actual != payload[field]:
            mismatched[field] = {"expected": payload[field], "actual": actual}
    status = result.get("submit_status")
    checks["form_capture"] = {
        "passed": not mismatched and submitted.get("email") == lead.email
        and status is not None and status < 400,
        "submit_url": result.get("submit_url"),
        "http_status": status,
        "mismatched": mismatched,
    }

    expected = dict(payload)
    conversion_id = submitted_value("original_conversion_id")
    if conversion_id:
        expected["original_conversion_id"] = conversion_id
    else:
        checks["original_conversion_id"] = {
            "passed": False, "reason": "The form submitted no original_conversion_id.",
        }

    record = _lookup(checks, lead.email, names, access_token, deadline, poll_seconds)
    if record is None:
        return report
    _compare(checks, record, mapping, expected, sent_at, max_latency_minutes)
    return _finish(report)
