"""leadtrace: Synthetic Lead Generator & Ingestion Parity Daemon
Author: Christopher Landaverde (FOCO / Focosys)
"""

__version__ = "0.1.0"

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
