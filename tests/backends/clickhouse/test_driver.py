from django.test import TestCase

from clickhouse_backend.driver import connect


class Tests(TestCase):
    def test_pool_size(self):
        conn = connect(host='localhost', connections_min=2, connections_max=4)
        assert conn.pool.connections_min == 2
        assert conn.pool.connections_max == 4
        assert len(conn.pool._pool) == 2
