from clickhouse_driver.dbapi import connection
from clickhouse_driver.dbapi import cursor

from .pool import ClickhousePool


class Cursor(cursor.Cursor):
    def close(self):
        """Push client back to connection pool"""
        self._state = self._states.CURSOR_CLOSED
        self._connection.pool.push(self._client)

    @property
    def closed(self):
        return self._state == self._states.CURSOR_CLOSED


class Connection(connection.Connection):
    """Connection class with support for connection pool."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = ClickhousePool(
            connections_min=kwargs.pop('connections_min', 0),
            connections_max=kwargs.pop('connections_max', 500),
            dsn=self.dsn, host=self.host, port=self.port,
            user=self.user, password=self.password,
            database=self.database, **self.connection_kwargs,
        )

    def _make_client(self):
        """
        :return: a new Client instance.
        """
        return self.pool.pull()

    def close(self):
        self.pool.cleanup()
        self.is_closed = True

    def cursor(self, cursor_factory=Cursor):
        """Use clickhouse_backend.connection.Cursor which support
        connection pool to create cursor."""
        return super().cursor(cursor_factory)
