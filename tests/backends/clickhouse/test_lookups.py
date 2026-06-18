from unittest import mock

from django.db.models.lookups import BuiltinLookup, IStartsWith, StartsWith
from django.test import SimpleTestCase

from clickhouse_backend.backend import lookups as clickhouse_lookups


class LookupTests(SimpleTestCase):
    def assertLookupCompiles(self, lookup_class, expected_sql):
        lookup = object.__new__(lookup_class)
        lookup.process_lhs = mock.Mock(return_value=('"field"', ["lhs-param"]))

        with mock.patch.object(
            BuiltinLookup,
            "process_rhs",
            return_value=("%s", ["rhs-param"]),
        ) as process_rhs:
            sql, params = lookup.as_clickhouse(
                mock.sentinel.compiler,
                mock.sentinel.connection,
            )

        self.assertEqual(sql, expected_sql)
        self.assertEqual(params, ["lhs-param", "rhs-param"])
        lookup.process_lhs.assert_called_once_with(
            mock.sentinel.compiler,
            mock.sentinel.connection,
        )
        process_rhs.assert_called_once_with(
            lookup,
            mock.sentinel.compiler,
            mock.sentinel.connection,
        )

    def test_startswith_registered_as_clickhouse_lookup(self):
        self.assertIs(
            StartsWith.as_clickhouse,
            clickhouse_lookups.startswith_as_clickhouse,
        )

    def test_istartswith_registered_as_clickhouse_lookup(self):
        self.assertIs(
            IStartsWith.as_clickhouse,
            clickhouse_lookups.istartswith_as_clickhouse,
        )

    def test_startswith_compiles_to_clickhouse_function(self):
        self.assertLookupCompiles(StartsWith, 'startsWith("field", %s)')

    def test_istartswith_compiles_to_clickhouse_function(self):
        self.assertLookupCompiles(
            IStartsWith,
            'startsWithCaseInsensitive("field", %s)',
        )
