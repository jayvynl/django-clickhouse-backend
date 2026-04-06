from unittest.mock import MagicMock, PropertyMock, patch

from django.db import connection
from django.test import TestCase

from clickhouse_backend.driver import connect
from clickhouse_backend.driver.pool import ClickhousePool

from .. import models


class Tests(TestCase):
    def test_pool_size(self):
        conn = connect(host="localhost", connections_min=2, connections_max=4)
        assert conn.pool.connections_min == 2
        assert conn.pool.connections_max == 4
        assert len(conn.pool._pool) == 2


class PoolConnectionValidationTests(TestCase):
    """Tests for connection ping validation when returning connections to pool."""

    def _make_pool_and_client(self):
        """Helper to create a pool and pull a client from it."""
        conn = connect(host="localhost", connections_min=1, connections_max=2)
        pool = conn.pool
        client = pool.pull()
        return pool, client

    def test_push_valid_connection_returns_to_pool(self):
        """A connection that passes ping should be returned to the pool."""
        pool, client = self._make_pool_and_client()
        pool_size_before = len(pool._pool)

        pool.push(client=client)

        self.assertEqual(len(pool._pool), pool_size_before + 1)
        pool.cleanup()

    def test_push_dead_connection_not_returned_to_pool(self):
        """A connection that fails ping should be disconnected, not pooled."""
        pool, client = self._make_pool_and_client()
        pool._pool.clear()  # empty pool so push will try to add it back

        # Simulate a dead connection: ping returns False
        original_ping = client.connection.ping
        client.connection.ping = MagicMock(return_value=False)

        pool.push(client=client)

        # Dead connection should NOT be in pool
        self.assertEqual(len(pool._pool), 0)

        client.connection.ping = original_ping
        pool.cleanup()

    def test_push_disconnected_connection_not_returned_to_pool(self):
        """A connection with connected=False should not be returned to pool."""
        pool, client = self._make_pool_and_client()
        pool._pool.clear()

        # Disconnect the client so connected=False
        client.disconnect()

        pool.push(client=client)

        # Disconnected connection should NOT be in pool
        self.assertEqual(len(pool._pool), 0)
        pool.cleanup()


class PoolCleanupLoggingTests(TestCase):
    """Tests for disconnect error logging during pool cleanup."""

    def test_cleanup_logs_disconnect_errors(self):
        """Errors during disconnect in cleanup() should be logged, not silenced."""
        conn = connect(host="localhost", connections_min=1, connections_max=2)
        pool = conn.pool

        # Make disconnect raise an exception
        for client in pool._pool:
            client.disconnect = MagicMock(
                side_effect=Exception("mock disconnect error")
            )

        with self.assertLogs(
            "clickhouse_backend.driver.pool", level="ERROR"
        ) as log_output:
            pool.cleanup()

        # Verify error was logged
        self.assertTrue(
            any("mock disconnect error" in msg for msg in log_output.output)
        )

    def test_cleanup_succeeds_despite_disconnect_errors(self):
        """Pool should still be marked closed even if disconnect fails."""
        conn = connect(host="localhost", connections_min=1, connections_max=2)
        pool = conn.pool

        for client in pool._pool:
            client.disconnect = MagicMock(
                side_effect=Exception("mock disconnect error")
            )

        with self.assertLogs("clickhouse_backend.driver.pool", level="ERROR"):
            pool.cleanup()

        self.assertTrue(pool.closed)


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
