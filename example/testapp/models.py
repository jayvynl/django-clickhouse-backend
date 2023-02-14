from django.db.models import CheckConstraint, Func, Q
from django.utils import timezone

from clickhouse_backend import models


class Event(models.ClickhouseModel):
    src_ip = models.GenericIPAddressField(default='::')
    sport = models.UInt16Field(default=0)
    dst_ip = models.GenericIPAddressField(default='::')
    dport = models.UInt16Field(default=0)
    transport = models.FixedStringField(max_bytes=3, default='')
    protocol = models.StringField(default='')
    content = models.StringField(default='')
    timestamp = models.DateTime64Field(default=timezone.now)
    created_at = models.DateTime64Field(auto_now_add=True)
    length = models.UInt32Field(default=0)
    count = models.UInt32Field(default=1)

    class Meta:
        verbose_name = 'Network event'
        ordering = ['-id']
        db_table = 'event'
        engine = models.ReplacingMergeTree(
            order_by=('dst_ip', 'timestamp'),
            partition_by=Func('timestamp', function='toYYYYMMDD')
        )
        indexes = [
            models.Index(
                fields=('src_ip', 'dst_ip'),
                name='src_ip_dst_ip_idx',
                type=models.Set(1000),
                granularity=4
            )
        ]
        constraints = (
            CheckConstraint(
                name='sport_range',
                check=Q(sport__gte=0, dport__lte=65535),
            ),
        )


class Test(models.ClickhouseModel):
    a = models.ArrayField(models.Int8Field(null=True, low_cardinality=True))

    class Meta:
        engine = models.MergeTree(order_by=())
