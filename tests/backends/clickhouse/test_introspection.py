from django.db import connection
from django.test import TestCase

from ..models import Person


class DatabaseIntrospectionTests(TestCase):
    def test_field_type(self):
        self.assertEqual(
            connection.introspection.get_field_type("FixedString(20)", ""),
            "FixedStringField",
        )
        self.assertEqual(
            connection.introspection.get_field_type("DateTime64(6, 'UTC')", ""),
            "DateTime64Field",
        )
        self.assertEqual(
            connection.introspection.get_field_type("Nullable(Decimal(8, 2))", ""),
            "DecimalField",
        )
        self.assertEqual(
            connection.introspection.get_field_type(
                "LowCardinality(Nullable(Decimal(8, 2)))", ""
            ),
            "DecimalField",
        )

    def test_table_list(self):
        with connection.cursor() as cursor:
            self.assertIn(
                (Person._meta.db_table, "t", ""),
                connection.introspection.get_table_list(cursor),
            )

    def test_table_description(self):
        with connection.cursor() as cursor:
            self.assertEqual(
                [field.column for field in Person._meta.fields],
                [
                    info.name
                    for info in connection.introspection.get_table_description(
                        cursor, Person._meta.db_table
                    )
                ],
            )
