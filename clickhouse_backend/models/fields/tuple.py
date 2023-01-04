import collections
import collections.abc
import copy
import json

from django.contrib.postgres.fields.utils import AttributeSetter
from django.contrib.postgres.utils import prefix_validation_error
from django.core import checks, exceptions
from django.db.models import Field, Func, Value
from django.db.models import lookups
from django.utils.functional import cached_property
from django.utils.itercompat import is_iterable
from django.utils.translation import gettext_lazy as _

from .base import FieldMixin

__all__ = ["TupleField"]


class TupleField(FieldMixin, Field):
    low_cardinality_allowed = False
    nullable_allowed = False
    empty_strings_allowed = False
    default_error_messages = {
        "item_invalid": _("Item %(nth)s in the array did not validate:"),
        "value_length_mismatch": _("Value length does not match tuple length."),
    }

    def __init__(self, base_fields, **kwargs):
        if isinstance(base_fields, collections.abc.Iterator):
            base_fields = list(base_fields)
        self.base_fields = base_fields
        super().__init__(**kwargs)

    def get_internal_type(self):
        return "TupleField"

    @property
    def model(self):
        try:
            return self.__dict__["model"]
        except KeyError:
            raise AttributeError("'%s' object has no attribute 'model'" % self.__class__.__name__)

    @model.setter
    def model(self, model):
        self.__dict__["model"] = model
        for field in self.base_fields:
            if isinstance(field, Field):
                field.model = model
            else:
                field[1].model = model

    @classmethod
    def _choices_is_value(cls, value):
        return isinstance(value, (list, tuple)) or super()._choices_is_value(value)

    def check(self, **kwargs):
        errors = super().check(**kwargs)
        if errors:
            return errors

        invalid_error = [
            checks.Error(
                "'base_fields' must be an iterable containing only(not both) "
                "field instance or (field name, field instance) tuples, "
                "field name must be valid python identifiers.",
                obj=self,
            )
        ]
        if not is_iterable(self.base_fields) or isinstance(self.base_fields, str):
            return invalid_error

        fields = []
        named_field_flags = []
        for index, field in enumerate(self.base_fields, start=1):
            if isinstance(field, Field):
                fields.append(field)
                named_field_flags.append(False)
            else:
                try:
                    name, field = field
                except (TypeError, ValueError):
                    return invalid_error
                if not isinstance(name, str) or not name.isidentifier() or not isinstance(field, Field):
                    return invalid_error
                fields.append((name, field))
                named_field_flags.append(True)

            if field.remote_field:
                return [
                    checks.Error(
                        "Field %ss cannot be a related field." % index,
                        obj=self,
                    )
                ]
            if hasattr(field, "low_cardinality") and field.low_cardinality:
                # clickhouse_driver have bug when there is LowCardinality subtype inside Tuple.
                field.low_cardinality = False
            base_errors = field.check()
            if base_errors:
                messages = "\n    ".join("%s (%s)" % (error.msg, error.id) for error in base_errors)
                return [
                    checks.Error(
                        "Field %ss has errors:\n    %s" % (index, messages),
                        obj=self,
                    )
                ]
        if not fields:
            return [
                checks.Error(
                    "'base_fields' must not be empty.",
                    obj=self,
                )
            ]

        if all(named_field_flags):
            name = self.name
            if name:
                name = name.capitalize()
            else:
                name = "Tuple"
            self.container_class = collections.namedtuple(name, (fn for fn, _ in fields))
            self.is_named_tuple = True
        elif not any(named_field_flags):
            self.container_class = tuple
            self.is_named_tuple = False
        else:
            return invalid_error
        self.base_fields = tuple(fields)
        if self.is_named_tuple:
            self._base_fields = tuple(f for _, f in self.base_fields)
        else:
            self._base_fields = self.base_fields
        # For performance, only add a from_db_value() method if any base field
        # implements it.
        if any(hasattr(field, "from_db_value") for field in self._base_fields):
            self.from_db_value = self._from_db_value
        return []

    def set_attributes_from_name(self, name):
        super().set_attributes_from_name(name)
        for field in self._base_fields:
            field.set_attributes_from_name(name)

    @property
    def description(self):
        base_description = ", ".join(
            field.description for field in self._base_fields
        )
        return "Tuple of %s" % base_description

    def db_type(self, connection):
        base_type = ", ".join(
            "%s %s" % (field[0], field[1].db_type(connection))
            if self.is_named_tuple else field.db_type(connection)
            for field in self.base_fields
        )
        return "Tuple(%s)" % base_type

    def cast_db_type(self, connection):
        base_type = ", ".join(
            "%s %s" % (field[0], field[1].cast_db_type(connection))
            if self.is_named_tuple else field.cast_db_type(connection)
            for field in self.base_fields
        )
        return "Tuple(%s)" % base_type

    def get_placeholder(self, value, compiler, connection):
        return "%s::{}".format(self.db_type(connection))

    def call_base_fields(self, func_name, value, *args, **kwargs):
        if value is None:
            return value
        self._validate_length(value)
        values = []
        for i, field in zip(value, self._base_fields):
            values.append(getattr(field, func_name)(i, *args, **kwargs))
        return values

    def get_db_prep_value(self, value, connection, prepared=False):
        if isinstance(value, (list, tuple)):
            values = self.call_base_fields(
                "get_db_prep_value",
                value, connection, prepared=prepared
            )
            return tuple(values)
        return value

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if path == "clickhouse_backend.models.fields.tuple.TupleField":
            path = "clickhouse_backend.models.Tuple"
        kwargs.update({
            "base_fields": copy.deepcopy(self.base_fields),
        })
        return name, path, args, kwargs

    def to_python(self, value):
        if isinstance(value, str):
            # Assume we're deserializing
            vals = json.loads(value)
            values = self.call_base_fields("to_python", vals)
            return self.container_class(*values)
        return value

    def _from_db_value(self, value, expression, connection):
        if value is None:
            return value
        self._validate_length(value)
        values = []
        for i, field in zip(value, self._base_fields):
            if hasattr(field, "from_db_value"):
                values.append(field.from_db_value(i, expression, connection))
            else:
                values.append(i)
        return tuple(values)

    def value_to_string(self, obj):
        values = []
        vals = self.value_from_object(obj)
        self._validate_length(vals)

        for val, field in zip(vals, self._base_fields):
            if val is None:
                values.append(None)
            else:
                obj = AttributeSetter(field.attname, val)
                values.append(field.value_to_string(obj))
        return json.dumps(values)

    @cached_property
    def base_filed_map(self):
        if self.is_named_tuple:
            return dict(self.base_fields)
        else:
            return dict(enumerate(self.base_fields))

    def get_transform(self, name):
        transform = super().get_transform(name)
        if transform:
            return transform
        try:
            name = int(name)
        except ValueError:
            field = self.base_filed_map[name]
        else:
            field = self.base_filed_map[name]
            name += 1  # Clickhouse uses 1-indexing
        return IndexTransformFactory(name, field)

    def _validate_length(self, values):
        if len(values) != len(self.base_fields):
            raise exceptions.ValidationError(
                code="value_length_mismatch",
                message=self.error_messages["value_length_mismatch"]
            )

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        self._validate_length(value)
        for index, (part, field) in enumerate(zip(value, self._base_fields)):
            try:
                field.validate(part, model_instance)
            except exceptions.ValidationError as error:
                raise prefix_validation_error(
                    error,
                    prefix=self.error_messages["item_invalid"],
                    code="item_invalid",
                    params={"nth": index + 1},
                )

    def run_validators(self, value):
        super().run_validators(value)
        self._validate_length(value)
        for index, (part, field) in enumerate(zip(value, self._base_fields)):
            try:
                field.run_validators(part)
            except exceptions.ValidationError as error:
                raise prefix_validation_error(
                    error,
                    prefix=self.error_messages["item_invalid"],
                    code="item_invalid",
                    params={"nth": index + 1},
                )


class TupleRHSMixin:
    def __init__(self, lhs, rhs):
        if isinstance(rhs, (tuple, list)):
            expressions = []
            for value in rhs:
                if not hasattr(value, "resolve_expression"):
                    field = lhs.output_field
                    value = Value(field.base_field.get_prep_value(value))
                expressions.append(value)
            rhs = Func(*expressions, function="tuple")
        super().__init__(lhs, rhs)

    def process_rhs(self, compiler, connection):
        rhs, rhs_params = super().process_rhs(compiler, connection)
        cast_type = self.lhs.output_field.cast_db_type(connection)
        return "%s::%s" % (rhs, cast_type), rhs_params


@TupleField.register_lookup
class TupleExact(TupleRHSMixin, lookups.Exact):
    pass


class IndexTransform(lookups.Transform):
    def __init__(self, index, base_field, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = index
        self.base_field = base_field

    def as_sql(self, compiler, connection):
        lhs, params = compiler.compile(self.lhs)
        return "%s.{}".format(self.index) % lhs, params

    @property
    def output_field(self):
        return self.base_field


class IndexTransformFactory:
    def __init__(self, index, base_field):
        self.index = index
        self.base_field = base_field

    def __call__(self, *args, **kwargs):
        return IndexTransform(self.index, self.base_field, *args, **kwargs)
