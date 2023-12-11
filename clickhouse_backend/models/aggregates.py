from django.db.models import Aggregate
from django.db.models.expressions import Star
from django.db.models.fields import IntegerField

__all__ = [
    "uniqExact",
    "uniq",
    "uniqCombined",
    "uniqCombined64",
    "uniqHLL12",
    "uniqTheta",
]


class uniqExact(Aggregate):
    function = "uniqExact"
    name = "uniqExact"
    output_field = IntegerField()
    allow_distinct = True
    empty_result_set_value = 0

    def __init__(self, expression, filter=None, **extra):
        if expression == "*":
            expression = Star()
        if isinstance(expression, Star) and filter is not None:
            raise ValueError("Star cannot be used with filter.")
        super().__init__(expression, filter=filter, **extra)


class uniq(Aggregate):
    function = "uniq"
    name = "uniq"
    output_field = IntegerField()
    allow_distinct = True
    empty_result_set_value = 0

    def __init__(self, expression, filter=None, **extra):
        if expression == "*":
            expression = Star()
        if isinstance(expression, Star) and filter is not None:
            raise ValueError("Star cannot be used with filter.")
        super().__init__(expression, filter=filter, **extra)


class uniqCombined(Aggregate):
    function = "uniqCombined"
    name = "uniqCombined"
    output_field = IntegerField()
    allow_distinct = True
    empty_result_set_value = 0

    def __init__(self, expression, filter=None, **extra):
        if expression == "*":
            expression = Star()
        if isinstance(expression, Star) and filter is not None:
            raise ValueError("Star cannot be used with filter.")
        super().__init__(expression, filter=filter, **extra)


class uniqCombined64(Aggregate):
    function = "uniqCombined64"
    name = "uniqCombined64"
    output_field = IntegerField()
    allow_distinct = True
    empty_result_set_value = 0

    def __init__(self, expression, filter=None, **extra):
        if expression == "*":
            expression = Star()
        if isinstance(expression, Star) and filter is not None:
            raise ValueError("Star cannot be used with filter.")
        super().__init__(expression, filter=filter, **extra)


class uniqHLL12(Aggregate):
    function = "uniqHLL12"
    name = "uniqHLL12"
    output_field = IntegerField()
    allow_distinct = True
    empty_result_set_value = 0

    def __init__(self, expression, filter=None, **extra):
        if expression == "*":
            expression = Star()
        if isinstance(expression, Star) and filter is not None:
            raise ValueError("Star cannot be used with filter.")
        super().__init__(expression, filter=filter, **extra)


class uniqTheta(Aggregate):
    function = "uniqTheta"
    name = "uniqTheta"
    output_field = IntegerField()
    allow_distinct = True
    empty_result_set_value = 0

    def __init__(self, expression, filter=None, **extra):
        if expression == "*":
            expression = Star()
        if isinstance(expression, Star) and filter is not None:
            raise ValueError("Star cannot be used with filter.")
        super().__init__(expression, filter=filter, **extra)
