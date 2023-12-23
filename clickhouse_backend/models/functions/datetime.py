from django.db import models

from clickhouse_backend.models import fields
from clickhouse_backend.utils.timezone import get_timezone

from .base import Func

__all__ = [
    "toYYYYMM",
    "toYYYYMMDD",
    "toYYYYMMDDhhmmss",
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
                    len(expressions),
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
