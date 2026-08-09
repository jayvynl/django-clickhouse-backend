from django.db.models import functions
from django.db.utils import NotSupportedError

from .fields.json import JSON_PARAM, WRAPPER_KEY, is_json_text

__all__ = [
    "patch_functions",
    "patch_random",
]


def patch_functions():
    patch_now()
    patch_random()
    patch_json_object()
    if hasattr(functions, "JSONArray"):
        # django 5.2 added it.
        patch_json_array()


def patch_now():
    def as_clickhouse(self, compiler, connection, **extra_context):
        return functions.Now.as_sql(
            self, compiler, connection, template="now64()", **extra_context
        )

    functions.Now.as_clickhouse = as_clickhouse


def patch_random():
    def as_clickhouse(self, compiler, connection, **extra_context):
        return functions.Random.as_sql(
            self, compiler, connection, function="rand64", **extra_context
        )

    functions.Random.as_clickhouse = as_clickhouse


def json_parts(function, compiler, connection):
    """Compile the arguments of a JSON function as their JSON text.

    A key transform is read as JSON text already, everything else is a value
    which toJSONString() renders. SQL NULL becomes the JSON null the databases
    django supports keep in a JSON array too.
    """
    if not connection.features.supports_json_field:
        raise NotSupportedError(
            "JSONFields are not supported on this database backend."
        )
    parts = []
    params = []
    for expression in function.get_source_expressions():
        sql, expression_params = compiler.compile(expression)
        if not is_json_text(expression):
            sql = "toJSONString(%s)" % sql
        parts.append("ifNull(%s, 'null')" % sql)
        params.extend(expression_params)
    return parts, params


def json_concat(items, opening, closing):
    """Cast the JSON text of a container, its items joined by commas, to JSON."""
    args = [opening]
    for index, item in enumerate(items):
        if index:
            args.append("','")
        args.extend(item)
    args.append(closing)
    return JSON_PARAM % ("concat(%s)" % ", ".join(args))


def json_select_format(function):
    """Read the value as JSON text, the way a JSONField column is read.

    Clickhouse-driver decodes a JSON value natively into a dict, which the
    ``from_db_value`` of django's own JSONField cannot parse.
    """
    base_select_format = function.select_format

    def select_format(self, compiler, sql, params):
        if compiler.connection.vendor == "clickhouse":
            return "toJSONString(%s)" % sql, params
        return base_select_format(self, compiler, sql, params)

    function.select_format = select_format


def patch_json_object():
    """JSON_OBJECT() has no clickhouse equivalent, but casting the JSON text
    built from the arguments to JSON does the same, and normalizes it.
    """

    def as_clickhouse(self, compiler, connection, **extra_context):
        parts, params = json_parts(self, compiler, connection)
        pairs = [
            (parts[index], "':'", parts[index + 1]) for index in range(0, len(parts), 2)
        ]
        return json_concat(pairs, "'{'", "'}'"), params

    functions.JSONObject.as_clickhouse = as_clickhouse
    json_select_format(functions.JSONObject)


def patch_json_array():
    """A JSON value cannot be an array at its root, so the array is cast inside
    a wrapper object and read back out of it as a ``Dynamic``.
    """

    def as_clickhouse(self, compiler, connection, **extra_context):
        parts, params = json_parts(self, compiler, connection)
        wrapper = json_concat(
            [(part,) for part in parts], "'{\"%s\":['" % WRAPPER_KEY, "']}'"
        )
        return "getSubcolumn(%s, '%s')" % (wrapper, WRAPPER_KEY), params

    functions.JSONArray.as_clickhouse = as_clickhouse
    json_select_format(functions.JSONArray)
