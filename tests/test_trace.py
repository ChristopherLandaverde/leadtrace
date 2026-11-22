"""Trace-record terminal output. Synthetic data only."""

import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from leadtrace import cli, trace

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
REPORT = {
    "token": "foco_1_abc", "email": "foco_test+foco_1_abc@test.focosys.io", "passed": False,
    "checks": {
        "landing": {"passed": False, "final_url": "https://x.test/lp", "missing": ["gclid"]},
        "form_capture": {"passed": True, "submit_url": "https://x.test/submit", "http_status": 200,
                         "mismatched": {}, "other_posts": ["https://x.test/beacon"], "blocked_requests": []},
        "ft_source": {"passed": True, "expected": "google_ads", "actual": "google_ads"},
        "gclid": {"passed": False, "expected": "gclid_syn_1", "actual": None},
        "sync_latency": {"passed": True, "minutes": 0.4, "sla_minutes": 120},
    },
}


class Tty(io.StringIO):
    def isatty(self):
        return True


class AsciiStream(io.StringIO):
    encoding = "ascii"


def run_cli(argv, stdout=None):
    stdout = stdout or io.StringIO()
    with patch("sys.argv", ["leadtrace", *argv]), contextlib.redirect_stdout(stdout), \
            self_exit() as code:
        cli.main()
    return stdout.getvalue(), code[0]


@contextlib.contextmanager
def self_exit():
    code = [None]
    try:
        yield code
    except SystemExit as exc:
        code[0] = exc.code


class TraceRender(unittest.TestCase):
    def test_audit_record_names_each_break(self):
        out = io.StringIO()
        trace.render_audit(REPORT, "browser", out)
        text = out.getvalue()
        self.assertTrue(text.startswith("LEADTRACE / AUDIT\nbrowser mode · "))
        self.assertIn("synthetic lead, test data only", text)
        self.assertIn("↓ TRACED     landing page → form POST → HubSpot contact search", text)
        self.assertIn("× landing                 dropped on the way: gclid", text)
        self.assertIn("× gclid                   expected gclid_syn_1, got (missing)", text)
        self.assertIn("1 other POST(s) ignored", text)
        self.assertIn("✓ sync_latency            0.4 min (SLA 120 min)", text)
        self.assertTrue(text.rstrip().endswith("× BROKEN     2 of 5 checks failed"))

    def test_passing_record(self):
        report = {**REPORT, "passed": True, "checks": {"ft_source": REPORT["checks"]["ft_source"]}}
        out = io.StringIO()
        trace.render_audit(report, "webhook", out)
        self.assertTrue(out.getvalue().rstrip().endswith("✓ VERIFIED   1 of 1 checks passed"))

    def test_color_only_on_tty_and_respects_no_color(self):
        plain, tty = io.StringIO(), Tty()
        with patch.dict(os.environ, {"TERM": "xterm"}, clear=False):
            os.environ.pop("NO_COLOR", None)
            trace.render_audit(REPORT, "browser", plain)
            trace.render_audit(REPORT, "browser", tty)
            self.assertNotIn("\033[", plain.getvalue())
            self.assertIn("\033[31m×", tty.getvalue())
            self.assertIn("\033[32m✓", tty.getvalue())
            no_color = Tty()
            with patch.dict(os.environ, {"NO_COLOR": "1"}):
                trace.render_audit(REPORT, "browser", no_color)
            self.assertNotIn("\033[", no_color.getvalue())

    def test_ascii_terminal_fallback(self):
        out = AsciiStream()
        trace.render_audit(REPORT, "browser", out)
        out.getvalue().encode("ascii")  # raises if any glyph leaked through
        self.assertIn("x BROKEN", out.getvalue())


class CliFormats(unittest.TestCase):
    def test_verify_trace_and_unknown_latency(self):
        text, code = run_cli(["verify", "--expected", str(FIXTURES / "sample_lead.json"),
                              "--actual", str(FIXTURES / "sample_crm_record.json")])
        self.assertEqual(code, 0)
        self.assertIn("✓ sync_latency            15.0 min (SLA 120 min)", text)
        self.assertIn("✓ VERIFIED   first-touch values and click IDs match", text)

        lead = json.loads((FIXTURES / "sample_lead.json").read_text())
        record = {"email": lead["email"]}
        path = Path(self.id() + ".json")
        path.write_text(json.dumps(record))
        self.addCleanup(path.unlink)
        text, code = run_cli(["verify", "--expected", str(FIXTURES / "sample_lead.json"), "--actual", str(path)])
        self.assertEqual(code, 1)
        self.assertIn("□ sync_latency            unknown", text)
        self.assertIn("× BROKEN", text)

    def test_audit_json_when_piped_trace_when_asked(self):
        report = {**REPORT, "passed": True}
        with patch.object(cli, "audit_lead", return_value=report), \
                patch.dict(os.environ, {"HUBSPOT_ACCESS_TOKEN": "t"}):
            text, code = run_cli(["audit", "https://x.test/lp"])
            self.assertEqual(json.loads(text), report)
            text, _ = run_cli(["audit", "https://x.test/lp", "--format", "trace"])
            self.assertIn("LEADTRACE / AUDIT", text)
            text, _ = run_cli(["audit", "https://x.test/lp"], stdout=Tty())
            self.assertIn("LEADTRACE / AUDIT", text)
            text, _ = run_cli(["audit", "https://x.test/lp", "--format", "json"], stdout=Tty())
            self.assertEqual(json.loads(text)["token"], "foco_1_abc")
        self.assertEqual(code, 0)

    def test_inject_dry_run(self):
        text, code = run_cli(["inject", "dry-run", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("LEADTRACE / INJECT\nform payload · dry run · ", text)
        self.assertIn("✓ VERIFIED   endpoint accepted the lead · HTTP 200", text)


if __name__ == "__main__":
    unittest.main()
