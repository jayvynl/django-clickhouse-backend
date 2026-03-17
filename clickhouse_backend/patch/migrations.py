from .cluster import install_cluster_patches
from .recorder import _check_replicas, _get_replicas, install_recorder_patches

__all__ = [
    "patch_migrations",
    "patch_migration_recorder",
    "patch_migration",
    "_check_replicas",
    "_get_replicas",
]


def patch_migrations():
    patch_migration_recorder()
    patch_migration()


def patch_migration_recorder():
    install_recorder_patches()


def patch_migration():
    install_cluster_patches()
