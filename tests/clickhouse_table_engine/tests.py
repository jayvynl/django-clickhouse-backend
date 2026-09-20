import re

from django.db import connection
from django.db.models import F
from django.test import TestCase
from django.test.utils import isolate_apps

from clickhouse_backend.models import (
    ClickhouseModel,
    Index,
    MergeTree,
    MinMax,
    StringField,
    farmFingerprint64,
    sipHash64,
)
from clickhouse_backend.utils.timezone import get_timezone

from . import models


CLAUSES = ("PARTITION BY", "PRIMARY KEY", "ORDER BY", "SAMPLE BY")
CLAUSE_RE = re.compile(
    r"\b(%s) \((.*?)\)(?= (?:%s)\b|$)"
    % ("|".join(CLAUSES), "|".join((*CLAUSES, "TTL", "SETTINGS")))
)


def normalize_engine_full(engine_full):
    """Normalize engine_full for comparison across ClickHouse versions.

    Newer ClickHouse versions preserve the parentheses wrapping a clause value
    (``ORDER BY (id)``) that older versions strip (``ORDER BY id``). Stripping
    them from both sides of an assertion makes the two spellings compare equal.
    """
    return CLAUSE_RE.sub(r"\1 \2", engine_full)


class TestMergeTree(TestCase):
    def get_engine_full(self, model):
        with connection.cursor() as cursor:
            cursor.execute(
                "select engine_full from system.tables "
                "where database = currentDatabase() and table = %s",
                [model._meta.db_table],
            )
            return cursor.fetchone()[0]

    def assertEngineEquals(self, model, engine):
        engine_full = self.get_engine_full(model)
        self.assertEqual(
            normalize_engine_full(engine_full.partition(" SETTINGS ")[0]),
            normalize_engine_full(engine),
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
        # ClickHouse expands {database} in the stored engine_full.
        db_name = connection.settings_dict["NAME"]
        self.assertEngineEquals(
            models.ReplicatedReplacingMergeTreeWithZooReplica,
            f"ReplicatedReplacingMergeTree('/clickhouse/tables/{db_name}/{{shard}}/table_name', '{{replica}}') ORDER BY id",
        )

    def test_sample_by(self):
        # Only the SAMPLE BY clause is asserted, because ClickHouse versions
        # disagree on how many redundant parentheses they keep around a function
        # call inside a clause value, and ORDER BY is covered by test_table.
        self.assertRegex(
            self.get_engine_full(models.SampleMergeTree),
            r"SAMPLE BY \(?farmFingerprint64\(uid\)\)?",
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
        # ClickHouse uses order_by as the primary key when primary_key is absent.
        with self.assertRaisesMessage(
            ValueError, "sample_by must be present in primary_key"
        ):
            MergeTree(order_by=("a", "b"), sample_by="c")
        with self.assertRaisesMessage(
            ValueError, "sample_by must be present in primary_key"
        ):
            MergeTree(order_by=("a", "b"), primary_key=("a",), sample_by="b")

    def test_sample_by_is_a_single_expression(self):
        """Unlike the key clauses, SAMPLE BY takes one expression, not a tuple."""
        self.assertEqual(MergeTree(order_by="id", sample_by="id").sample_by, "id")
        self.assertEqual(MergeTree(order_by="id").sample_by, None)

    def test_sample_by_expression_equality(self):
        """sample_by is compared to the key expressions as spelled."""
        MergeTree(
            order_by=(farmFingerprint64("uid"), "id"),
            sample_by=farmFingerprint64("uid"),
        )
        with self.assertRaisesMessage(
            ValueError, "sample_by must be present in primary_key"
        ):
            MergeTree(order_by=("uid", "id"), sample_by=F("uid"))

    def test_sample_by_deconstruct(self):
        """sample_by must survive serialization into a migration."""
        path, args, kwargs = MergeTree(
            order_by=(farmFingerprint64("uid"), "id"),
            sample_by=farmFingerprint64("uid"),
        ).deconstruct()
        self.assertEqual(path, "clickhouse_backend.models.MergeTree")
        self.assertEqual(args, ())
        self.assertEqual(kwargs["sample_by"], farmFingerprint64("uid"))


class TestEngineSettings(TestCase):
    def test(self):
        opts = models.EngineWithSettings._meta
        with connection.cursor() as cursor:
            cursor.execute(
                "select engine_full from system.tables "
                "where database = currentDatabase() and table = %s",
                [opts.db_table],
            )
            engine_full = cursor.fetchone()[0]
        for k, v in opts.engine.settings.items():
            self.assertTrue(f"{k} = {v}" in engine_full)


class TestIndexCheck(TestCase):
    """Django 6.0 moved the index system checks into Index.check(), #185."""

    def test_valid(self):
        self.assertEqual(models.SkippingIndex.check(databases=["default"]), [])

    @isolate_apps("clickhouse_table_engine")
    def test_errors(self):
        def index(name, *expressions, **kwargs):
            return Index(
                *expressions, name=name, type=MinMax(), granularity=1, **kwargs
            )

        class Model(ClickhouseModel):
            trace_id = StringField()

            class Meta:
                engine = MergeTree(order_by="id")
                indexes = [
                    index("_trace_id_idx", fields=["trace_id"]),
                    index("x" * (Index.max_name_length + 1), "trace_id"),
                    index("missing_idx", fields=["missing"]),
                    index("missing_hash_idx", sipHash64("missing")),
                ]

        self.assertEqual(
            sorted(error.id for error in Model.check(databases=["default"])),
            ["models.E012", "models.E012", "models.E033", "models.E034"],
        )
