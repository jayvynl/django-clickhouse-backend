from clickhouse_backend import models


class EngineWithSettings(models.ClickhouseModel):
    class Meta:
        engine = models.MergeTree(
            order_by=(),
            index_granularity=1024,
            index_granularity_bytes=1 << 20,
            enable_mixed_granularity_parts=1,
        )
