"""
Department Leadership Councils

Pre-configured councils for organizational departments:
- Executive Council: C-suite strategic decisions
- Finance Council: Financial planning and allocation
- Operations Council: Operational efficiency
- Technology Council: Technical architecture and security
"""

from src.agents.councils.executive_council import create_executive_council
from src.agents.councils.finance_council import create_finance_council

__all__ = [
    "create_executive_council",
    "create_finance_council",
]
