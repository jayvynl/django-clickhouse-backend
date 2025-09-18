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
