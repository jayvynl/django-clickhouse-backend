from datetime import date, datetime

import pytz
from django.db import connection
from django.test import TestCase

from clickhouse_backend import models
from clickhouse_backend.utils.timezone import get_timezone

from .models import Author

TZ = pytz.timezone(get_timezone())

# These take the value alone. ClickHouse truncates in the server timezone and the
# result type carries no timezone, so the values come back naive.
PLAIN_TRUNCATIONS = [
    models.toStartOfMinute,
    models.toStartOfFiveMinutes,
    models.toStartOfTenMinutes,
    models.toStartOfFifteenMinutes,
    models.toStartOfHour,
]

# These take an optional timezone, defaulting to the current one, so their
# DateTime results carry a timezone and come back as aware datetimes.
TIMEZONE_TRUNCATIONS = [
    models.toStartOfDay,
    models.toStartOfMonth,
    models.toStartOfQuarter,
    models.toStartOfYear,
]

# toStartOfWeek takes a mode between the two, so it is listed separately.
TRUNCATIONS = PLAIN_TRUNCATIONS + TIMEZONE_TRUNCATIONS + [models.toStartOfWeek]


def naive_local(*args, **kwargs):
    """Build what the driver makes of the given UTC time.

    The plain truncations get no timezone, so ClickHouse truncates in the server
    timezone -- UTC in the test cluster -- and the DateTime it answers with
    carries no timezone either, which makes the driver return a naive datetime in
    the local one. Both ends depend on where the tests run, so the expected values
    have to be built instead of written out.
    """
    return datetime.fromtimestamp(
        pytz.utc.localize(datetime(*args, **kwargs)).timestamp()
    )


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
            # 2024-01-01 is a Monday.
            birth_date=date(2024, 1, 1),
            birth_date32=date(2024, 1, 1),
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
        self.assertEqual(john.v, naive_local(2023, 11, 30, hour=22, minute=12))

        elena = Author.objects.annotate(v=models.toStartOfMinute("birthday")).get(
            id=self.elena.id
        )
        self.assertEqual(elena.v, naive_local(2023, 11, 30, hour=16, minute=59))

    def test_tostartoffiveminutes(self):
        john = Author.objects.annotate(v=models.toStartOfFiveMinutes("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(john.v, naive_local(2023, 11, 30, hour=22, minute=10))

        elena = Author.objects.annotate(v=models.toStartOfFiveMinutes("birthday")).get(
            id=self.elena.id
        )
        self.assertEqual(elena.v, naive_local(2023, 11, 30, hour=16, minute=55))

    def test_tostartoftenminutes(self):
        john = Author.objects.annotate(v=models.toStartOfTenMinutes("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(john.v, naive_local(2023, 11, 30, hour=22, minute=10))

        elena = Author.objects.annotate(v=models.toStartOfTenMinutes("birthday")).get(
            id=self.elena.id
        )
        self.assertEqual(elena.v, naive_local(2023, 11, 30, hour=16, minute=50))

    def test_tostartoffifteenminutes(self):
        john = Author.objects.annotate(
            v=models.toStartOfFifteenMinutes("birthday")
        ).get(id=self.john.id)
        self.assertEqual(john.v, naive_local(2023, 11, 30, hour=22))

        elena = Author.objects.annotate(
            v=models.toStartOfFifteenMinutes("birthday")
        ).get(id=self.elena.id)
        self.assertEqual(elena.v, naive_local(2023, 11, 30, hour=16, minute=45))

    def test_tostartofhour(self):
        john = Author.objects.annotate(v=models.toStartOfHour("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(john.v, naive_local(2023, 11, 30, hour=22))

        elena = Author.objects.annotate(v=models.toStartOfHour("birthday")).get(
            id=self.elena.id
        )
        self.assertEqual(elena.v, naive_local(2023, 11, 30, hour=16))

    def test_tostartofday(self):
        john = Author.objects.annotate(v=models.toStartOfDay("birthday")).get(
            id=self.john.id
        )
        self.assertEqual(john.v, TZ.localize(datetime(2023, 11, 30)))

        # 2023-12-31 23:30:00 UTC is still 2023-12-31 in the current timezone.
        sarah = Author.objects.annotate(v=models.toStartOfDay("birthday")).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, TZ.localize(datetime(2023, 12, 31)))

        # In Asia/Shanghai it is already 2024-01-01 07:30.
        sarah = Author.objects.annotate(
            v=models.toStartOfDay("birthday", "Asia/Shanghai")
        ).get(id=self.sarah.id)
        self.assertEqual(
            sarah.v, pytz.timezone("Asia/Shanghai").localize(datetime(2024, 1, 1))
        )

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

        # In Asia/Shanghai it is already Monday 2024-01-01.
        sarah = Author.objects.annotate(
            v=models.toStartOfWeek("birthday", 0, "Asia/Shanghai")
        ).get(id=self.sarah.id)
        self.assertEqual(sarah.v, date(2023, 12, 31))
        sarah = Author.objects.annotate(
            v=models.toStartOfWeek("birthday", 1, "Asia/Shanghai")
        ).get(id=self.sarah.id)
        self.assertEqual(sarah.v, date(2024, 1, 1))

    def test_tostartofmonth(self):
        sarah = Author.objects.annotate(v=models.toStartOfMonth("birthday")).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, date(2023, 12, 1))

        sarah = Author.objects.annotate(
            v=models.toStartOfMonth("birthday", "Asia/Shanghai")
        ).get(id=self.sarah.id)
        self.assertEqual(sarah.v, date(2024, 1, 1))

    def test_tostartofquarter(self):
        sarah = Author.objects.annotate(v=models.toStartOfQuarter("birthday")).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, date(2023, 10, 1))

        sarah = Author.objects.annotate(
            v=models.toStartOfQuarter("birthday", "Asia/Shanghai")
        ).get(id=self.sarah.id)
        self.assertEqual(sarah.v, date(2024, 1, 1))

    def test_tostartofyear(self):
        sarah = Author.objects.annotate(v=models.toStartOfYear("birthday")).get(
            id=self.sarah.id
        )
        self.assertEqual(sarah.v, date(2023, 1, 1))

        sarah = Author.objects.annotate(
            v=models.toStartOfYear("birthday", "Asia/Shanghai")
        ).get(id=self.sarah.id)
        self.assertEqual(sarah.v, date(2024, 1, 1))

    def test_tostartof_date_argument(self):
        """The truncations to a Date take no timezone for a date argument.

        A date has no time of day, so truncating it to the start of a week,
        month, quarter or year is the same in every timezone, and ClickHouse
        rejects the argument instead of ignoring it:
        DB::Exception: The timezone argument of function toStartOfMonth is
        allowed only when the 1st argument is DateTime or DateTime64.
        """
        expected = {
            # Mode 0 starts the week on Sunday, the day before.
            models.toStartOfWeek: date(2023, 12, 31),
            models.toStartOfMonth: date(2024, 1, 1),
            models.toStartOfQuarter: date(2024, 1, 1),
            models.toStartOfYear: date(2024, 1, 1),
        }
        for field in ["birth_date", "birth_date32"]:
            for func, expected_date in expected.items():
                with self.subTest(func=func.__name__, field=field):
                    sarah = Author.objects.annotate(v=func(field)).get(id=self.sarah.id)
                    self.assertEqual(sarah.v, expected_date)

                    # A timezone that was passed explicitly is as meaningless
                    # for a date as the default one, so it is dropped too.
                    if func is models.toStartOfWeek:
                        args = (field, 0, "Asia/Shanghai")
                    else:
                        args = (field, "Asia/Shanghai")
                    sarah = Author.objects.annotate(v=func(*args)).get(id=self.sarah.id)
                    self.assertEqual(sarah.v, expected_date)

    def test_tostartofday_date_argument(self):
        """toStartOfDay does take a timezone for a date argument.

        Its result has a time of day, and ClickHouse reads the date as midnight
        in the given timezone rather than shifting it.
        """
        for field in ["birth_date", "birth_date32"]:
            with self.subTest(field=field):
                sarah = Author.objects.annotate(v=models.toStartOfDay(field)).get(
                    id=self.sarah.id
                )
                self.assertEqual(sarah.v, TZ.localize(datetime(2024, 1, 1)))

                sarah = Author.objects.annotate(
                    v=models.toStartOfDay(field, "Asia/Shanghai")
                ).get(id=self.sarah.id)
                self.assertEqual(
                    sarah.v,
                    pytz.timezone("Asia/Shanghai").localize(datetime(2024, 1, 1)),
                )

    def test_tostartof_always_passes_timezone(self):
        """These truncations must not depend on how the server is configured.

        A column without an explicit timezone uses the server timezone, so
        without an explicit timezone argument ClickHouse would truncate in the
        server timezone while the client works in another one, giving results
        that are not even on a boundary.
        """
        for func in TIMEZONE_TRUNCATIONS + [models.toStartOfWeek]:
            with self.subTest(func=func.__name__):
                timezone = func("birthday").get_source_expressions()[-1]
                self.assertEqual(timezone.value, get_timezone())

                if func is models.toStartOfWeek:
                    args = ("birthday", 1, "Asia/Shanghai")
                else:
                    args = ("birthday", "Asia/Shanghai")
                timezone = func(*args).get_source_expressions()[-1]
                self.assertEqual(timezone.value, "Asia/Shanghai")

    def test_tostartof_without_timezone(self):
        """The minute and hour truncations take the value alone.

        ClickHouse does accept a timezone for them, but this backend does not
        pass one, so they truncate in the server timezone.
        """
        for func in PLAIN_TRUNCATIONS:
            with self.subTest(func=func.__name__):
                self.assertEqual(len(func("birthday").get_source_expressions()), 1)

    def resolved_output_field(self, func, *args):
        query = Author.objects.all().query
        return func("birthday", *args).resolve_expression(query).output_field

    def test_output_field_of_datetime_results(self):
        """The truncations to a time of day always return a DateTime.

        Only with enable_extended_results_for_datetime_functions would a Date32
        or a DateTime64 argument give something wider, and that setting is not
        supported. See the clickhouse_backend.models.functions.datetime docs.
        """
        for func in [
            models.toStartOfMinute,
            models.toStartOfFiveMinutes,
            models.toStartOfTenMinutes,
            models.toStartOfFifteenMinutes,
            models.toStartOfHour,
            models.toStartOfDay,
        ]:
            with self.subTest(func=func.__name__):
                output_field = self.resolved_output_field(func)
                self.assertEqual(output_field.db_type(connection), "DateTime")

    def test_output_field_converted_types(self):
        """The converting functions return the type the docs describe."""
        expected = {
            models.toStartOfWeek: "Date",
            models.toStartOfMonth: "Date",
            models.toStartOfQuarter: "Date",
            models.toStartOfYear: "Date",
            models.toYYYYMM: "UInt32",
            models.toYYYYMMDD: "UInt32",
            models.toYYYYMMDDhhmmss: "UInt64",
            models.toYearWeek: "UInt32",
            models.ULIDStringToDateTime: "DateTime64(3)",
        }
        for func, db_type in expected.items():
            with self.subTest(func=func.__name__):
                output_field = self.resolved_output_field(func)
                self.assertEqual(output_field.db_type(connection), db_type)

    def test_tostartof_fractional_offset_timezone(self):
        """Timezones whose offset is not a whole hour must work too.

        Asia/Kathmandu is UTC+5:45. Truncating in UTC and converting afterwards
        would give 18:15 for the day below, which is not a day boundary at all, so
        the timezone has to reach ClickHouse.
        """
        # elena is 2023-11-30 16:59:59 UTC, that is 22:44:59 in Kathmandu.
        ktm = pytz.timezone("Asia/Kathmandu")
        elena = Author.objects.annotate(
            v=models.toStartOfDay("birthday", "Asia/Kathmandu")
        ).get(id=self.elena.id)
        self.assertEqual(elena.v, ktm.localize(datetime(2023, 11, 30)))

        # sarah is 2023-12-31 23:30:00 UTC, already 2024 in Kathmandu.
        sarah = Author.objects.annotate(
            v=models.toStartOfYear("birthday", "Asia/Kathmandu")
        ).get(id=self.sarah.id)
        self.assertEqual(sarah.v, date(2024, 1, 1))

    def test_tostartof_arity(self):
        """Each shape of the family rejects the arities it does not take.

        https://clickhouse.com/docs/sql-reference/functions/date-time-functions
        """
        for func in PLAIN_TRUNCATIONS:
            with self.subTest(func=func.__name__):
                func("birthday")
                for arity, args in [(0, ()), (2, ("birthday", "UTC"))]:
                    with self.assertRaisesMessage(
                        TypeError,
                        f"'{func.__name__}' takes exactly 1 argument ({arity} given)",
                    ):
                        func(*args)

        for func in TIMEZONE_TRUNCATIONS:
            with self.subTest(func=func.__name__):
                func("birthday")
                func("birthday", "UTC")
                with self.assertRaisesMessage(
                    TypeError, f"'{func.__name__}' takes 1 or 2 arguments (0 given)"
                ):
                    func()
                with self.assertRaisesMessage(
                    TypeError, f"'{func.__name__}' takes 1 or 2 arguments (3 given)"
                ):
                    func("birthday", 1, "UTC")

        models.toStartOfWeek("birthday")
        models.toStartOfWeek("birthday", 1)
        models.toStartOfWeek("birthday", 1, "UTC")
        with self.assertRaisesMessage(
            TypeError, "'toStartOfWeek' takes between 1 and 3 arguments (0 given)"
        ):
            models.toStartOfWeek()
        with self.assertRaisesMessage(
            TypeError, "'toStartOfWeek' takes between 1 and 3 arguments (4 given)"
        ):
            models.toStartOfWeek("birthday", 1, "UTC", 1)

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
