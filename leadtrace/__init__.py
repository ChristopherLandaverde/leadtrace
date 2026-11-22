"""LeadTrace: verify that a synthetic lead keeps its attribution from ingestion to CRM.
Author: Christopher Landaverde (FOCO Systems)
"""

__version__ = "0.2.0"

from .generator import generate_synthetic_lead, SyntheticLead
from .verifier import verify_lead_parity, ParityResult
from .client import inject_lead, InjectionResult

__all__ = [
    "generate_synthetic_lead",
    "SyntheticLead",
    "verify_lead_parity",
    "ParityResult",
    "inject_lead",
    "InjectionResult",
]
