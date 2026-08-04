import socket
from unittest import mock

from django.db import connection
from django.test import TestCase

from clickhouse_backend.driver import connect

from .. import models


class Tests(TestCase):
    def test_pool_size(self):
        conn = connect(host="localhost", connections_min=2, connections_max=4)
        assert conn.pool.connections_min == 2
        assert conn.pool.connections_max == 4
        assert len(conn.pool._pool) == 2


class PoolCleanupTests(TestCase):
    def test_disconnect_error_is_logged_and_does_not_stop_cleanup(self):
        """
        A client that fails to disconnect must not silence the failure, nor
        prevent the remaining clients from being closed.
        """
        pool = connect(host="localhost", connections_min=2, connections_max=4).pool
        failing, healthy = pool._pool
        error = OSError("cannot disconnect")
        failing.disconnect = mock.Mock(side_effect=error)
        healthy.disconnect = mock.Mock()

        with self.assertLogs("clickhouse_backend.driver.pool", "WARNING") as logs:
            pool.cleanup()

        assert pool.closed
        healthy.disconnect.assert_called_once_with()
        (record,) = logs.records
        # Rendering the message must not raise for a client that never
        # connected, otherwise it would hide the error being reported.
        assert repr(failing.connection) in record.getMessage()
        assert record.exc_info[1] is error


class ConnectionRecoveryTests(TestCase):
    def test_connection_that_died_while_pooled_is_recovered_on_use(self):
        """
        A pooled connection can be dropped by the server at any point while it
        sits idle, which is why push() does not check liveness on the way in.
        Recovery happens on use: clickhouse_driver pings and reconnects when a
        query is issued.
        """
        with connection.cursor() as cursor:
            cursor.execute("select 1")
            assert cursor.fetchall() == [(1,)]

        (client,) = connection.connection.pool._pool
        # Mimic the server hanging up on an idle pooled connection.
        client.connection.socket.shutdown(socket.SHUT_RDWR)
        # The connection is dead, but its own flag does not know that yet.
        assert client.connection.connected

        with connection.cursor() as cursor:
            cursor.execute("select 2")
            assert cursor.fetchall() == [(2,)]


class IterationTests(TestCase):
    """
    Testing connection behaviour when iterating over queryset is interrupted.
    """

    @classmethod
    def setUpTestData(cls):
        cls.a1, cls.a2, cls.a3 = models.Author.objects.bulk_create(
            [
                models.Author(name="a1"),
                models.Author(name="a2"),
                models.Author(name="a3"),
            ]
        )

    def test_connection_not_reused_when_iteration_interrupted(self):
        """
        This test demonstrates that if a queryset is iterated over and the
        iteration is interrupted (e.g. via a break statement), the connection
        used for that iteration is disconnected and not returned to the pool.
        """
        pool = connection.connection.pool

        connection_count_before = len(pool._pool)
        assert connection_count_before == 1

        authors = models.Author.objects.all()
        for author in authors.iterator(1):
            author = author.name
            break

        connection_count_after_iterator = len(pool._pool)
        # Connection was closed and not returned to pool
        assert connection_count_after_iterator == 0

        author = authors.get(id=self.a1.id)
