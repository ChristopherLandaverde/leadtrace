# LeadTrace

LeadTrace sends one synthetic lead through your form webhook or server-side
GTM endpoint. It then checks whether HubSpot still holds the attribution the
lead started with.

`Tool / README · v0.1.0 · HubSpot ingestion audit, assumptions, and limits`

```
□ OBSERVED   one synthetic lead with 6 attribution fields: ft_source, ft_medium,
             ft_campaign, original_conversion_id, gclid, fbclid
↓ TRACED     one POST to your endpoint, then a HubSpot contact search by the
             lead's exact synthetic email
× BROKEN     any field that is missing or changed in HubSpot, a contact that
             is missing or duplicated, or a sync slower than the SLA
✓ VERIFIED   a JSON report with expected and actual values for each check.
             Exit 0 = every check passed. Exit 1 = at least one failed.
```

## Scope

LeadTrace does:
- check the server endpoint and the HubSpot record it writes
- check an sGTM receipt for the CAPI event it built (see below)

LeadTrace does not:
- test browser redirects or hidden form inputs. Submit the real form in a
  separate browser test for those.
- confirm that Meta received the event
- look up Salesforce records or reconcile HubSpot with Salesforce (not in v1)

All test data is synthetic. Send it only to test portals and test
destinations.

## Why this exists

CRM merge and sync logic can overwrite first-touch values without raising
an error. One example: a field keeps whichever value was written last, not
the original UTM value. The report still says "paid", but the record
underneath has changed. LeadTrace catches the change at ingestion, before
anyone makes a budget decision from that report.

## Run a HubSpot audit

You need Python 3.9 or later. LeadTrace has no runtime dependencies beyond
the standard library.

```sh
python -m pip install .
```

1. Point a test webhook at a test HubSpot portal. The webhook must accept a
   flat JSON lead. In the portal, create contact properties for
   `ft_source`, `ft_medium`, `ft_campaign`, `original_conversion_id`,
   `gclid`, and `fbclid`.
2. Create a HubSpot private app token with the `crm.objects.contacts.read`
   scope. Set it as `HUBSPOT_ACCESS_TOKEN` in your environment.
3. Run the audit against your endpoint:

```sh
leadtrace audit https://your-test-endpoint.example/lead \
  --property ft_source=first_touch_source
```

If a HubSpot property uses a different internal name, map it with
`--property FIELD=INTERNAL_NAME`. You can repeat the flag.

The audit:
- sends one POST and expects HTTP 200 or 201
- searches HubSpot for the lead's exact synthetic email
- compares each field with the value it sent

| Limit | Default | Flag |
|---|---|---|
| SLA from dispatch to HubSpot `createdate` | 120 minutes | `--max-latency` |
| Time to wait for the contact to show up in search | 120 seconds | `--wait-seconds` (`7200` = 2 hours) |
| Time between searches | 5 seconds | `--poll-seconds` |

If the contact is not in search results by the deadline, the audit reports
a timeout.

### sGTM receipt

Use `--mode sgtm` when your endpoint returns a JSON receipt with the
outbound CAPI event under `capi_event`. LeadTrace posts the same flat JSON
lead. Your endpoint sends it to HubSpot and builds the CAPI event.

LeadTrace then checks the receipt:
- `event_id` must match the lead's `original_conversion_id`
- `user_data.em` and `user_data.ph` must match the SHA-256 hashes of the
  synthetic email and phone

Return the event your server actually built, not a copy of the input. This
checks the receipt only. You need separate evidence that Meta received the
event.

## Local tools

```sh
leadtrace generate --format form
leadtrace inject dry-run --dry-run
leadtrace verify --expected fixtures/sample_lead.json --actual fixtures/sample_crm_record.json
leadtrace mcp
python -m unittest discover -s tests -v
```

- `generate` builds test payloads.
- `verify` compares fixture files offline.
- `mcp` runs the same tools as an MCP stdio server, so an agent can call
  them.
- `audit` is the only command that runs the strict HubSpot checks.

The test suite runs the audit against mocked webhook and HubSpot search
responses. It needs no live CRM credentials.

---

Built by Christopher Landaverde, FOCO Systems.
Field notes on this problem ↗ [focosys.io](https://focosys.io) ·
[christopher@focosys.io](mailto:christopher@focosys.io)
