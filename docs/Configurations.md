Configurations
---

To configurate your django project to use clickhouse backend, only a few django's own configuration item is needed to be changed.
No extra configuration item is introduced by this project.

### DATABASES

Only `ENGINE` is required in `DATABASES` configuration, other options have default values.

- ENGINE: required, set to `clickhouse_backend.backend`.
- NAME: database name, default `default`.
- HOST: database host, default `localhost`.
- PORT: database port, default `9000`.
- USER: database user, default `default`.
- PASSWORD: database password, default empty.

  ```python
  DATABASES = {
      'default': {
          'ENGINE': 'clickhouse_backend.backend',
          'NAME': 'default',
          'HOST': 'localhost',
          'USER': 'DB_USER',
          'PASSWORD': 'DB_PASSWORD',
          'OPTIONS': {
              'settings': {'mutations_sync': 1}
          },
          'TEST': {
              'fake_transaction': True
          }
      }
  }
  ```

Valid `OPTIONS` keys:

- `connections_min` is maximum number of connections can be kept in connection pool, default 10. Set this value to 0 will disable connection pool.
- `connections_max` is maximum number of connections can be used, default 100. In fact, `connections_max` is maximum numbers of queries one can execute concurrently.
Because [source code of DBAPI Connection](https://github.com/mymarilyn/clickhouse-driver/blob/0.2.5/clickhouse_driver/dbapi/connection.py#L46) shows that every cursor creates a new connection.
- `dsn` provide connection url, for example `clickhouse://localhost/test?param1=value1&...`. If dsn is provided, all other connection parameters are ignored.
- All other [clickhouse_driver.connection.Connection](https://clickhouse-driver.readthedocs.io/en/latest/api.html#connection) parameters.
- `settings` can contain [clickhouse_driver.Client](https://clickhouse-driver.readthedocs.io/en/latest/api.html?highlight=client#clickhouse_driver.Client) settings.
- `settings` can contain [clickhouse settings](https://clickhouse.com/docs/en/operations/settings/settings).

Valid `TEST` keys:

- 'fake_transaction' make clickhouse pretending to be transactional.
  In the case of multiple databases, if another database supports transactions, use TransactionTestCase or inherited classes (including pytest_django) for testing, all test data (including various setup and pytest fixtures) for each database will be automatically flushed after each test case by calling django's flush command.
  In order to use transactions to isolate the postgresql data of each test case (speed up test), all databases need to support transactions. You can make clickhouse connections support fake transactions. By setting 'TEST' in the database: {'fake_transaction': True}.
  But this will have a side effect, that is, the clickhouse data of each test case will not be isolated. So in general it is not recommended to use this feature unless you know very well what is the impaction.


### Auto Field

Django ORM depends heavily on single column primary key, this primary key is a unique identifier of an ORM object.
All `get` `save` `delete` actions depend on primary key.

But in ClickHouse [primary key](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree#primary-keys-and-indexes-in-queries) has different meaning from django primary key. ClickHouse does not require a unique primary key. You can insert multiple rows with the same primary key.

There is [no unique constraint](https://github.com/ClickHouse/ClickHouse/issues/3386#issuecomment-429874647) or auto increasing column in clickhouse.

By default, django will add a field named `id` as auto increasing primary key.

Django `AutoField`, `SmallAutoField` and `BigAutoField` ar mapped to clickhouse Int64 data type. If primary key is not specified when insert data, then `clickhouse_driver.idworker.id_worker` is used to generate this unique id.

Default `id_worker` is an instance of `clickhouse.idworker.snowflake.SnowflakeIDWorker` which implement [twitter snowflake id](https://en.wikipedia.org/wiki/Snowflake_ID).
If data insertions happen on multiple datacenter, server, process or thread, you should ensure uniqueness of (CLICKHOUSE_WORKER_ID, CLICKHOUSE_DATACENTER_ID) environment variable.
Because work_id and datacenter_id are 5 bits, they should be an integer between 0 and 31. CLICKHOUSE_WORKER_ID default to 0, CLICKHOUSE_DATACENTER_ID will be generated randomly if not provided.

`clickhouse.idworker.snowflake.SnowflakeIDWorker` is not thread safe. You could inherit `clickhouse.idworker.base.BaseIDWorker` and implement one, then set `CLICKHOUSE_ID_WORKER` in `settings.py` to doted import path of your IDWorker instance.
