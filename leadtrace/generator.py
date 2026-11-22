import hashlib
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

@dataclass
class SyntheticLead:
    token: str
    email: str
    first_name: str
    last_name: str
    phone: str
    company: str
    created_timestamp: int
    ft_source: str
    ft_medium: str
    ft_campaign: str
    original_conversion_id: str
    gclid: str
    fbclid: str
    hashed_email: str
    hashed_phone: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_form_payload(self) -> Dict[str, Any]:
        """Flat payload for form webhooks or Web-to-Lead."""
        return {
            "email": self.email,
            "firstname": self.first_name,
            "lastname": self.last_name,
            "phone": self.phone,
            "company": self.company,
            "ft_source": self.ft_source,
            "ft_medium": self.ft_medium,
            "ft_campaign": self.ft_campaign,
            "original_conversion_id": self.original_conversion_id,
            "gclid": self.gclid,
            "fbclid": self.fbclid,
        }

    def to_capi_payload(self, event_name: str = "Lead", action_source: str = "website") -> Dict[str, Any]:
        """Standard Meta CAPI / sGTM format."""
        return {
            "event_name": event_name,
            "event_time": self.created_timestamp,
            "event_id": self.original_conversion_id,
            "action_source": action_source,
            "user_data": {
                "em": [self.hashed_email],
                "ph": [self.hashed_phone],
                "fbc": f"fb.1.{self.created_timestamp}.{self.fbclid}",
                "external_id": self.original_conversion_id,
            },
            "custom_data": {
                "lead_token": self.token,
                "ft_source": self.ft_source,
                "ft_medium": self.ft_medium,
                "ft_campaign": self.ft_campaign,
            }
        }

def generate_synthetic_lead(
    prefix: str = "foco_test",
    source: str = "google_ads",
    medium: str = "cpc",
    campaign: str = "q4_synthetic_audit",
    domain: str = "test.focosys.io",
    custom_token: Optional[str] = None
) -> SyntheticLead:
    ts = int(time.time())
    token = custom_token or f"foco_{ts}_{uuid.uuid4().hex}"
    email = f"{prefix}+{token}@{domain}".lower()
    phone_e164 = "+1555" + str(ts)[-7:]
    conv_id = f"conv_{token}"

    h_email = hashlib.sha256(email.encode("utf-8")).hexdigest()
    h_phone = hashlib.sha256(phone_e164.encode("utf-8")).hexdigest()

    return SyntheticLead(
        token=token,
        email=email,
        first_name="Synthetic",
        last_name=f"Lead_{token[:8]}",
        phone=phone_e164,
        company="FOCO Parity Test Corp",
        created_timestamp=ts,
        ft_source=source,
        ft_medium=medium,
        ft_campaign=campaign,
        original_conversion_id=conv_id,
        gclid=f"gclid_syn_{token}",
        fbclid=f"fbclid_syn_{token}",
        hashed_email=h_email,
        hashed_phone=h_phone
    )
