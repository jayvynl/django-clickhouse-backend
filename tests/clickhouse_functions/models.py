"""
Tests for Function expressions.
"""
from clickhouse_backend import models


class Author(models.ClickhouseModel):
    name = models.StringField(max_length=50)
    alias = models.StringField(max_length=50, null=True, blank=True)
    goes_by = models.StringField(max_length=50, null=True, blank=True)
    birthday = models.DateTime64Field(null=True)
    age = models.UInt16Field(default=30)
