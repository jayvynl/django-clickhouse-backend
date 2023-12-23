from django.db.models.expressions import Value

from .base import Func

__all__ = [
    "Tuple",
    "tupleElement",
]


class Tuple(Func):
    pass


class tupleElement(Func):
    def __init__(self, *expressions, output_field=None, **extra):
        if len(expressions) == 2:
            expressions = (expressions[0], Value[1])
        elif len(expressions) == 3:
            expressions = (expressions[0], Value[1], expressions[2])
        else:
            raise TypeError(
                "'%s' takes 2 or 3 arguments (%s given)"
                % (
                    self.__class__.__name__,
                    len(expressions),
                )
            )
        super().__init__(*expressions, output_field=output_field, **extra)
