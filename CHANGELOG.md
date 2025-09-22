### 1.5.0
- feat: #134: add `argMax` aggregation https://clickhouse.com/docs/sql-reference/aggregate-functions/reference/argmax
- feat: #133: Fix simultaneous queries error when iteration is interrupted
- feat: #130: Add `distributed_migrations` database setting to support distributed migration queries.
- feat: #129: Add `toYearWeek` datetime functionality

### 1.4.0

- feat: #119 Allow query results returned in columns and deserialized to `numpy` objects
- feat: #125 Add database functions `toStartOfMinute`, `toStartOfFiveMinutes`, `toStartOfTenMinutes`, `toStartOfFifteenMinutes` and `toStartofHour`
- feat: #122 Django 5.2 Support

### 1.3.2

- feat(aggragation-function): add anyLast function.
- fix: pass DSN to clickhouse-client if configured.
- feat: #108 Queryset.iterator use clickhouse_driver.Client.execute_iter.
- chore: test for python3.13.
- refactor: Using collections.abc.Iterable instead of deprecated django.utils.itercompat.is_iterable

### 1.3.1

- fix: #99 update value containing "where" cause exception.
- fix: #97 JSONField error in ClickHouse 24.8.
- fix: tuple function error in ClickHouse 24.8.
- support Django 5.1, update clickhouse-driver to 0.2.9.

### 1.3.0

- fix #92 last_executed_query() when params is a mappinglast_executed_query() when params is a mapping.
- support Django 5.0, update clickhouse-driver to 0.2.8, drop clickhouse-pool dependency.

### 1.2.0

- feat: #72 support window functions.
- feat: #80 support [prewhere clause](https://clickhouse.com/docs/en/sql-reference/statements/select/prewhere).

### 1.1.7

- fix: #76 `AttributeError: 'ReplicatedReplacingMergeTree' object has no attribute 'expressions'`.
- fix: migrate ReplacingMergeTree with [`ver`](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/replacingmergetree#ver) raising `AttributeError: 'F' object has no attribute 'get_source_expressions'`.
- fix: unable to omit [`zoo_path`](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/replication#zoo_path) and [`replica_name`](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/replication#replica_name) in replicated engines other than `ReplicatedMergeTree`.

### 1.1.6

- add `CLICKHOUSE_ENABLE_UPDATE_ROWCOUNT` django setting.

### 1.1.5
- refactor: refactor uniq aggregate function.
- feat: add some ClickHouse tuple and hash functions.
- fix: test and fix ClickHouse functions.
- ci: remove deploy of testpypi.
- docs: update DatabaseOperations.max_in_list_size docstring.
- docs: fix readme error word.
- chore: clickhouse_backend.models.functions turn module to package.

### 1.1.4
- fix [#57](https://github.com/jayvynl/django-clickhouse-backend/issues/57).
- Implemente an improved version of inspectdb command.
- Fix update compiler.

### 1.1.3
- Fix #50 partition by single expression raise TypeError.
- Fix #51 .
- Fix #53 .

### 1.1.2
- Use [flake8](https://flake8.pycqa.org/) to lint code.
- Add GitHub action which runs tests.
- Add test coverage to ci and send data to coveralls, add coverage badge.
- Fix distributed and replicated table engine tests, add test guide to README.md.

### 1.1.1
- [Black](https://github.com/psf/black) code style.
- Support [MergeTree settings](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree#settings) in creating table.
- Support [distributed DDL](https://clickhouse.com/docs/en/sql-reference/distributed-ddl) and [distributed table](https://clickhouse.com/docs/en/engines/table-engines/special/distributed).
- Support create migration table and run migrating on cluster.
- Fix bug: exception is raised when insert data with expression values.
- Fix bug: exception is raised when alter field from not null to null.
- Support escaping dict data.

### 1.1.0
- Change `AutoFiled` and `SmallAutoField` to clickhouse `Int64`, so that id worker can generate value for them.
This allows more compatibilities with existing apps such as `django.contrib.auth`.
- `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` is no longer a required configuration item.

### 1.0.3
- Fix reading settings in explain, pull request [#13](https://github.com/jayvynl/django-clickhouse-backend/pull/13) by [mahdi-jfri](https://github.com/mahdi-jfri).
- Add toYYYYMM[DD[hhmmss]] functions.
- Fix str(queryset.query) when default database is not clickhouse.
- Fix [bug when save django model instance](https://github.com/jayvynl/django-clickhouse-backend/issues/9).
- Support [clickhouse-driver 0.2.6](https://github.com/mymarilyn/clickhouse-driver), drop support for python3.6.
- Support [Django 4.2](https://docs.djangoproject.com).
- Support [clickhouse JSON type](https://clickhouse.com/docs/en/sql-reference/data-types/json).

### 1.0.2 (2023-02-28)
- Fix test db name when NAME not provided in DATABASES setting.
- Fix Enum error when provided an IntegerChoices value.
- Add document about multiple db settings.

### 1.0.1 (2023-02-23)

- Add `return_int` parameter to `Enum[8|16]Field` to control whether to get an int or str value when querying from the database.
- Fix TupleField container_class.
- Add fields documentation.


### 1.0.0 (2023-02-21)

- Add tests for migrations.
- Fix bytes escaping.
- Fix date and datetime lookup.
- Add documentations.
- Add lots of new field types:
  - Float32/64
  - [U]Int8/16/32/64/128/256
  - Date/Date32/DateTime('timezone')/DateTime64('timezone')
  - String/FixedString(N)
  - Enum8/16
  - Array(T)
  - Bool
  - UUID
  - Decimal
  - IPv4/IPv6
  - LowCardinality(T)
  - Tuple(T1, T2, ...)
  - Map(key, value)

0.2.1 (2022-10-30)
---

- Add tests for backends.
- Remove redundant code.
- Correct database features.
- Fix bugs that find by new tests.

0.2.0 (2022-10-26)
---

- Adopt some testcase from django project.
- Fix bugs such as datetime escaping and update field use F expression.

0.1.0 (2022-10-16)
---

- ID worker interface changes and configuration item adjustments.
- Support database connection pool.
- Refactored the implementation of Engine to be more concise and stable.
- Database related features are concentrated in the SQLCompiler implementation.
- Ignore unsupported field-level db_index attribute, and AlterUniqueTogether migration operation in favor of django built-in model or 3rd party model migration.

0.0.14 (2022-08-18)
---

- matches Django 4.x.

0.0.13 (2022-08-18)
---

- Fixed searching for GenericIPAddressField field.

0.0.12 (2022-08-09)
---

- Fixed an issue where multiple order by fields were wrong when creating a table.

0.0.11 (2022-08-01)
---

- Fixed AlterField migration to support Nullable to non-Nullable type changes, update old `NULL` values with provided defaults.

0.0.10
---

- Support field type change migration

0.0.9
---

- Fixed the problem that deleting and updating model objects could not be executed synchronously

0.0.8
---

- QuerySet supports setting query, you can pass in Clickhouse setting items, refer to [SETTINGS in SELECT Query](https://clickhouse.com/docs/en/sql-reference/statements/select/#settings-in-select)
- Fixed that the correct object id cannot be set when inserting data, bulk_create and create and save can display the correct id

0.0.7
---

- The fake_transaction attribute is added to the database connection. Setting this attribute during testing can prevent other database data that supports transactions such as postgresql from being emptied between transaction testcase.
- Added AutoField type, mapped to Int32
- Improve documentation about testing/migration/primary keys

0.0.6
---

- When the GenericIPAddressField type field is optimized to store ipv4 addresses, the default output type is Ipv6 format, and it is converted to the corresponding Ipv4 type

0.0.5
---

- Fixed the issue that the time zone is lost after the clickhouse driver escapes the datetime type value

0.0.4
---

- Added PositiveSmallIntegerField, PositiveIntegerField, PositiveBigIntegerField field types, corresponding to the correct clickhouse uint type range.

- Modified the README and corrected the description about unit testing.

0.0.3
---

- Solved the problem that the options.DEFAULT_NAMES monkey patch in clickhouse.models did not take effect when there were multiple apps.

- Improve the README, add the description of the auto-increment primary key, and adjust the format.
