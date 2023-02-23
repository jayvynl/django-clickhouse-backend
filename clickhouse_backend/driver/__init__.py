from clickhouse_driver import defines
from clickhouse_driver.dbapi import (  # NOQA
    apilevel, threadsafety, paramstyle, __all__
)
from clickhouse_driver.dbapi.errors import (  # NOQA
    Warning, Error, DataError, DatabaseError, ProgrammingError, IntegrityError,
    InterfaceError, InternalError, NotSupportedError, OperationalError
)

from .connection import Connection
# Binary is compatible for django's BinaryField.
from .types import (  # NOQA
    Binary
)


def connect(dsn=None, host=None,
            user=defines.DEFAULT_USER, password=defines.DEFAULT_PASSWORD,
            port=defines.DEFAULT_PORT, database=defines.DEFAULT_DATABASE,
            **kwargs):
    """
    Support dict type params in INSERT query and support connection pool.
    """

    if dsn is None and host is None:
        raise ValueError('host or dsn is required')

    return Connection(dsn=dsn, user=user, password=password, host=host,
                      port=port, database=database, **kwargs)
