from django.db.models import aggregates, fields
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


class ArgMax(Aggregate):
    function = "argMax"
    name = "ArgMax"
    arity = 2

    def __init__(self, value_expr, order_by_expr, **extra):
        if "output_field" not in extra:
            # Infer output_field from value_expr
            if hasattr(value_expr, "output_field"):
                extra["output_field"] = value_expr.output_field
            else:
                # Fallback: assume CharField
                extra["output_field"] = fields.CharField()
        expressions = [value_expr, order_by_expr]
        super().__init__(*expressions, **extra)

    def as_sql(self, compiler, connection, **extra_context):
        self.extra["template"] = "%(function)s(%(expressions)s)"
        return super().as_sql(compiler, connection, **extra_context)
