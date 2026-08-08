"""https://clickhouse.com/docs/sql-reference/functions/json-functions

Each function is documented there under the anchor of its own name.
"""

from django.db.models.fields import json as django_json
from django.db.utils import NotSupportedError

from clickhouse_backend.models import fields
from clickhouse_backend.patch.fields.json import subcolumns

from .base import Func

__all__ = [
    "JSONAllPaths",
    "JSONAllPathsWithTypes",
    "JSONAllValues",
    "JSONLength",
    "JSONMergePatch",
    "JSONSharedDataPaths",
    "dynamicType",
    "isValidJSON",
    "toJSONString",
]


class JSONAllPaths(Func):
    arity = 1
    output_field = fields.ArrayField(fields.StringField())


class JSONAllPathsWithTypes(Func):
    arity = 1
    output_field = fields.MapField(fields.StringField(), fields.StringField())


class JSONAllValues(Func):
    """Needs ClickHouse 26.4."""

    arity = 1
    output_field = fields.ArrayField(fields.StringField())


class JSONSharedDataPaths(Func):
    """The paths stored together past ``max_dynamic_paths``, not as sub-columns."""

    arity = 1
    output_field = fields.ArrayField(fields.StringField())


class JSONLength(Func):
    output_field = fields.UInt64Field()


class JSONMergePatch(Func):
    output_field = fields.StringField()


class isValidJSON(Func):
    arity = 1
    output_field = fields.BoolField()


class toJSONString(Func):
    arity = 1
    output_field = fields.StringField()


class dynamicType(Func):
    arity = 1
    output_field = fields.StringField()

    def as_clickhouse(self, compiler, connection):
        (expression,) = self.source_expressions
        if not isinstance(expression, django_json.KeyTransform):
            return self.as_sql(compiler, connection)
        # A key transform compiles to the JSON text of the path, whose type is
        # always String. Read the Dynamic sub-column itself instead.
        dynamic, _, text_keys, params = subcolumns(expression, compiler, connection)
        if text_keys:
            raise NotSupportedError(
                "dynamicType() cannot read a JSON path which follows an array "
                "index, it is read from JSON text instead of as a sub-column."
            )
        return "dynamicType(%s)" % dynamic, params
