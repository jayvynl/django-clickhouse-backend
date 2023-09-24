from django.db import connection
from django.test import TestCase

from clickhouse_backend import models

from .models import EngineWithSettings, Event


class TestMergeTree(TestCase):
    def test_table(self):
        opts = Event._meta
        with connection.cursor() as cursor:
            cursor.execute(
                f"select engine_full from system.tables where table='{opts.db_table}'"
            )
            engine_full = cursor.fetchone()[0]
        self.assertEqual(
            engine_full.partition(" SETTINGS ")[0],
            "MergeTree PARTITION BY toYYYYMMDD(timestamp) PRIMARY KEY timestamp ORDER BY (timestamp, id)",
        )

    def test_mergetree_init_exception(self):
        with self.assertRaisesMessage(
            AssertionError, "At least one of order_by or primary_key must be provided"
        ):
            models.MergeTree()
        with self.assertRaisesMessage(ValueError, "None is not allowed in order_by"):
            models.MergeTree(order_by=(None, "a"))
        with self.assertRaisesMessage(
            ValueError, "primary_key must be a prefix of order_by"
        ):
            models.MergeTree(order_by=("a", "b"), primary_key=["b"])
        with self.assertRaisesMessage(
            ValueError, "primary_key must be a prefix of order_by"
        ):
            models.MergeTree(order_by=("a", "b"), primary_key=["a", "b", "c"])


class TestEngineSettings(TestCase):
    def test(self):
        opts = EngineWithSettings._meta
        with connection.cursor() as cursor:
            cursor.execute(
                f"select engine_full from system.tables where table='{opts.db_table}'"
            )
            engine_full = cursor.fetchone()[0]
        for k, v in opts.engine.settings.items():
            self.assertTrue(f"{k} = {v}" in engine_full)
