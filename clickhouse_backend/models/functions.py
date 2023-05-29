from django.conf import settings
from django.db.models import Func, Value

__all__ = [
    'toYYYYMM',
    'toYYYYMMDD',
    'toYYYYMMDDhhmmss',
]


class toYYYYMM(Func):
    function = 'toYYYYMM'

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
            expressions = (expressions[0], Value(expressions[1]))
        elif settings.USE_TZ:
            expressions = (expressions[0], Value(settings.TIME_ZONE))
        super().__init__(*expressions, output_field=output_field, **extra)


class toYYYYMMDD(toYYYYMM):
    function = 'toYYYYMMDD'


class toYYYYMMDDhhmmss(toYYYYMM):
    function = 'toYYYYMMDDhhmmss'
