from clickhouse_backend.models import fields

from .base import Func

__all__ = [
    "currentDatabase",
    "hostName",
]


class currentDatabase(Func):
    arity = 0
    output_field = fields.StringField()


class hostName(Func):
    arity = 0
    output_field = fields.StringField()
