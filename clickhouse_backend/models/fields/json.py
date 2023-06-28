from django.db.models.fields import json

from clickhouse_backend.driver import JSON
from .base import FieldMixin

__all__ = ["JSONField"]


class JSONField(FieldMixin, json.JSONField):
    nullable_allowed = False

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if path.startswith("clickhouse_backend.models.json"):
            path = path.replace("clickhouse_backend.models.json", "clickhouse_backend.models")
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        return value

    def get_db_prep_save(self, value, connection):
        value = super().get_db_prep_save(value, connection)
        if isinstance(value, JSON):
            value = value.value
        return value
