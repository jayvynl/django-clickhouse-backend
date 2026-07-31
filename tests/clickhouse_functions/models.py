"""
Tests for Function expressions.
"""

from clickhouse_backend import models


class Author(models.ClickhouseModel):
    name = models.StringField(max_length=50)
    alias = models.StringField(max_length=50, null=True, blank=True)
    goes_by = models.StringField(max_length=50, null=True, blank=True)
    birthday = models.DateTime64Field(null=True)
    # The truncations behave differently for arguments without a time of day.
    birth_date = models.DateField(null=True)
    birth_date32 = models.Date32Field(null=True)
    age = models.UInt16Field(default=30)
    ulid = models.FixedStringField(max_bytes=26, null=True, blank=True)
