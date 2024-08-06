from datetime import datetime

import pytz
from django.test import TestCase

from clickhouse_backend import models
from clickhouse_backend.utils.timezone import get_timezone

from .models import Author


class DateTimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.john = Author.objects.create(
            name="John Smith",
            alias="smithj",
            # https://stackoverflow.com/a/18862958
            birthday=pytz.timezone(get_timezone()).localize(
                datetime(2023, 11, 30, 16), is_dst=False
            ),
        )
        cls.elena = Author.objects.create(
            name="Élena Jordan",
            alias="elena",
            birthday=pytz.utc.localize(datetime(2023, 11, 30, 16), is_dst=False),
        )

    def test_yyyymm(self):
        john = Author.objects.annotate(v=models.toYYYYMM("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(john.v, 202311)
        elena = Author.objects.annotate(
            v=models.toYYYYMM("birthday", "Asia/Shanghai")
        ).get(id=self.elena.id)
        self.assertEqual(elena.v, 202312)

    def test_yyyymmdd(self):
        john = Author.objects.annotate(v=models.toYYYYMMDD("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(john.v, 20231130)
        elena = Author.objects.annotate(
            v=models.toYYYYMMDD("birthday", "Asia/Shanghai")
        ).get(id=self.elena.id)
        self.assertEqual(elena.v, 20231201)

    def test_yyyymmddhhmmss(self):
        john = Author.objects.annotate(v=models.toYYYYMMDDhhmmss("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(john.v, 20231130160000)
        elena = Author.objects.annotate(
            v=models.toYYYYMMDDhhmmss("birthday", "Asia/Shanghai")
        ).get(id=self.elena.id)
        self.assertEqual(elena.v, 20231201000000)
