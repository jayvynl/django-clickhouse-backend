from django.db.models.lookups import BuiltinLookup, IStartsWith, StartsWith

__all__ = [
    "patch_lookups",
    "patch_startswith",
    "patch_istartswith",
]


def patch_lookups():
    patch_startswith()
    patch_istartswith()


def process_prefix(lookup, compiler, connection):
    # BuiltinLookup.process_rhs, not PatternLookup's, passes the prefix as is,
    # without appending the % wildcard and escaping the % and _ it contains.
    lhs, lhs_params = lookup.process_lhs(compiler, connection)
    rhs, rhs_params = BuiltinLookup.process_rhs(lookup, compiler, connection)
    return lhs, rhs, (*lhs_params, *rhs_params)


def patch_startswith():
    def as_clickhouse(self, compiler, connection):
        lhs, rhs, params = process_prefix(self, compiler, connection)
        return f"startsWith({lhs}, {rhs})", params

    StartsWith.as_clickhouse = as_clickhouse


def patch_istartswith():
    def as_clickhouse(self, compiler, connection):
        lhs, rhs, params = process_prefix(self, compiler, connection)
        # Only the UTF8 variants fold the case beyond ASCII, as ILIKE does.
        if connection.features.has_starts_with_case_insensitive:
            return f"startsWithCaseInsensitiveUTF8({lhs}, {rhs})", params
        return f"startsWith(lowerUTF8({lhs}), lowerUTF8({rhs}))", params

    IStartsWith.as_clickhouse = as_clickhouse
