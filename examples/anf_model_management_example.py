"""
Example: ANF-Powered Model Weight Management

Demonstrates Azure NetApp Files advanced features for AI model lifecycle:
- Snapshots: Instant version control (copy-on-write, space-efficient)
- Clones: Fast deployment without data copying
- Regional Replication: Multi-region model distribution
- Volume Tiering: Hot/warm/cold model optimization
- ANF Backups: Long-term retention and DR

This is the "memory substrate" from the ANTS whitepaper:
ANF as the persistent enterprise mind where model artifacts live.
"""
import asyncio
from src.core.storage.anf_model_manager import (
    ANFModelManager,
    ANFTier,
    create_anf_model_manager
)


async def example_1_register_models():
    """Example 1: Register AI models in ANF."""
    print("=" * 60)
    print("Example 1: Register AI Models in ANF")
    print("=" * 60 + "\n")

    # Initialize ANF model manager (simulation mode)
    manager = create_anf_model_manager(
        subscription_id="12345678-1234-1234-1234-123456789012",
        resource_group="ants-production",
        anf_account="ants-models",
        pool_name="model-weights",
        enable_simulation=True  # Simulation for demo
    )

    print("Registering enterprise AI models...\n")

    # Register hot models (frequently accessed)
    models_hot = [
        {
            "model_id": "gpt-4-turbo-2024-04-09",
            "model_name": "GPT-4 Turbo",
            "provider": "OpenAI",
            "version": "2024-04-09",
            "model_path": "/anf/models/openai/gpt-4-turbo",
            "size_gb": 85.0,
            "tier": ANFTier.PREMIUM,  # Hot: 64 MiB/s per TiB
            "replicate_to": ["westus2", "eastus2", "westeurope"],  # Multi-region
            "snapshot_policy": "hourly"
        },
        {
            "model_id": "claude-opus-4",
            "model_name": "Claude Opus 4",
            "provider": "Anthropic",
            "version": "4.0",
            "model_path": "/anf/models/anthropic/claude-opus-4",
            "size_gb": 120.0,
            "tier": ANFTier.PREMIUM,
            "replicate_to": ["westus2", "eastus2"],
            "snapshot_policy": "hourly"
        }
    ]

    # Register warm models (occasionally accessed)
    models_warm = [
        {
            "model_id": "claude-sonnet-4",
            "model_name": "Claude Sonnet 4",
            "provider": "Anthropic",
            "version": "4.0",
            "model_path": "/anf/models/anthropic/claude-sonnet-4",
            "size_gb": 75.0,
            "tier": ANFTier.STANDARD,  # Warm: 16 MiB/s per TiB
            "replicate_to": ["westus2"],
            "snapshot_policy": "daily"
        },
        {
            "model_id": "gemini-1.5-pro",
            "model_name": "Gemini 1.5 Pro",
            "provider": "Google",
            "version": "1.5",
            "model_path": "/anf/models/google/gemini-1.5-pro",
            "size_gb": 95.0,
            "tier": ANFTier.STANDARD,
            "replicate_to": ["westus2"],
            "snapshot_policy": "daily"
        }
    ]

    # Register all models
    for model_data in models_hot + models_warm:
        metadata = await manager.register_model(**model_data)
        print(f"Registered: {metadata.model_name}")
        print(f"  Model ID: {metadata.model_id}")
        print(f"  Provider: {metadata.provider}")
        print(f"  Size: {metadata.size_gb} GB")
        print(f"  Tier: {metadata.tier.value}")
        print(f"  Regions: {', '.join(metadata.replicated_regions)}")
        print()

    print(f"Total models registered: {manager.stats['total_models']}")
    print(f"Total storage: {manager.stats['total_storage_gb']:.1f} GB\n")
    print()

    return manager


async def example_2_version_control_snapshots():
    """Example 2: Version control via ANF snapshots."""
    print("=" * 60)
    print("Example 2: Version Control via ANF Snapshots")
    print("=" * 60 + "\n")

    manager = await example_1_register_models()

    print("Scenario: Model fine-tuning creates new versions\n")

    # Create snapshots for different versions
    versions = [
        ("gpt-4-turbo-2024-04-09", "v1.0.0", "Initial production version"),
        ("gpt-4-turbo-2024-04-09", "v1.1.0", "Finance domain fine-tuning"),
        ("gpt-4-turbo-2024-04-09", "v1.2.0", "Improved accuracy on reconciliation")
    ]

    for model_id, version, description in versions:
        snapshot = await manager.create_snapshot(
            model_id=model_id,
            version=version,
            description=description
        )

        print(f"Created snapshot: {snapshot.snapshot_name}")
        print(f"  Model: {model_id}")
        print(f"  Version: {version}")
        print(f"  Size: {snapshot.size_gb} GB (initial)")
        print(f"  Created: {snapshot.created_at}")
        print()

    print("Benefits of ANF Snapshots:")
    print("✓ Instant creation (<1 second)")
    print("✓ Space-efficient (copy-on-write)")
    print("✓ Can restore to any version instantly")
    print("✓ Snapshots persist even if volume deleted")
    print("✓ Up to 255 snapshots per volume")
    print()


async def example_3_fast_deployment_via_clones():
    """Example 3: Fast model deployment via ANF clones."""
    print("=" * 60)
    print("Example 3: Fast Deployment via ANF Clones")
    print("=" * 60 + "\n")

    manager = await example_1_register_models()

    print("Scenario: Deploy models to new regions for low-latency inference\n")

    # Deploy to multiple regions
    deployments = [
        ("claude-opus-4", "westeurope"),
        ("claude-opus-4", "southeastasia"),
        ("gpt-4-turbo-2024-04-09", "australiaeast")
    ]

    print("Traditional Copy vs ANF Clone:\n")

    for model_id, region in deployments:
        model = manager.get_model(model_id)

        print(f"Deploying {model.model_name} to {region}:")
        print(f"  Model size: {model.size_gb} GB")
        print(f"  Traditional copy: {model.size_gb / 10:.1f} minutes (10 GB/min)")
        print(f"  ANF clone: <1 second ⚡")

        deployment = await manager.deploy_model(
            model_id=model_id,
            target_region=region,
            use_clone=True  # Instant, no data movement
        )

        print(f"  ✓ Deployed: {deployment.volume_path}")
        print(f"  Type: {deployment.deployment_type}")
        print(f"  Ready: {deployment.ready}")
        print()

    print("ANF Clone Benefits:")
    print("✓ Instant deployment (copy-on-write)")
    print("✓ No data movement/copying")
    print("✓ Same storage efficiency as snapshots")
    print("✓ Can clone from snapshot (specific version)")
    print("✓ Perfect for A/B testing and canary deployments")
    print()


async def example_4_multi_region_replication():
    """Example 4: Multi-region replication for global models."""
    print("=" * 60)
    print("Example 4: Multi-Region Replication")
    print("=" * 60 + "\n")

    manager = await example_1_register_models()

    print("Scenario: Global deployment with automatic replication\n")

    # Get model with replication
    model = manager.get_model("gpt-4-turbo-2024-04-09")

    print(f"Model: {model.model_name}")
    print(f"Primary region: westus2")
    print(f"Replicated to: {', '.join(model.replicated_regions)}")
    print()

    print("Replication Architecture:")
    print("┌─────────────────────────────────────────────┐")
    print("│        Primary: westus2 (Premium)           │")
    print("│         GPT-4 Turbo (85 GB)                 │")
    print("└─────────────────┬───────────────────────────┘")
    print("                  │")
    print("      ┌───────────┼───────────┐")
    print("      │           │           │")
    print("      ▼           ▼           ▼")
    print("  eastus2    westeurope   (future)")
    print("  Replica      Replica     regions")
    print()

    print("Replication Features:")
    print("✓ Automatic synchronization (hourly/daily/weekly)")
    print("✓ Cross-region DR (disaster recovery)")
    print("✓ Low-latency inference globally")
    print("✓ Regional failover capability")
    print("✓ Bandwidth-efficient (only changes replicated)")
    print()


async def example_5_tiering_optimization():
    """Example 5: Automatic tiering for cost optimization."""
    print("=" * 60)
    print("Example 5: Automatic Tiering Optimization")
    print("=" * 60 + "\n")

    manager = await example_1_register_models()

    print("Scenario: Optimize costs by moving cold models to Standard tier\n")

    # Simulate access patterns
    print("Simulating access patterns:\n")

    models = manager.list_models()
    for model in models[:2]:
        model.access_count = 500  # Frequently accessed
        print(f"  {model.model_name}: {model.access_count} accesses (hot)")

    for model in models[2:]:
        model.access_count = 10  # Rarely accessed
        # Simulate old last_access
        from datetime import datetime, timedelta
        old_date = datetime.utcnow() - timedelta(days=10)
        model.last_accessed = old_date.isoformat()
        print(f"  {model.model_name}: {model.access_count} accesses (cold, 10 days inactive)")

    print()

    # Run optimization
    print("Running tiering optimization...\n")

    result = await manager.optimize_tiering(
        access_threshold_days=7,
        cold_tier=ANFTier.STANDARD,
        hot_tier=ANFTier.PREMIUM
    )

    print(f"Optimization complete:")
    print(f"  Total changes: {result['total_changes']}")
    print()

    for change in result['changes']:
        print(f"  {change['model_id']}:")
        print(f"    Action: {change['action']}")
        print(f"    Tier: {change['from']} → {change['to']}")
        if 'days_inactive' in change:
            print(f"    Reason: {change['days_inactive']} days inactive")
        if 'access_count' in change:
            print(f"    Reason: {change['access_count']} accesses")
        print()

    print("Cost Impact:")
    print("  Premium tier: $0.000403/GB/hour")
    print("  Standard tier: $0.000202/GB/hour (50% cheaper)")
    print()
    print("For 100 GB cold model:")
    print("  Premium: $29.66/month")
    print("  Standard: $14.87/month")
    print("  Savings: $14.79/month per cold model")
    print()


async def example_6_backup_and_dr():
    """Example 6: Long-term backups and disaster recovery."""
    print("=" * 60)
    print("Example 6: ANF Backups and Disaster Recovery")
    print("=" * 60 + "\n")

    manager = await example_1_register_models()

    print("Scenario: Create long-term backups for compliance and DR\n")

    # Create backups
    critical_models = ["gpt-4-turbo-2024-04-09", "claude-opus-4"]

    for model_id in critical_models:
        model = manager.get_model(model_id)

        print(f"Creating backup for {model.model_name}:")

        backup = await manager.create_backup(
            model_id=model_id,
            vault_name="ants-model-vault-prod",
            retention_days=90  # 90-day retention
        )

        print(f"  Backup ID: {backup['backup_id']}")
        print(f"  Vault: {backup['vault']}")
        print(f"  Size: {backup['size_gb']} GB")
        print(f"  Retention: {backup['retention_days']} days")
        print()

    print("ANF Backup Features:")
    print("✓ Independent of source volume (persist even if volume deleted)")
    print("✓ Long-term retention (configurable)")
    print("✓ Restore to any region")
    print("✓ Incremental backups (bandwidth-efficient)")
    print("✓ Vault-level encryption")
    print("✓ Compliance: SOC 2, ISO 27001")
    print()


async def example_7_statistics():
    """Example 7: Storage statistics and capacity planning."""
    print("=" * 60)
    print("Example 7: Storage Statistics")
    print("=" * 60 + "\n")

    manager = await example_1_register_models()

    # Create some snapshots
    await manager.create_snapshot("gpt-4-turbo-2024-04-09", "v1.0.0")
    await manager.create_snapshot("gpt-4-turbo-2024-04-09", "v1.1.0")
    await manager.create_snapshot("claude-opus-4", "v1.0.0")

    stats = manager.get_stats()

    print("ANF Model Storage Statistics:\n")
    print(f"Total models: {stats['total_models']}")
    print(f"Total storage: {stats['total_storage_gb']:.1f} GB")
    print(f"Total snapshots: {stats['total_snapshots']}")
    print(f"Total deployments: {stats['total_deployments']}")
    print()

    print("By tier:")
    for tier, count in stats['by_tier'].items():
        print(f"  {tier}: {count} models")
    print()

    print("By provider:")
    for provider, count in stats['by_provider'].items():
        print(f"  {provider}: {count} models")
    print()

    print("Snapshots by model:")
    for model_id, count in stats['snapshot_count_by_model'].items():
        print(f"  {model_id}: {count} snapshots")
    print()

    print("Replication by region:")
    for region, count in stats['replication_count_by_region'].items():
        print(f"  {region}: {count} deployments")
    print()


async def main():
    """Run all ANF model management examples."""
    print("\n")
    print("█" * 60)
    print("ANTS ANF Model Weight Management Examples")
    print("Azure NetApp Files: The Memory Substrate")
    print("█" * 60)
    print("\n")

    await example_1_register_models()
    await example_2_version_control_snapshots()
    await example_3_fast_deployment_via_clones()
    await example_4_multi_region_replication()
    await example_5_tiering_optimization()
    await example_6_backup_and_dr()
    await example_7_statistics()

    print("=" * 60)
    print("All Examples Complete")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("✓ ANF Snapshots: Instant version control (copy-on-write)")
    print("✓ ANF Clones: Fast deployment (<1s vs minutes)")
    print("✓ Cross-Region Replication: Global low-latency inference")
    print("✓ Volume Tiering: Hot (Premium) / Warm (Standard) optimization")
    print("✓ ANF Backups: Long-term retention and DR")
    print("✓ Cost optimization: Move cold models to Standard tier (50% cheaper)")
    print()
    print("The Memory Substrate:")
    print("ANF is the persistent enterprise mind where model artifacts live,")
    print("evolve, and replicate across regions with entropy management.")
    print()
    print("Storage costs for 1TB of model weights:")
    print("  Premium tier: $403/month (hot models)")
    print("  Standard tier: $202/month (warm models)")
    print("  Snapshots: Incremental, space-efficient")
    print("  Replication: Bandwidth-efficient (only changes)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
