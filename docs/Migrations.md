Migrations
===

Migrations are difficult and complex. The most complex one is schema changes such as alter field type.

Because the limitations of clickhouse such as not supporting transaction and unique constraint, not table level collation, migrations of clickhouse are slightly different from RDBMS such as postgresql.

Limitations
---

- All operations related to unique constraint.
- Although you can use ForeignKey in model(Because django can handle this in python), but no database level fk constraints will be created.
- Data migrations are not rolled back when exception occurred.
- Anonymous indexes and constraints(db_index, unique, index_together, unique_together) are not supported, you must provide names explicitly.
- Alter field type to which is not compatible will raise exception when field is used in primary key or order by.
  Compatible means when changed, value length are not changed and ordering is kept.
  ```shell
  DB::Exception: ALTER of key column id from type FixedString(100) to type FixedString(99) is not safe because it can change the representation of primary key.
  ```
- Alter field type to which is not compatible will raise exception when field is used in index.
  Data type from not null to Nullable is supported but not the reversal.
  ```shell
  DB::Exception: ALTER of key column pink is forbidden.
  ```


Differences
---

- Use `clickhouse_backend.models.indexes.Index` instead of `django.db.models.Index` to add index.
- When using `migrations.RunSQL` to execute raw sql query, multiline sql separated by semicolon is not supported.
- When using `migrations.RunSQL` to execute `INSERT INTO` query, values must be provided using params and end your statement with a VALUES clause.

  ```python
  migrations.RunSQL(
      # forwards
      (
          [
              "INSERT INTO i_love_ponies (id, special_thing) VALUES;",
              [(1, "Django"), (2, "Ponies")],
          ],
          (
              "INSERT INTO i_love_ponies (id, special_thing) VALUES;",
              [(3, "Python")],
          ),
      ),
      # backwards
      [
          "ALTER TABLE i_love_ponies DELETE WHERE special_thing = 'Django';",
          ["ALTER TABLE i_love_ponies DELETE WHERE special_thing = 'Ponies';", None],
          (
              "ALTER TABLE i_love_ponies DELETE WHERE id = %s OR special_thing = %s;",
              [3, "Python"],
          ),
      ],
  )
  ```
