### Unreleased

- **known issue**: on ClickHouse 26.1 to at least 26.7, `Min()` and `Max()` over a `DateTimeField` return a wrong row for values before 1970, once the query has run often enough to be JIT compiled (three times by default). ClickHouse compares the `DateTime64` as unsigned there, so a value before the epoch comes out as the largest one, reported as [ClickHouse#113942](https://github.com/ClickHouse/ClickHouse/issues/113942). Add `"compile_aggregate_expressions": 0` to the `settings` of the database `OPTIONS` if you aggregate datetimes before 1970.
- feat: database functions for the [JSON type](https://clickhouse.com/docs/sql-reference/functions/json-functions): `JSONAllPaths()` and `JSONAllPathsWithTypes()` for the paths a value holds, `JSONSharedDataPaths()` for the ones that spilled past `max_dynamic_paths`, `JSONAllValues()` (ClickHouse 26.4) for every value as text, and `dynamicType()` for the type a path holds in each row. `JSONAllPaths()` and `JSONAllValues()` are also the expressions a [data skipping index](https://clickhouse.com/docs/sql-reference/data-types/newjson#data-skipping-indexes-for-json) is built on. Plus `toJSONString()`, `isValidJSON()`, `JSONLength()` and `JSONMergePatch()` for JSON held in a string.
- fix: the second argument of `generateSerialID()`, the start value of a new series, needs ClickHouse [25.10](https://github.com/ClickHouse/ClickHouse/blob/31081d9f05014003321333553bb3e657eb3da168/docs/changelogs/v25.10.1.3832-stable.md?plain=1#L128), which added it. Its test used to run on every version that has the function at all, failing with `Number of arguments for function generateSerialID doesn't match` on 25.1 to 25.9.
- **breaking** feat: `JSONField` maps to the [JSON](https://clickhouse.com/docs/sql-reference/data-types/newjson) type instead of `Object('json')`, which ClickHouse deprecated and removed in [25.11](https://github.com/ClickHouse/ClickHouse/blob/31081d9f05014003321333553bb3e657eb3da168/docs/changelogs/v25.11.1.558-stable.md?plain=1#L12). It needs ClickHouse [24.8](https://github.com/ClickHouse/ClickHouse/blob/31081d9f05014003321333553bb3e657eb3da168/docs/changelogs/v24.8.1.2684-lts.md?plain=1#L27), is production ready since [25.3](https://github.com/ClickHouse/ClickHouse/blob/31081d9f05014003321333553bb3e657eb3da168/docs/changelogs/v25.3.1.2703-lts.md?plain=1#L25), and needs `allow_experimental_json_type = 1` on 24.8 to 25.2 instead of `allow_experimental_object_type`. No migration is generated for an existing table, its column keeps the old type until you convert it yourself. `QuerySet.update()` and `Model.save()` of an existing row need 25.6.3, which allowed `ALTER TABLE ... UPDATE` on a column holding dynamic sub-columns.
- **breaking** feat: key transforms compile to JSON sub-column accessors, `json.a.b` and `json.^a.b`, instead of `tupleElement()`. A value is no longer padded into a uniform schema, so `{"b": [{"c": 1}, {"d": 2}]}` reads back as it was written; a key which is absent reads as `None` instead of failing the query; and a value is compared in its JSON type, so `filter(json__c=('e',))` and `filter(json__c={'any_key': 'e'})` no longer match `{"c": {"d": "e"}}`. `gt`, `gte`, `lt` and `lte` compare a path as the ClickHouse type matching the python value, leaving out rows whose value does not convert to it. The keys which follow an array index, `json__a__0__b`, are read from the JSON text of the path before them.
- feat: `JSONField` accepts the [hints](https://clickhouse.com/docs/sql-reference/data-types/newjson) of the JSON type as `max_dynamic_types`, `max_dynamic_paths`, `typed_paths`, `skip_paths` and `skip_regexps`, and `inspectdb` reads them back. A hint only applies to a value clickhouse parses itself, so `skip_paths` and `skip_regexps` usually do not drop a path from a value saved through django, which clickhouse-driver writes over the native protocol; they do for an insert holding a database default or an expression, whose values django renders as SQL. `typed_paths`, which clickhouse-driver cannot write at all, is only usable on a table django reads, reported as a warning unless the model sets `managed = False`.
- feat: `JSONField` supports the `has_key`, `has_keys` and `has_any_keys` lookups, compiled to an `IS NOT NULL` test of the path's sub-columns, which a [data skipping index](https://clickhouse.com/docs/sql-reference/data-types/newjson#json-indexes-jsonallpaths) over `JSONAllPaths()` answers on its own. A key whose value is `null` does not exist for them, clickhouse does not store it. `contains` and `contained_by` remain unsupported, clickhouse has no containment operator.
- fix: `JSONField` reads a value with its `decoder`, which it used to ignore.
- feat: `JSONField` accepts `null=True`, mapping to `Nullable(JSON)`. The `Object('json')` type it used to map to had no nullable form. A root `null` is still not storable in the value itself: clickhouse turns it into an empty object, so `None` saved into a field which is not nullable reads back as `{}`.
- fix: `Client` no longer adds `use_client_time_zone` to the `settings` dict of a connection's `OPTIONS` in place. `DatabaseWrapper.get_new_connection()` compares connection parameters to decide whether a connection can be shared, and only the aliasing of that one dict kept the comparison true.
- fix: every connection now sends `output_format_json_quote_64bit_integers = 0`, which is the default from ClickHouse [25.8](https://github.com/ClickHouse/ClickHouse/blob/31081d9f05014003321333553bb3e657eb3da168/docs/changelogs/v25.8.1.5101-lts.md?plain=1#L11) on only. A JSON value is read through `toJSONString()`, so without it an `Int64` came back as its own text: `{'a': 1}` read back as `{'a': '1'}` on 25.7 and below. Set it back to `1` in the `settings` of a connection's `OPTIONS` if some other query of yours needs the quoting.
- **breaking** fix: `clickhouse_backend.driver.JSON` is removed. A JSON value now travels as the text `JSONField` serializes it to, which clickhouse casts to JSON itself when it is inserted or assigned; the `CAST` a comparison needs is compiled by the lookups of `JSONField` instead of by escaping a parameter of a dedicated type.
- fix: `escape_param()` only implements the types clickhouse-driver escapes differently or not at all — `datetime`, the collections, `IPv4Address`, `IPv6Address`, `Enum` and `bytes` — and delegates the rest to it.
- **breaking** fix: `DatabaseWrapper.ch_version` caches the version tuple, such as `(22, 9, 3, 18)`, instead of the `"22.9.3.18"` string, so `get_database_version()` no longer reparses it on every call.
- feat: #135 support [SAMPLE BY](https://clickhouse.com/docs/engines/table-engines/mergetree-family/mergetree#sample-by) in `MergeTree` family engines and the [SAMPLE clause](https://clickhouse.com/docs/sql-reference/statements/select/sample) via `QuerySet.sample()`, based on an idea from @asantoni.
- feat: #135 add database functions `toStartOfDay`, `toStartOfWeek`, `toStartOfMonth`, `toStartOfQuarter` and `toStartOfYear`.
- feat: #166 the `startswith` and `istartswith` lookups now compile to ClickHouse's native prefix functions instead of `LIKE`/`ILIKE`, based on a PR from @AhmedIbrahim226. `istartswith` uses `startsWithCaseInsensitiveUTF8()` on ClickHouse [25.10](https://github.com/ClickHouse/ClickHouse/blob/31081d9f05014003321333553bb3e657eb3da168/docs/changelogs/v25.10.1.3832-stable.md?plain=1#L37) and later, which added it, and `startsWith(lowerUTF8(...), lowerUTF8(...))` on older servers. Both match what `ILIKE` matched, but a literal prefix no longer needs its `%` and `_` escaped.
- fix: `toStartOfMinute` and the functions inheriting from it used django's own `DateTimeField` as `output_field` instead of the ClickHouse one, which does not truncate the microseconds that `DateTime` cannot hold.
- fix: `toStartOfDay`, `toStartOfWeek`, `toStartOfMonth`, `toStartOfQuarter`, `toStartOfYear` and `toYearWeek` now always pass a timezone, defaulting to the current one like `toYYYYMM` already did. Without it ClickHouse truncates in the server timezone, so results depended on server configuration and were wrong whenever the server and the client were in different timezones, or when the offset was not a whole hour. **The `DateTime` results of `toStartOfDay` are now timezone aware**, because the returned ClickHouse type carries a timezone. The four functions returning a `Date` leave the timezone out for a `Date` or a `Date32` argument, for which ClickHouse rejects it instead of ignoring it.
- fix: `QuerySet.union(all=True)` generated `UNION ALL ALL`, which ClickHouse rejects as a syntax error.
- fix: #137 two `EXPLAIN` problems reported by @Azmisov: `QUERY TREE` was not an allowed type, and `QuerySet.explain(format=...)` rejected every output format whose ClickHouse spelling is not all upper case, such as `TabSeparated`.
- depends: #172 update clickhouse-driver to 0.2.11 on python 3.9 and later, reported by @khvn26. Python 3.7 and 3.8 stay on 0.2.9.
- fix: drop the `clickhouse_driver.connection.Connection.send_query` monkey patch added for #14. clickhouse-driver has guarded that code with `server_side_params` itself since 0.2.7, so the patch no longer changed anything for this backend, while still replacing upstream's server side parameter escaping process wide — costing any code that uses clickhouse-driver directly the list and tuple escaping fix in 0.2.11. `clickhouse_backend.driver.escape.escape_param()` and `escape_params()` lose their now unreachable `for_server` argument.
- fix: #167 test database cloning skipped migrations entirely for a database whose `TEST` settings set `managed` to `False`. Such an alias must not run `CREATE DATABASE` for a clone, because the managed alias already created it `ON CLUSTER`, but it does have to migrate: tables that are not `ON CLUSTER` only exist on the node the migration ran against. Clones were therefore missing every local table, such as `django_content_type`, on the unmanaged alias' node, which broke `manage.py test --parallel` against a cluster.

### 1.6.0
* Feat db comment db default by @jayvynl in https://github.com/jayvynl/django-clickhouse-backend/pull/146
* tests: fix tests of Object(json) by @jayvynl in https://github.com/jayvynl/django-clickhouse-backend/pull/147
* feat: add generateSerialID by @jayvynl in https://github.com/jayvynl/django-clickhouse-backend/pull/148
* fix(#136): DatabaseDefault object appears in SQL when bulk_create() b… by @jayvynl in https://github.com/jayvynl/django-clickhouse-backend/pull/149
* depends(#141): Update clickhouse-driver to version 0.2.10 by @jayvynl in https://github.com/jayvynl/django-clickhouse-backend/pull/150
* feat: Support python3.14 by @jayvynl in https://github.com/jayvynl/django-clickhouse-backend/pull/151
* docs(README.md): fix example in README.md, #142 #143 by @jayvynl in https://github.com/jayvynl/django-clickhouse-backend/pull/152
* feat(#145): support Django6.0 by @jayvynl in https://github.com/jayvynl/django-clickhouse-backend/pull/153

**Full Changelog**: https://github.com/jayvynl/django-clickhouse-backend/compare/v1.5.0...1.6.0

### 1.5.0
- feat: #140: Adding pre-commit with ruff as linter and code formatter. 
- fix: #139: Fix to replicas query when using default as cluster name
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
