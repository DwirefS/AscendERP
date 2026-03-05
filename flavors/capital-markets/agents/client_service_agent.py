"""
Client Service Agent for Capital Markets.
Handles client queries, portfolio summaries, and relationship management.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

logger = structlog.get_logger()


class ClientServiceAgent(BaseAgent):
    """
    Agent for client-facing services including portfolio inquiries,
    transaction history, and relationship management.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Client Service Agent",
                description="Provides client support and portfolio information",
                tools=[
                    "lookup_client",
                    "get_portfolio_summary",
                    "get_transaction_history",
                    "schedule_callback",
                    "create_ticket"
                ],
                max_iterations=10,
                timeout_seconds=60,
                model_name="gpt-4-turbo"
            )
        super().__init__(config)

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Parse client service request.

        Expected input:
        {
            "client_id": str,
            "query_type": "portfolio_summary" | "transaction_history" | "general_inquiry" | "callback",
            "message": str (optional),
            "parameters": dict (optional)
        }
        """
        logger.info(
            "perceiving_client_request",
            trace_id=context.trace_id,
            client_id=input_data.get("client_id"),
            query_type=input_data.get("query_type")
        )

        perception = {
            "client_id": input_data.get("client_id"),
            "query_type": input_data.get("query_type", "general_inquiry").lower(),
            "message": input_data.get("message", ""),
            "parameters": input_data.get("parameters", {}),
            "request_time": datetime.utcnow().isoformat()
        }

        if not perception["client_id"]:
            raise ValueError("Client ID is required")

        return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Retrieve client history and interaction data.
        """
        retrieved = {}

        if self.memory:
            # Get full client interaction history
            episodic = await self.memory.retrieve_episodic(
                context={"client_id": perception["client_id"]},
                tenant_id=context.tenant_id,
                limit=50
            )
            retrieved["interaction_history"] = [e.content for e in episodic]

            # Get client preferences and service guidelines
            semantic = await self.memory.retrieve_semantic(
                query=f"client service guidelines {perception['client_id']}",
                tenant_id=context.tenant_id,
                limit=5
            )
            retrieved["service_guidelines"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Determine appropriate client service response.
        """
        prompt = f"""
        You are an expert client service representative for a capital markets firm.
        Based on the client request and interaction history, provide an appropriate response.

        Client Request:
        - Client ID: {perception['client_id']}
        - Query Type: {perception['query_type']}
        - Message: {perception['message']}

        Past Interactions:
        {retrieved_context.get('interaction_history', [])}

        Service Guidelines:
        {retrieved_context.get('service_guidelines', [])}

        Provide a professional, helpful response that addresses the client's needs.
        Include specific data points from their account history when relevant.
        """

        if self.llm:
            try:
                response = await self.llm.generate(
                    prompt=prompt,
                    max_tokens=self.config.max_tokens,
                    temperature=0.5
                )

                return {
                    "action": {
                        "type": "respond_to_client",
                        "client_id": perception["client_id"],
                        "query_type": perception["query_type"],
                        "response": response.get("response", ""),
                        "requires_callback": response.get("requires_callback", False),
                        "requires_ticket": response.get("requires_ticket", False)
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get("reasoning", "")
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed",
                    error=str(e),
                    fallback="template_response"
                )

        # Fallback: Route to human
        return {
            "action": {
                "type": "respond_to_client",
                "client_id": perception["client_id"],
                "query_type": perception["query_type"],
                "response": "Thank you for contacting us. Your request requires personalized attention. A team member will contact you shortly.",
                "requires_callback": True,
                "requires_ticket": True
            },
            "confidence": 0.70,
            "reasoning": "Routing to human agent"
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """
        Execute client service action.
        """
        client_id = action.get("client_id")
        query_type = action.get("query_type")
        response_text = action.get("response", "")

        logger.info(
            "executing_client_service_action",
            trace_id=context.trace_id,
            client_id=client_id,
            query_type=query_type
        )

        try:
            # Get client data
            client_data = await self._lookup_client(client_id)

            result = {
                "status": "complete",
                "client_id": client_id,
                "client_name": client_data.get("name"),
                "response": response_text,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Handle specific query types
            if query_type == "portfolio_summary":
                portfolio_summary = await self._get_portfolio_summary(client_id)
                result["portfolio_summary"] = portfolio_summary
                result["response"] = self._format_portfolio_response(portfolio_summary)

            elif query_type == "transaction_history":
                params = action.get("parameters", {})
                history = await self._get_transaction_history(
                    client_id,
                    params.get("days", 90),
                    params.get("limit", 20)
                )
                result["transaction_history"] = history
                result["response"] = self._format_transaction_response(history)

            elif query_type == "general_inquiry":
                result["requires_callback"] = action.get("requires_callback", False)
                result["requires_ticket"] = action.get("requires_ticket", False)

            # Schedule callback if needed
            if action.get("requires_callback"):
                callback = await self._schedule_callback(client_id, context)
                result["callback_scheduled"] = callback

            # Create ticket if needed
            if action.get("requires_ticket"):
                ticket = await self._create_ticket(
                    client_id,
                    query_type,
                    response_text,
                    context
                )
                result["ticket_created"] = ticket

            # Update CRM with interaction
            await self._update_crm(client_id, query_type, response_text, context)

            return result

        except Exception as e:
            logger.error(
                "client_service_action_failed",
                trace_id=context.trace_id,
                error=str(e)
            )
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def verify(
        self,
        result: Any,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Verify client service response quality.
        """
        status = result.get("status", "unknown")

        if status == "complete":
            response = result.get("response", "")

            return {
                "complete": bool(response),
                "quality_score": 0.95 if response else 0.5,
                "metrics": {
                    "has_response": bool(response),
                    "callback_scheduled": result.get("callback_scheduled", False),
                    "ticket_created": result.get("ticket_created", False)
                }
            }

        return {
            "complete": False,
            "quality_score": 0.0,
            "metrics": {}
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext
    ):
        """
        Store client interactions and service improvements.
        """
        if not self.memory or not actions_taken:
            return

        last_action = actions_taken[-1]
        result = last_action.get("result", {})

        # Store episodic memory of interaction
        await self.memory.store_episodic(
            content={
                "client_id": input_data.get("client_id"),
                "query_type": input_data.get("query_type"),
                "message": input_data.get("message"),
                "response": result.get("response"),
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": context.trace_id
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id
        )

    async def _lookup_client(self, client_id: str) -> Dict[str, Any]:
        """Look up client information."""
        logger.info("looking_up_client", client_id=client_id)

        # Placeholder: Fetch from CRM
        return {
            "client_id": client_id,
            "name": "John Smith",
            "email": "john.smith@example.com",
            "phone": "+1-555-0123",
            "account_type": "premium",
            "aum": 5000000,
            "relationship_manager": "Jane Doe"
        }

    async def _get_portfolio_summary(self, client_id: str) -> Dict[str, Any]:
        """Get portfolio summary for client."""
        logger.info("getting_portfolio_summary", client_id=client_id)

        # Placeholder: Fetch from portfolio system
        return {
            "client_id": client_id,
            "total_value": 5000000,
            "ytd_return": 0.08,
            "allocation": {
                "equities": 0.60,
                "fixed_income": 0.30,
                "alternatives": 0.10
            },
            "top_holdings": [
                {"ticker": "AAPL", "value": 500000, "weight": 0.10},
                {"ticker": "MSFT", "value": 400000, "weight": 0.08},
                {"ticker": "GOOGL", "value": 350000, "weight": 0.07}
            ],
            "performance": {
                "1_month": 0.02,
                "3_month": 0.04,
                "ytd": 0.08,
                "1_year": 0.12
            }
        }

    async def _get_transaction_history(
        self,
        client_id: str,
        days: int = 90,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get transaction history for client."""
        logger.info(
            "getting_transaction_history",
            client_id=client_id,
            days=days,
            limit=limit
        )

        # Placeholder: Fetch from transaction system
        return [
            {
                "date": "2026-03-01",
                "type": "buy",
                "ticker": "AAPL",
                "quantity": 100,
                "price": 150.00,
                "amount": 15000,
                "commission": 15
            },
            {
                "date": "2026-02-25",
                "type": "sell",
                "ticker": "MSFT",
                "quantity": 50,
                "price": 400.00,
                "amount": 20000,
                "commission": 20
            }
        ]

    async def _schedule_callback(
        self,
        client_id: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """Schedule callback with relationship manager."""
        logger.info("scheduling_callback", client_id=client_id)

        # Placeholder: Integrate with calendar system
        return {
            "scheduled": True,
            "callback_time": "2026-03-04 14:00 EST",
            "assigned_to": "Jane Doe"
        }

    async def _create_ticket(
        self,
        client_id: str,
        query_type: str,
        description: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """Create support ticket for client."""
        logger.info("creating_ticket", client_id=client_id, query_type=query_type)

        # Placeholder: Integrate with ticket system
        ticket_id = f"TKT-{int(datetime.utcnow().timestamp())}"

        return {
            "ticket_id": ticket_id,
            "client_id": client_id,
            "query_type": query_type,
            "status": "open",
            "created_at": datetime.utcnow().isoformat()
        }

    async def _update_crm(
        self,
        client_id: str,
        query_type: str,
        notes: str,
        context: AgentContext
    ):
        """Update CRM with interaction."""
        logger.info("updating_crm", client_id=client_id)

        # Placeholder: Update CRM system
        pass

    def _format_portfolio_response(self, portfolio: Dict[str, Any]) -> str:
        """Format portfolio summary into readable response."""
        return f"""
        Your Portfolio Summary:

        Total Value: ${portfolio['total_value']:,.0f}
        YTD Return: {portfolio['performance']['ytd']:.1%}

        Asset Allocation:
        - Equities: {portfolio['allocation']['equities']:.0%}
        - Fixed Income: {portfolio['allocation']['fixed_income']:.0%}
        - Alternatives: {portfolio['allocation']['alternatives']:.0%}

        Top Holdings:
        {chr(10).join(
            f"- {h['ticker']}: ${h['value']:,.0f} ({h['weight']:.1%})"
            for h in portfolio['top_holdings'][:3]
        )}
        """

    def _format_transaction_response(self, history: List[Dict[str, Any]]) -> str:
        """Format transaction history into readable response."""
        if not history:
            return "No transactions found for the requested period."

        transactions_str = "\n".join(
            f"- {t['date']}: {t['type'].upper()} {t['quantity']} shares of {t['ticker']} @ ${t['price']:.2f}"
            for t in history[:5]
        )

        return f"""
        Recent Transactions:

        {transactions_str}

        Total transactions: {len(history)}
        """
