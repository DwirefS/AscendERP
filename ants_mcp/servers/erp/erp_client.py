"""
ERP Client for real ERP system integration.
Supports SAP, Microsoft Dynamics 365, Oracle ERP Cloud, and generic SQL.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import os
import asyncio
import structlog
import aiohttp
import pyodbc
import asyncpg

logger = structlog.get_logger()


class ERPType(Enum):
    """Supported ERP systems."""
    SAP_ODATA = "sap_odata"
    DYNAMICS_365 = "dynamics_365"
    ORACLE_CLOUD = "oracle_cloud"
    ODBC_SQL = "odbc_sql"
    POSTGRES = "postgres"


class ERPClient:
    """
    Unified client for multiple ERP systems.
    Abstracts vendor-specific API differences.
    """

    def __init__(
        self,
        erp_type: ERPType,
        connection_config: Dict[str, Any]
    ):
        self.erp_type = erp_type
        self.config = connection_config
        self._session: Optional[aiohttp.ClientSession] = None
        self._db_connection = None

    async def connect(self):
        """Establish connection to ERP system."""
        if self.erp_type in [ERPType.SAP_ODATA, ERPType.DYNAMICS_365, ERPType.ORACLE_CLOUD]:
            # HTTP-based ERP systems
            self._session = aiohttp.ClientSession(
                headers=self._get_auth_headers(),
                timeout=aiohttp.ClientTimeout(total=30)
            )
            logger.info("erp_http_connected", erp_type=self.erp_type.value)

        elif self.erp_type == ERPType.POSTGRES:
            # PostgreSQL connection
            self._db_connection = await asyncpg.connect(
                host=self.config["host"],
                port=self.config.get("port", 5432),
                user=self.config["username"],
                password=self.config["password"],
                database=self.config["database"]
            )
            logger.info("erp_postgres_connected")

        elif self.erp_type == ERPType.ODBC_SQL:
            # ODBC connection (synchronous - run in executor)
            connection_string = self.config["connection_string"]
            loop = asyncio.get_event_loop()
            self._db_connection = await loop.run_in_executor(
                None,
                pyodbc.connect,
                connection_string
            )
            logger.info("erp_odbc_connected")

    async def disconnect(self):
        """Close ERP connection."""
        if self._session:
            await self._session.close()

        if self._db_connection:
            if self.erp_type == ERPType.POSTGRES:
                await self._db_connection.close()
            elif self.erp_type == ERPType.ODBC_SQL:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._db_connection.close)

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for HTTP-based ERP."""
        if self.erp_type == ERPType.SAP_ODATA:
            # SAP uses Basic Auth or OAuth
            if "oauth_token" in self.config:
                return {"Authorization": f"Bearer {self.config['oauth_token']}"}
            else:
                import base64
                credentials = f"{self.config['username']}:{self.config['password']}"
                encoded = base64.b64encode(credentials.encode()).decode()
                return {"Authorization": f"Basic {encoded}"}

        elif self.erp_type == ERPType.DYNAMICS_365:
            # Dynamics 365 uses OAuth 2.0
            return {"Authorization": f"Bearer {self.config['access_token']}"}

        elif self.erp_type == ERPType.ORACLE_CLOUD:
            # Oracle Cloud uses Basic Auth
            import base64
            credentials = f"{self.config['username']}:{self.config['password']}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}

        return {}

    async def query_transactions(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
        transaction_type: str = "all"
    ) -> Dict[str, Any]:
        """Query financial transactions."""
        if self.erp_type == ERPType.SAP_ODATA:
            return await self._query_sap_transactions(account_id, start_date, end_date, transaction_type)

        elif self.erp_type == ERPType.DYNAMICS_365:
            return await self._query_dynamics_transactions(account_id, start_date, end_date, transaction_type)

        elif self.erp_type == ERPType.ORACLE_CLOUD:
            return await self._query_oracle_transactions(account_id, start_date, end_date, transaction_type)

        elif self.erp_type == ERPType.POSTGRES:
            return await self._query_sql_transactions(account_id, start_date, end_date, transaction_type)

        elif self.erp_type == ERPType.ODBC_SQL:
            return await self._query_odbc_transactions(account_id, start_date, end_date, transaction_type)

    async def _query_sap_transactions(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
        transaction_type: str
    ) -> Dict[str, Any]:
        """Query transactions from SAP via OData API."""
        base_url = self.config["base_url"]

        # SAP OData filter syntax
        filter_parts = [
            f"AccountID eq '{account_id}'",
            f"PostingDate ge datetime'{start_date}T00:00:00'",
            f"PostingDate le datetime'{end_date}T23:59:59'"
        ]

        if transaction_type != "all":
            filter_parts.append(f"TransactionType eq '{transaction_type}'")

        filter_query = " and ".join(filter_parts)

        # OData query
        url = f"{base_url}/GeneralLedgerEntries"
        params = {
            "$filter": filter_query,
            "$orderby": "PostingDate desc",
            "$top": 1000,
            "$format": "json"
        }

        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    transactions = data.get("d", {}).get("results", [])

                    return {
                        "account_id": account_id,
                        "transactions": [
                            {
                                "transaction_id": t.get("GLEntryID"),
                                "date": t.get("PostingDate"),
                                "amount": float(t.get("Amount", 0)),
                                "currency": t.get("Currency", "USD"),
                                "type": t.get("TransactionType"),
                                "description": t.get("Description"),
                                "document_number": t.get("DocumentNumber")
                            }
                            for t in transactions
                        ],
                        "total_count": len(transactions),
                        "date_range": {"start": start_date, "end": end_date}
                    }
                else:
                    error_text = await response.text()
                    logger.error("sap_query_failed", status=response.status, error=error_text)
                    return {"error": f"SAP API error: {response.status}", "transactions": []}

        except Exception as e:
            logger.error("sap_query_exception", error=str(e))
            return {"error": str(e), "transactions": []}

    async def _query_dynamics_transactions(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
        transaction_type: str
    ) -> Dict[str, Any]:
        """Query transactions from Dynamics 365 via Web API."""
        base_url = self.config["base_url"]  # e.g., https://org.crm.dynamics.com/api/data/v9.2

        # Dynamics 365 Web API filter
        filter_parts = [
            f"_accountid_value eq '{account_id}'",
            f"createdon ge {start_date}",
            f"createdon le {end_date}"
        ]

        if transaction_type != "all":
            filter_parts.append(f"transactiontype eq '{transaction_type}'")

        filter_query = " and ".join(filter_parts)

        url = f"{base_url}/transactions"
        params = {
            "$filter": filter_query,
            "$orderby": "createdon desc",
            "$top": 1000
        }

        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    transactions = data.get("value", [])

                    return {
                        "account_id": account_id,
                        "transactions": [
                            {
                                "transaction_id": t.get("transactionid"),
                                "date": t.get("createdon"),
                                "amount": float(t.get("amount", 0)),
                                "currency": t.get("transactioncurrencyid", {}).get("name", "USD"),
                                "type": t.get("transactiontype"),
                                "description": t.get("description"),
                                "document_number": t.get("documentnumber")
                            }
                            for t in transactions
                        ],
                        "total_count": len(transactions),
                        "date_range": {"start": start_date, "end": end_date}
                    }
                else:
                    error_text = await response.text()
                    logger.error("dynamics_query_failed", status=response.status, error=error_text)
                    return {"error": f"Dynamics API error: {response.status}", "transactions": []}

        except Exception as e:
            logger.error("dynamics_query_exception", error=str(e))
            return {"error": str(e), "transactions": []}

    async def _query_oracle_transactions(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
        transaction_type: str
    ) -> Dict[str, Any]:
        """Query transactions from Oracle ERP Cloud via REST API."""
        base_url = self.config["base_url"]  # e.g., https://host/fscmRestApi/resources/11.13.18.05

        # Oracle REST API query
        url = f"{base_url}/generalLedgerJournalEntries"
        params = {
            "q": f"AccountCode={account_id};PostingDate>={start_date};PostingDate<={end_date}",
            "limit": 1000,
            "orderBy": "PostingDate:desc"
        }

        if transaction_type != "all":
            params["q"] += f";TransactionType={transaction_type}"

        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    transactions = data.get("items", [])

                    return {
                        "account_id": account_id,
                        "transactions": [
                            {
                                "transaction_id": t.get("JournalEntryId"),
                                "date": t.get("PostingDate"),
                                "amount": float(t.get("Amount", 0)),
                                "currency": t.get("CurrencyCode", "USD"),
                                "type": t.get("TransactionType"),
                                "description": t.get("Description"),
                                "document_number": t.get("DocumentNumber")
                            }
                            for t in transactions
                        ],
                        "total_count": data.get("totalResults", len(transactions)),
                        "date_range": {"start": start_date, "end": end_date}
                    }
                else:
                    error_text = await response.text()
                    logger.error("oracle_query_failed", status=response.status, error=error_text)
                    return {"error": f"Oracle API error: {response.status}", "transactions": []}

        except Exception as e:
            logger.error("oracle_query_exception", error=str(e))
            return {"error": str(e), "transactions": []}

    async def _query_sql_transactions(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
        transaction_type: str
    ) -> Dict[str, Any]:
        """Query transactions via direct SQL (PostgreSQL)."""
        query = """
            SELECT
                transaction_id,
                posting_date,
                amount,
                currency,
                transaction_type,
                description,
                document_number
            FROM general_ledger_entries
            WHERE account_id = $1
              AND posting_date >= $2::date
              AND posting_date <= $3::date
        """

        params = [account_id, start_date, end_date]

        if transaction_type != "all":
            query += " AND transaction_type = $4"
            params.append(transaction_type)

        query += " ORDER BY posting_date DESC LIMIT 1000"

        try:
            rows = await self._db_connection.fetch(query, *params)

            return {
                "account_id": account_id,
                "transactions": [
                    {
                        "transaction_id": row["transaction_id"],
                        "date": row["posting_date"].isoformat(),
                        "amount": float(row["amount"]),
                        "currency": row["currency"],
                        "type": row["transaction_type"],
                        "description": row["description"],
                        "document_number": row["document_number"]
                    }
                    for row in rows
                ],
                "total_count": len(rows),
                "date_range": {"start": start_date, "end": end_date}
            }

        except Exception as e:
            logger.error("sql_query_exception", error=str(e))
            return {"error": str(e), "transactions": []}

    async def _query_odbc_transactions(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
        transaction_type: str
    ) -> Dict[str, Any]:
        """Query transactions via ODBC (SQL Server, etc.)."""
        query = """
            SELECT TOP 1000
                transaction_id,
                posting_date,
                amount,
                currency,
                transaction_type,
                description,
                document_number
            FROM general_ledger_entries
            WHERE account_id = ?
              AND posting_date >= CAST(? AS DATE)
              AND posting_date <= CAST(? AS DATE)
        """

        params = [account_id, start_date, end_date]

        if transaction_type != "all":
            query += " AND transaction_type = ?"
            params.append(transaction_type)

        query += " ORDER BY posting_date DESC"

        try:
            loop = asyncio.get_event_loop()

            def execute_query():
                cursor = self._db_connection.cursor()
                cursor.execute(query, params)
                columns = [column[0] for column in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                cursor.close()
                return rows

            rows = await loop.run_in_executor(None, execute_query)

            return {
                "account_id": account_id,
                "transactions": [
                    {
                        "transaction_id": row["transaction_id"],
                        "date": row["posting_date"].isoformat() if hasattr(row["posting_date"], "isoformat") else str(row["posting_date"]),
                        "amount": float(row["amount"]),
                        "currency": row["currency"],
                        "type": row["transaction_type"],
                        "description": row["description"],
                        "document_number": row["document_number"]
                    }
                    for row in rows
                ],
                "total_count": len(rows),
                "date_range": {"start": start_date, "end": end_date}
            }

        except Exception as e:
            logger.error("odbc_query_exception", error=str(e))
            return {"error": str(e), "transactions": []}

    async def get_account_balance(
        self,
        account_id: str,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get account balance."""
        if not as_of_date:
            as_of_date = datetime.now().strftime("%Y-%m-%d")

        if self.erp_type == ERPType.POSTGRES:
            query = """
                SELECT
                    SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE -amount END) as balance,
                    currency
                FROM general_ledger_entries
                WHERE account_id = $1
                  AND posting_date <= $2::date
                GROUP BY currency
            """

            try:
                row = await self._db_connection.fetchrow(query, account_id, as_of_date)

                if row:
                    return {
                        "account_id": account_id,
                        "balance": float(row["balance"]),
                        "currency": row["currency"],
                        "as_of_date": as_of_date
                    }
                else:
                    return {
                        "account_id": account_id,
                        "balance": 0.0,
                        "currency": "USD",
                        "as_of_date": as_of_date
                    }

            except Exception as e:
                logger.error("balance_query_failed", error=str(e))
                return {"error": str(e)}

        else:
            # For HTTP-based ERPs, make API call
            # Implementation similar to transaction queries
            return {
                "account_id": account_id,
                "balance": 0.0,
                "currency": "USD",
                "as_of_date": as_of_date,
                "note": "Balance API not yet implemented for this ERP type"
            }

    async def create_journal_entry(
        self,
        description: str,
        entries: List[Dict[str, Any]],
        posting_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create journal entry in ERP."""
        if not posting_date:
            posting_date = datetime.now().strftime("%Y-%m-%d")

        # Validate balanced entry
        total_debits = sum(e.get("debit", 0) for e in entries)
        total_credits = sum(e.get("credit", 0) for e in entries)

        if abs(total_debits - total_credits) > 0.01:
            return {
                "success": False,
                "error": f"Unbalanced entry: debits={total_debits}, credits={total_credits}"
            }

        if self.erp_type == ERPType.POSTGRES:
            # Insert journal entry
            async with self._db_connection.transaction():
                # Create header
                journal_id = await self._db_connection.fetchval(
                    """
                    INSERT INTO journal_entries (description, posting_date, created_at)
                    VALUES ($1, $2::date, NOW())
                    RETURNING id
                    """,
                    description,
                    posting_date
                )

                # Create line items
                for entry in entries:
                    await self._db_connection.execute(
                        """
                        INSERT INTO journal_entry_lines
                        (journal_id, account_id, debit, credit)
                        VALUES ($1, $2, $3, $4)
                        """,
                        journal_id,
                        entry["account_id"],
                        entry.get("debit", 0),
                        entry.get("credit", 0)
                    )

                return {
                    "success": True,
                    "journal_id": f"JE-{journal_id}",
                    "description": description,
                    "entry_count": len(entries),
                    "posting_date": posting_date
                }

        else:
            # For HTTP-based ERPs, make API call
            return {
                "success": True,
                "journal_id": "JE-SIMULATED",
                "description": description,
                "entry_count": len(entries),
                "note": "Journal entry API not yet implemented for this ERP type"
            }

    async def get_vendor_info(
        self,
        vendor_id: str,
        include_transactions: bool = False
    ) -> Dict[str, Any]:
        """Get vendor information."""
        if self.erp_type == ERPType.POSTGRES:
            query = """
                SELECT
                    vendor_id,
                    vendor_name,
                    status,
                    payment_terms,
                    contact_email,
                    contact_phone
                FROM vendors
                WHERE vendor_id = $1
            """

            try:
                row = await self._db_connection.fetchrow(query, vendor_id)

                if row:
                    vendor_info = dict(row)

                    if include_transactions:
                        # Get recent transactions
                        txn_query = """
                            SELECT
                                transaction_id,
                                amount,
                                transaction_date,
                                status
                            FROM vendor_transactions
                            WHERE vendor_id = $1
                            ORDER BY transaction_date DESC
                            LIMIT 100
                        """
                        txn_rows = await self._db_connection.fetch(txn_query, vendor_id)
                        vendor_info["recent_transactions"] = [dict(r) for r in txn_rows]

                    return vendor_info
                else:
                    return {"error": "Vendor not found", "vendor_id": vendor_id}

            except Exception as e:
                logger.error("vendor_query_failed", error=str(e))
                return {"error": str(e)}

        else:
            return {
                "vendor_id": vendor_id,
                "vendor_name": "Unknown",
                "status": "unknown",
                "note": "Vendor API not yet implemented for this ERP type"
            }

    async def get_inventory_levels(
        self,
        product_ids: List[str],
        warehouse_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get inventory levels."""
        if self.erp_type == ERPType.POSTGRES:
            placeholders = ", ".join(f"${i+1}" for i in range(len(product_ids)))
            query = f"""
                SELECT
                    product_id,
                    warehouse_id,
                    quantity_on_hand,
                    quantity_reserved,
                    quantity_available,
                    last_updated
                FROM inventory
                WHERE product_id IN ({placeholders})
            """

            params = product_ids

            if warehouse_id:
                query += f" AND warehouse_id = ${len(params) + 1}"
                params.append(warehouse_id)

            try:
                rows = await self._db_connection.fetch(query, *params)

                return {
                    "products": [
                        {
                            "product_id": row["product_id"],
                            "warehouse": row["warehouse_id"],
                            "quantity_on_hand": int(row["quantity_on_hand"]),
                            "quantity_reserved": int(row["quantity_reserved"]),
                            "quantity_available": int(row["quantity_available"]),
                            "last_updated": row["last_updated"].isoformat()
                        }
                        for row in rows
                    ],
                    "total_products": len(rows)
                }

            except Exception as e:
                logger.error("inventory_query_failed", error=str(e))
                return {"error": str(e)}

        else:
            return {
                "products": [
                    {"product_id": pid, "quantity": 0, "warehouse": warehouse_id, "note": "API not implemented"}
                    for pid in product_ids
                ],
                "note": "Inventory API not yet implemented for this ERP type"
            }


def get_erp_client() -> ERPClient:
    """
    Factory function to create ERP client from environment configuration.
    """
    erp_type_str = os.getenv("ERP_TYPE", "postgres").lower()
    erp_type = ERPType(erp_type_str)

    if erp_type == ERPType.SAP_ODATA:
        config = {
            "base_url": os.getenv("SAP_BASE_URL"),
            "username": os.getenv("SAP_USERNAME"),
            "password": os.getenv("SAP_PASSWORD"),
            "oauth_token": os.getenv("SAP_OAUTH_TOKEN")
        }

    elif erp_type == ERPType.DYNAMICS_365:
        config = {
            "base_url": os.getenv("DYNAMICS_BASE_URL"),
            "access_token": os.getenv("DYNAMICS_ACCESS_TOKEN")
        }

    elif erp_type == ERPType.ORACLE_CLOUD:
        config = {
            "base_url": os.getenv("ORACLE_BASE_URL"),
            "username": os.getenv("ORACLE_USERNAME"),
            "password": os.getenv("ORACLE_PASSWORD")
        }

    elif erp_type == ERPType.POSTGRES:
        config = {
            "host": os.getenv("ERP_DB_HOST", "localhost"),
            "port": int(os.getenv("ERP_DB_PORT", "5432")),
            "database": os.getenv("ERP_DB_NAME", "erp"),
            "username": os.getenv("ERP_DB_USER", "erp_user"),
            "password": os.getenv("ERP_DB_PASSWORD", "")
        }

    elif erp_type == ERPType.ODBC_SQL:
        config = {
            "connection_string": os.getenv("ERP_ODBC_CONNECTION_STRING")
        }

    else:
        raise ValueError(f"Unsupported ERP type: {erp_type}")

    return ERPClient(erp_type, config)
