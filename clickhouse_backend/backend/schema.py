import warnings

from django.db.backends.base.schema import (
    BaseDatabaseSchemaEditor,
    _related_non_m2m_objects,
)
from django.db.backends.ddl_references import (
    Expressions, IndexName, Statement, Table, Columns
)
from django.db.models.expressions import ExpressionList
from django.db.models.indexes import IndexExpression

from clickhouse_backend.driver.escape import escape_param


class ChColumns(Columns):
    def __str__(self):
        def col_str(column, idx):
            col = self.quote_name(column)
            try:
                suffix = self.col_suffixes[idx]
                if suffix:
                    col = '-{}'.format(col)
            except IndexError:
                pass
            return col

        return ', '.join(col_str(column, idx) for idx, column in enumerate(self.columns))


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
    sql_create_table = "CREATE TABLE %(table)s (%(definition)s) ENGINE = %(engine)s %(extra)s"
    sql_rename_table = "RENAME TABLE %(old_table)s TO %(new_table)s"
    sql_delete_table = "DROP TABLE %(table)s"
    sql_alter_column_type = "MODIFY COLUMN %(column)s %(type)s"
    sql_alter_column_null = "MODIFY COLUMN %(column)s Nullable(%(type)s)"
    sql_alter_column_not_null = sql_alter_column_type
    sql_alter_column_default = "MODIFY COLUMN %(column)s DEFAULT %(default)s"
    sql_alter_column_no_default = "MODIFY COLUMN %(column)s REMOVE DEFAULT"
    sql_alter_column_no_default_null = sql_alter_column_no_default
    sql_delete_column = "ALTER TABLE %(table)s DROP COLUMN %(column)s"
    sql_update_with_default = (
        "ALTER TABLE %(table)s UPDATE %(column)s = %(default)s "
        "WHERE %(column)s IS NULL SETTINGS mutations_sync=1"
    )

    sql_index = "INDEX %(name)s (%(columns)s) TYPE %(type)s GRANULARITY %(granularity)s"
    sql_create_index = "ALTER TABLE %(table)s ADD " + sql_index
    sql_delete_index = "ALTER TABLE %(table)s DROP INDEX %(name)s"

    sql_create_constraint = "ALTER TABLE %(table)s ADD %(constraint)s"

    def _column_check_name(self, field):
        return "_check_%s" % field.column

    def _column_check_sql(self, field):
        db_params = field.db_parameters(connection=self.connection)
        if db_params["check"]:
            return self._check_sql(
                name=self._column_check_name(field),
                check=self.sql_check_constraint % db_params
            )

    def table_sql(self, model):
        # https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree/#table_engine-mergetree-creating-a-table
        # TODO: Support SAMPLE/TTL/SETTINGS
        """Take a model and return its table definition."""
        # Create column SQL, include constraint and index.
        column_sqls = []
        params = []
        constraints = []
        for field in model._meta.local_fields:
            definition, extra_params = self.column_sql(model, field)
            if definition is None:
                continue
            params.extend(extra_params)
            # Add the SQL to our big list.
            column_sqls.append("%s %s" % (
                self.quote_name(field.column),
                definition,
            ))
            constraints.append(self._column_check_sql(field))
        for constraint in model._meta.constraints:
            constraints.append(
                constraint.constraint_sql(model, self)
            )

        engine = self._get_engine(model)
        extra_parts = self._model_extra_sql(model, engine)
        sql = self.sql_create_table % {
            "table": self.quote_name(model._meta.db_table),
            "definition": ", ".join(
                str(constraint)
                for constraint in (*column_sqls, *constraints)
                if constraint
            ),
            "engine": self._get_engine_expression(model, engine),
            "extra": " ".join(extra_parts)
        }
        return sql, params

    def _get_engine(self, model):
        from clickhouse_backend.models.engines import MergeTree
        return getattr(
            model._meta,
            "engine",
            MergeTree(order_by=model._meta.pk.attname)
        )

    def _get_engine_expression(self, model, engine):
        from clickhouse_backend.models.sql import Query
        compiler = Query(model, alias_cols=False).get_compiler(
            connection=self.connection
        )
        return Expressions(model._meta.db_table, engine, compiler, self.quote_value)

    def column_sql(self, model, field, include_default=False):
        # https://clickhouse.com/docs/en/sql-reference/statements/create/table/#create-table-query
        # TODO: Support [MATERIALIZED|EPHEMERAL|ALIAS expr1] [compression_codec] [TTL expr1]
        """
        Take a field and return its column definition.
        The field must already have had set_attributes_from_name() called.
        """
        # Get the column's type and use that as the basis of the SQL
        db_params = field.db_parameters(connection=self.connection)
        sql = db_params["type"]
        params = []
        # Check for fields that aren't actually columns (e.g. M2M)
        if sql is None:
            return None, None
        if field.null and "Nullable" not in sql:  # Compatible with django fields.
            sql = "Nullable(%s)" % sql
        if include_default:
            default_value = self.effective_default(field)
            if default_value is not None:
                column_default = " DEFAULT " + self._column_default_sql(field)
                sql += column_default
                params.append(default_value)
        return sql, params

    def _model_indexes_sql(self, model):
        """
        Return a list of all index SQL statements for the specified model.
        field indexes and index_together are ignored, only Meta.indexes is considered.
        """
        if not model._meta.managed or model._meta.proxy or model._meta.swapped:
            return []
        output = []

        msg = (
            "Because index requires extra params, such as TYPE and GRANULARITY, "
            "so field level index=True and Meta level index_together is ignored. "
            "Refer to https://clickhouse.com/docs/en/engines/table-engines/"
            "mergetree-family/mergetree/#table_engine-mergetree-data_skipping-indexes"
        )
        if any(field.db_index for field in model._meta.local_fields) or model._meta.index_together:
            warnings.warn(msg)

        for index in model._meta.indexes:
            output.append(index.create_sql(model, self))

        from clickhouse_backend.models.engines import BaseMergeTree
        engine = self._get_engine(model)
        if output and not isinstance(engine, BaseMergeTree):
            raise ValueError("Index manipulation is supported only for tables with "
                             "*MergeTree engine (including replicated variants). Refer to "
                             "https://clickhouse.com/docs/en/sql-reference/statements/alter/index.")
        return output

    def _get_expression(self, model, *expressions):
        index_expressions = []
        for expression in expressions:
            index_expression = IndexExpression(expression)
            index_expression.set_wrapper_classes(self.connection)
            index_expressions.append(index_expression)
        from clickhouse_backend.models.sql import Query
        query = Query(model, alias_cols=False)
        expression_list = ExpressionList(*index_expressions).resolve_expression(query)
        compiler = query.get_compiler(
            connection=self.connection,
        )
        return Expressions(model._meta.db_table, expression_list, compiler, self.quote_value)

    def _model_extra_sql(self, model, engine):
        extra_parts = []
        from clickhouse_backend.models.engines import BaseMergeTree
        if isinstance(engine, BaseMergeTree):
            order_by = engine.order_by
            partition_by = engine.partition_by
            primary_key = engine.primary_key

            if order_by:
                if not isinstance(order_by, (list, tuple)):
                    order_by = [order_by]
                extra_parts.append(
                    "ORDER BY (%s)" % self._get_expression(model, *order_by)
                )
            else:
                extra_parts.append(
                    "ORDER BY tuple()"
                )
            if partition_by:
                if not isinstance(partition_by, (list, tuple)):
                    partition_by = [partition_by]
                extra_parts.append(
                    "PARTITION BY (%s)" % self._get_expression(model, *partition_by)
                )
            if primary_key:
                if not isinstance(primary_key, (list, tuple)):
                    primary_key = [primary_key]
                extra_parts.append(
                    "PRIMARY KEY (%s)" % self._get_expression(model, *primary_key)
                )
        return extra_parts

    def add_field(self, model, field):
        """
        Create a field on a model. Usually involves adding a column, but may
        involve adding a table instead (for M2M fields).
        """
        # Special-case implicit M2M tables
        if field.many_to_many and field.remote_field.through._meta.auto_created:
            return self.create_model(field.remote_field.through)
        # Get the column's definition
        definition, params = self.column_sql(model, field, include_default=False)
        # It might not actually have a column behind it
        if definition is None:
            return

        check_sql = self._column_check_sql(field)
        if check_sql:
            self.deferred_sql.append(
                self.sql_create_constraint % {
                    "table": self.quote_name(model._meta.db_table),
                    "constraint": check_sql
                }
            )

        # Build the SQL and run it
        sql = self.sql_create_column % {
            "table": self.quote_name(model._meta.db_table),
            "column": self.quote_name(field.column),
            "definition": definition,
        }
        self.execute(sql, params)
        # Drop the default if we need to
        # (Django usually does not use in-database defaults)
        if self.effective_default(field) is not None:
            # Update existing rows with default value
            sql_update_default = (
                "ALTER TABLE %(table)s UPDATE %(column)s = %(default)s "
                "WHERE 1 SETTINGS mutations_sync=1"
            )
            self.execute(
                sql_update_default % {
                    "table": self.quote_name(model._meta.db_table),
                    "column": self.quote_name(field.column),
                    "default": "%s",
                },
                [self.effective_default(field)],
            )

    def remove_field(self, model, field):
        """
        Remove a field from a model. Usually involves deleting a column,
        but for M2Ms may involve deleting a table.
        """
        # Special-case implicit M2M tables
        if field.many_to_many and field.remote_field.through._meta.auto_created:
            return self.delete_model(field.remote_field.through)
        # It might not actually have a column behind it
        db_params = field.db_parameters(connection=self.connection)
        if db_params["type"] is None:
            return
        # Delete the column
        sql = self.sql_delete_column % {
            "table": self.quote_name(model._meta.db_table),
            "column": self.quote_name(field.column),
        }
        self.execute(sql)
        if db_params["check"]:
            constraint_name = self._column_check_name(field)
            self.execute(self._delete_check_sql(model, constraint_name))
        # Reset connection if required
        if self.connection.features.connection_persists_old_columns:
            self.connection.close()
        # Remove all deferred statements referencing the deleted column.
        for sql in list(self.deferred_sql):
            if isinstance(sql, Statement) and sql.references_column(
                model._meta.db_table, field.column
            ):
                self.deferred_sql.remove(sql)

    def quote_value(self, value):
        if isinstance(value, str):
            value = value.replace("%", "%%")
        return escape_param(value, {})

    def _field_indexes_sql(self, model, field):
        return []

    def _field_data_type(self, field):
        if field.is_relation:
            return field.rel_db_type(self.connection)
        return self.connection.data_types.get(
            field.get_internal_type(),
            field.db_type(self.connection),
        )

    def _field_base_data_types(self, field):
        # Yield base data types for array fields.
        if field.base_field.get_internal_type() == "ArrayField":
            yield from self._field_base_data_types(field.base_field)
        else:
            yield self._field_data_type(field.base_field)

    def _field_should_be_altered(self, old_field, new_field):
        _, old_path, old_args, old_kwargs = old_field.deconstruct()
        _, new_path, new_args, new_kwargs = new_field.deconstruct()
        # Don't alter when:
        # - changing only a field name
        # - changing an attribute that doesn't affect the schema
        # - adding only a db_column and the column name is not changed
        non_database_attrs = (
            "verbose_name",
            # field primary_key is an internal concept of django,
            # clickhouse MergeTree primary_key is a different concept.
            "primary_key",
            # Clickhouse dont have unique constraint
            "unique",
            "blank",
            # Clickhouse don't support inline index, use meta index instead
            "db_index",
            "editable",
            "serialize",
            "unique_for_date",
            "unique_for_month",
            "unique_for_year",
            "help_text",
            "db_column",
            "db_tablespace",
            "auto_created",
            "validators",
            "error_messages",
            "on_delete",
            "related_name",
            "related_query_name",
            "db_collation",
            "limit_choices_to",
            "size",
        )

        from clickhouse_backend.models import EnumField
        if not isinstance(old_field, EnumField):
            old_kwargs.pop("choices", None)
        if not isinstance(new_field, EnumField):
            new_kwargs.pop("choices", None)

        for attr in non_database_attrs:
            old_kwargs.pop(attr, None)
            new_kwargs.pop(attr, None)
        return (
            self.quote_name(old_field.column) != self.quote_name(new_field.column) or
            (old_path, old_args, old_kwargs) != (new_path, new_args, new_kwargs)
        )

    def _alter_field(self, model, old_field, new_field, old_type, new_type,
                     old_db_params, new_db_params, strict=False):
        # Change check constraints?
        if (old_db_params["check"] and (old_db_params["check"] != new_db_params["check"]
                                        or old_field.column != new_field.column)):
            constraint_name = self._column_check_name(old_field)
            self.execute(self._delete_check_sql(model, constraint_name))
        # Have they renamed the column?
        if old_field.column != new_field.column:
            self.execute(
                self._rename_field_sql(
                    model._meta.db_table, old_field, new_field, new_type
                )
            )
            # Rename all references to the renamed column.
            for sql in self.deferred_sql:
                if isinstance(sql, Statement):
                    sql.rename_column_references(
                        model._meta.db_table, old_field.column, new_field.column
                    )
        # Next, start accumulating actions to do
        actions = []
        null_actions = []
        post_actions = []
        # Type change?
        if old_type != new_type:
            fragment, other_actions = self._alter_column_type_sql(
                model, old_field, new_field, new_type
            )
            actions.append(fragment)
            post_actions.extend(other_actions)
        # When changing a column NULL constraint to NOT NULL with a given
        # default value, we need to perform 4 steps:
        #  1. Add a default for new incoming writes
        #  2. Update existing NULL rows with new default
        #  3. Replace NULL constraint with NOT NULL
        #  4. Drop the default again.
        # Default change?
        needs_database_default = False
        if old_field.null and not new_field.null:
            old_default = self.effective_default(old_field)
            new_default = self.effective_default(new_field)
            if (
                not self.skip_default_on_alter(new_field) and
                old_default != new_default
                and new_default is not None
            ):
                needs_database_default = True
                actions.append(
                    self._alter_column_default_sql(model, old_field, new_field)
                )
        # Nullability change?
        if old_field.null != new_field.null:
            fragment = self._alter_column_null_sql(model, old_field, new_field)
            if fragment:
                null_actions.append(fragment)
        # Only if we have a default and there is a change from NULL to NOT NULL
        four_way_default_alteration = (
            new_field.has_default() and
            (old_field.null and not new_field.null)
        )
        if actions or null_actions:
            if not four_way_default_alteration:
                # If we don't have to do a 4-way default alteration we can
                # directly run a (NOT) NULL alteration
                actions = actions + null_actions
            # Combine actions together if we can (e.g. postgres)
            if self.connection.features.supports_combined_alters and actions:
                sql, params = tuple(zip(*actions))
                actions = [(", ".join(sql), sum(params, []))]
            # Apply those actions
            for sql, params in actions:
                self.execute(
                    self.sql_alter_column % {
                        "table": self.quote_name(model._meta.db_table),
                        "changes": sql,
                    },
                    params,
                )
            if four_way_default_alteration:
                # Update existing rows with default value
                self.execute(
                    self.sql_update_with_default % {
                        "table": self.quote_name(model._meta.db_table),
                        "column": self.quote_name(new_field.column),
                        "default": "%s",
                    },
                    [new_default],
                )
                # Since we didn't run a NOT NULL change before we need to do it
                # now
                for sql, params in null_actions:
                    self.execute(
                        self.sql_alter_column % {
                            "table": self.quote_name(model._meta.db_table),
                            "changes": sql,
                        },
                        params,
                    )
        if post_actions:
            for sql, params in post_actions:
                self.execute(sql, params)
        # Type alteration on primary key? Then we need to alter the column
        # referring to us.
        drop_foreign_keys = (
            (old_field.primary_key and new_field.primary_key)
            and (old_type != new_type)
        )
        rels_to_update = []
        if drop_foreign_keys:
            rels_to_update.extend(_related_non_m2m_objects(old_field, new_field))
        # Changed to become primary key?
        if self._field_became_primary_key(old_field, new_field):
            # Update all referencing columns
            rels_to_update.extend(_related_non_m2m_objects(old_field, new_field))
        # Handle our type alters on the other end of rels from the PK stuff above
        for old_rel, new_rel in rels_to_update:
            rel_db_params = new_rel.field.db_parameters(connection=self.connection)
            rel_type = rel_db_params["type"]
            if new_rel.field.null and "Nullable" not in rel_type:  # Compatible with django fields.
                rel_type = "Nullable(%s)" % rel_type
            fragment, other_actions = self._alter_column_type_sql(
                new_rel.related_model, old_rel.field, new_rel.field, rel_type
            )
            self.execute(
                self.sql_alter_column
                % {
                    "table": self.quote_name(new_rel.related_model._meta.db_table),
                    "changes": fragment[0],
                },
                fragment[1],
            )
            for sql, params in other_actions:
                self.execute(sql, params)
        # Does it have check constraints we need to add?
        if (new_db_params["check"] and (old_db_params["check"] != new_db_params["check"]
                                        or old_field.column != new_field.column)):
            check_sql = self._column_check_sql(new_field)
            if check_sql:
                self.execute(
                    self.sql_create_constraint % {
                        "table": self.quote_name(model._meta.db_table),
                        "constraint": check_sql
                    }
                )
        # Drop the default if we need to
        # (Django usually does not use in-database defaults)
        if needs_database_default:
            changes_sql, params = self._alter_column_default_sql(
                model, old_field, new_field, drop=True
            )
            sql = self.sql_alter_column % {
                "table": self.quote_name(model._meta.db_table),
                "changes": changes_sql,
            }
            self.execute(sql, params)
        # Reset connection if required
        if self.connection.features.connection_persists_old_columns:
            self.connection.close()

    def _create_index_sql(self, model, *, fields=None, name=None, sql=None, suffix="", col_suffixes=None,
                          type=None, granularity=None, expressions=None, inline=False):
        """
        Return the SQL statement to create the index for one or several fields
        or expressions. `sql` can be specified if the syntax differs from the
        standard (GIS indexes, ...).
        """
        fields = fields or []
        expressions = expressions or []
        from clickhouse_backend.models.sql import Query
        compiler = Query(model, alias_cols=False).get_compiler(
            connection=self.connection,
        )
        columns = [field.column for field in fields]
        sql_create_index = sql or (self.sql_index if inline else self.sql_create_index)
        table = model._meta.db_table

        def create_index_name(*args, **kwargs):
            nonlocal name
            if name is None:
                name = self._create_index_name(*args, **kwargs)
            return self.quote_name(name)
        return Statement(
            sql_create_index,
            table=Table(table, self.quote_name),
            name=IndexName(table, columns, suffix, create_index_name),
            columns=(
                Columns(table, columns, self.quote_name, col_suffixes)
                if columns
                else Expressions(table, expressions, compiler, self.quote_value)
            ),
            type=Expressions(table, type, compiler, self.quote_value),
            granularity=granularity
        )

    def alter_unique_together(self, model, old_unique_together, new_unique_together):
        """for django or other third party app, ignore unique constraint.
        User defined app should never use UniqueConstraint"""
        pass
