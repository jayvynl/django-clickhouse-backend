from datetime import datetime, timezone
from enum import Enum
from ipaddress import IPv4Address, IPv6Address
from itertools import chain
from typing import Dict, Sequence, Union

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
    """Escape the types clickhouse-driver escapes differently, or not at all.

    A collection is escaped here rather than left to clickhouse-driver, which
    would escape the elements with its own escape_param and lose these branches.
    """
    if isinstance(item, datetime):
        return escape_datetime(item, context)

    elif isinstance(item, list):
        return "[%s]" % ",".join(str(escape_param(x, context)) for x in item)

    elif isinstance(item, tuple):
        # clickhouse-driver renders a one element tuple as (x), which is just x.
        return "tuple(%s)" % ",".join(str(escape_param(x, context)) for x in item)

    elif isinstance(item, dict):
        return "map(%s)" % ",".join(
            str(escape_param(x, context)) for x in chain.from_iterable(item.items())
        )

    elif isinstance(item, Enum):
        return escape_param(item.value, context)

    elif isinstance(item, (IPv4Address, IPv6Address)):
        return "'%s'" % str(item)

    elif isinstance(item, types.Binary):
        return escape_binary(item, context)

    return escape.escape_param(item, context)


def escape_params(params: Params, context: Dict) -> Params:
    """Escape param to qualified string representation.

    This function is not used in INSERT INTO queries.
    """
    if isinstance(params, dict):
        escaped = {key: escape_param(value, context) for key, value in params.items()}
    else:
        escaped = tuple(escape_param(value, context) for value in params)

    return escaped
