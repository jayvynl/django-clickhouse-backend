from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.backends.ddl_references import (
    Expressions, IndexName, Statement, Table,
)
from django.db.models.expressions import ExpressionList
from django.db.models.indexes import IndexExpression

from clickhouse_backend.driver.escape import escape_param


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

    sql_table_index = 'INDEX %(name)s (%(columns)s) TYPE %(type)s GRANULARITY %(granularity)s'
    sql_create_index = 'ALTER TABLE %(table)s ADD ' + sql_table_index
    sql_delete_index = "ALTER TABLE %(table)s DROP INDEX %(name)s"

    sql_nullable_field = 'Nullable(%s)'

    def create_model(self, model):
        """
        Create a table and any accompanying indexes or constraints for
        the given `model`.
        """
        sql, params = self.table_sql(model)
        # Prevent using [] as params, in the case a literal '%' is used in the definition
        self.execute(sql, params or None)
        self.deferred_sql.extend(self._model_indexes_sql(model))

    def delete_model(self, model):
        """Delete a model from the database."""
        # Delete the table
        self.execute(self.sql_delete_table % {
            "table": self.quote_name(model._meta.db_table),
        })

    def alter_db_table(self, model, old_db_table, new_db_table):
        """Rename the table a model points to."""
        if old_db_table == new_db_table:
            return
        self.execute(self.sql_rename_table % {
            "old_table": self.quote_name(old_db_table),
            "new_table": self.quote_name(new_db_table),
        })

    def table_sql(self, model):
        # https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree/#table_engine-mergetree-creating-a-table
        # TODO: Support SAMPLE/TTL/SETTINGS
        """Take a model and return its table definition."""
        # Create column SQL, include constraint and index.
        column_sqls = []
        params = []
        for field in model._meta.local_fields:
            definition, extra_params = self.column_sql(model, field)
            if definition is None:
                continue
            # if field.db_index:
            #     raise ValueError('Column level index is not supported in clickhouse_backend, '
            #                      'use table level index instead.')
            params.extend(extra_params)
            # Add the SQL to our big list.
            column_sqls.append('%s %s' % (
                self.quote_name(field.column),
                definition,
            ))
        from clickhouse_backend.models.engines import MergeTree
        engine = getattr(model._meta, 'engine', MergeTree(order_by=model._meta.pk.attname))
        extra_parts = self._model_extra_sql(model, engine)
        sql = self.sql_create_table % {
            'table': self.quote_name(model._meta.db_table),
            'definition': ', '.join(column_sqls),
            'engine': self._get_engine(model, engine),
            'extra': ' '.join(extra_parts)
        }
        return sql, params

    def _get_engine(self, model, engine):
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
        sql = db_params['type']
        params = []
        # Check for fields that aren't actually columns (e.g. M2M)
        if sql is None:
            return None, None
        if field.null:
            sql = self.sql_nullable_field % sql
        if include_default:
            default_value = self.effective_default(field)
            column_default = ' DEFAULT ' + self._column_default_sql(field)
            if default_value is not None:
                sql += column_default
                params += [default_value]
        return sql, params

    def _model_indexes_sql(self, model):
        """
        Return a list of all index SQL statements (field indexes,
        index_together, Meta.indexes) for the specified model.
        """
        if not model._meta.managed or model._meta.proxy or model._meta.swapped:
            return []
        output = []
        # https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree/#table_engine-mergetree-data_skipping-indexes
        # Because index requires extra params, such as TYPE and GRANULARITY,
        # so field level index=True and Meta level index_together is disabled.
        # for field in model._meta.local_fields:
        #     output.extend(self._field_indexes_sql(model, field))

        # for field_names in model._meta.index_together:
        #     fields = [model._meta.get_field(field) for field in field_names]
        #     output.append(self._create_index_sql(model, fields=fields, suffix='_idx'))

        for index in model._meta.indexes:
            output.append(index.create_sql(model, self))
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
                    'ORDER BY (%s)' % self._get_expression(model, *order_by)
                )
            if partition_by:
                if not isinstance(partition_by, (list, tuple)):
                    partition_by = [partition_by]
                extra_parts.append(
                    'PARTITION BY (%s)' % self._get_expression(model, *partition_by)
                )
            if primary_key:
                if not isinstance(primary_key, (list, tuple)):
                    primary_key = [primary_key]
                extra_parts.append(
                    'PRIMARY KEY (%s)' % self._get_expression(model, *primary_key)
                )
        return extra_parts

    def quote_value(self, value):
        if isinstance(value, str):
            value = value.replace('%', '%%')
        return escape_param(value, {}, cast=True)

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
        if field.base_field.get_internal_type() == 'ArrayField':
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
        non_database_attrs = [
            'blank',
            'db_column',
            'editable',
            'error_messages',
            'help_text',
            'limit_choices_to',
            # Database-level options are not supported, see #21961.
            'on_delete',
            'related_name',
            'related_query_name',
            'validators',
            'verbose_name',
            # Clickhouse dont have unique constraint
            'unique',
            # Clickhouse dont support inline index, use meta index instead
            'db_index',
            # field primary_key is an internal concept of django,
            # clickhouse_backend use meta primary_key
            'primary_key',
        ]
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
        if old_db_params['check'] != new_db_params['check'] and old_db_params['check']:
            meta_constraint_names = {constraint.name for constraint in model._meta.constraints}
            constraint_names = self._constraint_names(
                model, [old_field.column], check=True,
                exclude=meta_constraint_names,
            )
            if strict and len(constraint_names) != 1:
                raise ValueError("Found wrong number (%s) of check constraints for %s.%s" % (
                    len(constraint_names),
                    model._meta.db_table,
                    old_field.column,
                ))
            for constraint_name in constraint_names:
                self.execute(self._delete_check_sql(model, constraint_name))
        # Have they renamed the column?
        if old_field.column != new_field.column:
            self.execute(self._rename_field_sql(model._meta.db_table, old_field, new_field, new_type))
        # Next, start accumulating actions to do
        actions = []
        null_actions = []
        post_actions = []

        # Type change?
        if old_type != new_type:
            fragment, other_actions = self._alter_column_type_sql(model, old_field, new_field, new_type)
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
                old_default != new_default and
                new_default is not None
            ):
                needs_database_default = True
                actions.append(self._alter_column_default_sql(model, old_field, new_field))
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
        # Does it have check constraints we need to add?
        if old_db_params['check'] != new_db_params['check'] and new_db_params['check']:
            constraint_name = self._create_index_name(model._meta.db_table, [new_field.column], suffix='_check')
            self.execute(self._create_check_sql(model, constraint_name, new_db_params['check']))
        # Drop the default if we need to
        # (Django usually does not use in-database defaults)
        if needs_database_default:
            changes_sql, params = self._alter_column_default_sql(model, old_field, new_field, drop=True)
            sql = self.sql_alter_column % {
                "table": self.quote_name(model._meta.db_table),
                "changes": changes_sql,
            }
            self.execute(sql, params)
        # Reset connection if required
        if self.connection.features.connection_persists_old_columns:
            self.connection.close()

    def _create_index_sql(self, model, *, fields=None, name=None, sql=None, suffix='',
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
        columns = [model._meta.get_field(field).column for field in fields]
        sql_create_index = sql or (self.sql_table_index if inline else self.sql_create_index)
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
                self._index_columns(table, columns, (), None)
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
