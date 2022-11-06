Django ClickHouse Database Backend
===

[中文文档](https://github.com/jayvynl/django-clickhouse-backend/blob/main/README_cn.md)

Django clickhouse backend is a [django database backend](https://docs.djangoproject.com/en/4.1/ref/databases/) for 
[clickhouse](https://clickhouse.com/docs/en/home/) database. This project allows using django ORM to interact with 
clickhouse.

Thanks to [clickhouse driver](https://github.com/mymarilyn/clickhouse-driver), django clickhouse backend use it as [DBAPI](https://peps.python.org/pep-0249/).
Thanks to [clickhouse pool](https://github.com/ericmccarthy7/clickhouse-pool), it makes clickhouse connection pool.

[Documentation](https://github.com/jayvynl/django-clickhouse-backend/blob/main/docs/README.md)

**features:**

- Support [Clickhouse native interface](https://clickhouse.com/docs/en/interfaces/tcp/) and connection pool.
- Define clickhouse specific schema features such as [Engine](https://clickhouse.com/docs/en/engines/table-engines/) and [Index](https://clickhouse.com/docs/en/guides/improving-query-performance/skipping-indexes) in django ORM.
- Support table migrations.
- Support creating test database and table, working with django TestCase and pytest-django.
- Support most types of query and data types, full feature is under developing.
- Support [SETTINGS in SELECT Query](https://clickhouse.com/docs/en/sql-reference/statements/select/#settings-in-select-query).

Get started
---

### Installation

```shell
pip install django-clickhouse-backend
```

or

```shell
git clone https://github.com/jayvynl/django-clickhouse-backend
cd django-clickhouse-backend
python setup.py install
```

### Configuration

Only `ENGINE` is required, other options have default values.

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
          'TEST': {
              'fake_transaction': True
          }
      }
  }
  DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
  ```

`DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` IS REQUIRED TO WORKING WITH DJANGO MIGRATION.
More details will be covered in [Primary key](#Primary key).

### Model

```python
from django.db import models
from django.utils import timezone

from clickhouse_backend import models as chm
from clickhouse_backend.models import indexes, engines


class Event(chm.ClickhouseModel):
    src_ip = chm.GenericIPAddressField(default='::')
    sport = chm.PositiveSmallIntegerField(default=0)
    dst_ip = chm.GenericIPAddressField(default='::')
    dport = chm.PositiveSmallIntegerField(default=0)
    transport = models.CharField(max_length=3, default='')
    protocol = models.TextField(default='')
    content = models.TextField(default='')
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    length = chm.PositiveIntegerField(default=0)
    count = chm.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Network event'
        ordering = ['-id']
        db_table = 'event'
        engine = engines.ReplacingMergeTree(
            order_by=('dst_ip', 'timestamp'),
            partition_by=models.Func('timestamp', function='toYYYYMMDD')
        )
        indexes = [
            indexes.Index(
                fields=('src_ip', 'dst_ip'),
                type=indexes.Set(1000),
                granularity=4
            )
        ]
        constraints = (
            models.CheckConstraint(
                name='sport_range',
                check=models.Q(sport__gte=0, dport__lte=65535),
            ),
        )
```

### Migration

```shell
python manage.py makemigrations
```

### Testing

Writing testcase is all the same as normal django project. You can use django TestCase or pytest-django.
**Notice:** clickhouse use mutations for [deleting or updating](https://clickhouse.com/docs/en/guides/developer/mutations).
By default, data mutations is processed asynchronously, so you should change this default behavior in testing for deleting or updating.
There are 2 ways to do that:

- Config database engine as follows, this sets [`mutations_sync=1`](https://clickhouse.com/docs/en/operations/settings/settings#mutations_sync) at session scope.
  ```python
  DATABASES = {
      'default': {
          'ENGINE': 'clickhouse_backend.backend',
          'OPTIONS': {
              'settings': {
                  'mutations_sync': 1,
              }
          }
      }
  }
  ```
- Use [SETTINGS in SELECT Query](https://clickhouse.com/docs/en/sql-reference/statements/select/#settings-in-select-query).
  ```python
  Event.objects.filter(transport='UDP').settings(mutations_sync=1).delete()
  ```

Sample test case.

```python
from django.test import TestCase

class TestEvent(TestCase):
    def test_spam(self):
        assert Event.objects.count() == 0
```

Topics
---

### Primary key

Django ORM depends heavily on single column primary key, this primary key is a unique identifier of an ORM object.
All `get` `save` `delete` actions depend on primary key.

But in ClickHouse [primary key](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree#primary-keys-and-indexes-in-queries) has different meaning from django primary key. ClickHouse does not require a unique primary key. You can insert multiple rows with the same primary key.

There is [no unique constraint](https://github.com/ClickHouse/ClickHouse/issues/3386#issuecomment-429874647) or auto increasing column in clickhouse.

By default, django will add a field named `id` as auto increasing primary key.

- AutoField

  Mapped to clickhouse Int32 data type. You should generate this unique id yourself.

- BigAutoField

  Mapped to clickhouse Int64 data type. If primary key is not specified when insert data, then `clickhouse_driver.idworker.id_worker` is used to generate this unique id.

  Default id_worker is an instance of `clickhouse.idworker.snowflake.SnowflakeIDWorker` which implement [twitter snowflake id](https://en.wikipedia.org/wiki/Snowflake_ID).
  If data insertions happen on multiple datacenter, server, process or thread, you should ensure uniqueness of (CLICKHOUSE_WORKER_ID, CLICKHOUSE_DATACENTER_ID) environment variable.
  Because work_id and datacenter_id are 5 bits, they should be an integer between 0 and 31. CLICKHOUSE_WORKER_ID default to 0, CLICKHOUSE_DATACENTER_ID will be generated randomly if not provided.

  `clickhouse.idworker.snowflake.SnowflakeIDWorker` is not thread safe. You could inherit `clickhouse.idworker.base.BaseIDWorker` and implement one, then set `CLICKHOUSE_ID_WORKER` in `settings.py` to doted import path of your IDWorker instance.

Django use a table named `django_migrations` to track migration files. ID field should be BigAutoField, so that IDWorker can generate unique id for you.
After Django 3.2，a new [config `DEFAULT_AUTO_FIELD`](https://docs.djangoproject.com/en/4.1/releases/3.2/#customizing-type-of-auto-created-primary-keys) is introduced to control field type of default primary key.
So `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` is required if you want to use migrations with django clickhouse backend.


Test
---

To run test for this project:

```shell
git clone https://github.com/jayvynl/django-clickhouse-backend
cd django-clickhouse-backend
# docker and docker-compose are required.
docker-compose up -d
python tests/runtests.py
```

**Note:** This project is not fully tested yet and should be used with caution in production.

License
---

Django clickhouse backend is distributed under the [MIT license](http://www.opensource.org/licenses/mit-license.php).
