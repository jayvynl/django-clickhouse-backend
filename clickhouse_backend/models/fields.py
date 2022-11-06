import ipaddress

from django.core import validators
from django.db.models import fields
from django.utils.functional import cached_property

from clickhouse_backend.backend.operations import DatabaseOperations

__all__ = [
    "GenericIPAddressField",
    "PositiveSmallIntegerField", "PositiveIntegerField", "PositiveBigIntegerField",
]


class DeconstructMixin:
    def deconstruct(self):
        path, name, args, kwargs = super().deconstruct()
        if name.startswith("clickhouse_backend.models.fields"):
            name = name.replace("clickhouse_backend.models.fields", "clickhouse_backend.models")
        return path, name, args, kwargs


class GenericIPAddressField(DeconstructMixin, fields.GenericIPAddressField):
    def db_type(self, connection):
        if self.protocol.lower() == "ipv4":
            return "IPv4"
        else:
            return "IPv6"

    def get_db_prep_value(self, value, connection, prepared=False):
        if not prepared:
            value = self.get_prep_value(value)
        if value is None:
            return value
        try:
            value = ipaddress.ip_address(value)
        except ValueError:
            pass
        else:
            if isinstance(value, ipaddress.IPv4Address) and self.protocol.lower() in ["both", "ipv6"]:
                value = ipaddress.IPv6Address("::ffff:%s" % value)
        return value

    def get_prep_value(self, value):
        if value is None:
            return None
        value = str(value)
        if value and ":" in value:
            try:
                return fields.clean_ipv6_address(value, self.unpack_ipv4)
            except fields.exceptions.ValidationError:
                pass
        return value


class PositiveIntegerFieldMixin(DeconstructMixin):
    """
    Make positive integer have correct limitation corresponding to clickhouse uint type.
    """
    @cached_property
    def validators(self):
        validators_ = [*self.default_validators, *self._validators]
        internal_type = self.get_internal_type()
        min_value, max_value = DatabaseOperations.integer_field_ranges[internal_type]
        if min_value is not None and not any(
            (
                isinstance(validator, validators.MinValueValidator) and (
                    validator.limit_value()
                    if callable(validator.limit_value)
                    else validator.limit_value
                ) >= min_value
            ) for validator in validators_
        ):
            validators_.append(validators.MinValueValidator(min_value))
        if max_value is not None and not any(
            (
                isinstance(validator, validators.MaxValueValidator) and (
                    validator.limit_value()
                    if callable(validator.limit_value)
                    else validator.limit_value
                ) <= max_value
            ) for validator in validators_
        ):
            validators_.append(validators.MaxValueValidator(max_value))
        return validators_


class PositiveSmallIntegerField(
    PositiveIntegerFieldMixin,
    fields.PositiveSmallIntegerField
):
    pass


class PositiveIntegerField(
    PositiveIntegerFieldMixin,
    fields.PositiveIntegerField
):
    pass


class PositiveBigIntegerField(
    PositiveIntegerFieldMixin,
    fields.PositiveBigIntegerField
):
    pass
