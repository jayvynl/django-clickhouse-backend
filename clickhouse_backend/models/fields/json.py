import json as jsonlib

from django.core import checks
from django.db.models.fields import Field, json
from django.db.models.sql.compiler import SQLInsertCompiler

from clickhouse_backend import compat
from clickhouse_backend.driver.escape import escape_param
from clickhouse_backend.patch.fields.json import JSON_PARAM, quote_key

from .base import FieldMixin

__all__ = ["JSONField"]

# Hints of the JSON type, in the order clickhouse itself renders them, so that
# db_type() is the type an introspection reads back.
# https://clickhouse.com/docs/sql-reference/data-types/newjson
JSON_HINTS = [
    "max_dynamic_types",
    "max_dynamic_paths",
    "typed_paths",
    "skip_paths",
    "skip_regexps",
]


class JSONField(FieldMixin, json.JSONField):
    def __init__(
        self,
        *args,
        max_dynamic_types=None,
        max_dynamic_paths=None,
        typed_paths=None,
        skip_paths=None,
        skip_regexps=None,
        **kwargs,
    ):
        self.max_dynamic_types = max_dynamic_types
        self.max_dynamic_paths = max_dynamic_paths
        self.typed_paths = typed_paths
        self.skip_paths = skip_paths
        self.skip_regexps = skip_regexps
        super().__init__(*args, **kwargs)

    def check(self, **kwargs):
        return [*super().check(**kwargs), *self._check_typed_paths()]

    def _check_typed_paths(self):
        # clickhouse-driver writes a JSON column itself instead of letting
        # clickhouse parse JSON text, and it has no wire support for a typed path.
        if self.typed_paths and self.model._meta.managed:
            return [
                checks.Warning(
                    "clickhouse-driver cannot insert into a JSON column which has "
                    "a typed path.",
                    hint="Read such a table through a model with managed = False, "
                    "or leave typed_paths out.",
                    obj=self,
                )
            ]
        return []

    def json_type_hints(self):
        """Render the hints of the JSON type, an empty list when there is none."""
        hints = []
        if self.max_dynamic_types is not None:
            hints.append("max_dynamic_types=%d" % self.max_dynamic_types)
        if self.max_dynamic_paths is not None:
            hints.append("max_dynamic_paths=%d" % self.max_dynamic_paths)
        for path, path_type in (self.typed_paths or {}).items():
            hints.append("%s %s" % (quote_key(path), path_type))
        hints.extend("SKIP %s" % quote_key(path) for path in self.skip_paths or ())
        hints.extend(
            "SKIP REGEXP %s" % escape_param(regexp, {})
            for regexp in self.skip_regexps or ()
        )
        return hints

    def db_type(self, connection):
        self._check_backend(connection)
        db_type = connection.data_types[self.get_internal_type()]
        hints = self.json_type_hints()
        if hints:
            db_type = "%s(%s)" % (db_type, ", ".join(hints))
        return self._nested_type(db_type)

    def get_placeholder_sql(self, value, compiler, connection):
        """Cast a value, prepared as JSON text, back to JSON.

        An INSERT keeps the bare placeholder: its values travel natively, and
        clickhouse-driver only recognizes an insert query ending with VALUES.
        """
        if hasattr(value, "as_sql"):
            # Django 6.1 reads a placeholder before compiling an expression,
            # below that it compiles the expression first and never asks.
            return compiler.compile(value)
        if isinstance(compiler, SQLInsertCompiler):
            return "%s", [value]
        return JSON_PARAM, [value]

    if not compat.dj_ge61:
        # django looks up get_placeholder_sql from 6.1 on only.
        def get_placeholder(self, value, compiler, connection):
            return self.get_placeholder_sql(value, compiler, connection)[0]

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if path.startswith("clickhouse_backend.models.json"):
            path = path.replace(
                "clickhouse_backend.models.json", "clickhouse_backend.models"
            )
        for hint in JSON_HINTS:
            value = getattr(self, hint)
            if value is not None:
                kwargs[hint] = value
        return name, path, args, kwargs

    def select_format(self, compiler, sql, params):
        # Values are read as text instead of natively, because clickhouse-driver
        # cannot read a JSON value holding an Array(Dynamic), the type
        # clickhouse gives a heterogeneous array of an UPDATE.
        return "toJSONString(%s)" % sql, params

    def from_db_value(self, value, expression, connection):
        # select_format reads a value as JSON text, but a raw query has no
        # select_format, and clickhouse-driver decodes a JSON column natively
        # into a dict, which no decoder of ours has seen.
        if isinstance(value, str):
            return jsonlib.loads(value, cls=self.decoder)
        return value

    def get_prep_value(self, value):
        # django 4.1 and below dumps value as json string.
        return Field.get_prep_value(self, value)

    def get_db_prep_value(self, value, connection, prepared=False):
        value = super().get_db_prep_value(value, connection, prepared)
        # django 4.1 and below leaves the value alone, and it only grew
        # DatabaseOperations.adapt_json_value, which does this, in 4.2.
        if isinstance(value, dict):
            value = jsonlib.dumps(value, cls=self.encoder)
        return value
