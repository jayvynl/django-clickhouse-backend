from datetime import date, datetime, time, timezone
from enum import Enum
from ipaddress import IPv4Address, IPv6Address
from itertools import chain
from typing import Dict, Sequence, Union
from uuid import UUID

from clickhouse_driver.util import escape

from . import types

Params = Union[Sequence, Dict]


def escape_datetime(item: datetime, context):
    """Clickhouse backend always treats DateTime[64] with timezone as in UTC timezone.

    DateTime value does not support microsecond part,
    clickhouse_backend.models.DateTimeField will set microsecond to zero.
    As integer and float are always treated as UTC timestamps,
    it is required to convert a naive datetime to an utc timestamp.
    """
    if item.tzinfo is None:
        return item.timestamp()

    item = item.astimezone(timezone.utc)
    if item.microsecond == 0:
        return "'%s'" % item.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return "'%s'" % item.strftime("%Y-%m-%d %H:%M:%S.%f")


def escape_binary(item: bytes, context):
    # b"\x00F '\xfe" ->   '\x00F \'\xfe'
    b2s = str(item)
    if b2s[1] == '"':
        return "'%s'" % b2s[2:-1].replace("'", "\\'")
    return b2s[1:]


def escape_param(item, context):
    if item is None:
        return "NULL"

    elif isinstance(item, datetime):
        return escape_datetime(item, context)

    elif isinstance(item, date):
        return "'%s'" % item.strftime("%Y-%m-%d")

    elif isinstance(item, time):
        return "'%s'" % item.strftime("%H:%M:%S")

    elif isinstance(item, str):
        return "'%s'" % "".join(escape.escape_chars_map.get(c, c) for c in item)

    elif isinstance(item, list):
        return "[%s]" % ",".join(str(escape_param(x, context)) for x in item)

    elif isinstance(item, tuple):
        return "tuple(%s)" % ",".join(str(escape_param(x, context)) for x in item)

    elif isinstance(item, dict):
        return "map(%s)" % ",".join(
            str(escape_param(x, context)) for x in chain.from_iterable(item.items())
        )

    elif isinstance(item, Enum):
        return escape_param(item.value, context)

    elif isinstance(item, (UUID, IPv4Address, IPv6Address)):
        return "'%s'" % str(item)

    elif isinstance(item, types.Binary):
        return escape_binary(item, context)

    elif isinstance(item, types.JSON):
        value = item.value
        if isinstance(value, list):
            return escape_param([types.JSON(v) for v in value], context)
        elif isinstance(value, dict):
            return escape_param(tuple(types.JSON(v) for v in value.values()), context)
        else:
            return escape_param(value, context)

    else:
        return item


def escape_params(params: Params, context: Dict) -> Params:
    """Escape param to qualified string representation.

    This function is not used in INSERT INTO queries.
    """
    if isinstance(params, dict):
        escaped = {key: escape_param(value, context) for key, value in params.items()}
    else:
        escaped = tuple(escape_param(value, context) for value in params)

    return escaped
