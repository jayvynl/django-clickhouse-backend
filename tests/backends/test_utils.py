"""Tests for django.db.backends.utils"""
from decimal import Decimal, Rounded

from django.db.backends.utils import format_number, split_identifier, truncate_name
from django.test import SimpleTestCase

from clickhouse_backend import compat


class TestUtils(SimpleTestCase):
    def test_truncate_name(self):
        self.assertEqual(truncate_name("some_table", 10), "some_table")
        self.assertEqual(truncate_name("some_long_table", 10), "some_la38a")
        self.assertEqual(truncate_name("some_long_table", 10, 3), "some_loa38")
        self.assertEqual(truncate_name("some_long_table"), "some_long_table")
        # "user"."table" syntax
        self.assertEqual(
            truncate_name('username"."some_table', 10), 'username"."some_table'
        )
        self.assertEqual(
            truncate_name('username"."some_long_table', 10), 'username"."some_la38a'
        )
        self.assertEqual(
            truncate_name('username"."some_long_table', 10, 3), 'username"."some_loa38'
        )

    def test_split_identifier(self):
        self.assertEqual(split_identifier("some_table"), ("", "some_table"))
        self.assertEqual(split_identifier('"some_table"'), ("", "some_table"))
        self.assertEqual(
            split_identifier('namespace"."some_table'), ("namespace", "some_table")
        )
        self.assertEqual(
            split_identifier('"namespace"."some_table"'), ("namespace", "some_table")
        )

    def test_format_number(self):
        def equal(value, max_d, places, result):
            self.assertEqual(format_number(Decimal(value), max_d, places), result)

        equal("0", 12, 3, "0.000")
        equal("0", 12, 8, "0.00000000")
        equal("1", 12, 9, "1.000000000")
        equal("0.00000000", 12, 8, "0.00000000")
        equal("0.000000004", 12, 8, "0.00000000")
        equal("0.000000008", 12, 8, "0.00000001")
        equal("0.000000000000000000999", 10, 8, "0.00000000")
        equal("0.1234567890", 12, 10, "0.1234567890")
        equal("0.1234567890", 12, 9, "0.123456789")
        equal("0.1234567890", 12, 8, "0.12345679")
        equal("0.1234567890", 12, 5, "0.12346")
        equal("0.1234567890", 12, 3, "0.123")
        equal("0.1234567890", 12, 1, "0.1")
        equal("0.1234567890", 12, 0, "0")
        equal("0.1234567890", None, 0, "0")
        equal("1234567890.1234567890", None, 0, "1234567890")
        equal("1234567890.1234567890", None, 2, "1234567890.12")
        equal("0.1234", 5, None, "0.1234")
        equal("123.12", 5, None, "123.12")

        with self.assertRaises(Rounded):
            equal("0.1234567890", 5, None, "0.12346")
        with self.assertRaises(Rounded):
            equal("1234567890.1234", 5, None, "1234600000")

    def test_split_tzname_delta(self):
        if compat.dj_ge4:
            from django.db.backends.utils import split_tzname_delta

            tests = [
                ("Asia/Ust+Nera", ("Asia/Ust+Nera", None, None)),
                ("Asia/Ust-Nera", ("Asia/Ust-Nera", None, None)),
                ("Asia/Ust+Nera-02:00", ("Asia/Ust+Nera", "-", "02:00")),
                ("Asia/Ust-Nera+05:00", ("Asia/Ust-Nera", "+", "05:00")),
                (
                    "America/Coral_Harbour-01:00",
                    ("America/Coral_Harbour", "-", "01:00"),
                ),
                (
                    "America/Coral_Harbour+02:30",
                    ("America/Coral_Harbour", "+", "02:30"),
                ),
                ("UTC+15:00", ("UTC", "+", "15:00")),
                ("UTC-04:43", ("UTC", "-", "04:43")),
                ("UTC", ("UTC", None, None)),
                ("UTC+1", ("UTC+1", None, None)),
            ]
            for tzname, expected in tests:
                with self.subTest(tzname=tzname):
                    self.assertEqual(split_tzname_delta(tzname), expected)
