from django.db.models.fields import AutoFieldMixin
from django.db.models.sql import compiler

from clickhouse_backend import compat
from clickhouse_backend.idworker import id_worker

if compat.dj_ge42:
    from django.core.exceptions import FullResultSet


class ClickhouseMixin:
    def _add_explain_sql(self, sql, params):
        # Backward compatible for django 3.2
        explain_info = getattr(self.query, "explain_info", None)
        if explain_info:
            prefix, suffix = self.connection.ops.explain_query(
                format=explain_info.format,
                type=explain_info.type,
                **explain_info.options,
            )
            sql = "%s %s" % (prefix, sql.lstrip())
            if suffix:
                sql = "%s %s" % (sql, suffix)
        return sql, params

    def _add_settings_sql(self, sql, params):
        if getattr(self.query, "setting_info", None):
            setting_sql, setting_params = self.connection.ops.settings_sql(
                **self.query.setting_info
            )
            sql = "%s %s" % (sql, setting_sql)
            params = (*params, *setting_params)
        return sql, params

    def _compile_where(self, table):
        if compat.dj_ge42:
            try:
                where, params = self.compile(self.query.where)
            except FullResultSet:
                where, params = "", ()
        else:
            where, params = self.compile(self.query.where)
        if where:
            where = where.replace(table + ".", "")
        else:
            where = "1"
        return where, params


class SQLCompiler(ClickhouseMixin, compiler.SQLCompiler):
    def as_sql(self, *args, **kwargs):
        sql, params = super().as_sql(*args, **kwargs)
        sql, params = self._add_settings_sql(sql, params)
        sql, params = self._add_explain_sql(sql, params)
        return sql, params


class SQLInsertCompiler(compiler.SQLInsertCompiler):
    def as_sql(self):
        # We don't need quote_name_unless_alias() here, since these are all
        # going to be column names (so we can avoid the extra overhead).
        qn = self.connection.ops.quote_name
        opts = self.query.get_meta()
        insert_statement = self.connection.ops.insert_statement()

        fields = self.query.fields
        # Generate value for AutoField when needed.
        absent_of_pk = isinstance(opts.pk, AutoFieldMixin) and opts.pk not in fields
        if absent_of_pk:
            fields = fields + [opts.pk]
            for obj in self.query.objs:
                setattr(obj, opts.pk.attname, id_worker.get_id())

        result = [
            "%s %s(%s)" % (
                insert_statement,
                qn(opts.db_table),
                ", ".join(qn(f.column) for f in fields),
            )
        ]

        value_rows = [
            [self.prepare_value(field, self.pre_save_val(field, obj))
             for field in fields]
            for obj in self.query.objs
        ]

        placeholder_rows, param_rows = self.assemble_as_sql(fields, value_rows)
        # https://clickhouse.com/docs/en/sql-reference/statements/insert-into
        # If you want to specify SETTINGS for INSERT query then you have to do it before FORMAT clause
        # since everything after FORMAT format_name is treated as data.
        if getattr(self.query, "setting_info", None):
            setting_sql, setting_params = self.connection.ops.settings_sql(
                **self.query.setting_info
            )
            result.append(setting_sql % setting_params)

        result.append(self.connection.ops.bulk_insert_sql(fields, placeholder_rows))
        return [(" ".join(result), param_rows)]

    def execute_sql(self, returning_fields=None):
        as_sql = self.as_sql()
        self.returning_fields = returning_fields
        with self.connection.cursor() as cursor:
            for sql, params in as_sql:
                cursor.execute(sql, params)


class SQLDeleteCompiler(ClickhouseMixin, compiler.SQLDeleteCompiler):
    def _as_sql(self, query):
        """
        When execute DELETE and UPDATE query. Clickhouse does not support
        "table"."column" in WHERE clause.
        """
        table = self.quote_name_unless_alias(query.base_table)
        delete = "ALTER TABLE %s DELETE" % table
        where, params = self._compile_where(table)
        return f"{delete} WHERE {where}", tuple(params)

    def as_sql(self):
        sql, params = super().as_sql()
        sql, params = self._add_settings_sql(sql, params)
        return sql, params


class SQLUpdateCompiler(ClickhouseMixin, compiler.SQLUpdateCompiler):
    def as_sql(self):
        """
        When execute DELETE and UPDATE query. Clickhouse does not support
        "table"."column" in WHERE clause.
        """
        self.pre_sql_setup()
        if not self.query.values:
            return "", ()
        qn = self.quote_name_unless_alias
        values, update_params = [], []
        for field, model, val in self.query.values:
            if hasattr(val, "resolve_expression"):
                val = val.resolve_expression(
                    self.query, allow_joins=False, for_save=True
                )
                if val.contains_aggregate:
                    raise compiler.FieldError(
                        "Aggregate functions are not allowed in this query "
                        "(%s=%r)." % (field.name, val)
                    )
                if val.contains_over_clause:
                    raise compiler.FieldError(
                        "Window expressions are not allowed in this query "
                        "(%s=%r)." % (field.name, val)
                    )
            elif hasattr(val, "prepare_database_save"):
                if field.remote_field:
                    val = field.get_db_prep_save(
                        val.prepare_database_save(field),
                        connection=self.connection,
                    )
                else:
                    raise TypeError(
                        "Tried to update field %s with a model instance, %r. "
                        "Use a value compatible with %s."
                        % (field, val, field.__class__.__name__)
                    )
            else:
                val = field.get_db_prep_save(val, connection=self.connection)

            # Getting the placeholder for the field.
            if hasattr(field, "get_placeholder"):
                placeholder = field.get_placeholder(val, self, self.connection)
            else:
                placeholder = "%s"
            name = field.column
            if hasattr(val, "as_sql"):
                sql, params = self.compile(val)
                values.append("%s = %s" % (qn(name), placeholder % sql))
                update_params.extend(params)
            elif val is not None:
                values.append("%s = %s" % (qn(name), placeholder))
                update_params.append(val)
            else:
                values.append("%s = NULL" % qn(name))

        # Replace "table"."field" to "field", clickhouse does not support that.
        table = qn(self.query.base_table)
        result = [
            "ALTER TABLE %s UPDATE" % table,
            ", ".join(values).replace(table + ".", ""),
        ]
        where, params = self._compile_where(table)
        result.append(f"WHERE {where}")
        params = (*update_params, *params)
        return self._add_settings_sql(" ".join(result), params)


class SQLAggregateCompiler(ClickhouseMixin, compiler.SQLAggregateCompiler):
    def as_sql(self):
        sql, params = super().as_sql()
        sql, params = self._add_settings_sql(sql, params)
        sql, params = self._add_explain_sql(sql, params)
        return sql, params
