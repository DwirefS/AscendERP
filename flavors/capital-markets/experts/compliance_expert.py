"""
Compliance Expert - Capital Markets MoE

Specialized expert for regulatory compliance, AML/KYC, and policy enforcement
in capital markets operations.

Domains: regulations, aml, kyc, reporting, mifid, dodd_frank, basel

Key Feature: Always consulted for large trades (confidence > 0.5 for any financial task)
"""

from typing import Any, Dict, List
import logging

from src.core.moe.moe_agent import Expert, ExpertType, ExpertOutput

logger = logging.getLogger(__name__)


class ComplianceExpert(Expert):
    """
    Expert specialized in regulatory compliance and policy enforcement

    Ensures compliance with:
    - Anti-Money Laundering (AML) regulations
    - Know Your Customer (KYC) requirements
    - Market abuse and insider trading restrictions
    - Dodd-Frank Act requirements
    - MiFID II/MiFIR regulations
    - Basel III capital and liquidity rules
    - SEC reporting and disclosure rules
    - Best execution requirements
    - Sanctions screening (OFAC, EU, UN lists)
    """

    def __init__(self):
        """Initialize Compliance Expert"""
        super().__init__(
            expert_id="cm_compliance_expert",
            expert_type=ExpertType.FINANCE,
            domain=["regulations", "aml", "kyc", "reporting", "mifid", "dodd_frank", "basel"]
        )

    async def analyze(self, task: Dict[str, Any]) -> ExpertOutput:
        """
        Analyze compliance-related tasks

        Args:
            task: Dict containing:
                - transaction_type: Type of transaction
                - amount: Transaction amount
                - client_type: 'institutional', 'retail', 'sophisticated'
                - counterparty: Counterparty name
                - jurisdiction: Transaction jurisdiction
                - description: Compliance analysis task
                - is_large_trade: Boolean flag

        Returns:
            ExpertOutput with compliance assessment
        """
        logger.info(f"Compliance Expert analyzing: {task.get('description', 'compliance task')}")

        # Compliance expert always has high confidence for financial tasks
        confidence = await self.estimate_confidence(task)

        transaction_type = task.get("transaction_type", "unknown")
        amount = task.get("amount", 0)
        client_type = task.get("client_type", "retail")
        counterparty = task.get("counterparty", "Unknown")
        jurisdiction = task.get("jurisdiction", "US")

        analysis = self._analyze_compliance(
            transaction_type=transaction_type,
            amount=amount,
            client_type=client_type,
            counterparty=counterparty,
            jurisdiction=jurisdiction,
            task=task
        )

        result = {
            "compliance_status": analysis["compliance_status"],
            "regulatory_requirements": analysis["requirements"],
            "risk_assessment": analysis["risk_assessment"],
            "required_controls": analysis["controls"],
            "reporting_obligations": analysis["reporting"],
            "approval_needed": analysis["approval_needed"]
        }

        return ExpertOutput(
            expert_id=self.expert_id,
            expert_type=self.expert_type,
            result=result,
            confidence=confidence,
            reasoning=f"Compliance review: {analysis['rationale']}"
        )

    async def estimate_confidence(self, task: Dict[str, Any]) -> float:
        """
        Estimate confidence for compliance task

        KEY: Always high confidence (>0.5) for large trades regardless of domain
        """
        amount = task.get("amount", 0)
        task_domain = task.get("domain", "").lower()
        task_description = task.get("description", "").lower()
        is_financial = task.get("is_financial_task", False)

        compliance_keywords = ["compliance", "regulatory", "aml", "kyc", "reporting", "sanctions"]
        description_match = sum(1 for kw in compliance_keywords if kw in task_description)

        # Large trades always get compliance review with high confidence
        if amount > 5_000_000:
            return 0.95
        elif amount > 1_000_000:
            return 0.90

        # Standard compliance task routing
        if any(kw in task_domain for kw in self.domain):
            return 0.92
        elif description_match >= 2:
            return 0.85
        elif is_financial or any(d in task_domain for d in ["finance", "trading", "investment"]):
            return 0.65  # Always consulted for financial tasks
        elif any(kw in task_domain for kw in self.domain):
            return 0.75
        else:
            return 0.35

    def _analyze_compliance(
        self,
        transaction_type: str,
        amount: float,
        client_type: str,
        counterparty: str,
        jurisdiction: str,
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Comprehensive compliance analysis
        """
        # AML/KYC requirements
        kyc_required = client_type in ["retail", "new"] or amount > 100_000
        aml_screening_required = amount > 10_000 or client_type == "new"

        kyc_status = task.get("kyc_status", "pending")
        kyc_approved = kyc_status == "approved" and not task.get("kyc_expired", False)

        # Sanctions screening
        is_sanctioned = self._check_sanctions(counterparty, jurisdiction)

        # Transaction thresholds
        ctf_threshold = 10_000
        suspicious_activity_threshold = 5_000

        # Regulatory framework applicability
        regulations = self._get_applicable_regulations(jurisdiction, transaction_type, amount)

        # Best execution requirements
        best_execution_required = amount > 100_000 and client_type in ["retail", "sophisticated"]

        # Compliance status determination
        compliance_issues = []

        if aml_screening_required and not kyc_approved:
            compliance_issues.append("KYC approval required")
        if is_sanctioned:
            compliance_issues.append("Counterparty on sanctions list")
        if amount > ctf_threshold:
            compliance_issues.append("CTF/AML suspicious activity reporting required")

        if amount > suspicious_activity_threshold:
            compliance_issues.append("Enhanced due diligence recommended")

        if compliance_issues:
            status = "COMPLIANCE_VIOLATION" if is_sanctioned or (aml_screening_required and not kyc_approved) else "CONDITIONAL_APPROVAL"
        else:
            status = "COMPLIANT"

        # Required controls
        controls = self._get_required_controls(transaction_type, amount, client_type, is_sanctioned)

        # Reporting obligations
        reporting = self._get_reporting_obligations(transaction_type, amount, jurisdiction)

        # Approval requirements
        approval_chain = self._get_approval_chain(status, amount)

        rationale = f"{transaction_type.upper()}: {status}, Amount ${amount:,.0f}, Client {client_type}, Jurisdiction {jurisdiction}"

        return {
            "compliance_status": {
                "status": status,
                "issues": compliance_issues,
                "kyc_approved": kyc_approved,
                "aml_screened": not aml_screening_required or task.get("aml_screened", False),
                "sanctions_clear": not is_sanctioned
            },
            "requirements": {
                "applicable_regulations": regulations,
                "kyc_required": kyc_required,
                "aml_screening_required": aml_screening_required,
                "enhanced_due_diligence": amount > 500_000,
                "best_execution_required": best_execution_required,
                "client_suitability": self._assess_suitability(client_type, transaction_type)
            },
            "risk_assessment": {
                "aml_risk": "High" if aml_screening_required and not kyc_approved else "Low",
                "sanctions_risk": "High" if is_sanctioned else "Low",
                "transaction_risk": self._assess_transaction_risk(transaction_type, amount),
                "counterparty_risk": self._assess_counterparty_risk(counterparty, jurisdiction),
                "fraud_risk": "Medium" if amount > 1_000_000 else "Low"
            },
            "controls": controls,
            "reporting": reporting,
            "approval_needed": {
                "approval_level": approval_chain["level"],
                "approvers": approval_chain["approvers"],
                "estimated_time_hours": approval_chain["time_hours"]
            },
            "rationale": rationale
        }

    @staticmethod
    def _check_sanctions(counterparty: str, jurisdiction: str) -> bool:
        """Check if counterparty is on sanctions lists (simplified)"""
        # In production, this would query OFAC, EU, UN lists
        sanctions_indicators = ["iran", "north korea", "syria", "crimea", "sanctioned"]
        return any(indicator in counterparty.lower() for indicator in sanctions_indicators)

    @staticmethod
    def _get_applicable_regulations(
        jurisdiction: str,
        transaction_type: str,
        amount: float
    ) -> List[str]:
        """Determine applicable regulatory frameworks"""
        regulations = []

        if jurisdiction.upper() in ["US", "USA"]:
            regulations.extend(["Dodd-Frank", "SEC_Act", "Bank_Secrecy_Act"])
            if amount > 10_000:
                regulations.append("CTF_Reporting")

        if jurisdiction.upper() in ["EU", "UK"]:
            regulations.extend(["MiFID_II", "GDPR"])
            if transaction_type == "derivative":
                regulations.append("EMIR")

        regulations.extend(["AML", "KYC", "Sanctions_Screening"])

        return regulations

    @staticmethod
    def _get_required_controls(
        transaction_type: str,
        amount: float,
        client_type: str,
        is_sanctioned: bool
    ) -> List[str]:
        """Specify required compliance controls"""
        controls = []

        # Basic controls
        controls.extend(["Client_Identification", "Sanctions_Screening", "AML_Monitoring"])

        # Enhanced controls for large amounts
        if amount > 100_000:
            controls.extend(["Enhanced_Due_Diligence", "Source_of_Funds_Verification"])

        # Transaction-specific controls
        if transaction_type in ["derivative", "leverage"]:
            controls.extend(["Suitability_Assessment", "Risk_Disclosure"])

        if client_type == "retail":
            controls.extend(["Investor_Protection", "Suitability_Documentation"])

        if is_sanctioned:
            controls.append("BLOCK_TRANSACTION")

        return controls

    @staticmethod
    def _get_reporting_obligations(transaction_type: str, amount: float, jurisdiction: str) -> Dict[str, Any]:
        """Determine reporting requirements"""
        reporting = {
            "reports_required": []
        }

        if amount > 10_000:
            reporting["reports_required"].append("Currency Transaction Report (CTF)")

        if amount > 5_000:
            reporting["reports_required"].append("Suspicious Activity Monitoring")

        if jurisdiction.upper() in ["EU", "UK"] and transaction_type == "derivative":
            reporting["reports_required"].append("EMIR Trade Reporting")

        if jurisdiction.upper() in ["EU", "UK"]:
            reporting["reports_required"].append("MiFID II Reporting")

        reporting["reporting_deadline_hours"] = 24 if "Suspicious Activity" in str(reporting["reports_required"]) else 48
        reporting["reporting_authority"] = f"FinCEN/Regulatory Authority for {jurisdiction}"

        return reporting

    @staticmethod
    def _get_approval_chain(status: str, amount: float) -> Dict[str, Any]:
        """Determine approval chain"""
        if status == "COMPLIANCE_VIOLATION":
            return {
                "level": "EXECUTIVE",
                "approvers": ["Compliance Officer", "Legal", "CRO"],
                "time_hours": 48
            }
        elif amount > 10_000_000:
            return {
                "level": "SENIOR_MANAGEMENT",
                "approvers": ["Compliance Officer", "Head of Trading"],
                "time_hours": 4
            }
        elif amount > 1_000_000:
            return {
                "level": "MANAGER",
                "approvers": ["Compliance Manager"],
                "time_hours": 2
            }
        else:
            return {
                "level": "SYSTEM",
                "approvers": ["Automated"],
                "time_hours": 0.25
            }

    @staticmethod
    def _assess_suitability(client_type: str, transaction_type: str) -> Dict[str, Any]:
        """Assess client suitability for transaction"""
        suitability_required = client_type in ["retail", "sophisticated"]

        return {
            "assessment_required": suitability_required,
            "knowledge_required": f"{transaction_type} expertise",
            "documentation_required": suitability_required
        }

    @staticmethod
    def _assess_transaction_risk(transaction_type: str, amount: float) -> str:
        """Assess transaction risk level"""
        if transaction_type in ["derivative", "leverage"] and amount > 1_000_000:
            return "High"
        elif transaction_type == "derivative" or amount > 5_000_000:
            return "Medium"
        else:
            return "Low"

    @staticmethod
    def _assess_counterparty_risk(counterparty: str, jurisdiction: str) -> str:
        """Assess counterparty credit risk"""
        if jurisdiction.upper() in ["HIGH_RISK_JURISDICTIONS"]:
            return "High"
        elif len(counterparty) < 3:
            return "Medium"
        else:
            return "Low"
