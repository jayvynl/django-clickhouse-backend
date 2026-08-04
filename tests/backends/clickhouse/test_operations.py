from django.core.management.color import no_style
from django.db import connection
from django.test import SimpleTestCase

from ..models import Person, Tag


class OperationsTests(SimpleTestCase):
    def test_sql_flush(self):
        self.assertEqual(
            connection.ops.sql_flush(
                no_style(),
                [Person._meta.db_table, Tag._meta.db_table],
            ),
            [
                'TRUNCATE "backends_person"',
                'TRUNCATE "backends_tag"',
            ],
        )


class ExplainQueryTests(SimpleTestCase):
    def test_no_options(self):
        self.assertEqual(connection.ops.explain_query(), ("EXPLAIN", ""))

    def test_type(self):
        self.assertEqual(
            connection.ops.explain_query(type="pipeline"), ("EXPLAIN PIPELINE", "")
        )

    def test_query_tree_type(self):
        self.assertEqual(
            connection.ops.explain_query(type="query tree"),
            ("EXPLAIN QUERY TREE", ""),
        )

    def test_unknown_type(self):
        with self.assertRaisesMessage(ValueError, "BOGUS is not a recognized type."):
            connection.ops.explain_query(type="bogus")

    def test_settings(self):
        prefix, suffix = connection.ops.explain_query(indexes=True)
        self.assertEqual(prefix, "EXPLAIN indexes=1")
        self.assertEqual(suffix, "")

    def test_unknown_settings(self):
        with self.assertRaisesMessage(ValueError, "Unknown settings: bogus"):
            connection.ops.explain_query(bogus=True)

    def test_format_keeps_clickhouse_spelling(self):
        # Output format names are not all upper case, so they must not be
        # normalized by upper casing them.
        for format in ["TabSeparated", "tabseparated", "TABSEPARATED"]:
            with self.subTest(format=format):
                self.assertEqual(
                    connection.ops.explain_query(format=format),
                    ("EXPLAIN", "FORMAT TabSeparated"),
                )

    def test_unknown_format(self):
        with self.assertRaisesMessage(ValueError, "bogus is not a recognized format."):
            connection.ops.explain_query(format="bogus")
