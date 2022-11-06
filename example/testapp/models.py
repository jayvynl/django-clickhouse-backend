from django.db import models
from django.utils import timezone

from clickhouse_backend import models as chm
from clickhouse_backend.models import indexes, engines


class Event(chm.ClickhouseModel):
    src_ip = chm.GenericIPAddressField(default='::')
    sport = chm.PositiveSmallIntegerField(default=0)
    dst_ip = chm.GenericIPAddressField(default='::')
    dport = chm.PositiveSmallIntegerField(default=0)
    transport = models.CharField(max_length=3, default='')
    protocol = models.TextField(default='')
    content = models.TextField(default='')
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    length = models.PositiveIntegerField(default=0)
    count = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Network event'
        ordering = ['-id']
        db_table = 'event'
        engine = engines.ReplacingMergeTree(
            order_by=('dst_ip', 'timestamp'),
            partition_by=models.Func('timestamp', function='toYYYYMMDD')
        )
        indexes = [
            indexes.Index(
                fields=('src_ip', 'dst_ip'),
                name='src_ip_dst_ip_idx',
                type=indexes.Set(1000),
                granularity=4
            )
        ]
        constraints = (
            models.CheckConstraint(
                name='sport_range',
                check=models.Q(sport__gte=0, dport__lte=65535),
            ),
        )
