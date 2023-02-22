from django.conf import settings
from django.db.backends.base.operations import BaseDatabaseOperations

from clickhouse_backend import compat
from clickhouse_backend.utils import get_timezone
from clickhouse_backend.driver.client import insert_pattern


class DatabaseOperations(BaseDatabaseOperations):
    # Use this class attribute control whether using fake transaction.
    # Fake transaction is used in test, prevent other database such as postgresql
    # from flush at the end of each testcase. Only use this feature when you are
    # aware of the effect in TransactionTestCase.
    fake_transaction = False

    compiler_module = "clickhouse_backend.models.sql.compiler"
    cast_char_field_without_max_length = "String"
    integer_field_ranges = {
        # Django fields.
        "SmallIntegerField": (-32768, 32767),
        "IntegerField": (-2147483648, 2147483647),
        "BigIntegerField": (-9223372036854775808, 9223372036854775807),
        "PositiveBigIntegerField": (0, 18446744073709551615),
        "PositiveSmallIntegerField": (0, 65535),
        "PositiveIntegerField": (0, 4294967295),
        "SmallAutoField": (-32768, 32767),
        "AutoField": (-2147483648, 2147483647),
        "BigAutoField": (-9223372036854775808, 9223372036854775807),
        # Clickhouse fields.
        "Int8Field": (-1 << 7, -1 ^ (-1 << 7)),
        "Int16Field": (-1 << 15, -1 ^ (-1 << 15)),
        "Int32Field": (-1 << 31, -1 ^ (-1 << 31)),
        "Int64Field": (-1 << 63, -1 ^ (-1 << 63)),
        "Int128Field": (-1 << 127, -1 ^ (-1 << 127)),
        "Int256Field": (-1 << 255, -1 ^ (-1 << 255)),
        "UInt8Field": (0, -1 ^ (-1 << 8)),
        "UInt16Field": (0, -1 ^ (-1 << 16)),
        "UInt32Field": (0, -1 ^ (-1 << 32)),
        "UInt64Field": (0, -1 ^ (-1 << 64)),
        "UInt128Field": (0, -1 ^ (-1 << 128)),
        "UInt256Field": (0, -1 ^ (-1 << 256)),
    }
    set_operators = {
        "union": "UNION ALL",
        "intersection": "INTERSECT",
        "difference": "EXCEPT",
    }

    explain_prefix = "EXPLAIN"
    explain_types = {
        "AST",
        "SYNTAX",
        "PLAN",
        "PIPELINE",
        "ESTIMATE",
        "TABLE OVERRIDE",
    }
    explain_settings = {
        "header",
        "description",
        "indexes",
        "actions",
        "json",
    }
    # https://clickhouse.com/docs/en/sql-reference/formats
    supported_output_formats = {
        "TSV",
        "TabSeparated",
        "TabSeparatedRaw",
        "TabSeparatedWithNames",
        "TabSeparatedWithNamesAndTypes",
        "TabSeparatedRawWithNames",
        "TabSeparatedRawWithNamesAndTypes",
        "Template",
        "CSV",
        "CSVWithNames",
        "CSVWithNamesAndTypes",
        "CustomSeparated",
        "CustomSeparatedWithNames",
        "CustomSeparatedWithNamesAndTypes",
        "SQLInsert",
        "Values",
        "Vertical",
        "JSON",
        "JSONStrings",
        "JSONColumns",
        "JSONColumnsWithMetadata",
        "JSONCompact",
        "JSONCompactStrings",
        "JSONCompactColumns",
        "JSONEachRow",
        "JSONEachRowWithProgress",
        "JSONStringsEachRow",
        "JSONStringsEachRowWithProgress",
        "JSONCompactEachRow",
        "JSONCompactEachRowWithNames",
        "JSONCompactEachRowWithNamesAndTypes",
        "JSONCompactStringsEachRow",
        "JSONCompactStringsEachRowWithNames",
        "JSONCompactStringsEachRowWithNamesAndTypes",
        "JSONObjectEachRow",
        "TSKV",
        "Pretty",
        "PrettyNoEscapes",
        "PrettyMonoBlock",
        "PrettyNoEscapesMonoBlock",
        "PrettyCompact",
        "PrettyCompactNoEscapes",
        "PrettyCompactMonoBlock",
        "PrettyCompactNoEscapesMonoBlock",
        "PrettySpace",
        "PrettySpaceNoEscapes",
        "PrettySpaceMonoBlock",
        "PrettySpaceNoEscapesMonoBlock",
        "Prometheus",
        "Protobuf",
        "ProtobufSingle",
        "Avro",
        "Parquet",
        "Arrow",
        "ArrowStream",
        "ORC",
        "RowBinary",
        "RowBinaryWithNames",
        "RowBinaryWithNamesAndTypes",
        "Native",
        "Null",
        "XML",
        "CapnProto",
        "RawBLOB",
        "MsgPack",
    }

    def unification_cast_sql(self, output_field):
        db_type = output_field.db_type(self.connection)
        # normal django fields does not have 'nullable_allowed' attribute
        if (not hasattr(output_field, 'nullable_allowed')
                or output_field.nullable_allowed
                and not output_field.null):
            db_type = 'Nullable(%s)' % db_type
        return '%s::{}'.format(db_type)

    def date_extract_sql(self, lookup_type, sql, *args):
        # https://clickhouse.com/docs/en/sql-reference/functions/date-time-functions/
        if lookup_type == "iso_year":
            sql = f"toISOYear(%s)" % sql
        elif lookup_type == "day":
            sql = f"toDayOfMonth(%s)" % sql
        elif lookup_type == "week":
            sql = f"toISOWeek(%s)" % sql
        elif lookup_type == "week_day":
            sql = f"modulo(toDayOfWeek(%s), 7) + 1" % sql
        elif lookup_type == "iso_week_day":
            sql = f"toDayOfWeek(%s)" % sql
        else:
            sql = f"to%s(%s)" % (lookup_type.capitalize(), sql)
        if compat.dj_ge41:
            return sql, args[0]
        else:
            return sql

    def date_trunc_sql(self, lookup_type, sql, *args):
        # https://clickhouse.com/docs/en/sql-reference/functions/date-time-functions#tostartofyear
        *ex, tzname = args
        tzname = tzname or get_timezone()
        sql = "toDate(%s, '%s')" % (sql, tzname)
        if lookup_type != "day":
            sql = f"toStartOf{lookup_type.capitalize()}({sql})"

        if compat.dj_ge41:
            return sql, ex[0]
        else:
            return sql

    def datetime_cast_date_sql(self, sql, *args):
        *ex, tzname = args
        tzname = tzname or get_timezone()
        sql = "toDate(%s, '%s')" % (sql, tzname)
        if compat.dj_ge41:
            return sql, ex[0]
        else:
            return sql

    def datetime_extract_sql(self, lookup_type, sql, *args):
        *ex, tzname = args
        tzname = tzname or get_timezone()
        sql = "toTimeZone(%s, '%s')" % (sql, tzname)
        return self.date_extract_sql(lookup_type, sql, *ex)

    def datetime_trunc_sql(self, lookup_type, sql, *args):
        # https://clickhouse.com/docs/en/sql-reference/functions/date-time-functions/#date_trunc
        *ex, tzname = args
        if tzname:
            sql = "date_trunc('%s', %s, '%s')" % (lookup_type, sql, tzname)
        else:
            sql = "date_trunc('%s', %s)" % (lookup_type, sql)
        if compat.dj_ge41:
            return sql, ex[0]
        else:
            return sql

    def distinct_sql(self, fields, params):
        if fields:
            params = [param for param_list in params for param in param_list]
            return (["DISTINCT ON (%s)" % ", ".join(fields)], params)
        else:
            return ["DISTINCT"], []

    def lookup_cast(self, lookup_type, internal_type=None):
        lookup = "%s"

        # Cast text lookups to text to allow things like filter(x__contains=4)
        if lookup_type in ("iexact", "contains", "icontains", "startswith",
                           "istartswith", "endswith", "iendswith", "regex", "iregex"):
            if internal_type == "IPAddressField" or internal_type == "IPv4Field":
                lookup = "IPv4NumToString(%s)"
            elif internal_type == "IPv6Field":
                lookup = "IPv6NumToString(%s)"
            elif internal_type == "GenericIPAddressField":
                lookup = "replaceRegexpOne(IPv6NumToString(%s), '^::ffff:', '')"
            elif internal_type in ("EnumField", "Enum8Field", "Enum16Field"):
                lookup = "toString(%s)"
            else:
                lookup = "CAST(%s, 'Nullable(String)')"

        if lookup_type == "iexact":
            lookup = "UPPER(%s)" % lookup

        return lookup

    def max_name_length(self):
        """
        Return the maximum length of an identifier.

        https://stackoverflow.com/a/68362429/15096024
        Clickhouse does not have own limits on identifier's length.
        But you're limited by a filesystem's limits, because CH uses filenames as table/column names.
        Ext4 max filename length -- ext4 255 bytes. And a maximum path of 4096 characters.

        An example metadata_path from system.tables:
        /var/lib/clickhouse_backend/store/c13/c13f3d33-7a2e-4e30-813f-3d337a2e7e30/test.sql
        Take off the .sql suffix, actual length limit is 251
        """
        return 251

    def max_in_list_size(self):
        """
        The maximum size of an array is limited to one million elements.
        https://clickhouse.com/docs/en/sql-reference/data-types/array#working-with-data-types
        """
        return 1000000

    def no_limit_value(self):
        return None

    def prepare_sql_script(self, sql):
        return [sql]

    def quote_name(self, name):
        if name.startswith('"') and name.endswith('"'):
            return name  # Quoting once is enough.
        return '"%s"' % name

    def regex_lookup(self, lookup_type):
        if lookup_type == "regex":
            return "match(%s, %s)"
        else:
            return "match(%s, concat('(?i)', %s))"

    def sql_flush(self, style, tables, *, reset_sequences=False, allow_cascade=False):
        return [
            '%s %s' % (
                style.SQL_KEYWORD('TRUNCATE'),
                style.SQL_FIELD(self.quote_name(table))
            )
            for table in tables
        ]

    def prep_for_iexact_query(self, x):
        return x

    def bulk_insert_sql(self, fields, placeholder_rows):
        # https://clickhouse-driver.readthedocs.io/en/latest/quickstart.html#inserting-data
        # To insert data efficiently, provide data separately,
        # and end your statement with a VALUES clause:
        return "VALUES"

    def adapt_datefield_value(self, value):
        return value

    def adapt_datetimefield_value(self, value):
        return value

    def adapt_decimalfield_value(self, value, max_digits=None, decimal_places=None):
        return value

    def explain_query_prefix(self, format=None, **options):
        # bypass normal explain prefix insert in compiler.as_sql
        return ""

    def explain_query(self, format=None, type=None, **settings):
        # https://clickhouse.com/docs/en/sql-reference/statements/explain/
        prefix = self.explain_prefix
        suffix = ""
        options = {}
        unknown_settings = []
        for setting, value in settings:
            if setting in self.explain_settings:
                options[setting] = int(bool(value))
            else:
                unknown_settings.append(setting)

        if format:
            supported_formats = self.supported_output_formats
            normalized_format = format.upper()
            if normalized_format not in supported_formats:
                msg = "%s is not a recognized format." % normalized_format
                if supported_formats:
                    msg += " Allowed formats: %s" % ", ".join(sorted(supported_formats))
                else:
                    msg += (
                        f" {self.connection.display_name} does not support any formats."
                    )
                raise ValueError(msg)
            suffix = "FORMAT %s" % normalized_format
        if unknown_settings:
            raise ValueError("Unknown settings: %s" % ", ".join(sorted(unknown_settings)))
        if type:
            normalized_type = type.upper()
            if normalized_type not in self.explain_types:
                msg = "%s is not a recognized type. Allowed types: %s." % (
                    normalized_type,
                    ", ".join(sorted(self.explain_types))
                )
                raise ValueError(msg)
            prefix += " %s" % normalized_type
        if options:
            prefix += " %s" % ", ".join("%s=%s" % i for i in options.items())
        return prefix, suffix

    def last_insert_id(self, cursor, table_name, pk_name):
        query = "SELECT %s FROM %s ORDER BY %s DESC LIMIT 1"
        params = (self.quote_name(pk_name), self.quote_name(table_name), self.quote_name(pk_name))
        cursor.execute(query % params)
        return cursor.fetchone()[0]

    def savepoint_create_sql(self, sid):
        if self.fake_transaction:
            return "SELECT 1"
        return super().savepoint_create_sql(sid)

    def savepoint_commit_sql(self, sid):
        if self.fake_transaction:
            return "SELECT 1"
        return super().savepoint_commit_sql(sid)

    def savepoint_rollback_sql(self, sid):
        if self.fake_transaction:
            return "SELECT 1"
        return super().savepoint_rollback_sql(sid)

    def last_executed_query(self, cursor, sql, params):
        if params:
            if insert_pattern.match(sql):
                return "%s %s" % (sql, ", ".join(map(str, params)))
            else:
                return sql % tuple(params)
        return sql

    def settings_sql(self, **kwargs):
        result = []
        params = []
        unknown_settings = []
        for setting, value in kwargs.items():
            if setting in self.connection.introspection.settings:
                result.append("%s=%%s" % setting)
                params.append(value)
            else:
                unknown_settings.append(setting)
        if unknown_settings:
            raise ValueError("Unknown settings: %s" %
                             ", ".join(sorted(unknown_settings)))
        sql = "SETTINGS %s" % ", ".join(result)
        return sql, params
