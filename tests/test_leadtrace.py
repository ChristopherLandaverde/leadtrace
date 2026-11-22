import unittest
from leadtrace.generator import generate_synthetic_lead
from leadtrace.verifier import verify_lead_parity
from leadtrace.client import inject_lead
from leadtrace.mcp import handle_rpc_request

class TestLeadTrace(unittest.TestCase):
    def test_lead_generation(self):
        lead = generate_synthetic_lead(source="linkedin", medium="paid_social")
        self.assertEqual(lead.ft_source, "linkedin")
        self.assertTrue(lead.phone.startswith("+1555"))
        self.assertEqual(len(lead.hashed_email), 64)

    def test_parity_pass(self):
        lead = generate_synthetic_lead().to_dict()
        rec = {
            "email": lead["email"],
            "First_Touch_Source__c": lead["ft_source"],
            "First_Touch_Medium__c": lead["ft_medium"],
            "First_Touch_Campaign__c": lead["ft_campaign"],
            "Original_Conversion_Id__c": lead["original_conversion_id"],
            "created_timestamp": lead["created_timestamp"] + 900
        }
        res = verify_lead_parity(lead, rec, max_latency_minutes=60.0)
        self.assertTrue(res.passed)

    def test_parameter_drop_flagged(self):
        lead = generate_synthetic_lead().to_dict()
        rec = {"email": lead["email"]}  # Missing ft_source
        res = verify_lead_parity(lead, rec)
        self.assertFalse(res.passed)

    def test_dry_run_injection(self):
        res = inject_lead(url="dry-run", payload={"test": True}, dry_run=True)
        self.assertTrue(res.success)
        self.assertTrue(res.is_dry_run)

    def test_mcp_tools(self):
        resp = handle_rpc_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(len(resp["result"]["tools"]), 3)

if __name__ == "__main__":
    unittest.main()
