from clickhouse_driver.dbapi import connection
from clickhouse_driver.dbapi import cursor
from clickhouse_driver.dbapi import errors
from clickhouse_pool.pool import ChPoolError

from .pool import ClickhousePool


class Cursor(cursor.Cursor):
    def close(self):
        """Push client back to connection pool"""
        self._state = self._states.CURSOR_CLOSED
        try:
            self._connection.pool.push(self._client)
        except ChPoolError:
            pass

    @property
    def closed(self):
        return self._state == self._states.CURSOR_CLOSED

    def __del__(self):
        # If someone forgets calling close method,
        # then release connection when gc happens.
        if not self.closed:
            try:
                self._connection.pool.push(self._client)
            except ChPoolError:
                pass


class Connection(connection.Connection):
    """Connection class with support for connection pool."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = ClickhousePool(
            connections_min=kwargs.pop('connections_min', 10),
            connections_max=kwargs.pop('connections_max', 100),
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
        if self.is_closed:
            raise errors.InterfaceError('connection already closed')

        client = self._make_client()
        if self._hosts is None:
            self._hosts = client.connection.hosts
        else:
            client.connection.hosts = self._hosts
        cursor_factory = cursor_factory or Cursor
        return cursor_factory(client, self)
