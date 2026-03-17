from django.db.models import aggregates
from django.db.models.expressions import Star

from clickhouse_backend.models.fields import UInt64Field

__all__ = [
    "uniq",
    "uniqExact",
    "uniqCombined",
    "uniqCombined64",
    "uniqHLL12",
    "uniqTheta",
    "anyLast",
    "argMax",
    "argMin",
    "argMinIf",
    "groupArray",
    "groupUniqArray",
    "groupArrayIfAgg",
    "arrayAggDistinct",
    "if_combinator",
]


class Aggregate(aggregates.Aggregate):
    @property
    def function(self):
        return self.__class__.__name__

    @property
    def name(self):
        return self.__class__.__name__

    def deconstruct(self):
        module_name = self.__module__
        name = self.__class__.__name__
        if module_name.startswith("clickhouse_backend.models.aggregates"):
            module_name = "clickhouse_backend.models"
        return (
            f"{module_name}.{name}",
            self._constructor_args[0],
            self._constructor_args[1],
        )


class uniq(Aggregate):
    output_field = UInt64Field()
    allow_distinct = True
    empty_result_set_value = 0

    def __init__(self, *expressions, distinct=False, filter=None, **extra):
        expressions = [Star() if exp == "*" else exp for exp in expressions]
        super().__init__(*expressions, distinct=distinct, filter=filter, **extra)


class uniqExact(uniq):
    pass


class uniqCombined(uniq):
    pass


class uniqCombined64(uniq):
    pass


class uniqHLL12(uniq):
    pass


class uniqTheta(uniq):
    pass


class anyLast(Aggregate):
    pass


class argMax(Aggregate):
    arity = 2

    def _resolve_output_field(self):
        return self.get_source_fields()[0]


class argMin(Aggregate):
    arity = 2

    def _resolve_output_field(self):
        return self.get_source_fields()[0]


class groupArray(Aggregate):
    def get_group_by_cols(self):
        return []


class groupUniqArray(Aggregate):
    def get_group_by_cols(self):
        return []


def if_combinator(base_cls):
    attrs = {"__module__": base_cls.__module__}
    if hasattr(base_cls, "arity") and isinstance(base_cls.arity, int):
        attrs["arity"] = base_cls.arity + 1
    return type(base_cls.__name__ + "If", (base_cls,), attrs)


argMinIf = if_combinator(argMin)


class groupArrayIfAgg(Aggregate):
    function = "groupArrayIf"

    def __init__(self, *expressions, **extra):
        super().__init__(*expressions, **extra)

    def _resolve_output_field(self):
        return self.get_source_fields()[0]

    def get_group_by_cols(self):
        return []


class arrayAggDistinct(Aggregate):
    function = "groupArrayDistinct"
