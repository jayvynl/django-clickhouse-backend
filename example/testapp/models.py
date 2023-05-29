from django.db.models import CheckConstraint, Func, Q, IntegerChoices
from django.utils import timezone

from clickhouse_backend import models


class Event(models.ClickhouseModel):
    class Action(IntegerChoices):
        PASS = 1
        DROP = 2
        ALERT = 3
    ip = models.GenericIPAddressField(default='::')
    ipv4 = models.IPv4Field(default="127.0.0.1")
    ip_nullable = models.GenericIPAddressField(null=True)
    port = models.UInt16Field(default=0)
    protocol = models.StringField(default='', low_cardinality=True)
    content = models.StringField(default='')
    timestamp = models.DateTime64Field(default=timezone.now)
    created_at = models.DateTime64Field(auto_now_add=True)
    action = models.EnumField(choices=Action.choices, default=Action.PASS)

    class Meta:
        verbose_name = 'Network event'
        ordering = ['-id']
        db_table = 'event'
        engine = models.ReplacingMergeTree(
            order_by=['id'],
            partition_by=models.toYYYYMMDD('timestamp')
        )
        indexes = [
            models.Index(
                fields=["ip"],
                name='ip_set_idx',
                type=models.Set(1000),
                granularity=4
            ),
            models.Index(
                fields=["port"],
                name="port_bloom_idx",
                type=models.BloomFilter(0.001),
                granularity=1
            )
        ]
        constraints = (
            CheckConstraint(
                name='port_range',
                check=Q(port__gte=0, port__lte=65535),
            ),
        )
