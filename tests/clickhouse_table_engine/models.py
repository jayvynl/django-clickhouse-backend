from django.utils import timezone

from clickhouse_backend import models


class Event(models.ClickhouseModel):
    ip = models.GenericIPAddressField(default="::")
    port = models.UInt16Field(default=0)
    protocol = models.StringField(default="", low_cardinality=True)
    content = models.StringField(default="")
    timestamp = models.DateTime64Field(default=timezone.now)

    class Meta:
        ordering = ["-timestamp"]
        engine = models.MergeTree(
            primary_key="timestamp",
            order_by=("timestamp", "id"),
            partition_by=models.toYYYYMMDD("timestamp"),
        )


class EngineWithSettings(models.ClickhouseModel):
    class Meta:
        engine = models.MergeTree(
            order_by=(),
            index_granularity=1024,
            index_granularity_bytes=1 << 20,
            enable_mixed_granularity_parts=1,
        )


class Student(models.ClickhouseModel):
    name = models.StringField()
    address = models.StringField()
    score = models.Int8Field()

    class Meta:
        engine = models.ReplicatedMergeTree(order_by="id")
        cluster = "cluster"


class DistributedStudent(models.ClickhouseModel):
    name = models.StringField()
    score = models.Int8Field()

    class Meta:
        engine = models.Distributed(
            "cluster", models.currentDatabase(), Student._meta.db_table, models.Rand()
        )
        cluster = "cluster"


class ReplacingMergeTree(models.ClickhouseModel):
    ver = models.UInt64Field()
    is_deleted = models.UInt8Field()

    class Meta:
        engine = models.ReplacingMergeTree("ver", "is_deleted", order_by="id")


class ReplicatedReplacingMergeTree(models.ClickhouseModel):
    ver = models.UInt64Field()
    is_deleted = models.UInt8Field()

    class Meta:
        engine = models.ReplicatedReplacingMergeTree(
            other_parameters=("ver", "is_deleted"), order_by="id"
        )
        cluster = "cluster"


class ReplicatedReplacingMergeTreeWithZooReplica(models.ClickhouseModel):
    ver = models.UInt64Field()
    is_deleted = models.UInt8Field()

    class Meta:
        engine = models.ReplicatedReplacingMergeTree(
            "/clickhouse/tables/{shard}/table_name",
            "{replica}",
            order_by="id",
        )
        cluster = "cluster"
