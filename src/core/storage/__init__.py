"""
Storage module for ANTS.

ANF-powered model weight management leveraging Azure NetApp Files advanced features:
- Snapshots: Instant version control
- Clones: Fast deployment
- Regional replication: Multi-region distribution
- Volume tiering: Cost optimization
- ANF backups: Long-term retention and DR

This is the "memory substrate" from the ANTS whitepaper.
"""
from src.core.storage.anf_model_manager import (
    ANFModelManager,
    ANFTier,
    ReplicationSchedule,
    ModelMetadata,
    SnapshotInfo,
    DeploymentInfo,
    create_anf_model_manager
)

__all__ = [
    "ANFModelManager",
    "ANFTier",
    "ReplicationSchedule",
    "ModelMetadata",
    "SnapshotInfo",
    "DeploymentInfo",
    "create_anf_model_manager",
]
