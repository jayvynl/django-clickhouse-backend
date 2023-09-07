import re
from typing import Dict

from clickhouse_driver import connection
from clickhouse_driver.dbapi import connection as dbapi_connection
from clickhouse_driver.dbapi import cursor, errors
from clickhouse_pool.pool import ChPoolError

from .escape import escape_params
from .pool import ClickhousePool

update_pattern = re.compile(
    r"^\s*alter\s+table\s+(\S+)\s+.*?update.+?where\s+(.+?)(?:settings\s+.+)?$",
    flags=re.IGNORECASE,
)


def send_query(self, query, query_id=None, params=None):
    if not self.connected:
        self.connect()

    connection.write_varint(connection.ClientPacketTypes.QUERY, self.fout)

    connection.write_binary_str(query_id or "", self.fout)

    revision = self.server_info.used_revision
    if revision >= connection.defines.DBMS_MIN_REVISION_WITH_CLIENT_INFO:
        client_info = connection.ClientInfo(
            self.client_name, self.context, client_revision=self.client_revision
        )
        client_info.query_kind = connection.ClientInfo.QueryKind.INITIAL_QUERY

        client_info.write(revision, self.fout)

    settings_as_strings = (
        revision
        >= connection.defines.DBMS_MIN_REVISION_WITH_SETTINGS_SERIALIZED_AS_STRINGS
    )
    settings_flags = 0
    if self.settings_is_important:
        settings_flags |= connection.SettingsFlags.IMPORTANT
    connection.write_settings(
        self.context.settings, self.fout, settings_as_strings, settings_flags
    )

    if revision >= connection.defines.DBMS_MIN_REVISION_WITH_INTERSERVER_SECRET:
        connection.write_binary_str("", self.fout)

    connection.write_varint(connection.QueryProcessingStage.COMPLETE, self.fout)
    connection.write_varint(self.compression, self.fout)

    connection.write_binary_str(query, self.fout)

    if revision >= connection.defines.DBMS_MIN_PROTOCOL_VERSION_WITH_PARAMETERS:
        if not isinstance(params, Dict):
            params = None
        # Always settings_as_strings = True
        escaped = escape_params(params or {}, self.context, for_server=True)
        connection.write_settings(
            escaped, self.fout, True, connection.SettingsFlags.CUSTOM
        )

    connection.logger.debug("Query: %s", query)

    self.fout.flush()


# Monkey patch to resolve https://github.com/jayvynl/django-clickhouse-backend/issues/14
connection.Connection.send_query = send_query


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

    def execute(self, operation, parameters=None):
        """fix https://github.com/jayvynl/django-clickhouse-backend/issues/9"""
        if update_pattern.match(operation):
            query = self._client.substitute_params(
                operation, parameters, self._client.connection.context
            )
            table, where = update_pattern.match(query).groups()
            super().execute(f"select count(*) from {table} where {where}")
            (rowcount,) = self.fetchone()
            self._reset_state()
            self._rowcount = rowcount
        super().execute(operation, parameters)


class Connection(dbapi_connection.Connection):
    """Connection class with support for connection pool."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kwargs.setdefault("connections_min", 10)
        kwargs.setdefault("connections_max", 100)
        self.pool = ClickhousePool(
            dsn=self.dsn,
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            **self.connection_kwargs,
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
            raise errors.InterfaceError("connection already closed")

        client = self._make_client()
        if self._hosts is None:
            self._hosts = client.connection.hosts
        else:
            client.connection.hosts = self._hosts
        cursor_factory = cursor_factory or Cursor
        return cursor_factory(client, self)
