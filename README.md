# LeadTrace

Send a synthetic lead through a form webhook or server-side Google Tag Manager
(sGTM), then verify that HubSpot received the original attribution fields.
Developed by Christopher Landaverde (Focosys).

## Run a HubSpot audit

Install with `python -m pip install .` on Python 3.9 or later. The CLI uses
the Python standard library at runtime.

1. Use a test webhook that accepts a flat JSON lead and sends it to a test
   HubSpot portal. Configure the destination contact properties for
   `ft_source`, `ft_medium`, `ft_campaign`, `original_conversion_id`,
   `gclid`, and `fbclid`.
2. Set `HUBSPOT_ACCESS_TOKEN` in your environment using a HubSpot private
   app token with `crm.objects.contacts.read`.
3. Run the audit against your endpoint.

```sh
leadtrace audit https://your-test-endpoint.example/lead \
  --property ft_source=first_touch_source
```

Repeat `--property FIELD=INTERNAL_NAME` for any HubSpot properties that
use different internal names. The audit sends one POST, requires HTTP 200
or 201, polls HubSpot contact search by exact synthetic email, and reports
each check as JSON. Missing or modified attribution and click IDs fail the
audit. Exit code 0 means all checks passed, and exit code 1 means a check failed.

The default SLA is 120 minutes from dispatch to HubSpot contact creation.
Search visibility is a separate limit. The default search window is 120
seconds. Set `--wait-seconds 7200` to wait up to two hours and
`--poll-seconds` to control how often each search runs. The audit reports
a timeout if HubSpot search has yet to return the record by the deadline.

The POST exercises the configured server endpoint. To test browser
redirects and hidden inputs, submit through the actual browser form in a
separate browser-based test.

### sGTM receipt

Use `--mode sgtm` when the endpoint can return a JSON receipt containing
the outbound CAPI event under `capi_event`. The same flat JSON lead is
posted so the endpoint can send it to HubSpot and build the CAPI event.
LeadTrace compares the receipt's `event_id` to the lead's
`original_conversion_id` and checks `user_data.em` and `user_data.ph`
against the SHA-256 hashes of the synthetic email and phone. Return the
event the server actually constructed. This verifies the receipt, while
Meta delivery requires separate evidence. Route synthetic events to test
destinations.

## Local tools

```sh
leadtrace generate --format form
leadtrace inject dry-run --dry-run
leadtrace verify --expected fixtures/sample_lead.json --actual fixtures/sample_crm_record.json
leadtrace mcp
python -m unittest discover -s tests -v
```

The existing offline verifier and MCP tools can generate test payloads
and inspect fixtures. The `audit` command performs the strict HubSpot
checks. The test suite runs the audit through mocked HTTP responses for the webhook and
HubSpot search, with no live CRM credentials.

Salesforce lookup and HubSpot-to-Salesforce reconciliation are outside
the v1 HubSpot workflow.
