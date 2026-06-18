"""ClickHouse SQL rendering hooks for selected Django field lookups.

This module teaches Django's ``startswith`` and ``istartswith`` lookups how to
compile to ClickHouse-native string functions. Django's query compiler calls
the ``as_clickhouse()`` methods added here when building SQL for the ClickHouse
backend.
"""

from django.db.models.lookups import BuiltinLookup, StartsWith, IStartsWith


def startswith_as_clickhouse(self, compiler, connection):
    """Render Django's case-sensitive ``startswith`` lookup for ClickHouse."""
    lhs_sql, lhs_params = self.process_lhs(compiler, connection)
    rhs_sql, rhs_params = BuiltinLookup.process_rhs(self, compiler, connection)

    return f"startsWith({lhs_sql}, {rhs_sql})", lhs_params + rhs_params


def istartswith_as_clickhouse(self, compiler, connection):
    """Render Django's case-insensitive ``istartswith`` lookup for ClickHouse."""
    lhs_sql, lhs_params = self.process_lhs(compiler, connection)
    rhs_sql, rhs_params = BuiltinLookup.process_rhs(self, compiler, connection)

    return (
        f"startsWithCaseInsensitive({lhs_sql}, {rhs_sql})",
        lhs_params + rhs_params,
    )


StartsWith.as_clickhouse = startswith_as_clickhouse
IStartsWith.as_clickhouse = istartswith_as_clickhouse
