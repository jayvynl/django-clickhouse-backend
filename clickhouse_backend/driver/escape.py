from datetime import date, datetime, timezone
from enum import Enum
from typing import Sequence, Dict, Union
from uuid import UUID
from decimal import Decimal
from clickhouse_driver.util import escape

from . import types

Params = Union[Sequence, Dict]


def escape_datetime(item: datetime, context):
    """Clickhouse backend always treats DateTime[64] with timezone as in UTC timezone.

    DateTime value does not support microsecond part,
    clickhouse_backend.models.DateTimeField will set microsecond to zero. """
    if item.tzinfo is not None:
        item = item.astimezone(timezone.utc)
    if item.microsecond == 0:
        return "'%s'" % item.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return "'%s'" % item.strftime('%Y-%m-%d %H:%M:%S.%f')


def escape_binary(item: bytes, context):
    # b"\x00F '\xfe" ->   '\x00F \'\xfe'
    b2s = str(item)
    if b2s[1] == '"':
        return "'%s'" % b2s[2:-1].replace("'", "\\'")
    return b2s[1:]


def escape_param(item, context):
    if item is None:
        return 'NULL'

    elif isinstance(item, datetime):
        return escape_datetime(item, context)

    elif isinstance(item, date):
        return "'%s'" % item.strftime('%Y-%m-%d')

    elif isinstance(item, str):
        return "'%s'" % ''.join(escape.escape_chars_map.get(c, c) for c in item)

    elif isinstance(item, list):
        return "[%s]" % ', '.join(str(escape_param(x, context)) for x in item)

    elif isinstance(item, tuple):
        return "(%s)" % ', '.join(str(escape_param(x, context)) for x in item)

    elif isinstance(item, Enum):
        return escape_param(item.value, context)

    elif isinstance(item, UUID):
        return "'%s'" % str(item)

    elif isinstance(item, types.Binary):
        return escape_binary(item, context)

    # NOTE:
    # 1. When inserting Decimal value, both Float (3.1) or String ('3.1') literals are valid.
    #    But after testing, I figure out that String is faster than Float about 18 percents.
    # 2. When take place in mathematical operation, String representation of Decimal is not valid.
    #    Also, Float representation may lose precision, only toDecimal(32|64|128|256) is suitable.
    # elif isinstance(item, Decimal):
    #     return "'%s'" % str(item)

    else:
        return item


def escape_params(params: Params, context: Dict) -> Params:
    if isinstance(params, Dict):
        escaped = {
            key: escape_param(value, context)
            for key, value in params.items()
        }
    else:
        escaped = tuple(
            escape_param(value, context)
            for value in params
        )

    return escaped
