from datetime import date, datetime

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
                datetime(2023, 11, 30, hour=16, minute=12, second=15), is_dst=False
            ),
            ulid="01KNMCHTWZJ9M36D87THWBENGF",
        )
        cls.elena = Author.objects.create(
            name="Élena Jordan",
            alias="elena",
            birthday=pytz.utc.localize(
                datetime(2023, 11, 30, hour=16, minute=59, second=59), is_dst=False
            ),
        )
        cls.sarah = Author.objects.create(
            name="Sarah Connor",
            alias="sconnor",
            birthday=pytz.utc.localize(
                datetime(2023, 12, 31, hour=23, minute=30, second=00), is_dst=False
            ),
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
        self.assertEqual(john.v, 20231130161215)
        elena = Author.objects.annotate(
            v=models.toYYYYMMDDhhmmss("birthday", "Asia/Shanghai")
        ).get(id=self.elena.id)
        self.assertEqual(elena.v, 20231201005959)

    def test_tostartofminute(self):
        john = Author.objects.annotate(v=models.toStartOfMinute("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(
            john.v,
            datetime(
                2023,
                11,
                30,
                hour=16,
                minute=12,
                second=00,
            ),
        )

        elena = Author.objects.annotate(v=models.toStartOfMinute("birthday")).get(
            id=self.elena.id
        )
        self.assertEqual(
            elena.v,
            datetime(2023, 11, 30, hour=10, minute=59, second=00),
        )

    def test_tostartoffiveminutes(self):
        john = Author.objects.annotate(v=models.toStartOfFiveMinutes("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(
            john.v,
            datetime(
                2023,
                11,
                30,
                hour=16,
                minute=10,
                second=00,
            ),
        )

        elena = Author.objects.annotate(v=models.toStartOfFiveMinutes("birthday")).get(
            id=self.elena.id
        )
        self.assertEqual(
            elena.v,
            datetime(2023, 11, 30, hour=10, minute=55, second=00),
        )

    def test_tostartoftenminutes(self):
        john = Author.objects.annotate(v=models.toStartOfTenMinutes("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(
            john.v,
            datetime(
                2023,
                11,
                30,
                hour=16,
                minute=10,
                second=00,
            ),
        )

        elena = Author.objects.annotate(v=models.toStartOfTenMinutes("birthday")).get(
            id=self.elena.id
        )
        self.assertEqual(
            elena.v,
            datetime(2023, 11, 30, hour=10, minute=50, second=00),
        )

    def test_tostartoffifteenminutes(self):
        john = Author.objects.annotate(
            v=models.toStartOfFifteenMinutes("birthday")
        ).get(id=self.john.id)
        self.assertEqual(
            john.v,
            datetime(
                2023,
                11,
                30,
                hour=16,
                minute=00,
                second=00,
            ),
        )

        elena = Author.objects.annotate(
            v=models.toStartOfFifteenMinutes("birthday")
        ).get(id=self.elena.id)
        self.assertEqual(
            elena.v,
            datetime(2023, 11, 30, hour=10, minute=45, second=00),
        )

    def test_tostartofhour(self):
        john = Author.objects.annotate(v=models.toStartOfHour("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(
            john.v,
            datetime(
                2023,
                11,
                30,
                hour=16,
                minute=00,
                second=00,
            ),
        )

        elena = Author.objects.annotate(v=models.toStartOfHour("birthday")).get(
            id=self.elena.id
        )
        self.assertEqual(
            elena.v,
            datetime(2023, 11, 30, hour=10, minute=00, second=00),
        )

    @staticmethod
    def utc_to_current_timezone(dt):
        """Render a naive UTC datetime in the current time zone, still naive.

        birthday is stored as a DateTime64 in UTC, so a truncation returns a
        DateTime in UTC, which is then rendered in the current time zone because
        USE_TZ is off.
        """
        return (
            pytz.utc.localize(dt)
            .astimezone(pytz.timezone(get_timezone()))
            .replace(tzinfo=None)
        )

    def test_tostartofday(self):
        # 2023-11-30 22:12:15 UTC
        john = Author.objects.annotate(v=models.toStartOfDay("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(john.v, self.utc_to_current_timezone(datetime(2023, 11, 30)))

        # 2023-12-31 23:30:00 UTC
        sarah = Author.objects.annotate(v=models.toStartOfDay("birthday")).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, self.utc_to_current_timezone(datetime(2023, 12, 31)))

    def test_tostartofweek(self):
        # 2023-12-31 is a Sunday, mode 0 starts the week on Sunday.
        sarah = Author.objects.annotate(v=models.toStartOfWeek("birthday")).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, date(2023, 12, 31))

        # Mode 1 starts the week on Monday.
        sarah = Author.objects.annotate(v=models.toStartOfWeek("birthday", 1)).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, date(2023, 12, 25))

    def test_tostartofmonth(self):
        sarah = Author.objects.annotate(v=models.toStartOfMonth("birthday")).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, date(2023, 12, 1))

    def test_tostartofquarter(self):
        sarah = Author.objects.annotate(v=models.toStartOfQuarter("birthday")).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, date(2023, 10, 1))

    def test_tostartofyear(self):
        sarah = Author.objects.annotate(v=models.toStartOfYear("birthday")).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, date(2023, 1, 1))

    def test_tostartof_arity(self):
        for func in [
            models.toStartOfDay,
            models.toStartOfMonth,
            models.toStartOfQuarter,
            models.toStartOfYear,
        ]:
            with self.subTest(func=func.__name__):
                with self.assertRaisesMessage(
                    TypeError, f"'{func.__name__}' takes 1 argument (2 given)"
                ):
                    func("birthday", 1)
        with self.assertRaisesMessage(
            TypeError, "'toStartOfWeek' takes 1 or 2 arguments (3 given)"
        ):
            models.toStartOfWeek("birthday", 1, "UTC")

    def test_toyearweek(self):
        sarah = Author.objects.annotate(v=models.toYearWeek("birthday")).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, 202353)

        sarah = Author.objects.annotate(v=models.toYearWeek("birthday", 1)).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, 202352)

        sarah = Author.objects.annotate(
            v=models.toYearWeek("birthday", 1, "Pacific/Kiritimati")
        ).get(id=self.sarah.id)
        self.assertEqual(sarah.v, 202401)

    def test_ulid_string_to_datetime(self):
        john = Author.objects.annotate(
            v=models.ULIDStringToDateTime("ulid", "UTC")
        ).get(id=self.john.id)

        expected_datetime = datetime(
            2026,
            4,
            7,
            hour=16,
            minute=31,
            second=31,
            microsecond=231000,
            tzinfo=pytz.utc,
        )

        self.assertEqual(john.v, expected_datetime)

    def test_ulid_string_to_datetime_with_timezone_conversion(self):
        john = Author.objects.annotate(
            v=models.ULIDStringToDateTime("ulid", "Asia/Shanghai")
        ).get(id=self.john.id)

        expected_datetime = pytz.timezone("Asia/Shanghai").localize(
            datetime(2026, 4, 8, hour=0, minute=31, second=31, microsecond=231000)
        )

        self.assertEqual(john.v, expected_datetime)
