from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.utils import (
    CursorDebugWrapper as BaseCursorDebugWrapper
)
from django.db.utils import DEFAULT_DB_ALIAS
from django.utils.asyncio import async_unsafe

from clickhouse_backend import driver as Database
from .client import DatabaseClient  # NOQA
from .creation import DatabaseCreation  # NOQA
from .features import DatabaseFeatures  # NOQA
from .introspection import DatabaseIntrospection  # NOQA
from .operations import DatabaseOperations  # NOQA
from .schema import DatabaseSchemaEditor  # NOQA


class DatabaseWrapper(BaseDatabaseWrapper):
    vendor = 'clickhouse'
    display_name = 'ClickHouse'
    # This dictionary maps Field objects to their associated ClickHouse column
    # types, as strings. Column-type strings can contain format strings; they'll
    # be interpolated against the values of Field.__dict__ before being output.
    # If a column type is set to None, it won't be included in the output.
    data_types = {
        'AutoField': 'Int32',
        'BigAutoField': 'Int64',
        'IPAddressField': 'IPv4',
        'GenericIPAddressField': 'IPv6',
        'BinaryField': 'String',
        'CharField': 'FixedString(%(max_length)s)',
        'DateField': 'Date32',
        'DateTimeField': "DateTime64(6, 'UTC')" if settings.USE_TZ else 'DateTime64(6)',
        'DecimalField': 'Decimal(%(max_digits)s, %(decimal_places)s)',
        'FileField': 'String',
        'FilePathField': 'String',
        'FloatField': 'Float64',
        'IntegerField': 'Int32',
        'BigIntegerField': 'Int64',
        'PositiveBigIntegerField': 'UInt64',
        'PositiveIntegerField': 'UInt32',
        'PositiveSmallIntegerField': 'UInt16',
        'SlugField': 'String',
        'SmallIntegerField': 'Int16',
        'TextField': 'String',
        'UUIDField': 'UUID',
        'BooleanField': 'Int8',
    }
    operators = {
        'exact': '= %s',
        'iexact': '= UPPER(%s)',
        'contains': 'LIKE %s',
        'icontains': 'ILIKE %s',
        'gt': '> %s',
        'gte': '>= %s',
        'lt': '< %s',
        'lte': '<= %s',
        'startswith': 'LIKE %s',
        'endswith': 'LIKE %s',
        'istartswith': 'LIKE UPPER(%s)',
        'iendswith': 'LIKE UPPER(%s)',
    }

    # The patterns below are used to generate SQL pattern lookup clauses when
    # the right-hand side of the lookup isn't a raw string (it might be an expression
    # or the result of a bilateral transformation).
    # In those cases, special characters for LIKE operators (e.g. \, *, _) should be
    # escaped on database side.
    #
    # Note: we use str.format() here for readability as '%' is used as a wildcard for
    # the LIKE operator.
    pattern_esc = r"replaceAll(replaceAll(replaceAll({}, '\\', '\\\\'), '%', '\\%'), '_', '\\_')"
    pattern_ops = {
        'contains': "LIKE '%%' || {} || '%%'",
        'icontains': "LIKE '%%' || UPPER({}) || '%%'",
        'startswith': "LIKE {} || '%%'",
        'istartswith': "LIKE UPPER({}) || '%%'",
        'endswith': "LIKE '%%' || {}",
        'iendswith': "LIKE '%%' || UPPER({})",
    }

    Database = Database
    SchemaEditorClass = DatabaseSchemaEditor
    # Classes instantiated in __init__().
    client_class = DatabaseClient
    creation_class = DatabaseCreation
    features_class = DatabaseFeatures
    introspection_class = DatabaseIntrospection
    ops_class = DatabaseOperations

    def __init__(self, settings_dict, alias=DEFAULT_DB_ALIAS):
        super().__init__(settings_dict, alias)
        # Use fake_transaction control whether using fake transaction.
        # Fake transaction is used in test, prevent other database such as postgresql
        # from flush at the end of each testcase. Only use this feature when you are
        # aware of the effect in TransactionTestCase.
        self.fake_transaction = settings_dict.get('fake_transaction', False)

    @property
    def fake_transaction(self):
        return self._fake_transaction

    @fake_transaction.setter
    def fake_transaction(self, value):
        self._fake_transaction = value
        self.features.fake_transaction = self._fake_transaction
        self.ops.fake_transaction = self._fake_transaction

    def get_connection_params(self):
        settings_dict = self.settings_dict
        if len(settings_dict['NAME'] or '') > self.ops.max_name_length():
            raise ImproperlyConfigured(
                "The database name '%s' (%d characters) is longer than "
                "Clickhouse's limit of %d characters. Supply a shorter NAME "
                "in settings.DATABASES." % (
                    settings_dict['NAME'],
                    len(settings_dict['NAME']),
                    self.ops.max_name_length(),
                )
            )

        conn_params = {
            'host': settings_dict['HOST'] or 'localhost',
            **settings_dict.get('OPTIONS', {}),
        }
        if settings_dict['NAME']:
            conn_params['database'] = settings_dict['NAME']
        if settings_dict['USER']:
            conn_params['user'] = settings_dict['USER']
        if settings_dict['PASSWORD']:
            conn_params['password'] = settings_dict['PASSWORD']
        if settings_dict['PORT']:
            conn_params['port'] = settings_dict['PORT']
        return conn_params

    @async_unsafe
    def get_new_connection(self, conn_params):
        connection = Database.connect(**conn_params)
        return connection

    def init_connection_state(self):
        pass

    @async_unsafe
    def create_cursor(self, name=None):
        return self.connection.cursor()

    def _set_autocommit(self, autocommit):
        pass

    def is_usable(self):
        try:
            # Use a psycopg cursor directly, bypassing Django's utilities.
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Database.Error:
            return False
        else:
            return True

    def make_debug_cursor(self, cursor):
        return CursorDebugWrapper(cursor, self)


class CursorDebugWrapper(BaseCursorDebugWrapper):
    pass
