from django.db import models

from clickhouse_backend.models.functions.base import Func

__all__ = [
    "array",
    "hasAny",
    "arrayFirstIndex",
    "groupArrayIf",
    "groupUniqArrayIf",
]


class array(Func):
    function = "array"


class hasAny(Func):
    function = "hasAny"
    arity = 2
    output_field = models.BooleanField()


class arrayFirstIndex(Func):
    function = "arrayFirstIndex"
    template = "%(direction)s%(function)s(p -> p = %(field)s, %(array_with_order)s)"

    def __init__(self, field, array_with_order, direction="", **extra):
        super().__init__(
            field, array_with_order=array_with_order, direction=direction, **extra
        )

    def get_group_by_cols(self):
        return []


class groupArrayIf(Func):
    function = "groupArrayIf"

    def _resolve_output_field(self):
        return self.get_source_fields()[0]

    def get_group_by_cols(self):
        return []


class groupUniqArrayIf(Func):
    function = "groupUniqArrayIf"

    def _resolve_output_field(self):
        return self.get_source_fields()[0]

    def get_group_by_cols(self):
        return []
