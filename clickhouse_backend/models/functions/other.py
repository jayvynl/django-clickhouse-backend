from django.db.models import Value

from clickhouse_backend.models import fields

from .base import Func

__all__ = [
    "currentDatabase",
    "hostName",
    "generateSerialID",
]


class currentDatabase(Func):
    arity = 0
    output_field = fields.StringField()


class hostName(Func):
    arity = 0
    output_field = fields.StringField()


class generateSerialID(Func):
    """
    https://clickhouse.com/docs/sql-reference/functions/other-functions#generateSerialID

    The second argument, the start value of a new series, needs ClickHouse 25.10.
    https://github.com/ClickHouse/ClickHouse/blob/31081d9f05014003321333553bb3e657eb3da168/docs/changelogs/v25.10.1.3832-stable.md?plain=1#L128
    """

    output_field = fields.UInt64Field()

    def __init__(self, *expressions):
        arity = len(expressions)
        if arity < 1 or arity > 2:
            raise TypeError(
                "'%s' takes 1 or 2 arguments (%s given)"
                % (
                    self.__class__.__name__,
                    len(expressions),
                )
            )

        if isinstance(expressions[0], str):
            expressions = (Value(expressions[0]), *expressions[1:])
        super().__init__(*expressions)
