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
