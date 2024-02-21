from django.db import connection
from django.test import TestCase

from clickhouse_backend.models import MergeTree
from clickhouse_backend.utils.timezone import get_timezone

from . import models


class TestMergeTree(TestCase):
    def assertEngineEquals(self, model, engine):
        with connection.cursor() as cursor:
            cursor.execute(
                f"select engine_full from system.tables where table='{model._meta.db_table}'"
            )
            engine_full = cursor.fetchone()[0]
        self.assertEqual(
            engine_full.partition(" SETTINGS ")[0],
            engine,
        )

    def test_table(self):
        self.assertEngineEquals(
            models.Event,
            f"MergeTree PARTITION BY toYYYYMMDD(timestamp, '{get_timezone()}') PRIMARY KEY timestamp ORDER BY (timestamp, id)",
        )
        self.assertEngineEquals(
            models.ReplacingMergeTree, "ReplacingMergeTree(ver, is_deleted) ORDER BY id"
        )
        self.assertEngineEquals(
            models.ReplicatedReplacingMergeTree,
            "ReplicatedReplacingMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}', ver, is_deleted) ORDER BY id",
        )
        self.assertEngineEquals(
            models.ReplicatedReplacingMergeTreeWithZooReplica,
            "ReplicatedReplacingMergeTree('/clickhouse/tables/{shard}/table_name', '{replica}') ORDER BY id",
        )

    def test_mergetree_init_exception(self):
        with self.assertRaisesMessage(
            AssertionError, "At least one of order_by or primary_key must be provided"
        ):
            MergeTree()
        with self.assertRaisesMessage(ValueError, "None is not allowed in order_by"):
            MergeTree(order_by=(None, "a"))
        with self.assertRaisesMessage(
            ValueError, "primary_key must be a prefix of order_by"
        ):
            MergeTree(order_by=("a", "b"), primary_key=["b"])
        with self.assertRaisesMessage(
            ValueError, "primary_key must be a prefix of order_by"
        ):
            MergeTree(order_by=("a", "b"), primary_key=["a", "b", "c"])


class TestEngineSettings(TestCase):
    def test(self):
        opts = models.EngineWithSettings._meta
        with connection.cursor() as cursor:
            cursor.execute(
                f"select engine_full from system.tables where table='{opts.db_table}'"
            )
            engine_full = cursor.fetchone()[0]
        for k, v in opts.engine.settings.items():
            self.assertTrue(f"{k} = {v}" in engine_full)
