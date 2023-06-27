from django.db.models.fields import json

from .base import FieldMixin

__all__ = ["JSONField"]


class JSONField(FieldMixin, json.JSONField):
    nullable_allowed = False

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if path.startswith("clickhouse_backend.models.json"):
            path = path.replace("clickhouse_backend.models.json", "clickhouse_backend.models")
        return name, path, args, kwargs
