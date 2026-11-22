"""Acceptance tests for `audit --mode browser` (SPEC.md A1-A6, A8).

Runs headless Chrome against a local fixture site. HubSpot search is mocked.
Synthetic data only; no live CRM credentials.
"""

import contextlib
import io
import json
import os
import shutil
import unittest
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import Mock, patch

from browser_site import server as fixture_site
from leadtrace import browser as browser_mod
from leadtrace.audit import audit_lead

CHROME = os.environ.get("LEADTRACE_BROWSER") or next(
    (p for p in map(shutil.which, ("google-chrome", "chromium", "chromium-browser")) if p), None
)
import importlib.util

HAVE_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None

ALIASES = {"utm_source": "ft_source", "utm_medium": "ft_medium", "utm_campaign": "ft_campaign"}


@unittest.skipUnless(HAVE_PLAYWRIGHT and CHROME, "Playwright and Chrome are required")
class BrowserAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.submissions = fixture_site.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.submissions.clear()
        self.changes = {}

    def hubspot(self, request, timeout):
        """Mock HubSpot search: the contact is whatever the form submitted."""
        self.assertEqual(request.full_url, "https://api.hubapi.com/crm/v3/objects/contacts/search")
        results = []
        if self.submissions:
            record = {ALIASES.get(k, k): v for k, v in self.submissions[-1].items()}
            record["createdate"] = datetime.now(timezone.utc).isoformat()
            record.update(self.changes)
            results = [{"properties": record}]
        response = BytesIO(json.dumps({"results": results}).encode())
        response.status = 200
        return response

    def run_audit(self, page, **kwargs):
        with patch("leadtrace.client.urllib.request.build_opener", return_value=Mock(open=self.hubspot)):
            return audit_lead(
                f"{self.base}/{page}", "test-token", mode="browser", wait_seconds=5,
                poll_seconds=0.05, browser_path=CHROME, **kwargs,
            )

    def test_clean_form_passes(self):  # A1
        report = self.run_audit("landing.html")
        self.assertTrue(report["passed"], json.dumps(report, indent=2))
        self.assertEqual(len(self.submissions), 1)
        self.assertEqual(self.submissions[0]["email"], report["email"])
        for key in ("landing", "form_capture", "destination_lookup", "ft_source", "gclid", "sync_latency"):
            self.assertTrue(report["checks"][key]["passed"], key)

    def test_fetch_form_passes(self):  # assumption: fetch() submits are captured
        report = self.run_audit("landing-fetch.html")
        self.assertTrue(report["passed"], json.dumps(report, indent=2))

    def test_redirect_strips_param(self):  # A2
        report = self.run_audit("redirect")
        self.assertFalse(report["passed"])
        landing = report["checks"]["landing"]
        self.assertFalse(landing["passed"])
        self.assertEqual(landing["missing"], ["gclid"])
        self.assertIn("/landing.html", landing["final_url"])

    def test_hidden_input_not_populated(self):  # A3
        report = self.run_audit("landing-broken.html")
        self.assertTrue(report["checks"]["landing"]["passed"])
        capture = report["checks"]["form_capture"]
        self.assertFalse(capture["passed"])
        self.assertEqual(list(capture["mismatched"]), ["ft_campaign"])
        self.assertEqual(capture["mismatched"]["ft_campaign"]["actual"], "")

    def test_crm_overwrite_detected(self):  # A4
        self.changes = {"ft_source": "direct"}
        report = self.run_audit("landing.html")
        self.assertFalse(report["passed"])
        self.assertTrue(report["checks"]["form_capture"]["passed"])
        check = report["checks"]["ft_source"]
        self.assertFalse(check["passed"])
        self.assertEqual(check["expected"], "google_ads")
        self.assertEqual(check["actual"], "direct")

    def test_conversion_id_from_form(self):  # A5
        report = self.run_audit("landing.html")
        check = report["checks"]["original_conversion_id"]
        self.assertTrue(check["passed"])
        self.assertTrue(check["expected"].startswith("conv_page_"))
        self.changes = {"original_conversion_id": "conv_overwritten"}
        report = self.run_audit("landing.html")
        self.assertFalse(report["checks"]["original_conversion_id"]["passed"])

    def test_missing_submit_button_fails_cleanly(self):
        report = self.run_audit("landing.html", submit="#nope")
        self.assertFalse(report["passed"])
        self.assertFalse(report["checks"]["form_capture"]["passed"])
        self.assertIn("reason", report["checks"]["form_capture"])
        self.assertNotIn("destination_lookup", report["checks"])


class BrowserModeGuards(unittest.TestCase):
    def test_missing_playwright_message(self):  # A6
        from leadtrace import cli
        err = io.StringIO()
        with patch.object(browser_mod, "_load_playwright", side_effect=browser_mod.BrowserUnavailable("x")), \
                patch.dict(os.environ, {"HUBSPOT_ACCESS_TOKEN": "t"}), \
                patch("sys.argv", ["leadtrace", "audit", "https://example.test/lp", "--mode", "browser"]), \
                contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as exit_info:
            cli.main()
        self.assertEqual(exit_info.exception.code, 2)
        self.assertIn("leadtrace[browser]", err.getvalue())

    def test_rejects_plain_http(self):  # A8
        with self.assertRaises(ValueError):
            audit_lead("http://example.test/lp", "t", mode="browser")

    def test_landing_url_keeps_existing_query(self):
        url = browser_mod.landing_url("https://example.test/lp?ref=a", {
            "ft_source": "s", "ft_medium": "m", "ft_campaign": "c", "gclid": "g", "fbclid": "f",
        })
        self.assertEqual(
            url, "https://example.test/lp?ref=a&utm_source=s&utm_medium=m&utm_campaign=c&gclid=g&fbclid=f"
        )


if __name__ == "__main__":
    unittest.main()
