from django.conf import settings
from django.db import models

__all__ = [
    "toYYYYMM",
    "toYYYYMMDD",
    "toYYYYMMDDhhmmss",
    "currentDatabase",
    "Rand",
    "hostName",
]


class Func(models.Func):
    @property
    def function(self):
        return self.__class__.__name__


class toYYYYMM(Func):
    def __init__(self, *expressions, output_field=None, **extra):
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
        elif settings.USE_TZ:
            expressions = (expressions[0], models.Value(settings.TIME_ZONE))
        super().__init__(*expressions, output_field=output_field, **extra)


class toYYYYMMDD(toYYYYMM):
    pass


class toYYYYMMDDhhmmss(toYYYYMM):
    pass


class currentDatabase(Func):
    arity = 0


class Rand(Func):
    arity = 0


class hostName(Func):
    arity = 0
