from django.db.backends.base.introspection import (
    BaseDatabaseIntrospection, FieldInfo, TableInfo,
)


class DatabaseIntrospection(BaseDatabaseIntrospection):
    # Maps type codes to Django Field types.
    data_types_reverse = {
        # 'String': 'BinaryField',
        # The best type for String is BinaryField, but sometime you may need TextField.
        'String': 'TextField',
        'Int64': 'BigIntegerField',
        'Int16': 'SmallIntegerField',
        'Int32': 'IntegerField',
        'UInt64': 'PositiveBigIntegerField',
        'UInt16': 'PositiveSmallIntegerField',
        'UInt32': 'PositiveIntegerField',
        'Float32': 'FloatField',
        'Float64': 'FloatField',
        'IPv4': 'IPAddressField',
        'IPv6': 'GenericIPAddressField',
        'Date': 'DateField',
        'Date32': 'DateField',
        'DateTime': 'DateTimeField',
        'UUID': 'UUIDField',
    }

    ignored_tables = []

    def get_field_type(self, data_type, description):
        if data_type.startswith('FixedString'):  # FixedString(20)
            return 'CharField'
        elif data_type.startswith('DateTime64'):
            return 'DateTimeField'
        elif data_type.startswith('Decimal'):
            return 'DecimalField'
        elif data_type.startswith('Nullable'):  # Nullable(Int16)
            return self.get_field_type(data_type[9:-1], description)
        return super().get_field_type(data_type, description)

    def get_table_list(self, cursor):
        """Return a list of table and view names in the current database."""
        cursor.execute("""
            SELECT table_name,
            CASE table_type WHEN 2 THEN 'v' ELSE 't' END
            FROM INFORMATION_SCHEMA.TABLES
            WHERE table_catalog = currentDatabase()
            AND table_type IN (1, 2)
        """)
        return [TableInfo(*row) for row in cursor.fetchall() if row[0] not in self.ignored_tables]

    def get_table_description(self, cursor, table_name):
        """
        Return a description of the table with the DB-API cursor.description
        interface.
        """
        # Query the pg_catalog tables as cursor.description does not reliably
        # return the nullable property and information_schema.columns does not
        # contain details of materialized views.
        cursor.execute("""
            SELECT column_name, data_type, NULL, character_maximum_length,
            coalesce(numeric_precision, datetime_precision),
            numeric_scale, is_nullable, column_default
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE table_catalog = currentDatabase() AND table_name = %s
        """, [table_name])
        return [
            FieldInfo(
                *line, None
            )
            for line in cursor.fetchall()
        ]
