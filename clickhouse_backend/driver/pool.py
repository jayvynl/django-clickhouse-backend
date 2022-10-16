import clickhouse_pool

from .client import Client


class ClickhousePool(clickhouse_pool.ChPool):
    """Support connection from dsn and use `clickhouse_backend.driver.client.Client`."""
    def __init__(self, **kwargs):
        self.dsn = kwargs.pop('dsn', None)
        super().__init__(**kwargs)

    def _connect(self, key: str = None) -> Client:
        """Create a new client and assign to a key."""
        if self.dsn is not None:
            client = Client.from_url(self.dsn)
        else:
            client = Client(**self.connection_args)
        if key is not None:
            self._used[key] = client
            self._rused[id(client)] = key
        else:
            self._pool.append(client)
        return client
