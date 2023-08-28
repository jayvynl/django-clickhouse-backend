from clickhouse_backend import models


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
