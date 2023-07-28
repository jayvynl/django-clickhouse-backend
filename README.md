Django ClickHouse Database Backend
===

Django clickhouse backend is a [django database backend](https://docs.djangoproject.com/en/4.1/ref/databases/) for 
[clickhouse](https://clickhouse.com/docs/en/home/) database. This project allows using django ORM to interact with 
clickhouse, the goal of the project is to operate clickhouse like operating mysql, postgresql in django.

Thanks to [clickhouse driver](https://github.com/mymarilyn/clickhouse-driver), django clickhouse backend use it as [DBAPI](https://peps.python.org/pep-0249/).
Thanks to [clickhouse pool](https://github.com/ericmccarthy7/clickhouse-pool), it makes clickhouse connection pool.

Read [Documentation](https://github.com/jayvynl/django-clickhouse-backend/blob/main/docs/README.md) for more.

**Features:**

- Reuse most of the existed django ORM facilities, minimize your learning costs.
- Connect to clickhouse efficiently via [clickhouse native interface](https://clickhouse.com/docs/en/interfaces/tcp/) and connection pool.
- No other intermediate storage, no need to synchronize data, just interact directly with clickhouse.
- Support clickhouse specific schema features such as [Engine](https://clickhouse.com/docs/en/engines/table-engines/) and [Index](https://clickhouse.com/docs/en/guides/improving-query-performance/skipping-indexes).
- Support most types of table migrations.
- Support creating test database and table, working with django TestCase and pytest-django.
- Support most clickhouse data types.
- Support [SETTINGS in SELECT Query](https://clickhouse.com/docs/en/sql-reference/statements/select/#settings-in-select-query).

**Notes:**

- Not tested upon all versions of clickhouse-server, clickhouse-server 22.x.y.z or over is suggested.
- Aggregation functions result in 0 or nan (Not NULL) when data set is empty. max/min/sum/count is 0, avg/STDDEV_POP/VAR_POP is nan.
- In outer join, clickhouse will set missing columns to empty values (0 for number, empty string for text, unix epoch for date/datatime) instead of NULL. 
  So Count("book") resolve to 1 in a missing LEFT OUTER JOIN match, not 0.
  In aggregation expression Avg("book__rating", default=2.5), default=2.5 have no effect in a missing match.
- Clickhouse does not support unique constraint and foreignkey constraint. `ForeignKey`, `ManyToManyField` and `OneToOneField` can be used with clickhouse backend, but no database level constraints will be added, so there could be some consistency problems.
- Clickhouse does not support transaction. If any exception occurs during migrating, then your clickhouse database will be in an untracked state. Any migration should be full tested in test environment before deployed to production environment.

**Requirements:**

- [Python](https://www.python.org/) >= 3.7
- [Django](https://docs.djangoproject.com/) >= 3.2
- [clickhouse driver](https://github.com/mymarilyn/clickhouse-driver)
- [clickhouse pool](https://github.com/ericmccarthy7/clickhouse-pool)


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


Only `ENGINE` is required in database setting, other options have default values.

- ENGINE: required, set to `clickhouse_backend.backend`.
- NAME: database name, default `default`.
- HOST: database host, default `localhost`.
- PORT: database port, default `9000`.
- USER: database user, default `default`.
- PASSWORD: database password, default empty.

In the most cases, you may just use clickhouse to store some big events tables,
and use some RDBMS to store other tables.
Here I give an example setting for clickhouse and postgresql.

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'localhost',
        'USER': 'postgres',
        'PASSWORD': '123456',
        'NAME': 'postgres',
    },
    'clickhouse': {
        'ENGINE': 'clickhouse_backend.backend',
        'NAME': 'default',
        'HOST': 'localhost',
        'USER': 'DB_USER',
        'PASSWORD': 'DB_PASSWORD',
    }
}
DATABASE_ROUTERS = ['dbrouters.ClickHouseRouter']
```

```python
# dbrouters.py
from clickhouse_backend.models import ClickhouseModel

def get_subclasses(class_):
    classes = class_.__subclasses__()

    index = 0
    while index < len(classes):
        classes.extend(classes[index].__subclasses__())
        index += 1

    return list(set(classes))


class ClickHouseRouter:
    def __init__(self):
        self.route_model_names = set()
        for model in get_subclasses(ClickhouseModel):
            if model._meta.abstract:
                continue
            self.route_model_names.add(model._meta.label_lower)

    def db_for_read(self, model, **hints):
        if (model._meta.label_lower in self.route_model_names
                or hints.get('clickhouse')):
            return 'clickhouse'
        return None

    def db_for_write(self, model, **hints):
        if (model._meta.label_lower in self.route_model_names
                or hints.get('clickhouse')):
            return 'clickhouse'
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if (f'{app_label}.{model_name}' in self.route_model_names
                or hints.get('clickhouse')):
            return db == 'clickhouse'
        elif db == 'clickhouse':
            return False
        return None
```

You should use [database router](https://docs.djangoproject.com/en/4.1/topics/db/multi-db/#automatic-database-routing) to
automatically route your queries to the right database. In the preceding example, I write a database router which route all
queries from subclasses of `clickhouse_backend.models.ClickhouseModel` or custom migrations with a `clickhouse` hint key to clickhouse.
All other queries are routed to the default database (postgresql).


### Model Definition

Clickhouse backend support django builtin fields and clickhouse specific fields.

Read [fields documentation](https://github.com/jayvynl/django-clickhouse-backend/blob/main/docs/Fields.md) for more.

Notices about model definition:

- import models from clickhouse_backend, not from django.db
- add low_cardinality for StringFiled, when the data field cardinality is relatively low, this configuration can significantly improve query performance

- cannot use db_index=True in Field, but we can add in the Meta indexes
- need to specify the ordering in Meta just for default query ordering
- need to specify the engine for clickhouse, specify the order_by for clickhouse order and the partition_by argument

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
    ipv4 = models.GenericIPAddressField(default='127.0.0.1')
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
$ python manage.py migrate --database clickhouse
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
By default, data mutations is processed asynchronously.
That is, when you update or delete a row, clickhouse will perform the action after a period of time.
So you should change this default behavior in testing for deleting or updating.
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
  Event.objects.filter(protocol='UDP').settings(mutations_sync=1).delete()
  ```

Sample test case.

```python
from django.test import TestCase

class TestEvent(TestCase):
    def test_spam(self):
        assert Event.objects.count() == 0
```


Test
---

To run test for this project:

```shell
$ git clone https://github.com/jayvynl/django-clickhouse-backend
$ cd django-clickhouse-backend
# docker and docker-compose are required.
$ docker-compose up -d
$ python tests/runtests.py
# run test for every python version and django version
$ pip install tox
$ tox
```

Changelog
---

[All changelogs](https://github.com/jayvynl/django-clickhouse-backend/blob/main/CHANGELOG.md).


License
---

Django clickhouse backend is distributed under the [MIT license](http://www.opensource.org/licenses/mit-license.php).
