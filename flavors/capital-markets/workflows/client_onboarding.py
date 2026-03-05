"""
Client Onboarding Workflow for Capital Markets.

Orchestrates comprehensive client acquisition and compliance onboarding.
Implements KYC (Know Your Customer), AML (Anti-Money Laundering) screening,
and risk-based account activation.

Workflow Flow:
    Registration → KYC Document Collection → AML Screening → Risk Scoring
    → [if high-risk] Risk Committee Review → Account Activation/Rejection

Uses LangGraph for orchestration with TypedDict state management.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


class ClientOnboardingState(TypedDict):
    """State management for client onboarding workflow."""

    # Client information
    client_id: str
    client_name: str
    email: str
    phone: str
    client_type: str  # "individual", "institution", "hedge_fund", "corporation"
    preferred_contact: str  # "email", "phone"

    # Registration phase
    registration_complete: bool
    registration_validated: bool
    validation_errors: List[str]
    registration_timestamp: str

    # KYC (Know Your Customer) phase
    kyc_complete: bool
    kyc_documents_required: List[str]
    kyc_documents_submitted: Dict[str, Dict[str, Any]]
    kyc_documents_verified: bool
    kyc_issues: List[str]

    # Personal/Entity information (KYC)
    date_of_birth: Optional[str]
    address: str
    country_of_residence: str
    citizenship: str
    occupation: Optional[str]
    source_of_wealth: str
    politically_exposed_person: bool
    politically_exposed_details: Optional[str]

    # Financial information
    estimated_annual_income: float
    total_investable_assets: float
    investment_experience_years: int
    investment_objectives: List[str]  # "income", "growth", "preservation", "speculation"

    # AML Screening phase
    aml_screening_complete: bool
    aml_checks_performed: Dict[str, Any]
    aml_screening_passed: bool
    aml_screening_status: str  # "passed", "failed", "manual_review"
    aml_issues: List[str]
    sanctions_checked: bool
    adverse_media_checked: bool
    pep_checked: bool

    # Risk Scoring
    risk_assessment_complete: bool
    risk_score: float  # 0-100, where 100 is highest risk
    risk_category: str  # "low", "medium", "high", "very_high"
    risk_factors: List[Dict[str, Any]]

    # Committee review (if needed)
    committee_review_required: bool
    committee_reviewed: bool
    committee_decision: Optional[str]
    committee_recommendations: List[str]
    committee_concerns: List[str]

    # Account activation
    activation_complete: bool
    account_status: str  # "approved", "rejected", "pending_review", "suspended"
    account_created_timestamp: Optional[str]
    trading_enabled: bool
    deposits_enabled: bool
    withdrawal_limits: Optional[Dict[str, float]]  # Daily, monthly limits

    # Compliance & approvals
    terms_accepted: bool
    privacy_policy_accepted: bool
    compliance_certifications: List[str]

    # Follow-up actions
    follow_up_required: bool
    follow_up_actions: List[Dict[str, Any]]
    next_review_date: Optional[str]

    # Workflow metadata
    workflow_status: str
    errors: List[str]
    created_at: str
    updated_at: str


async def process_registration(state: ClientOnboardingState) -> ClientOnboardingState:
    """
    PERCEIVE: Process and validate client registration information.

    Validates basic information, email, phone, and client type.
    Checks for duplicate accounts and basic eligibility.
    """
    logger.info(f"[REGISTRATION] Processing registration for {state['client_name']}")

    state["updated_at"] = datetime.utcnow().isoformat()
    state["registration_timestamp"] = datetime.utcnow().isoformat()

    errors = []

    try:
        # Validate client name
        if not state["client_name"] or len(state["client_name"]) < 2:
            errors.append("Client name too short")

        # Validate email
        if not state["email"] or "@" not in state["email"]:
            errors.append(f"Invalid email: {state['email']}")

        # Validate phone
        if not state["phone"] or len(state["phone"]) < 10:
            errors.append(f"Invalid phone number: {state['phone']}")

        # Validate client type
        valid_types = ["individual", "institution", "hedge_fund", "corporation"]
        if state["client_type"] not in valid_types:
            errors.append(f"Invalid client type: {state['client_type']}")

        # Check for required fields
        if not state["address"]:
            errors.append("Address is required")

        if not state["country_of_residence"]:
            errors.append("Country of residence is required")

        # Check for duplicate account (mock)
        # In production, would query client database
        existing_clients = []  # Mock - would check DB
        if any(c["email"] == state["email"] for c in existing_clients):
            errors.append(f"Account already exists for {state['email']}")

        # Validate financial information
        if state["total_investable_assets"] < 10000:
            errors.append("Minimum investable assets requirement not met")

        state["registration_validated"] = len(errors) == 0
        state["validation_errors"] = errors
        state["registration_complete"] = True

        logger.info(
            f"[REGISTRATION] Registration validation: "
            f"{'PASSED' if state['registration_validated'] else 'FAILED'}"
        )

    except Exception as e:
        logger.error(f"[REGISTRATION] Error processing registration: {str(e)}")
        state["validation_errors"].append(str(e))
        state["registration_complete"] = True

    return state


async def collect_kyc_documents(state: ClientOnboardingState) -> ClientOnboardingState:
    """
    RETRIEVE: Determine and collect KYC documentation requirements.

    Different requirements based on client type:
    - Individual: ID, address proof, occupation verification
    - Institution: Articles of incorporation, beneficial owners list
    - Hedge fund: Fund documents, regulatory filings
    - Corporation: Corporate documents, stakeholder verification
    """
    logger.info(f"[KYC] Collecting KYC documents for {state['client_name']}")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        # Determine document requirements based on client type
        if state["client_type"] == "individual":
            state["kyc_documents_required"] = [
                "government_issued_id",
                "address_proof",
                "proof_of_income",
                "bank_statement",
            ]

        elif state["client_type"] == "institution":
            state["kyc_documents_required"] = [
                "articles_of_incorporation",
                "beneficial_owners_list",
                "audited_financial_statements",
                "certificate_of_authority",
                "board_resolution",
            ]

        elif state["client_type"] == "hedge_fund":
            state["kyc_documents_required"] = [
                "fund_prospectus",
                "fund_offering_documents",
                "audited_fund_statements",
                "aum_verification",
                "fund_compliance_certificate",
                "manager_background_check",
            ]

        else:  # corporation
            state["kyc_documents_required"] = [
                "articles_of_incorporation",
                "certificate_of_good_standing",
                "list_of_officers",
                "financial_statements",
                "tax_identification",
            ]

        # Mock document submission
        # In production, would actually collect and store documents
        state["kyc_documents_submitted"] = {}

        for doc_type in state["kyc_documents_required"]:
            state["kyc_documents_submitted"][doc_type] = {
                "submitted": True,
                "submitted_at": datetime.utcnow().isoformat(),
                "status": "verified",
                "verified_at": datetime.utcnow().isoformat(),
            }

        # Verify all documents
        verification_issues = []

        # Mock document verification
        # In production, would use OCR and manual review
        for doc_type, doc_info in state["kyc_documents_submitted"].items():
            if doc_info["status"] == "verified":
                logger.info(f"[KYC] Document verified: {doc_type}")
            else:
                verification_issues.append(f"Document {doc_type} verification failed")

        state["kyc_documents_verified"] = len(verification_issues) == 0
        state["kyc_issues"] = verification_issues
        state["kyc_complete"] = True

        logger.info(
            f"[KYC] KYC documents collection complete. "
            f"Documents: {len(state['kyc_documents_submitted'])}, "
            f"Verified: {state['kyc_documents_verified']}"
        )

    except Exception as e:
        logger.error(f"[KYC] Error collecting KYC documents: {str(e)}")
        state["errors"].append(str(e))
        state["kyc_complete"] = True

    return state


async def aml_screening(state: ClientOnboardingState) -> ClientOnboardingState:
    """
    REASON: Perform AML (Anti-Money Laundering) and sanctions screening.

    Checks client against:
    - OFAC sanctions lists
    - FATF high-risk jurisdictions
    - Adverse media (PEP lists, criminal records)
    - Custom risk thresholds
    """
    logger.info(f"[AML] Performing AML screening for {state['client_name']}")

    state["updated_at"] = datetime.utcnow().isoformat()

    aml_issues = []

    try:
        state["aml_checks_performed"] = {}

        # Check against OFAC sanctions list (mock)
        logger.info("[AML] Checking OFAC sanctions list...")
        sanctions_check = {
            "passed": True,
            "matches": [],
            "confidence": 1.0,
        }
        state["aml_checks_performed"]["sanctions_check"] = sanctions_check
        state["sanctions_checked"] = True

        if not sanctions_check["passed"]:
            aml_issues.append(
                f"OFAC sanctions match: {', '.join(sanctions_check['matches'])}"
            )

        # Check PEP (Politically Exposed Person) status (mock)
        logger.info("[AML] Checking PEP status...")
        pep_check = {
            "is_pep": state["politically_exposed_person"],
            "pep_level": "none" if not state["politically_exposed_person"] else "medium",
            "jurisdictions": [],
        }
        state["aml_checks_performed"]["pep_check"] = pep_check
        state["pep_checked"] = True

        if state["politically_exposed_person"]:
            aml_issues.append(
                "Client is politically exposed person - enhanced due diligence required"
            )

        # Adverse media check (mock)
        logger.info("[AML] Checking adverse media...")
        adverse_media_check = {
            "passed": True,
            "adverse_findings": [],
            "confidence": 1.0,
        }
        state["aml_checks_performed"]["adverse_media"] = adverse_media_check
        state["adverse_media_checked"] = True

        if not adverse_media_check["passed"]:
            aml_issues.append("Adverse media findings detected")

        # Check high-risk jurisdictions (mock)
        logger.info("[AML] Checking jurisdiction risk...")
        high_risk_jurisdictions = ["Iran", "North Korea", "Syria"]
        jurisdiction_risk = {
            "country": state["country_of_residence"],
            "is_high_risk": state["country_of_residence"] in high_risk_jurisdictions,
            "risk_level": "high" if state["country_of_residence"] in high_risk_jurisdictions else "low",
        }
        state["aml_checks_performed"]["jurisdiction"] = jurisdiction_risk

        if jurisdiction_risk["is_high_risk"]:
            aml_issues.append(
                f"High-risk jurisdiction: {state['country_of_residence']}"
            )

        # Source of wealth verification (mock)
        logger.info("[AML] Verifying source of wealth...")
        acceptable_sources = [
            "employment",
            "business",
            "investment",
            "inheritance",
            "savings",
        ]
        wealth_source = {
            "source": state["source_of_wealth"],
            "acceptable": state["source_of_wealth"] in acceptable_sources,
            "verification_status": "verified",
        }
        state["aml_checks_performed"]["source_of_wealth"] = wealth_source

        if not wealth_source["acceptable"]:
            aml_issues.append(
                f"Source of wealth not acceptable: {state['source_of_wealth']}"
            )

        state["aml_screening_passed"] = len(aml_issues) == 0
        state["aml_issues"] = aml_issues

        if state["aml_screening_passed"]:
            state["aml_screening_status"] = "passed"
        elif len(aml_issues) <= 2:
            state["aml_screening_status"] = "manual_review"
        else:
            state["aml_screening_status"] = "failed"

        state["aml_screening_complete"] = True

        logger.info(
            f"[AML] AML screening complete. "
            f"Status: {state['aml_screening_status']}, "
            f"Issues: {len(aml_issues)}"
        )

    except Exception as e:
        logger.error(f"[AML] Error during AML screening: {str(e)}")
        state["errors"].append(str(e))
        state["aml_screening_complete"] = True

    return state


async def calculate_risk_score(state: ClientOnboardingState) -> ClientOnboardingState:
    """
    Calculate risk score for client based on multiple factors.

    Risk factors include:
    - Financial profile (income, assets)
    - Investment experience
    - Geographic risk
    - Regulatory status (PEP, sanctions)
    - KYC/AML findings
    """
    logger.info(f"[RISK] Calculating risk score for {state['client_name']}")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        risk_score = 0.0
        risk_factors = []

        # Factor 1: Financial profile (0-25 points)
        if state["total_investable_assets"] < 50000:
            risk_score += 10
            risk_factors.append({
                "factor": "low_investable_assets",
                "value": state["total_investable_assets"],
                "contribution": 10,
            })
        elif state["total_investable_assets"] < 500000:
            risk_score += 5
            risk_factors.append({
                "factor": "medium_investable_assets",
                "value": state["total_investable_assets"],
                "contribution": 5,
            })

        # Factor 2: Investment experience (0-15 points)
        if state["investment_experience_years"] < 2:
            risk_score += 15
            risk_factors.append({
                "factor": "low_experience",
                "value": state["investment_experience_years"],
                "contribution": 15,
            })
        elif state["investment_experience_years"] < 5:
            risk_score += 10
            risk_factors.append({
                "factor": "moderate_experience",
                "value": state["investment_experience_years"],
                "contribution": 10,
            })
        else:
            risk_score += 5
            risk_factors.append({
                "factor": "good_experience",
                "value": state["investment_experience_years"],
                "contribution": 5,
            })

        # Factor 3: Geographic risk (0-20 points)
        high_risk_countries = ["Iran", "North Korea", "Syria", "Venezuela"]
        medium_risk_countries = ["Russia", "Belarus", "Hong Kong"]

        if state["country_of_residence"] in high_risk_countries:
            risk_score += 20
            risk_factors.append({
                "factor": "high_risk_jurisdiction",
                "value": state["country_of_residence"],
                "contribution": 20,
            })
        elif state["country_of_residence"] in medium_risk_countries:
            risk_score += 10
            risk_factors.append({
                "factor": "medium_risk_jurisdiction",
                "value": state["country_of_residence"],
                "contribution": 10,
            })

        # Factor 4: PEP status (0-15 points)
        if state["politically_exposed_person"]:
            risk_score += 15
            risk_factors.append({
                "factor": "politically_exposed",
                "value": True,
                "contribution": 15,
            })

        # Factor 5: KYC/AML status (0-20 points)
        if not state["kyc_documents_verified"]:
            risk_score += 10
            risk_factors.append({
                "factor": "kyc_unverified",
                "value": False,
                "contribution": 10,
            })

        if not state["aml_screening_passed"]:
            risk_score += 10
            risk_factors.append({
                "factor": "aml_failed",
                "value": False,
                "contribution": 10,
            })

        # Factor 6: Client type (0-10 points)
        client_type_contributions = {
            "individual": 5,
            "institution": 2,
            "hedge_fund": 3,
            "corporation": 3,
        }
        contribution = client_type_contributions.get(state["client_type"], 3)
        risk_score += contribution

        risk_factors.append({
            "factor": "client_type",
            "value": state["client_type"],
            "contribution": contribution,
        })

        state["risk_score"] = risk_score
        state["risk_factors"] = risk_factors

        # Categorize risk
        if risk_score < 20:
            state["risk_category"] = "low"
        elif risk_score < 40:
            state["risk_category"] = "medium"
        elif risk_score < 60:
            state["risk_category"] = "high"
        else:
            state["risk_category"] = "very_high"

        state["risk_assessment_complete"] = True

        logger.info(
            f"[RISK] Risk score calculated: {risk_score:.0f}/100 "
            f"({state['risk_category']})"
        )

    except Exception as e:
        logger.error(f"[RISK] Error calculating risk score: {str(e)}")
        state["errors"].append(str(e))
        state["risk_assessment_complete"] = True

    return state


async def check_committee_requirement(state: ClientOnboardingState) -> str:
    """
    Conditional routing: Determine if Risk Committee review is needed.

    Committee review is required for:
    - High-risk or very-high-risk clients
    - Clients with AML findings or manual review status
    - Clients with unverified KYC documents
    - Politically exposed persons
    """
    if state["risk_category"] in ["high", "very_high"]:
        state["committee_review_required"] = True
        logger.info("[ROUTE] High-risk category - Committee review required")
        return "risk_committee_review"

    if state["aml_screening_status"] == "manual_review" or not state["aml_screening_passed"]:
        state["committee_review_required"] = True
        logger.info("[ROUTE] AML issues found - Committee review required")
        return "risk_committee_review"

    if state["politically_exposed_person"]:
        state["committee_review_required"] = True
        logger.info("[ROUTE] PEP status - Committee review required")
        return "risk_committee_review"

    logger.info("[ROUTE] Risk criteria met - Proceeding to account activation")
    return "account_activation"


async def risk_committee_review(state: ClientOnboardingState) -> ClientOnboardingState:
    """
    Risk Committee reviews high-risk applications.

    Committee deliberates on:
    - Risk score and category
    - AML/KYC findings
    - Special circumstances (PEP, unusual source of wealth)
    - Enhanced due diligence requirements
    """
    logger.info(f"[COMMITTEE] Risk Committee reviewing {state['client_name']}")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        # Mock Risk Committee deliberation
        concerns = []
        recommendations = []

        # Assess risk score
        if state["risk_score"] > 60:
            concerns.append(
                f"Very high-risk score: {state['risk_score']:.0f} - "
                f"recommend enhanced monitoring"
            )
            recommendations.append("Require quarterly compliance reviews")

        if state["politically_exposed_person"]:
            concerns.append("Client is politically exposed - enhanced due diligence needed")
            recommendations.append("Verify source of wealth with supporting documents")
            recommendations.append("Restrict high-risk jurisdictions")

        if not state["aml_screening_passed"]:
            concerns.append(f"AML screening issues: {', '.join(state['aml_issues'][:2])}")
            recommendations.append("Request additional source of funds documentation")

        # Mock committee decision
        if len(concerns) > 3 or state["risk_score"] > 75:
            state["committee_decision"] = "reject"
            logger.warning("[COMMITTEE] Committee recommendation: REJECT")
        elif len(concerns) > 1:
            state["committee_decision"] = "conditional_approval"
            recommendations.append("Require enhanced due diligence completion before trading")
            logger.info("[COMMITTEE] Committee recommendation: CONDITIONAL APPROVAL")
        else:
            state["committee_decision"] = "approve"
            logger.info("[COMMITTEE] Committee recommendation: APPROVE")

        state["committee_concerns"] = concerns
        state["committee_recommendations"] = recommendations
        state["committee_reviewed"] = True

    except Exception as e:
        logger.error(f"[COMMITTEE] Error during committee review: {str(e)}")
        state["errors"].append(str(e))
        state["committee_decision"] = "manual_review"
        state["committee_reviewed"] = True

    return state


async def activate_account(state: ClientOnboardingState) -> ClientOnboardingState:
    """
    EXECUTE: Activate or reject client account.

    Sets account status, creates account in systems, and enables
    deposits/withdrawals with appropriate limits.
    """
    logger.info(f"[ACTIVATE] Processing account activation for {state['client_name']}")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        # Determine account status based on all factors
        should_reject = (
            not state["registration_validated"]
            or not state["kyc_documents_verified"]
            or (state["committee_reviewed"] and state["committee_decision"] == "reject")
        )

        if should_reject:
            state["account_status"] = "rejected"
            state["trading_enabled"] = False
            state["deposits_enabled"] = False
            logger.warning(
                f"[ACTIVATE] Account rejected for {state['client_name']}"
            )

        elif (
            state["committee_reviewed"]
            and state["committee_decision"] == "conditional_approval"
        ):
            state["account_status"] = "pending_review"
            state["trading_enabled"] = False
            state["deposits_enabled"] = True
            state["withdrawal_limits"] = {
                "daily_limit": 50000,
                "monthly_limit": 200000,
            }
            logger.info(
                f"[ACTIVATE] Account pending review for {state['client_name']}"
            )

        else:
            # Account approved
            state["account_status"] = "approved"
            state["account_created_timestamp"] = datetime.utcnow().isoformat()
            state["trading_enabled"] = True
            state["deposits_enabled"] = True

            # Set withdrawal limits based on risk category
            if state["risk_category"] == "low":
                withdrawal_limit = 10_000_000
                daily_limit = 1_000_000
            elif state["risk_category"] == "medium":
                withdrawal_limit = 5_000_000
                daily_limit = 500_000
            else:
                withdrawal_limit = 1_000_000
                daily_limit = 100_000

            state["withdrawal_limits"] = {
                "daily_limit": daily_limit,
                "monthly_limit": withdrawal_limit,
            }

            logger.info(
                f"[ACTIVATE] Account approved for {state['client_name']}. "
                f"Status: {state['account_status']}"
            )

        # Set compliance requirements
        follow_up_actions = []

        if state["politically_exposed_person"]:
            follow_up_actions.append({
                "action": "Annual PEP verification",
                "due_date": "2026-03-04",
                "priority": "high",
            })

        if state["risk_category"] in ["high", "very_high"]:
            follow_up_actions.append({
                "action": "Quarterly compliance review",
                "due_date": "2026-06-04",
                "priority": "high",
            })

        # Calculate next review date
        if follow_up_actions:
            next_review = "2026-06-04"  # 3 months from now
        else:
            next_review = "2027-03-04"  # 1 year from now

        state["follow_up_actions"] = follow_up_actions
        state["follow_up_required"] = len(follow_up_actions) > 0
        state["next_review_date"] = next_review

        state["activation_complete"] = True

    except Exception as e:
        logger.error(f"[ACTIVATE] Error activating account: {str(e)}")
        state["errors"].append(str(e))
        state["account_status"] = "pending_review"
        state["activation_complete"] = True

    return state


def create_client_onboarding_workflow():
    """
    Create and compile the Client Onboarding workflow.

    Returns:
        Compiled StateGraph workflow ready for execution.

    Workflow Phases:
        1. REGISTRATION: Validate client basic information
        2. KYC: Collect and verify Know Your Customer documentation
        3. AML: Perform Anti-Money Laundering screening
        4. RISK SCORING: Calculate client risk profile
        5. COMMITTEE: [Conditional] Risk Committee review for high-risk clients
        6. ACTIVATION: Create account and set operational parameters

    The workflow ensures comprehensive compliance with regulatory requirements
    before allowing client trading activities.
    """
    workflow = StateGraph(ClientOnboardingState)

    # Add nodes
    workflow.add_node("registration", process_registration)
    workflow.add_node("kyc", collect_kyc_documents)
    workflow.add_node("aml", aml_screening)
    workflow.add_node("risk_scoring", calculate_risk_score)
    workflow.add_node("risk_committee_review", risk_committee_review)
    workflow.add_node("account_activation", activate_account)

    # Add edges - linear flow through compliance checks
    workflow.add_edge("registration", "kyc")
    workflow.add_edge("kyc", "aml")
    workflow.add_edge("aml", "risk_scoring")

    # Conditional edge: check if committee review is needed
    workflow.add_conditional_edges(
        "risk_scoring",
        check_committee_requirement,
        {
            "risk_committee_review": "risk_committee_review",
            "account_activation": "account_activation",
        }
    )

    # Committee review leads to account activation
    workflow.add_edge("risk_committee_review", "account_activation")

    # Account activation is final step
    workflow.add_edge("account_activation", END)

    # Set entry point
    workflow.set_entry_point("registration")

    return workflow.compile()


if __name__ == "__main__":
    """Demo execution of client onboarding workflow."""
    import asyncio
    from datetime import datetime

    async def demo():
        # Create workflow
        onboarding_workflow = create_client_onboarding_workflow()

        # Create sample client onboarding request
        initial_state: ClientOnboardingState = {
            "client_id": "CLT-001-NEW",
            "client_name": "Jane Smith",
            "email": "jane.smith@example.com",
            "phone": "+1-555-0123",
            "client_type": "individual",
            "preferred_contact": "email",
            "registration_complete": False,
            "registration_validated": False,
            "validation_errors": [],
            "registration_timestamp": "",
            "kyc_complete": False,
            "kyc_documents_required": [],
            "kyc_documents_submitted": {},
            "kyc_documents_verified": False,
            "kyc_issues": [],
            "date_of_birth": "1985-06-15",
            "address": "123 Main Street, New York, NY 10001",
            "country_of_residence": "United States",
            "citizenship": "United States",
            "occupation": "Software Engineer",
            "source_of_wealth": "employment",
            "politically_exposed_person": False,
            "politically_exposed_details": None,
            "estimated_annual_income": 250000,
            "total_investable_assets": 1500000,
            "investment_experience_years": 8,
            "investment_objectives": ["growth", "income"],
            "aml_screening_complete": False,
            "aml_checks_performed": {},
            "aml_screening_passed": False,
            "aml_screening_status": "pending",
            "aml_issues": [],
            "sanctions_checked": False,
            "adverse_media_checked": False,
            "pep_checked": False,
            "risk_assessment_complete": False,
            "risk_score": 0.0,
            "risk_category": "unknown",
            "risk_factors": [],
            "committee_review_required": False,
            "committee_reviewed": False,
            "committee_decision": None,
            "committee_recommendations": [],
            "committee_concerns": [],
            "activation_complete": False,
            "account_status": "pending",
            "account_created_timestamp": None,
            "trading_enabled": False,
            "deposits_enabled": False,
            "withdrawal_limits": None,
            "terms_accepted": True,
            "privacy_policy_accepted": True,
            "compliance_certifications": [],
            "follow_up_required": False,
            "follow_up_actions": [],
            "next_review_date": None,
            "workflow_status": "pending",
            "errors": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        print("\n" + "="*80)
        print("CLIENT ONBOARDING WORKFLOW DEMO")
        print("="*80)
        print(f"Client Name: {initial_state['client_name']}")
        print(f"Client ID: {initial_state['client_id']}")
        print(f"Client Type: {initial_state['client_type']}")
        print(f"Email: {initial_state['email']}")
        print("="*80 + "\n")

        # Execute workflow
        final_state = await onboarding_workflow.ainvoke(initial_state)

        print("\n" + "="*80)
        print("ONBOARDING RESULTS")
        print("="*80)
        print(f"Registration: {'PASSED' if final_state['registration_validated'] else 'FAILED'}")
        print(f"KYC Documents: {'VERIFIED' if final_state['kyc_documents_verified'] else 'NOT VERIFIED'}")
        print(f"  Documents Submitted: {len(final_state['kyc_documents_submitted'])}")
        print(f"\nAML Screening: {final_state['aml_screening_status'].upper()}")
        if final_state['aml_issues']:
            print(f"  Issues: {', '.join(final_state['aml_issues'][:2])}")
        print(f"\nRisk Assessment:")
        print(f"  Risk Score: {final_state['risk_score']:.0f}/100")
        print(f"  Risk Category: {final_state['risk_category'].upper()}")
        print(f"  Risk Factors: {len(final_state['risk_factors'])}")
        print(f"\nCommittee Review Required: {final_state['committee_review_required']}")
        if final_state['committee_reviewed']:
            print(f"  Committee Decision: {final_state['committee_decision'].upper()}")
            if final_state['committee_concerns']:
                print(f"  Concerns: {len(final_state['committee_concerns'])}")
            if final_state['committee_recommendations']:
                print(f"  Recommendations: {len(final_state['committee_recommendations'])}")
        print(f"\nAccount Status: {final_state['account_status'].upper()}")
        print(f"Trading Enabled: {final_state['trading_enabled']}")
        print(f"Deposits Enabled: {final_state['deposits_enabled']}")
        if final_state['withdrawal_limits']:
            print(f"Daily Withdrawal Limit: ${final_state['withdrawal_limits']['daily_limit']:,.0f}")
            print(f"Monthly Withdrawal Limit: ${final_state['withdrawal_limits']['monthly_limit']:,.0f}")
        print(f"\nFollow-up Required: {final_state['follow_up_required']}")
        if final_state['next_review_date']:
            print(f"Next Review Date: {final_state['next_review_date']}")
        print("="*80 + "\n")

        if final_state['errors']:
            print("ERRORS:")
            for error in final_state['errors']:
                print(f"  - {error}")

    asyncio.run(demo())
