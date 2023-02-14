from clickhouse_backend import models


class Foo(models.ClickhouseModel):
    a = models.UInt8Field(null=True, low_cardinality=True)
    b = models.StringField(null=True, low_cardinality=True)
