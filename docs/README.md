Django clickhouse database backend
===

Introduction
---

Django clickhouse backend is a [django database backend](https://docs.djangoproject.com/en/4.1/ref/databases/) for 
[clickhouse](https://clickhouse.com/docs/en/home/) database. This project allows using django ORM to interact with 
clickhouse.

This project is built on [clickhouse driver](https://github.com/mymarilyn/clickhouse-driver) and [clickhouse pool](https://github.com/ericmccarthy7/clickhouse-pool).

Features
---

- Reuse most of the existed django ORM facilities, minimize your learning costs.
- Connect to clickhouse efficiently via [clickhouse native interface](https://clickhouse.com/docs/en/interfaces/tcp/) and connection pool.
- No other intermediate storage, no need to synchronize data, just interact directly with clickhouse.
- Support clickhouse specific schema features such as [Engine](https://clickhouse.com/docs/en/engines/table-engines/) and [Index](https://clickhouse.com/docs/en/guides/improving-query-performance/skipping-indexes).
- Support most types of table migrations.
- Support creating test database and table, working with django TestCase and pytest-django.
- Support most frequently-used data types.
- Support [SETTINGS in SELECT Query](https://clickhouse.com/docs/en/sql-reference/statements/select/#settings-in-select-query).

Requirements
---

- [Python](https://www.python.org/) 3.4+
- [Django](https://docs.djangoproject.com/) 3.2+
- [clickhouse driver](https://github.com/mymarilyn/clickhouse-driver)
- [clickhouse pool](https://github.com/ericmccarthy7/clickhouse-pool)

Installation
---

```shell
pip install django-clickhouse-backend
```

or

```shell
git clone https://github.com/jayvynl/django-clickhouse-backend
cd django-clickhouse-backend
python setup.py install
```

Topics
---

- [Configuration](Configurations.md)
- [Migrations](Migrations.md)
- [Fields](Fields.md)
