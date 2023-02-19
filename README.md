Django ClickHouse Database Backend
===

Django clickhouse backend is a [django database backend](https://docs.djangoproject.com/en/4.1/ref/databases/) for 
[clickhouse](https://clickhouse.com/docs/en/home/) database. This project allows using django ORM to interact with 
clickhouse, the goal of the project is to operate clickhouse like operating mysql, postgresql in django.

Thanks to [clickhouse driver](https://github.com/mymarilyn/clickhouse-driver), django clickhouse backend use it as [DBAPI](https://peps.python.org/pep-0249/).
Thanks to [clickhouse pool](https://github.com/ericmccarthy7/clickhouse-pool), it makes clickhouse connection pool.

Read [Documentation](https://github.com/jayvynl/django-clickhouse-backend/blob/main/docs/README.md) for more.

**Features:**

- Support [Clickhouse native interface](https://clickhouse.com/docs/en/interfaces/tcp/) and connection pool.
- Define clickhouse specific schema features such as [Engine](https://clickhouse.com/docs/en/engines/table-engines/) and [Index](https://clickhouse.com/docs/en/guides/improving-query-performance/skipping-indexes) in django ORM.
- Support table migrations.
- Support creating test database and table, working with django TestCase and pytest-django.
- Support most types of query and data types, full feature is under developing.
- Support [SETTINGS in SELECT Query](https://clickhouse.com/docs/en/sql-reference/statements/select/#settings-in-select-query).

**Notes:**

- Not tested upon all versions of clickhouse-server, clickhouse-server 22.x.y.z or over is suggested.
- Aggregate function result in 0 or nan when data set is empty. max/min/sum/count is 0, avg/STDDEV_POP/VAR_POP is nan.
- Clickhouse will set missing column empty value (0 for number, empty string for text, unix epoch for datatime type) instead of NULL in outer join. 
  So Count("book") resolve to 1 in a missing LEFT OUTER JOIN match, not 0.
  In aggregation expression Avg("book__rating", default=2.5), default=2.5 have no effect in missing match.


Get started
---

### Installation

```shell
$ pip install django-clickhouse-backend
```

or

```shell
$ git clone https://github.com/jayvynl/django-clickhouse-backend
$ cd django-clickhouse-backend
$ python setup.py install
```

### Configuration

we can use the docker compose file under the project for test and try

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

`DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'`  is required to working with django migration.
More details will be covered in [Primary key](#Primary key).

### Model Define

just like normal django model define

Changes:

-  import models from clickhouse_backend, not from django.db
- add low_cardinality for StringFiled, when the data field cardinality is relatively low, this configuration can significantly improve query performance

- cannot use db_index=True in Field, but we can add in the Meta indexes
- need to specify the ordering in Meta just for default query ordering
- need to specify the engine for clickhouse, specify the order_by for clickhouse order and ther partition_by argument

```python
from django.db.models import CheckConstraint, Func, Q, IntegerChoices
from django.utils import timezone

from clickhouse_backend import models


class Event(models.ClickhouseModel):
    class Action(IntegerChoices):
        PASS = 1
        DROP = 2
        ALERT = 3
    ip = models.GenericIPAddressField(default='::')
    ipv4 = models.GenericIPAddressField(default="127.0.0.1")
    ip_nullable = models.GenericIPAddressField(null=True)
    port = models.UInt16Field(default=0)
    protocol = models.StringField(default='', low_cardinality=True)
    content = models.StringField(default='')
    timestamp = models.DateTime64Field(default=timezone.now)
    created_at = models.DateTime64Field(auto_now_add=True)
    action = models.EnumField(choices=Action.choices, default=Action.PASS)

    class Meta:
        verbose_name = 'Network event'
        ordering = ['-id']
        db_table = 'event'
        engine = models.ReplacingMergeTree(
            order_by=['id'],
            partition_by=Func('timestamp', function='toYYYYMMDD')
        )
        indexes = [
            models.Index(
                fields=["ip"],
                name='ip_set_idx',
                type=models.Set(1000),
                granularity=4
            ),
            models.Index(
                fields=["ipv4"],
                name="ipv4_bloom_idx",
                type=models.BloomFilter(0.001),
                granularity=1
            )
        ]
        constraints = (
            CheckConstraint(
                name='port_range',
                check=Q(port__gte=0, port__lte=65535),
            ),
        )
```

### Migration

```shell
$ python manage.py makemigrations
```

this operation will generate migration file under apps/migrations/

then we mirgrate

```shell
$ python manage.py migrate
```

for the first time run, this operation will generate django_migrations table with create table sql like this

```sql
> show create table django_migrations;

CREATE TABLE other.django_migrations
(
    `id` Int64,
    `app` FixedString(255),
    `name` FixedString(255),
    `applied` DateTime64(6, 'UTC')
)
ENGINE = MergeTree
ORDER BY id
SETTINGS index_granularity = 8192 
```

we can query it with results like this

```sql
> select * from django_migrations;

┌──────────────────id─┬─app─────┬─name─────────┬────────────────────applied─┐
│ 1626937818115211264 │ testapp │ 0001_initial │ 2023-02-18 13:32:57.538472 │
└─────────────────────┴─────────┴──────────────┴────────────────────────────┘

```

migrate will create a table with name event as we define in the models

```sql
> show create table event;

CREATE TABLE other.event
(
    `id` Int64,
    `ip` IPv6,
    `ipv4` IPv6,
    `ip_nullable` Nullable(IPv6),
    `port` UInt16,
    `protocol` LowCardinality(String),
    `content` String,
    `timestamp` DateTime64(6, 'UTC'),
    `created_at` DateTime64(6, 'UTC'),
    `action` Enum8('Pass' = 1, 'Drop' = 2, 'Alert' = 3),
    INDEX ip_set_idx ip TYPE set(1000) GRANULARITY 4,
    INDEX port_bloom_idx port TYPE bloom_filter(0.001) GRANULARITY 1,
    CONSTRAINT port_range CHECK (port >= 0) AND (port <= 65535)
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY id
SETTINGS index_granularity = 8192
```

### Operate Data

create

```python
for i in range(10):
    Event.objects.create(ip_nullable=None, port=i,
                         protocol="HTTP", content="test", 
                         action=Event.Action.PASS.value)
assert Event.objects.count() == 10
```

query

```python
queryset = Event.objects.filter(content="test")
for i in queryset:
    print(i)
```

update

```python
Event.objects.filter(port__in=[1, 2, 3]).update(protocol="TCP")
time.sleep(1)
assert Event.objects.filter(protocol="TCP").count() == 3
```

delete

```python
Event.objects.filter(protocol="TCP").delete()
time.sleep(1)
assert not Event.objects.filter(protocol="TCP").exists()
```

Except for the model definition, all other operations are like operating relational databases such as mysql and postgresql

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
$ git clone https://github.com/jayvynl/django-clickhouse-backend
$ cd django-clickhouse-backend
# docker and docker-compose are required.
$ docker-compose up -d
$ python tests/runtests.py
```

**Note:** This project is not fully tested yet and should be used with caution in production.

License
---

Django clickhouse backend is distributed under the [MIT license](http://www.opensource.org/licenses/mit-license.php).
