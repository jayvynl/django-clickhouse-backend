import ipaddress
from datetime import datetime, timezone
from typing import Sequence, Dict, Union

from clickhouse_driver.util import escape

Params = Union[Sequence, Dict]


def escape_datetime(item: datetime, context):
    """Escape datetime to valid clickhouse_backend DateTime literal.

    All datetime are cast to DateTime64 with 6 precision.
    https://clickhouse.com/docs/en/sql-reference/data-types/datetime64
    """
    if item.tzinfo is not None:
        item = item.astimezone(timezone.utc)
    time_string = item.strftime('%Y-%m-%d %H:%M:%S.%f')

    if item.tzinfo is not None:
        return "toDateTime64('%s', 6, 'UTC')" % time_string
    return "toDateTime64('%s', 6)" % time_string


def escape_param(item, context, **kwargs):
    if isinstance(item, ipaddress.IPv4Address):
        return "toIPv4('%s')" % item.compressed
    elif isinstance(item, ipaddress.IPv6Address):
        return "toIPv6('%s')" % item.compressed
    elif isinstance(item, datetime):
        return escape_datetime(item, context)
    return escape.escape_param(item, context)


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
