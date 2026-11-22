from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class ParityDiscrepancy:
    field: str
    expected: Any
    actual: Any
    severity: str  # "ERROR", "WARNING"
    description: str

@dataclass
class ParityResult:
    passed: bool
    latency_minutes: Optional[float]  # None when either timestamp is missing
    discrepancies: List[ParityDiscrepancy] = field(default_factory=list)

    @property
    def errors(self) -> List[ParityDiscrepancy]:
        return [d for d in self.discrepancies if d.severity == "ERROR"]

    @property
    def warnings(self) -> List[ParityDiscrepancy]:
        return [d for d in self.discrepancies if d.severity == "WARNING"]

def _find_field_value(record: Dict[str, Any], candidate_keys: List[str]) -> Optional[Any]:
    norm_rec = {str(k).lower().replace("_", ""): v for k, v in record.items()}
    for key in candidate_keys:
        clean_key = key.lower().replace("_", "")
        if clean_key in norm_rec and norm_rec[clean_key] is not None:
            return norm_rec[clean_key]
    return None

def verify_lead_parity(
    expected_lead: Dict[str, Any],
    destination_record: Dict[str, Any],
    max_latency_minutes: float = 120.0
) -> ParityResult:
    discrepancies: List[ParityDiscrepancy] = []

    expected_email = str(expected_lead.get("email", "")).strip().lower()
    actual_email = _find_field_value(destination_record, ["email", "property_email", "lead_email"])

    if expected_email and actual_email and expected_email != str(actual_email).strip().lower():
        discrepancies.append(ParityDiscrepancy(
            field="email",
            expected=expected_email,
            actual=actual_email,
            severity="ERROR",
            description="Primary email anchor mismatch."
        ))

    field_mappings = [
        ("ft_source", ["ft_source", "first_touch_source", "first_touch_source__c", "property_ft_source", "original_source", "utm_source"], "First-Touch Source"),
        ("ft_medium", ["ft_medium", "first_touch_medium", "first_touch_medium__c", "property_ft_medium", "utm_medium"], "First-Touch Medium"),
        ("ft_campaign", ["ft_campaign", "first_touch_campaign", "first_touch_campaign__c", "property_ft_campaign", "utm_campaign"], "First-Touch Campaign"),
        ("original_conversion_id", ["original_conversion_id", "original_conversion_id__c", "conversion_token", "property_original_conversion_id"], "Original Conversion ID"),
    ]

    for field_key, candidates, label in field_mappings:
        exp_val = expected_lead.get(field_key)
        dest_val = _find_field_value(destination_record, candidates)

        if exp_val and (dest_val is None or str(dest_val).strip() == ""):
            discrepancies.append(ParityDiscrepancy(
                field=field_key,
                expected=exp_val,
                actual=None,
                severity="ERROR",
                description=f"{label} was stripped or dropped during ingestion/sync."
            ))
        elif exp_val and dest_val and str(exp_val).strip() != str(dest_val).strip():
            discrepancies.append(ParityDiscrepancy(
                field=field_key,
                expected=exp_val,
                actual=dest_val,
                severity="ERROR",
                description=f"{label} value was overwritten or corrupted."
            ))

    for click_key, candidates in [("gclid", ["gclid", "gclid__c"]), ("fbclid", ["fbclid", "fbclid__c"])]:
        exp_id = expected_lead.get(click_key)
        dest_id = _find_field_value(destination_record, candidates)
        if exp_id and not dest_id:
            discrepancies.append(ParityDiscrepancy(
                field=click_key,
                expected=exp_id,
                actual=None,
                severity="WARNING",
                description=f"Ad click identifier '{click_key}' missing in destination record."
            ))

    created_ts = expected_lead.get("created_timestamp")
    dest_ts = _find_field_value(destination_record, ["created_timestamp", "synced_timestamp", "createddate"])
    latency = None

    if created_ts and dest_ts:
        try:
            latency = max(0.0, (float(dest_ts) - float(created_ts)) / 60.0)
            if latency > max_latency_minutes:
                discrepancies.append(ParityDiscrepancy(
                    field="sync_latency",
                    expected=f"<= {max_latency_minutes}m",
                    actual=f"{latency:.1f}m",
                    severity="ERROR",
                    description=f"Sync latency exceeded {max_latency_minutes}m SLA."
                ))
        except (ValueError, TypeError):
            pass

    passed = len([d for d in discrepancies if d.severity == "ERROR"]) == 0
    return ParityResult(passed=passed, latency_minutes=latency, discrepancies=discrepancies)
