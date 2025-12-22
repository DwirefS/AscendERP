"""
Example: Edge Deployment via Azure Arc and Stack HCI

Demonstrates ANTS agents running on-premises for ultra-low latency
physical world control with hybrid cloud coordination.

Architecture:
- Cloud: Global orchestration, analytics, cross-site optimization
- Edge (Arc/HCI): Real-time control, local inference, <10ms latency
- Hybrid: Critical ops local, telemetry synced to cloud hourly

Use cases:
- Manufacturing: Assembly line control with <10ms response
- Warehouses: Robot coordination without internet dependency
- Facilities: HVAC control with offline capability
- Agriculture: Irrigation even if cloud disconnected
"""
import asyncio
from src.core.edge.arc_agent_manager import (
    ArcAgentManager,
    EdgeDeploymentMode,
    EdgeCapability,
    create_arc_agent_manager
)


async def example_1_deploy_edge_agents():
    """Example 1: Deploy ANTS agents to Azure Arc."""
    print("=" * 60)
    print("Example 1: Deploy Edge Agents via Azure Arc")
    print("=" * 60 + "\n")

    # Initialize Arc manager for factory floor
    arc_manager = create_arc_agent_manager(
        arc_cluster="factory-floor-chicago-01",
        region="on-premises-chicago",
        enable_simulation=True
    )

    print("Deploying ANTS agents to on-premises Azure Arc cluster...\n")

    # Deploy manufacturing control agent (full edge mode)
    print("1. Manufacturing Control Agent (Full Edge Mode):")
    print("   - Zero cloud dependency")
    print("   - Local model inference")
    print("   - Offline operation\n")

    config = await arc_manager.deploy_agent(
        agent_id="assembly_line_controller_01",
        agent_type="manufacturing.assembly_control",
        local_models=["gpt-4-turbo-edge", "claude-sonnet-edge"],
        deployment_mode=EdgeDeploymentMode.FULL_EDGE,
        capabilities=[
            EdgeCapability.LOCAL_INFERENCE,
            EdgeCapability.LOCAL_PHEROMONES,
            EdgeCapability.OFFLINE_MODE,
            EdgeCapability.GPU_INFERENCE
        ],
        cpu_cores=8,
        memory_gb=32,
        gpu_enabled=True  # NVIDIA GPU for local inference
    )

    print(f"   Agent ID: {config.agent_id}")
    print(f"   Cluster: {config.arc_cluster}")
    print(f"   Mode: {config.deployment_mode.value}")
    print(f"   Local models: {', '.join(config.local_models)}")
    print(f"   Resources: {config.resource_limits['cpu_cores']} cores, {config.resource_limits['memory_gb']} GB RAM")
    print(f"   GPU: {config.resource_limits['gpu_enabled']}")
    print()

    # Deploy warehouse robot coordinator (hybrid mode)
    print("2. Warehouse Robot Coordinator (Hybrid Mode):")
    print("   - Critical commands local (<10ms)")
    print("   - Analytics synced to cloud hourly")
    print("   - Fallback to offline if internet down\n")

    config2 = await arc_manager.deploy_agent(
        agent_id="warehouse_robot_coordinator_01",
        agent_type="warehouse.robot_control",
        local_models=["claude-haiku-edge"],  # Fast, lightweight
        deployment_mode=EdgeDeploymentMode.HYBRID,
        capabilities=[
            EdgeCapability.LOCAL_INFERENCE,
            EdgeCapability.LOCAL_PHEROMONES,
            EdgeCapability.OFFLINE_MODE
        ],
        cpu_cores=4,
        memory_gb=16,
        gpu_enabled=False
    )

    print(f"   Agent ID: {config2.agent_id}")
    print(f"   Mode: {config2.deployment_mode.value}")
    print(f"   Sync interval: {config2.sync_interval_seconds}s (hourly)")
    print()

    print(f"Total edge agents deployed: {arc_manager.stats['total_edge_agents']}")
    print()

    return arc_manager


async def example_2_deploy_local_models():
    """Example 2: Deploy model weights to edge via ANF."""
    print("=" * 60)
    print("Example 2: Deploy Models to Edge via ANF")
    print("=" * 60 + "\n")

    arc_manager = await example_1_deploy_edge_agents()

    print("Deploying model weights from cloud ANF to on-prem ANF...\n")

    print("Architecture:")
    print("┌────────────────────────────────────────┐")
    print("│  Cloud ANF (westus2)                   │")
    print("│  - GPT-4 Turbo: 85 GB                  │")
    print("│  - Claude Sonnet: 75 GB                │")
    print("└──────────────┬─────────────────────────┘")
    print("               │ ANF Snapshot + Clone")
    print("               │ (via Azure Arc)")
    print("               ▼")
    print("┌────────────────────────────────────────┐")
    print("│  On-Prem ANF (Chicago Factory)         │")
    print("│  - Models cloned to local volume       │")
    print("│  - Mounted to edge agent containers    │")
    print("│  - Zero cloud latency for inference    │")
    print("└────────────────────────────────────────┘")
    print()

    # Deploy models to edge
    result = await arc_manager.deploy_local_models(
        agent_id="assembly_line_controller_01",
        models=["gpt-4-turbo-edge", "claude-sonnet-edge"],
        anf_volume="/mnt/anf-edge/models"
    )

    print("Model deployment complete:")
    print(f"  Agent: {result['agent_id']}")
    print(f"  Models deployed: {result['models_deployed']}")
    print(f"  Total size: {result['total_size_gb']} GB")
    print()

    for model in result['models']:
        print(f"  - {model['model_id']}")
        print(f"    Volume: {model['volume']}")
        print(f"    Size: {model['size_gb']} GB")
        print(f"    Status: {model['status']}")
        print()

    print("Benefits:")
    print("✓ Models stored locally on ANF (sub-ms latency)")
    print("✓ ANF clone from cloud (instant, no data copy)")
    print("✓ Local inference: 5-10ms vs 50-200ms cloud")
    print("✓ Works offline (no internet required)")
    print()


async def example_3_local_command_execution():
    """Example 3: Execute commands with ultra-low latency."""
    print("=" * 60)
    print("Example 3: Ultra-Low Latency Local Commands")
    print("=" * 60 + "\n")

    arc_manager = await example_1_deploy_edge_agents()

    print("Scenario: Assembly line needs real-time robot control\n")

    print("Latency Comparison:")
    print("  Cloud agent → Device: 50-200ms (internet round-trip)")
    print("  Edge agent → Device:  <10ms (local LAN)")
    print("  Improvement: 10-20x faster!\n")

    # Execute local commands
    commands = [
        {
            "name": "Robot arm: Pick component from conveyor",
            "command": "move_robot",
            "device": "robot_arm_station_03",
            "params": {"position": {"x": 10, "y": 5, "z": 2}, "speed": 0.9}
        },
        {
            "name": "Conveyor: Adjust speed based on throughput",
            "command": "set_speed",
            "device": "conveyor_belt_01",
            "params": {"speed": 0.75}
        },
        {
            "name": "Quality sensor: Trigger inspection",
            "command": "read_sensor",
            "device": "vision_sensor_qc_01",
            "params": {}
        }
    ]

    print("Executing commands on edge agent...\n")

    for cmd_info in commands:
        result = await arc_manager.execute_local_command(
            agent_id="assembly_line_controller_01",
            command=cmd_info["command"],
            target_device=cmd_info["device"],
            params=cmd_info["params"]
        )

        print(f"✓ {cmd_info['name']}")
        print(f"  Device: {result['device']}")
        print(f"  Latency: {result['latency_ms']}ms")
        print(f"  Cloud round-trip: {result['cloud_round_trip']}")
        print(f"  Executed: {result['executed_at']}")
        print()

    metrics = arc_manager.get_edge_metrics("assembly_line_controller_01")
    print(f"Total commands executed: {metrics.commands_executed}")
    print(f"Average latency: {metrics.latency_ms}ms")
    print()

    print("→ Critical operations execute locally with <10ms latency")
    print("→ No internet dependency for real-time control")
    print()


async def example_4_hybrid_sync_to_cloud():
    """Example 4: Hybrid mode - sync telemetry to cloud."""
    print("=" * 60)
    print("Example 4: Hybrid Cloud Sync")
    print("=" * 60 + "\n")

    arc_manager = await example_1_deploy_edge_agents()

    print("Hybrid Architecture:")
    print("  - Critical operations: Execute on-premises (<10ms)")
    print("  - Telemetry: Sync to cloud hourly")
    print("  - Analytics: Cloud processes historical data")
    print("  - Optimization: Cloud calculates, edge executes\n")

    # Execute local commands (not synced immediately)
    for i in range(5):
        await arc_manager.execute_local_command(
            agent_id="warehouse_robot_coordinator_01",
            command="move_robot",
            target_device=f"robot_{i+1}",
            params={"position": {"x": i*2, "y": i*3}}
        )

    print("Executed 5 robot control commands locally (no cloud sync)\n")

    # Periodic sync to cloud
    print("Syncing telemetry to cloud (hourly scheduled sync)...\n")

    sync_result = await arc_manager.sync_to_cloud(
        agent_id="warehouse_robot_coordinator_01",
        sync_type="telemetry"
    )

    print(f"Sync complete:")
    print(f"  Agent: {sync_result['agent_id']}")
    print(f"  Type: {sync_result['sync_type']}")
    print(f"  Commands synced: {sync_result['commands_synced']}")
    print(f"  Timestamp: {sync_result['timestamp']}")
    print()

    print("Cloud processes synced data for:")
    print("✓ Long-term trend analysis")
    print("✓ Cross-site optimization")
    print("✓ Predictive maintenance")
    print("✓ Global swarm coordination")
    print()


async def example_5_offline_mode():
    """Example 5: Offline mode for air-gapped environments."""
    print("=" * 60)
    print("Example 5: Offline Mode (Zero Cloud Dependency)")
    print("=" * 60 + "\n")

    arc_manager = await example_1_deploy_edge_agents()

    print("Scenario: Internet outage or secure air-gapped environment\n")

    # Enable offline mode
    result = await arc_manager.enable_offline_mode(
        agent_id="assembly_line_controller_01"
    )

    print(f"Offline mode enabled:")
    print(f"  Agent: {result['agent_id']}")
    print(f"  Cloud connected: {result['cloud_connected']}")
    print(f"  Message: {result['message']}")
    print()

    # Verify agent can still operate
    print("Testing local operations in offline mode...\n")

    cmd_result = await arc_manager.execute_local_command(
        agent_id="assembly_line_controller_01",
        command="move_robot",
        target_device="robot_arm_station_01",
        params={"position": {"x": 5, "y": 5}}
    )

    print(f"✓ Command executed successfully")
    print(f"  Latency: {cmd_result['latency_ms']}ms")
    print(f"  Cloud dependency: None")
    print()

    print("Offline capabilities:")
    print("✓ Local model inference (GPT-4, Claude on-prem)")
    print("✓ Local pheromone messaging (edge Event Hub)")
    print("✓ Local state persistence (edge Cosmos DB)")
    print("✓ 100% uptime even without internet")
    print()

    print("Use cases:")
    print("  • Secure facilities (air-gapped)")
    print("  • Remote locations (unreliable internet)")
    print("  • Critical infrastructure (maximum reliability)")
    print()


async def example_6_edge_statistics():
    """Example 6: Edge deployment statistics."""
    print("=" * 60)
    print("Example 6: Edge Deployment Statistics")
    print("=" * 60 + "\n")

    arc_manager = await example_1_deploy_edge_agents()

    # Execute some commands
    await arc_manager.execute_local_command(
        agent_id="assembly_line_controller_01",
        command="test",
        target_device="test_device",
        params={}
    )

    stats = arc_manager.get_stats()

    print("Edge Deployment Statistics:\n")
    print(f"Arc Cluster: {stats['arc_cluster']}")
    print(f"Region: {stats['region']}")
    print(f"Total edge agents: {stats['total_edge_agents']}")
    print(f"Agents online: {stats['agents_online']}")
    print(f"Total commands: {stats['total_commands']}")
    print(f"Avg latency: {stats['avg_latency_ms']:.2f}ms")
    print()

    print("By deployment mode:")
    for mode, count in stats['by_deployment_mode'].items():
        print(f"  {mode}: {count} agents")
    print()

    print("By capability:")
    for cap, count in stats['by_capability'].items():
        if count > 0:
            print(f"  {cap}: {count} agents")
    print()

    print("Latency comparison:")
    print(f"  Edge (local): {stats['avg_latency_ms']:.2f}ms")
    print(f"  Cloud (typical): 50-200ms")
    print(f"  Improvement: {100 * (100 / stats['avg_latency_ms']):.0f}x faster!")
    print()


async def example_7_multi_site_deployment():
    """Example 7: Multi-site edge deployment."""
    print("=" * 60)
    print("Example 7: Multi-Site Edge Deployment")
    print("=" * 60 + "\n")

    print("Enterprise Deployment: 3 manufacturing sites\n")

    sites = [
        ("factory-chicago", "Chicago Assembly Plant"),
        ("factory-dallas", "Dallas Distribution Center"),
        ("factory-seattle", "Seattle Production Facility")
    ]

    managers = []

    for arc_cluster, site_name in sites:
        print(f"Deploying to: {site_name}")

        manager = create_arc_agent_manager(
            arc_cluster=arc_cluster,
            region=f"on-premises-{arc_cluster.split('-')[1]}",
            enable_simulation=True
        )

        # Deploy edge agent at each site
        await manager.deploy_agent(
            agent_id=f"{arc_cluster.split('-')[1]}_controller",
            agent_type="manufacturing.site_control",
            local_models=["gpt-4-turbo-edge"],
            deployment_mode=EdgeDeploymentMode.HYBRID,
            capabilities=[
                EdgeCapability.LOCAL_INFERENCE,
                EdgeCapability.LOCAL_PHEROMONES,
                EdgeCapability.OFFLINE_MODE
            ]
        )

        managers.append(manager)
        print(f"  ✓ Edge agent deployed")
        print()

    print("Multi-site architecture:")
    print("┌──────────────────────────────────────────────────┐")
    print("│           Cloud Swarm Orchestrator               │")
    print("│   - Cross-site optimization                      │")
    print("│   - Global analytics                             │")
    print("└────────┬─────────────┬────────────┬──────────────┘")
    print("         │             │            │")
    print("    Azure Arc     Azure Arc    Azure Arc")
    print("         │             │            │")
    print("         ▼             ▼            ▼")
    print("   Chicago        Dallas       Seattle")
    print("   Edge Agent    Edge Agent    Edge Agent")
    print("   (<10ms)       (<10ms)       (<10ms)")
    print()

    print("Benefits:")
    print("✓ Local control: <10ms latency at each site")
    print("✓ Site autonomy: Operates offline if internet down")
    print("✓ Cloud coordination: Global optimization across sites")
    print("✓ Data sovereignty: Sensitive data stays on-prem")
    print()


async def main():
    """Run all edge deployment examples."""
    print("\n")
    print("█" * 60)
    print("ANTS Edge Deployment Examples")
    print("Azure Arc + Stack HCI: Ultra-Low Latency Control")
    print("█" * 60)
    print("\n")

    await example_1_deploy_edge_agents()
    await example_2_deploy_local_models()
    await example_3_local_command_execution()
    await example_4_hybrid_sync_to_cloud()
    await example_5_offline_mode()
    await example_6_edge_statistics()
    await example_7_multi_site_deployment()

    print("=" * 60)
    print("All Examples Complete")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("✓ Edge agents on Azure Arc/Stack HCI for <10ms latency")
    print("✓ Local model inference (GPT-4, Claude on-premises)")
    print("✓ Zero cloud dependency for critical operations")
    print("✓ Hybrid mode: Local execution, cloud analytics")
    print("✓ Offline mode: 100% uptime without internet")
    print("✓ Multi-site: Global coordination + local autonomy")
    print()
    print("Deployment modes:")
    print("  • Full Edge: 100% on-prem, zero cloud dependency")
    print("  • Hybrid: Critical ops local, telemetry to cloud")
    print("  • Cloud-First: Cloud primary, edge backup")
    print()
    print("Real-time physical world control achieved!")
    print("No cloud latency for critical manufacturing operations.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
