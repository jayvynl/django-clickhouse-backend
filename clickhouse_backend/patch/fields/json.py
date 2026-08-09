import json as jsonlib
import re

from django.core.exceptions import FieldError
from django.db.models import lookups
from django.db.models.expressions import ExpressionList, Value
from django.db.models.fields import TextField, json
from django.db.utils import NotSupportedError

# CAST to JSON requires an object at the root, so a JSON value which is not an
# object travels inside a wrapper object under this key.
WRAPPER_KEY = "value"

# A JSON value travels as text, which clickhouse casts to JSON on its own when it
# is inserted or assigned. A comparison has to cast it: clickhouse compares a JSON
# column with a string as never equal, rather than raising anything.
JSON_PARAM = "CAST(%s, 'JSON')"

# An array index, which django reads out of the name of a key transform.
INDEX = re.compile(r"-?\d+")

# Type accurateCastOrNull converts a JSON path to, by python type of the value
# it is compared with.
COMPARISON_TYPES = {bool: "Bool", int: "Int64", float: "Float64", str: "String"}

base_select_format = json.KeyTransform.select_format


def quote_key(key):
    return "`%s`" % key.replace("\\", "\\\\").replace("`", "\\`")


def array_index(key):
    """A key as clickhouse indexes an array, which counts from one and reads a
    negative index from the end, or the key itself when it is not an index.
    """
    if not INDEX.fullmatch(key):
        return key
    index = int(key)
    return index + 1 if index >= 0 else index


def accessors(lhs, key_transforms):
    """Return ``json.a.b``, ``json.^a.b`` and the keys left over after an index.

    A path is readable through one of the two accessors only: the dynamic one is
    NULL for a nested object, the sub-object one an empty object for anything
    else. The sub-object accessor cannot express a path containing an index.
    """
    dynamic = lhs
    keys = []  # None once an array index makes the sub-object accessor unusable.
    text_keys = []
    for depth, key in enumerate(key_transforms):
        index = array_index(key)
        if text_keys or (keys is None and not isinstance(index, int)):
            # An accessor cannot follow an array index, clickhouse parses a dot
            # on an expression as tupleElement(). Read the rest from JSON text.
            text_keys.append(key)
        elif isinstance(index, int) and depth:
            # The root of a JSON column is an object, indexing it is an error.
            dynamic = "%s[%d]" % (dynamic, index)
            keys = None
        else:
            # A literal % is doubled, the driver interpolates the params of a
            # query into it.
            quoted = quote_key(key).replace("%", "%%")
            dynamic = "%s.%s" % (dynamic, quoted)
            keys.append(quoted)
    subobject = "%s.^%s" % (lhs, ".".join(keys)) if keys else None
    return dynamic, subobject, text_keys


def subcolumns(transform, compiler, connection):
    lhs, params, key_transforms = transform.preprocess_lhs(compiler, connection)
    return (*accessors(lhs, key_transforms), tuple(params))


def json_extract(function, dynamic, text_keys, params):
    """The JSON functions index an array the way the accessors do."""
    key_params = [array_index(key) for key in text_keys]
    return (
        "%s(toJSONString(%s), %s)"
        % (function, dynamic, ", ".join(["%s"] * len(text_keys))),
        (*params, *key_params),
    )


def json_text(sql):
    """The JSON text functions take a String, never a Nullable(String)."""
    return "ifNull(%s, '')" % sql


def path_text(lhs, key_transforms, params):
    """Read a JSON path as JSON text, NULL for a path which is absent."""
    dynamic, subobject, text_keys = accessors(lhs, key_transforms)
    if text_keys:
        # JSONExtractRaw returns the empty string for a path which is absent.
        sql, params = json_extract("JSONExtractRaw", dynamic, text_keys, params)
        return "nullIf(%s, '')" % sql, params
    if subobject is None:
        return "toJSONString(%s)" % dynamic, params
    return (
        "coalesce(toJSONString(%s), nullIf(toJSONString(%s), '{}'))"
        % (dynamic, subobject),
        params * 2,
    )


def lookup_lhs(lookup, compiler, connection):
    """The JSON column of the lhs of a lookup, and the keys of the path below it."""
    if isinstance(lookup.lhs, json.KeyTransform):
        lhs, params, keys = lookup.lhs.preprocess_lhs(compiler, connection)
        return lhs, tuple(params), keys
    lhs, params = lookup.process_lhs(compiler, connection)
    return lhs, tuple(params), []


def is_json_text(expression):
    """Whether an expression is compiled as JSON text: a key transform is, while
    the text transform below it reads the string a path holds.
    """
    return isinstance(expression, json.KeyTransform) and not isinstance(
        expression, json.KeyTextTransform
    )


def is_json_value(expression):
    """Whether an expression compiles to a clickhouse JSON value, which is read
    through toJSONString() to compare it with a path or to build a value of it.
    """
    if is_json_text(expression):
        return False
    try:
        return isinstance(expression.output_field, json.JSONField)
    except FieldError:
        return False


def lookup_value(lookup):
    """The python value of the rhs, which a containment lookup walks itself."""
    rhs = lookup.rhs.value if isinstance(lookup.rhs, Value) else lookup.rhs
    if hasattr(rhs, "resolve_expression"):
        raise NotSupportedError(
            "%s lookup only supports a literal value on this database backend."
            % lookup.lookup_name
        )
    return rhs


def json_text_param(value, encoder):
    """Compile ``value`` into SQL rendering it as clickhouse normalized JSON text.

    Normalizing both sides through clickhouse is what makes objects and arrays
    comparable at all: clickhouse sorts object keys and prints numbers its own
    way, and comparing arrays is type strict.
    """
    if isinstance(value, dict):
        return "toJSONString(%s)" % JSON_PARAM, jsonlib.dumps(value, cls=encoder)
    return (
        "toJSONString(getSubcolumn(%s, '%s'))" % (JSON_PARAM, WRAPPER_KEY),
        jsonlib.dumps({WRAPPER_KEY: value}, cls=encoder),
    )


def in_lookup_sql(lookup, compiler, connection, lhs_template="%s"):
    """Match against values with has(), IN takes neither of the two sides.

    Every value is rendered by clickhouse itself, which IN rejects as its right
    hand side because such a value is not a constant, and IN rejects a JSON
    column as its left one with "Illegal type JSON of argument of function in".
    """
    rhs = lookup.rhs
    if isinstance(rhs, ExpressionList):
        # Django 6.0 wraps a list holding an expression, below that it stays one.
        rhs = rhs.get_source_expressions()
    elif hasattr(rhs, "resolve_expression") or not rhs:
        return lookup.as_sql(compiler, connection)

    lhs_sql, params = lookup.process_lhs(compiler, connection)
    encoder = lookup.lhs.output_field.encoder
    values = []
    rhs_params = []
    for value in rhs:
        if isinstance(value, Value):
            value = value.value
        if hasattr(value, "resolve_expression"):
            # An expression is read as JSON text, the way the lhs is, so that
            # has() compares two values of the same type.
            value_sql, value_params = compiler.compile(value)
            if is_json_value(value):
                value_sql = "toJSONString(%s)" % value_sql
            values.append(value_sql)
            rhs_params.extend(value_params)
            continue
        value_sql, value_param = json_text_param(value, encoder)
        values.append(value_sql)
        rhs_params.append(value_param)
    return (
        "has([%s], %s)" % (", ".join(values), lhs_template % lhs_sql),
        (*rhs_params, *params),
    )


def key_transform_as_clickhouse(self, compiler, connection):
    """Read a JSON path as JSON text.

    ``Dynamic``, the type of a JSON path, has no representation in the native
    protocol and clickhouse allows it in neither GROUP BY nor ORDER BY, so the
    path is always read as text and deserialized by ``JSONField.from_db_value``.
    """
    lhs, params, key_transforms = self.preprocess_lhs(compiler, connection)
    return path_text(lhs, key_transforms, tuple(params))


def key_text_transform_as_clickhouse(self, compiler, connection):
    dynamic, _, text_keys, params = subcolumns(self, compiler, connection)
    if text_keys:
        return json_extract("JSONExtractString", dynamic, text_keys, params)
    return "toString(%s)" % dynamic, params


def key_transform_exact_as_clickhouse(self, compiler, connection):
    """Compare a JSON path and a value as JSON text.

    A path is a ``Dynamic`` holding whatever type each row stored under it, and
    clickhouse refuses to compare it with a value of another type. Comparing
    text is exact for objects, arrays and scalars alike.
    """
    if hasattr(self.rhs, "resolve_expression"):
        if not is_json_value(self.rhs):
            # Both sides are compiled as JSON text already.
            return self.as_sql(compiler, connection)
        # A JSON value is read as text, the way the path itself is.
        lhs_sql, params = self.process_lhs(compiler, connection)
        rhs_sql, rhs_params = self.process_rhs(compiler, connection)
        return "%s = toJSONString(%s)" % (lhs_sql, rhs_sql), (*params, *rhs_params)

    lhs_sql, params = self.process_lhs(compiler, connection)
    rhs_sql, rhs_param = json_text_param(self.rhs, self.lhs.output_field.encoder)
    return "%s = %s" % (lhs_sql, rhs_sql), (*params, rhs_param)


class JSONIn(getattr(json, "JSONIn", lookups.In)):
    """The ``in`` lookup of the field itself.

    Subclasses whatever django registers, which is a class of its own only from
    django 6.0 on, so that the behaviour of the other vendors is left alone.
    """

    def as_clickhouse(self, compiler, connection):
        # The lhs is the column itself, which has to be read as text like every
        # value it is compared with.
        return in_lookup_sql(self, compiler, connection, "toJSONString(%s)")


def path_exists(lhs, keys, params):
    """Read the sub-column accessors rather than JSONHas() over the whole value,
    which would serialize every row: a data skipping index over JSONAllPaths()
    answers IS NOT NULL on its own.
    """
    dynamic, subobject, text_keys = accessors(lhs, keys)
    if text_keys:
        return json_extract("JSONHas", dynamic, text_keys, params)
    if subobject is None:
        return "%s IS NOT NULL" % dynamic, params
    return (
        "(%s IS NOT NULL OR toJSONString(%s) != '{}')" % (dynamic, subobject),
        (*params, *params),
    )


def has_key_lookup_as_clickhouse(self, compiler, connection):
    """A key whose value is null does not exist, clickhouse drops it on the way in."""
    lhs_sql, lhs_params, lhs_keys = lookup_lhs(self, compiler, connection)
    sql_parts = []
    params = []
    for key in self.rhs if isinstance(self.rhs, (list, tuple)) else [self.rhs]:
        if isinstance(key, json.KeyTransform):
            key = key.preprocess_lhs(compiler, connection)[2]
        keys = key if isinstance(key, list) else [key]
        sql, key_params = path_exists(lhs_sql, [*lhs_keys, *keys], lhs_params)
        sql_parts.append(sql)
        params.extend(key_params)
    if self.logical_operator:
        return "(%s)" % self.logical_operator.join(sql_parts), params
    return sql_parts[0], params


def contains_sql(text, params, value, encoder, depth=0):
    """Whether the JSON text ``text`` contains ``value``, the way postgres ``@>`` does.

    Clickhouse has no containment function, but the value is known while the query
    is compiled, so walking it unrolls the recursion into the query itself: an
    object has to hold every key of the value, an array an element containing every
    element of it, and anything else has to be equal.
    """
    if isinstance(value, dict):
        if not value:
            return "JSONType(%s) = 'Object'" % json_text(text), params
        parts = []
        key_params = []
        for key, sub in value.items():
            # JSONExtractRaw returns the empty string for a key which is absent.
            sql, sub_params = contains_sql(
                "JSONExtractRaw(%s, %%s)" % text, (*params, key), sub, encoder, depth
            )
            parts.append(sql)
            key_params.extend(sub_params)
        return "(%s)" % " AND ".join(parts), tuple(key_params)
    if isinstance(value, (list, tuple)):
        if not value:
            return "JSONType(%s) = 'Array'" % json_text(text), params
        element = "x%d" % depth
        parts = []
        element_params = []
        for item in value:
            sql, item_params = contains_sql(element, (), item, encoder, depth + 1)
            parts.append(
                "arrayExists(%s -> %s, JSONExtractArrayRaw(%s))"
                % (element, sql, json_text(text))
            )
            element_params.extend((*item_params, *params))
        return "(%s)" % " AND ".join(parts), tuple(element_params)
    rhs_sql, rhs_param = json_text_param(value, encoder)
    return "%s = %s" % (text, rhs_sql), (*params, rhs_param)


def contains_conditions(lhs, keys, params, value, encoder):
    """Descend an object of the value through the sub-column accessors, so that a
    path is read on its own rather than by serializing the whole value. Only what
    is below an array of the value is compared as JSON text.
    """
    if isinstance(value, dict) and value:
        for key, sub in value.items():
            yield from contains_conditions(lhs, [*keys, key], params, sub, encoder)
    else:
        yield contains_sql(*path_text(lhs, keys, params), value, encoder)


def data_contains_as_clickhouse(self, compiler, connection):
    """Postgres, whose semantics these lookups take, returns false rather than NULL
    for a path which is absent, so that ``exclude()`` returns such a row.
    """
    lhs, params, keys = lookup_lhs(self, compiler, connection)
    value = lookup_value(self)
    encoder = self.lhs.output_field.encoder
    if isinstance(value, (dict, list, tuple)):
        conditions = list(contains_conditions(lhs, keys, params, value, encoder))
        sql = " AND ".join(sql for sql, _ in conditions)
        params = tuple(param for _, part in conditions for param in part)
    else:
        # An array contains a primitive value of its own, the one exception
        # postgres makes to the structures having to match, at the top level only.
        text, text_params = path_text(lhs, keys, params)
        rhs_sql, rhs_param = json_text_param(value, encoder)
        sql = "%s = %s OR has(JSONExtractArrayRaw(%s), %s)" % (
            text,
            rhs_sql,
            json_text(text),
            rhs_sql,
        )
        params = (*text_params, rhs_param, *text_params, rhs_param)
    return "ifNull(%s, 0)" % sql, params


def contained_by_sql(text, params, value, encoder, depth=0):
    """Whether ``value`` contains the JSON text ``text``, the way postgres ``<@`` does.

    The value is walked the same way as by a contains lookup, but it is the column
    which is unknown here, so every key of an object and every element of an array
    of the column has to be contained by one of the value.
    """
    if isinstance(value, dict):
        var = "kv%d" % depth
        parts = []
        body_params = []
        for key, sub in value.items():
            sql, sub_params = contained_by_sql(
                "%s.2" % var, (), sub, encoder, depth + 1
            )
            parts.append("(%s.1 = %%s AND %s)" % (var, sql))
            body_params.append(key)
            body_params.extend(sub_params)
        body = " OR ".join(parts) or "0"
        function = "JSONExtractKeysAndValuesRaw"
        json_type = "Object"
    elif isinstance(value, (list, tuple)):
        var = "x%d" % depth
        parts = []
        body_params = []
        for item in value:
            sql, item_params = contained_by_sql(var, (), item, encoder, depth + 1)
            parts.append("(%s)" % sql)
            body_params.extend(item_params)
        body = " OR ".join(parts) or "0"
        function = "JSONExtractArrayRaw"
        json_type = "Array"
    else:
        rhs_sql, rhs_param = json_text_param(value, encoder)
        return "%s = %s" % (text, rhs_sql), (*params, rhs_param)
    return (
        "(JSONType(%s) = '%s' AND arrayAll(%s -> %s, %s(%s)))"
        % (json_text(text), json_type, var, body, function, json_text(text)),
        (*params, *body_params, *params),
    )


def contained_by_as_clickhouse(self, compiler, connection):
    lhs, params, keys = lookup_lhs(self, compiler, connection)
    value = lookup_value(self)
    encoder = self.lhs.output_field.encoder
    text, text_params = path_text(lhs, keys, params)
    sql, params = contained_by_sql(text, text_params, value, encoder)
    primitives = [
        json_text_param(item, encoder)
        for item in (value if isinstance(value, (list, tuple)) else ())
        if not isinstance(item, (dict, list, tuple))
    ]
    if primitives:
        # The same exception as a contains lookup makes, read the other way round.
        sql = "%s OR has([%s], %s)" % (
            sql,
            ", ".join(item_sql for item_sql, _ in primitives),
            json_text(text),
        )
        params = (*params, *(param for _, param in primitives), *text_params)
    return "ifNull(%s, 0)" % sql, params


def json_exact_as_clickhouse(self, compiler, connection):
    """Compare the field itself with a value, which has to be CAST to JSON.

    Clickhouse matches no row when a JSON column is compared with a string,
    without raising anything.
    """
    if self.rhs is None or hasattr(self.rhs, "resolve_expression"):
        # A None rhs is rendered as the JSON text "null" by JSONExact, and
        # CAST('null', 'JSON') is an empty object rather than NULL.
        return self.as_sql(compiler, connection)

    lhs_sql, params = self.process_lhs(compiler, connection)
    rhs_sql, rhs_params = self.process_rhs(compiler, connection)
    return "%s = %s" % (lhs_sql, JSON_PARAM % rhs_sql), (*params, *rhs_params)


def key_transform_numeric_lookup_mixin_as_clickhouse(self, compiler, connection):
    """Compare a JSON path in a definite type, JSON text would order numbers as text.

    Rows holding a value that does not convert to that type are left out rather
    than failing the query, which comparing the ``Dynamic`` itself would do.
    """
    comparison_type = COMPARISON_TYPES.get(type(self.rhs))
    if comparison_type is None:
        return self.as_sql(compiler, connection)

    dynamic, _, text_keys, params = subcolumns(self.lhs, compiler, connection)
    if text_keys:
        # The JSON text of a number converts to it, the text of a string does not.
        dynamic, params = json_extract("JSONExtractRaw", dynamic, text_keys, params)
    rhs_sql, rhs_params = self.process_rhs(compiler, connection)
    return "accurateCastOrNull(%s, '%s') %s" % (
        dynamic,
        comparison_type,
        self.get_rhs_op(connection, rhs_sql),
    ), (*params, *rhs_params)


def key_transform_select_format(self, compiler, sql, params):
    if compiler.connection.vendor == "clickhouse":
        # JSONField.select_format reads a column as JSON text, a key transform
        # is compiled as text already.
        return sql, params
    return base_select_format(self, compiler, sql, params)


def patch_jsonfield():
    if "output_field" not in json.KeyTextTransform.__dict__:
        # Django 4.2 gave it one. Below that it resolves to the JSONField of the
        # lhs, whose from_db_value parses the text back into a value.
        json.KeyTextTransform.output_field = TextField()
    json.ContainedBy.as_clickhouse = contained_by_as_clickhouse
    json.DataContains.as_clickhouse = data_contains_as_clickhouse
    json.HasKeyLookup.as_clickhouse = has_key_lookup_as_clickhouse
    json.JSONExact.as_clickhouse = json_exact_as_clickhouse
    json.JSONField.register_lookup(JSONIn)
    json.KeyTransform.select_format = key_transform_select_format
    json.KeyTransform.as_clickhouse = key_transform_as_clickhouse
    json.KeyTextTransform.as_clickhouse = key_text_transform_as_clickhouse
    json.KeyTransformExact.as_clickhouse = key_transform_exact_as_clickhouse
    json.KeyTransformIn.as_clickhouse = in_lookup_sql
    json.KeyTransformNumericLookupMixin.as_clickhouse = (
        key_transform_numeric_lookup_mixin_as_clickhouse
    )
