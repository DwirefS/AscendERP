"""
ANTS Control CLI Implementation.
Concrete implementations for antsctl commands.
"""
import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncio
import structlog
import asyncpg
from kubernetes import client, config as k8s_config
from kubernetes.stream import stream

logger = structlog.get_logger()


class TerraformDeployer:
    """Handles Terraform infrastructure deployment."""

    def __init__(self, terraform_dir: str, environment: str):
        self.terraform_dir = Path(terraform_dir)
        self.environment = environment
        self.tfvars_file = self.terraform_dir / f"{environment}.tfvars"

    async def plan(self, spec: Dict[str, Any]) -> str:
        """Generate Terraform plan."""
        # Write spec to tfvars
        await self._write_tfvars(spec)

        # Run terraform plan
        cmd = [
            "terraform", "plan",
            f"-var-file={self.tfvars_file}",
            "-out=tfplan"
        ]

        result = subprocess.run(
            cmd,
            cwd=self.terraform_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"Terraform plan failed: {result.stderr}")

        return result.stdout

    async def apply(self, auto_approve: bool = False) -> str:
        """Apply Terraform plan."""
        cmd = ["terraform", "apply"]

        if auto_approve:
            cmd.append("-auto-approve")

        cmd.append("tfplan")

        result = subprocess.run(
            cmd,
            cwd=self.terraform_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"Terraform apply failed: {result.stderr}")

        return result.stdout

    async def destroy(self, auto_approve: bool = False) -> str:
        """Destroy Terraform-managed infrastructure."""
        cmd = ["terraform", "destroy", f"-var-file={self.tfvars_file}"]

        if auto_approve:
            cmd.append("-auto-approve")

        result = subprocess.run(
            cmd,
            cwd=self.terraform_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"Terraform destroy failed: {result.stderr}")

        return result.stdout

    async def _write_tfvars(self, spec: Dict[str, Any]):
        """Convert spec to tfvars format."""
        tfvars_content = []

        # Extract terraform variables from spec
        if 'tenant' in spec:
            tfvars_content.append(f'tenant_name = "{spec["tenant"]["name"]}"')
            tfvars_content.append(f'tenant_id = "{spec["tenant"]["id"]}"')

        if 'regions' in spec:
            regions_str = json.dumps(spec['regions'])
            tfvars_content.append(f'regions = {regions_str}')

        if 'infrastructure' in spec:
            infra = spec['infrastructure']

            if 'anf' in infra:
                tfvars_content.append(f'anf_capacity_pool_size_tb = {infra["anf"].get("capacity_tb", 4)}')

            if 'aks' in infra:
                tfvars_content.append(f'aks_node_count = {infra["aks"].get("node_count", 3)}')
                tfvars_content.append(f'aks_vm_size = "{infra["aks"].get("vm_size", "Standard_D4s_v3")}"')

        # Write to file
        with open(self.tfvars_file, 'w') as f:
            f.write('\n'.join(tfvars_content))


class HelmDeployer:
    """Handles Helm chart deployment."""

    def __init__(self, charts_dir: str, namespace: str = "ants"):
        self.charts_dir = Path(charts_dir)
        self.namespace = namespace

    async def install_chart(
        self,
        chart_name: str,
        release_name: str,
        values: Optional[Dict] = None
    ) -> str:
        """Install Helm chart."""
        chart_path = self.charts_dir / chart_name

        cmd = [
            "helm", "install",
            release_name,
            str(chart_path),
            "--namespace", self.namespace,
            "--create-namespace"
        ]

        # Add values file if provided
        if values:
            values_file = Path(f"/tmp/{release_name}_values.yaml")
            import yaml
            with open(values_file, 'w') as f:
                yaml.dump(values, f)
            cmd.extend(["--values", str(values_file)])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Helm install failed: {result.stderr}")

        return result.stdout

    async def upgrade_chart(
        self,
        release_name: str,
        chart_name: str,
        values: Optional[Dict] = None
    ) -> str:
        """Upgrade Helm release."""
        chart_path = self.charts_dir / chart_name

        cmd = [
            "helm", "upgrade",
            release_name,
            str(chart_path),
            "--namespace", self.namespace
        ]

        if values:
            values_file = Path(f"/tmp/{release_name}_values.yaml")
            import yaml
            with open(values_file, 'w') as f:
                yaml.dump(values, f)
            cmd.extend(["--values", str(values_file)])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Helm upgrade failed: {result.stderr}")

        return result.stdout

    async def uninstall_chart(self, release_name: str) -> str:
        """Uninstall Helm release."""
        cmd = ["helm", "uninstall", release_name, "--namespace", self.namespace]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Helm uninstall failed: {result.stderr}")

        return result.stdout

    async def list_releases(self) -> List[Dict]:
        """List Helm releases."""
        cmd = [
            "helm", "list",
            "--namespace", self.namespace,
            "--output", "json"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Helm list failed: {result.stderr}")

        return json.loads(result.stdout)


class KubernetesManager:
    """Manages Kubernetes resources."""

    def __init__(self, namespace: str = "ants"):
        self.namespace = namespace
        # Load kubeconfig
        k8s_config.load_kube_config()
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()

    async def get_deployment_status(self) -> Dict[str, Any]:
        """Get status of all deployments."""
        deployments = self.apps_v1.list_namespaced_deployment(self.namespace)

        status = {}
        for dep in deployments.items:
            name = dep.metadata.name
            status[name] = {
                "status": "healthy" if dep.status.ready_replicas == dep.status.replicas else "degraded",
                "replicas": f"{dep.status.ready_replicas}/{dep.status.replicas}",
                "version": dep.metadata.labels.get("version", "unknown")
            }

        return status

    async def scale_deployment(self, deployment_name: str, replicas: int):
        """Scale a deployment."""
        # Get current deployment
        deployment = self.apps_v1.read_namespaced_deployment(
            deployment_name,
            self.namespace
        )

        # Update replicas
        deployment.spec.replicas = replicas

        # Apply update
        self.apps_v1.patch_namespaced_deployment(
            deployment_name,
            self.namespace,
            deployment
        )

    async def get_logs(
        self,
        pod_name: str,
        container: Optional[str] = None,
        lines: int = 100,
        follow: bool = False
    ) -> List[str]:
        """Get pod logs."""
        if follow:
            # Stream logs
            log_stream = self.core_v1.read_namespaced_pod_log(
                pod_name,
                self.namespace,
                container=container,
                follow=True,
                _preload_content=False
            )

            logs = []
            for line in log_stream:
                logs.append(line.decode('utf-8'))
                if len(logs) >= lines:
                    break

            return logs
        else:
            # Get logs
            log = self.core_v1.read_namespaced_pod_log(
                pod_name,
                self.namespace,
                container=container,
                tail_lines=lines
            )

            return log.split('\n')

    async def exec_pod_command(
        self,
        pod_name: str,
        command: List[str],
        container: Optional[str] = None
    ) -> str:
        """Execute command in pod."""
        resp = stream(
            self.core_v1.connect_get_namespaced_pod_exec,
            pod_name,
            self.namespace,
            container=container,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False
        )

        return resp


class DatabaseManager:
    """Manages PostgreSQL database operations."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create connection pool."""
        self.pool = await asyncpg.create_pool(self.connection_string)

    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()

    async def get_agents(self, tenant_id: Optional[str] = None) -> List[Dict]:
        """Get registered agents from database."""
        query = """
            SELECT
                agent_id,
                agent_type,
                status,
                created_at,
                last_active_at
            FROM agents.registry
        """

        params = []
        if tenant_id:
            query += " WHERE tenant_id = $1"
            params.append(tenant_id)

        query += " ORDER BY created_at DESC"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows]

    async def search_memory(
        self,
        query: str,
        tenant_id: str,
        memory_type: str = "semantic",
        limit: int = 10
    ) -> List[Dict]:
        """Search memory substrate using vector similarity."""
        if memory_type == "semantic":
            # This would need embedding service
            # For now, simple text search
            search_query = """
                SELECT
                    id,
                    content,
                    metadata,
                    created_at
                FROM memory.semantic
                WHERE tenant_id = $1
                  AND content ILIKE $2
                ORDER BY created_at DESC
                LIMIT $3
            """

            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    search_query,
                    tenant_id,
                    f"%{query}%",
                    limit
                )

            return [dict(row) for row in rows]

        elif memory_type == "episodic":
            query_sql = """
                SELECT
                    id,
                    agent_id,
                    trace_data,
                    created_at
                FROM memory.episodic
                WHERE tenant_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """

            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query_sql, tenant_id, limit)

            return [dict(row) for row in rows]

        else:
            return []

    async def get_metrics(self, environment: str) -> Dict[str, Any]:
        """Get CLEAR metrics from database."""
        query = """
            SELECT
                metric_name,
                metric_value,
                metric_timestamp
            FROM metrics.clear_metrics
            WHERE environment = $1
              AND metric_timestamp > NOW() - INTERVAL '1 hour'
            ORDER BY metric_timestamp DESC
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, environment)

        # Aggregate metrics
        metrics = {
            "cost": {},
            "latency": {},
            "efficacy": {},
            "assurance": {},
            "reliability": {}
        }

        for row in rows:
            metric_name = row['metric_name']
            metric_value = row['metric_value']

            if metric_name.startswith('cost_'):
                metrics['cost'][metric_name] = metric_value
            elif metric_name.startswith('latency_'):
                metrics['latency'][metric_name] = metric_value
            # ... etc

        return metrics


class AgentInvoker:
    """Invokes agents via API gateway."""

    def __init__(self, api_gateway_url: str, api_key: str):
        self.api_gateway_url = api_gateway_url
        self.api_key = api_key

    async def invoke(
        self,
        agent_type: str,
        input_data: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Invoke an agent through API gateway."""
        import aiohttp

        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "agent_type": agent_type,
            "input_data": input_data,
            "tenant_id": tenant_id
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_gateway_url}/api/v1/agents/invoke",
                headers=headers,
                json=payload
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise RuntimeError(f"Agent invocation failed: {error}")

                return await resp.json()

    async def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """Get agent status."""
        import aiohttp

        headers = {"X-API-Key": self.api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.api_gateway_url}/api/v1/agents/{agent_id}",
                headers=headers
            ) as resp:
                return await resp.json()


class PolicyManager:
    """Manages OPA policies."""

    def __init__(self, policies_dir: str):
        self.policies_dir = Path(policies_dir)

    async def test_policies(self) -> Dict[str, Any]:
        """Run OPA policy tests."""
        cmd = ["opa", "test", str(self.policies_dir), "-v"]

        result = subprocess.run(cmd, capture_output=True, text=True)

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr
        }

    async def validate_policy(self, policy_file: str) -> Dict[str, Any]:
        """Validate a policy file."""
        cmd = ["opa", "check", policy_file]

        result = subprocess.run(cmd, capture_output=True, text=True)

        return {
            "valid": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr
        }

    async def evaluate_policy(
        self,
        policy_path: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate a policy with input data."""
        import tempfile

        # Write input to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(input_data, f)
            input_file = f.name

        try:
            cmd = [
                "opa", "eval",
                "--data", policy_path,
                "--input", input_file,
                "--format", "json",
                "data"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                return {"error": result.stderr}

            return json.loads(result.stdout)

        finally:
            os.unlink(input_file)
