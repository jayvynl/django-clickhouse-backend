"""Date and time functions.

Return types of the ``toStartOf*`` family
=========================================

They depend on the server setting ``enable_extended_results_for_datetime_functions``,
which defaults to ``0``. Only that default is supported, and the output fields below
are the types it produces, measured on ClickHouse 23.6.2.18, 24.3.18.7 and
26.6.1.1193, which agree:

* ``toStartOfMinute``, ``toStartOfFiveMinutes``, ``toStartOfTenMinutes``,
  ``toStartOfFifteenMinutes`` and ``toStartOfHour`` return ``DateTime`` and reject
  ``Date`` and ``Date32`` outright (ILLEGAL_TYPE_OF_ARGUMENT).
* ``toStartOfDay`` returns ``DateTime`` for every argument type.
* ``toStartOfWeek``, ``toStartOfMonth``, ``toStartOfQuarter`` and ``toStartOfYear``
  return ``Date``.

With the setting on, a ``Date32`` or a ``DateTime64(p)`` argument gives something
wider: ``DateTime64`` for the first group and ``Date32`` for the last one. Django
cannot follow that, because ``_resolve_output_field()`` gets no connection and the
output field is resolved while the query is still being built, before ``.using()``
has picked a database. Projects that turn the setting on should pass
``output_field`` explicitly, e.g.
``toStartOfDay(f, output_field=DateTime64Field(precision=3))``.

https://clickhouse.com/docs/reference/settings/session-settings/enable#enable_extended_results_for_datetime_functions

Beware that with the setting off a ``Date32`` outside the ``DateTime`` range
silently overflows: ``toStartOfDay(toDate32('1900-01-01'))`` is
``2036-02-07 06:28:16``. It overflows inside the function, so casting the result
afterwards cannot repair it.

The timezone argument is not accepted everywhere. The four functions returning a
``Date`` take one only for a ``DateTime`` or a ``DateTime64`` argument: a date has no
time of day, so the truncation cannot depend on a timezone, and passing one raises
ILLEGAL_TYPE_OF_ARGUMENT instead of being ignored -- see ``DateTruncation``.
``toStartOfDay`` does accept one for a ``Date`` and a ``Date32``. A timezone in the
argument type is carried over to the result, so ``toStartOfDay(toDateTime(..., 'UTC'))``
is a ``DateTime('UTC')``.
"""

from django.db import models

from clickhouse_backend.models import fields
from clickhouse_backend.utils.timezone import get_timezone

from .base import Func

__all__ = [
    "toStartOfMinute",
    "toStartOfFiveMinutes",
    "toStartOfTenMinutes",
    "toStartOfFifteenMinutes",
    "toStartOfHour",
    "toStartOfDay",
    "toStartOfWeek",
    "toStartOfMonth",
    "toStartOfQuarter",
    "toStartOfYear",
    "toYYYYMM",
    "toYYYYMMDD",
    "toYYYYMMDDhhmmss",
    "toYearWeek",
    "ULIDStringToDateTime",
]


class toYYYYMM(Func):
    output_field = fields.UInt32Field()

    def __init__(self, *expressions):
        arity = len(expressions)
        if arity < 1 or arity > 2:
            raise TypeError(
                "'%s' takes 1 or 2 arguments (%s given)"
                % (
                    self.__class__.__name__,
                    arity,
                )
            )
        if arity == 2 and isinstance(expressions[1], str):
            expressions = (expressions[0], models.Value(expressions[1]))
        else:
            expressions = (expressions[0], models.Value(get_timezone()))

        super().__init__(*expressions)


class toYYYYMMDD(toYYYYMM):
    pass


class toYYYYMMDDhhmmss(toYYYYMM):
    output_field = fields.UInt64Field()


class toStartOfMinute(Func):
    arity = 1
    output_field = fields.DateTimeField()


class toStartOfFiveMinutes(toStartOfMinute):
    pass


class toStartOfTenMinutes(toStartOfMinute):
    pass


class toStartOfFifteenMinutes(toStartOfMinute):
    pass


class toStartOfHour(toStartOfMinute):
    pass


class toStartOfDay(toYYYYMM):
    """Although not documented, toStartOfDay receives a second timezone argument."""

    output_field = fields.DateTimeField()


class DateTruncation(Func):
    """A truncation ClickHouse answers with a Date.

    These four take a timezone only for a DateTime or a DateTime64. A Date has no
    time of day, so truncating it to the start of a week, month, quarter or year
    is the same in every timezone, and ClickHouse rejects the argument with
    ILLEGAL_TYPE_OF_ARGUMENT rather than ignoring it. Which type the value has is
    only known once the expression is resolved, so that is where the timezone is
    dropped -- including one that was passed explicitly, which is as meaningless
    for a date as the default one.
    """

    output_field = fields.DateField()

    def __init__(self, *expressions):
        arity = len(expressions)
        if arity < 1 or arity > 2:
            raise TypeError(
                "'%s' takes 1 or 2 arguments (%s given)"
                % (
                    self.__class__.__name__,
                    arity,
                )
            )
        if arity == 2 and isinstance(expressions[1], str):
            expressions = (expressions[0], models.Value(expressions[1]))
        else:
            expressions = (expressions[0], models.Value(get_timezone()))

        super().__init__(*expressions)

    def resolve_expression(self, *args, **kwargs):
        c = super().resolve_expression(*args, **kwargs)
        source_field = c.get_source_fields()[0]
        # DateTimeField is a DateField subclass, hence the second check. An
        # argument of unknown type keeps the timezone, as a DateTime is the
        # common case and ClickHouse reports the mismatch well enough.
        if isinstance(source_field, models.DateField) and not isinstance(
            source_field, models.DateTimeField
        ):
            c.set_source_expressions(c.get_source_expressions()[:-1])
        return c


class toStartOfWeek(DateTruncation):
    def __init__(self, *expressions, **extra):
        arity = len(expressions)
        if not 1 <= arity <= 3:
            raise TypeError(
                "'%s' takes between 1 and 3 arguments (%s given)"
                % (
                    self.__class__.__name__,
                    arity,
                )
            )
        mode = expressions[1] if arity >= 2 else 0
        timezone = expressions[2] if arity >= 3 else get_timezone()
        Func.__init__(
            self, expressions[0], models.Value(mode), models.Value(timezone), **extra
        )


class toStartOfMonth(DateTruncation):
    pass


class toStartOfQuarter(DateTruncation):
    pass


class toStartOfYear(DateTruncation):
    pass


class toYearWeek(Func):
    output_field = fields.UInt32Field()

    def __init__(self, *expressions):
        arity = len(expressions)
        if not 1 <= arity <= 3:
            raise TypeError(
                "'%s' takes between 1 and 3 arguments (%s given)"
                % (
                    self.__class__.__name__,
                    arity,
                )
            )
        mode = expressions[1] if arity >= 2 else 0
        timezone = expressions[2] if arity >= 3 else get_timezone()
        super().__init__(expressions[0], models.Value(mode), models.Value(timezone))


class ULIDStringToDateTime(Func):
    output_field = fields.DateTime64Field(precision=3)

    def __init__(self, *expressions):
        arity = len(expressions)
        if not 1 <= arity <= 2:
            raise TypeError(
                "'%s' takes between 1 and 2 arguments (%s given)"
                % (
                    self.__class__.__name__,
                    len(expressions),
                )
            )

        expressions = (
            expressions[0],
            *(models.Value(expr) for expr in expressions[1:]),
        )

        super().__init__(*expressions)
