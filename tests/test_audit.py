import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import Mock, patch

from leadtrace.audit import FIELDS, audit_lead


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.payload = None
        self.searches = []
        self.injections = 0
        self.changes = {}
        self.status = 201
        self.receipt_changes = {}
        self.base = "https://mock.example"

    def respond(self, request, timeout):
        payload = json.loads(request.data)
        if request.full_url == self.base + "/webhook":
            self.assertIsNone(request.get_header("Authorization"))
            self.injections += 1
            self.payload = payload
            self.created = datetime.now(timezone.utc)
            event = {"event_id": payload["original_conversion_id"], "user_data": {
                "em": [hashlib.sha256(payload["email"].encode()).hexdigest()],
                "ph": [hashlib.sha256(payload["phone"].encode()).hexdigest()],
            }}
            event.update(self.receipt_changes)
            body, status = {"capi_event": event}, self.status
        else:
            self.assertEqual(request.full_url, "https://api.hubapi.com/crm/v3/objects/contacts/search")
            self.searches.append((payload, request.get_header("Authorization")))
            fields = {field: self.payload[field] for field in (*FIELDS, "email")}
            fields["createdate"] = self.created.isoformat()
            fields["first_source"] = fields.pop("ft_source")
            fields.update(self.changes)
            results = [] if len(self.searches) == 1 else [{"properties": fields}]
            body, status = {"results": results}, 200
        response = BytesIO(json.dumps(body).encode())
        response.status = status
        return response

    def run_audit(self):
        opener = Mock(open=self.respond)
        with patch("leadtrace.client.urllib.request.build_opener", return_value=opener):
            return audit_lead(
                self.base + "/webhook", "test-token", mode="sgtm", wait_seconds=2,
                poll_seconds=0.01, properties={"ft_source": "first_source"},
            )

    def test_pass_with_delayed_search_and_custom_property(self):
        report = self.run_audit()
        self.assertTrue(report["passed"], report)
        self.assertRegex(report["email"], r"^foco_test\+foco_\d+_[a-f0-9]{32}@test\.focosys\.io$")
        self.assertEqual(self.payload["ft_campaign"], "audit_test")
        self.assertEqual(self.injections, 1)
        self.assertEqual(len(self.searches), 2)
        query, auth = self.searches[-1]
        self.assertEqual(auth, "Bearer test-token")
        self.assertEqual(query["filterGroups"][0]["filters"][0]["value"], report["email"])
        self.assertIn("first_source", query["properties"])

    def test_flags_modified_missing_and_late_fields(self):
        self.changes = {
            "first_source": "direct", "gclid": "modified", "fbclid": None,
            "createdate": (datetime.now(timezone.utc) + timedelta(minutes=121)).isoformat(),
        }
        report = self.run_audit()
        self.assertFalse(report["passed"])
        for key in ("ft_source", "gclid", "fbclid", "sync_latency"):
            self.assertFalse(report["checks"][key]["passed"])

    def test_invalid_capi_and_missing_timestamp_fail(self):
        self.receipt_changes["user_data"] = {"em": ["plaintext"], "ph": []}
        self.changes["createdate"] = None
        report = self.run_audit()
        self.assertFalse(report["passed"])
        self.assertFalse(report["checks"]["capi_handshake"]["passed"])
        self.assertIsNone(report["checks"]["sync_latency"]["minutes"])

    def test_rejected_handshake_skips_search(self):
        self.status = 202
        report = self.run_audit()
        self.assertFalse(report["passed"])
        self.assertEqual(report["checks"]["injection"]["http_status"], 202)
        self.assertEqual(self.searches, [])
