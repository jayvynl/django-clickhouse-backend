from clickhouse_driver.dbapi.errors import (
    OperationalError as ch_driver_OperationalError,
)
from clickhouse_driver.errors import PartiallyConsumedQueryError
from django.db import connection
from django.db.utils import OperationalError as django_OperationalError
from django.test import TestCase

from clickhouse_backend.driver import connect

from .. import models


class Tests(TestCase):
    def test_pool_size(self):
        conn = connect(host="localhost", connections_min=2, connections_max=4)
        assert conn.pool.connections_min == 2
        assert conn.pool.connections_max == 4
        assert len(conn.pool._pool) == 2


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

    def test_connection_unusable_when_iteration_interrupted(self):
        """
        This test demonstrates that if a queryset is iterated over and the iteration
        is interrupted (e.g. via a break statement), the connection used for that
        iteration is not cleaned up and is left in a broken state. Any subsequent
        queries using that connection will fail.
        """
        pool = connection.connection.pool
        connection_count_before = len(pool._pool)

        assert connection_count_before == 1

        # Asserts most recent exception is Django OperationalError
        with self.assertRaises(django_OperationalError) as ex_context:
            # Get queryset
            authors = models.Author.objects.all()
            # Access iterator, but break after first item
            for author in authors.iterator(1):
                author = author.name
                break

            # Assert connection pool size is unchanged despite broken connection
            connection_count_after_iterator = len(pool._pool)
            assert connection_count_after_iterator == 1

            # Try to access queryset again, which won't work via same connection
            author = authors.get(id=self.a1.id)

        # Caused by ch driver driver Operational error
        self.assertIsInstance(
            ex_context.exception.__cause__, ch_driver_OperationalError
        )

        # ...The context of which is a PartiallyConsumedQueryError
        # https://github.com/mymarilyn/clickhouse-driver/blob/master/clickhouse_driver/connection.py#L801
        self.assertIsInstance(
            ex_context.exception.__cause__.__context__, PartiallyConsumedQueryError
        )
