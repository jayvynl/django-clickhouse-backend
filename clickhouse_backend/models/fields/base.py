from django.core import checks
from django.core.exceptions import ImproperlyConfigured


class FieldMixin:
    """All clickhouse field should inherit this mixin.

    1. Remove unsupported arguments: unique, db_index, unique_for_date,
    unique_for_month, unique_for_year, db_tablespace.
    2. Return shortened name in deconstruct method.
    3. Add low_cardinality attribute, corresponding to clickhouse LowCardinality Data Type.
    """
    low_cardinality_allowed = True
    nullable_allowed = True

    def __init__(self, *args, low_cardinality=False, **kwargs):
        self.low_cardinality = low_cardinality
        super().__init__(*args, **kwargs)

    def check(self, **kwargs):
        return [
            *super().check(**kwargs),
            *self._check_low_cardinality(),
            *self._check_nullable(),
        ]

    def _check_low_cardinality(self):
        if self.low_cardinality and not self.low_cardinality_allowed:
            return [
                checks.Error(
                    "%s must not define a 'low_cardinality=True' attribute." %
                    self.__class__.__name__,
                    obj=self,
                )
            ]
        return []

    def _check_nullable(self):
        if self.null and not self.nullable_allowed:
            return [
                checks.Error(
                    "%s must not define a 'null=True' attribute." %
                    self.__class__.__name__,
                    obj=self,
                )
            ]
        return []

    def deconstruct(self):
        path, name, args, kwargs = super().deconstruct()
        for key in [
            "unique",
            "db_index",
            "unique_for_date",
            "unique_for_month",
            "unique_for_year",
            "db_tablespace",
            "db_collation",
        ]:
            try:
                del kwargs[key]
            except KeyError:
                pass

        kwargs["low_cardinality"] = self.low_cardinality
        if name.startswith("clickhouse_backend.models.fields"):
            name = name.replace("clickhouse_backend.models.fields", "clickhouse_backend.models")
        return path, name, args, kwargs

    def _nested_type(self, value):
        if value is not None:
            # LowCardinality and Nullable sequence matters, reversal will cause DB::Exception:
            # Nested type LowCardinality(Int8) cannot be inside Nullable type. (ILLEGAL_TYPE_OF_ARGUMENT)
            if self.null:
                value = "Nullable(%s)" % value
            if self.low_cardinality:
                value = "LowCardinality(%s)" % value
        return value

    def _check_backend(self, connection):
        if connection.vendor != "clickhouse":
            raise ImproperlyConfigured(
                "%s must only be used with django clickhouse backend." %
                self.__class__.__name__
            )

    def db_type(self, connection):
        self._check_backend(connection)
        return self._nested_type(super().db_type(connection))
