from django.db import InterfaceError
from django.db.backends.base.features import BaseDatabaseFeatures
from django.utils.functional import cached_property


class DatabaseFeatures(BaseDatabaseFeatures):
    # Use this class attribute control whether using fake transaction.
    # Fake transaction is used in test, prevent other database such as postgresql
    # from flush at the end of each testcase. Only use this feature when you are
    # aware of the effect in TransactionTestCase.
    fake_transaction = False
    # Clickhouse do support Geo Data Types, but they are based on GeoJSON instead GIS.
    # https://clickhouse.com/docs/en/sql-reference/data-types/geo/
    # gis_enabled = False

    # There is no dedicated LOB type in clickhouse_backend, LOB is stored as string type.
    # https://clickhouse.com/docs/en/sql-reference/data-types/string/
    # allows_group_by_lob = True

    # In clickhouse_backend MergeTree table family, PK have different meaning as in RDBMS
    # PK is used for efficient range scans, pk can be duplicated, no auto incr pk.
    # https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree/#primary-keys-and-indexes-in-queries
    allows_group_by_pk = False
    allows_group_by_selected_pks = False

    # There is no unique constraint in clickhouse_backend.
    # supports_nullable_unique_constraints = True
    # supports_partially_nullable_unique_constraints = True
    supports_deferrable_unique_constraints = True

    # Transaction is not supported, and limited transaction is under development.
    # https://clickhouse.com/docs/en/sql-reference/ansi/
    # https://github.com/ClickHouse/ClickHouse/issues/32513
    @cached_property
    def uses_savepoints(self):
        return self.fake_transaction
    can_release_savepoints = False

    # Is there a true datatype for uuid?
    has_native_uuid_field = True

    # Clickhouse use re2 syntax which does not support backreference.
    supports_regex_backreferencing = False

    # Can date/datetime lookups be performed using a string?
    supports_date_lookup_using_string = False

    # Confirm support for introspected foreign keys
    # Every database can do this reliably, except MySQL,
    # which can't do it for MyISAM tables
    can_introspect_foreign_keys = False

    # Map fields which some backends may not be able to differentiate to the
    # field it's introspected as.
    introspected_field_types = {
        'BigIntegerField': 'BigIntegerField',
        'BinaryField': 'BinaryField',
        'BooleanField': 'BooleanField',
        'CharField': 'CharField',
        'DurationField': 'DurationField',
        'GenericIPAddressField': 'GenericIPAddressField',
        'IntegerField': 'IntegerField',
        'PositiveBigIntegerField': 'PositiveBigIntegerField',
        'PositiveIntegerField': 'PositiveIntegerField',
        'PositiveSmallIntegerField': 'PositiveSmallIntegerField',
        'SmallIntegerField': 'SmallIntegerField',
        'TimeField': 'TimeField',
    }

    # https://clickhouse.com/docs/en/sql-reference/statements/alter/index/
    # Index manipulation is supported only for tables with *MergeTree* engine (including replicated variants).
    supports_index_column_ordering = False

    # Does the backend support introspection of materialized views?
    can_introspect_materialized_views = False

    # Support for the DISTINCT ON clause
    can_distinct_on_fields = True

    # Does the backend prevent running SQL queries in broken transactions?
    atomic_transactions = False

    # Does it support operations requiring references rename in a transaction?
    supports_atomic_references_rename = False

    # Can we issue more than one ALTER COLUMN clause in an ALTER TABLE?
    supports_combined_alters = True

    # Does it support foreign keys?
    supports_foreign_keys = False

    # Does it support CHECK constraints?
    supports_column_check_constraints = False
    supports_table_check_constraints = True
    # Does the backend support introspection of CHECK constraints?
    can_introspect_check_constraints = False

    # What kind of error does the backend throw when accessing closed cursor?
    closed_cursor_error_class = InterfaceError

    # Does 'a' LIKE 'A' match?
    has_case_insensitive_like = False

    # https://clickhouse.com/docs/en/sql-reference/statements/insert-into/#constraints
    supports_ignore_conflicts = False

    # Does the backend support partial indexes (CREATE INDEX ... WHERE ...)?
    supports_partial_indexes = False

    # Does the backend support JSONField?
    supports_json_field = False

    # Does the backend support column collations?
    supports_collation_on_charfield = False
    supports_collation_on_textfield = False
    # Does the backend support non-deterministic collations?
    supports_non_deterministic_collations = False

    # SQL template override for tests.aggregation.tests.NowUTC
    test_now_utc_template = 'now64()'

    @cached_property
    def supports_explaining_query_execution(self):
        """Does this backend support explaining query execution?"""
        return True

    @cached_property
    def supports_transactions(self):
        return self.fake_transaction
