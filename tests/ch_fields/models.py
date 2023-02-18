from clickhouse_backend import models


class Foo(models.ClickhouseModel):
    a = models.UInt8Field()
    b = models.StringField(null=True)
    c = models.BoolField(low_cardinality=True)
    d = models.DateTimeField(null=True, low_cardinality=True)


class IntModel(models.ClickhouseModel):
    int8 = models.Int8Field(null=True, low_cardinality=True)
    uint8 = models.UInt8Field(null=True, low_cardinality=True)
    int16 = models.Int16Field(null=True, low_cardinality=True)
    uint16 = models.UInt16Field(null=True, low_cardinality=True)
    int32 = models.Int32Field(null=True, low_cardinality=True)
    uint32 = models.UInt32Field(null=True, low_cardinality=True)
    int64 = models.Int64Field(null=True, low_cardinality=True)
    uint64 = models.UInt64Field(null=True, low_cardinality=True)
    int128 = models.Int128Field(null=True, low_cardinality=True)
    uint128 = models.UInt128Field(null=True, low_cardinality=True)
    int256 = models.Int256Field(null=True, low_cardinality=True)
    uint256 = models.UInt256Field(null=True, low_cardinality=True)


class FloatModel(models.ClickhouseModel):
    float32 = models.Float32Field(null=True, low_cardinality=True)
    float64 = models.Float64Field(null=True, low_cardinality=True)


class DecimalModel(models.ClickhouseModel):
    decimal = models.DecimalField(max_digits=10, decimal_places=5)


class BoolModel(models.ClickhouseModel):
    boo = models.BoolField(null=True, low_cardinality=True)


class StringModel(models.ClickhouseModel):
    string = models.StringField(null=True, low_cardinality=True)


class FixedStringModel(models.ClickhouseModel):
    fixed_string = models.FixedStringField(max_bytes=10, null=True, low_cardinality=True)


class UUIDModel(models.ClickhouseModel):
    uuid = models.UUIDField(low_cardinality=True)


class DateModel(models.ClickhouseModel):
    date = models.DateField(low_cardinality=True)


class Date32Model(models.ClickhouseModel):
    date32 = models.Date32Field(null=True)


class DateTimeModel(models.ClickhouseModel):
    datetime = models.DateTimeField(null=True, low_cardinality=True)


class DateTime64Model(models.ClickhouseModel):
    datetime64 = models.DateTime64Field(null=True)


class EnumModel(models.ClickhouseModel):
    CHOICES = (("a", 1), ("b", 2), ("c", 3))

    enum = models.EnumField(null=True, choices=CHOICES)
    enum8 = models.EnumField(null=True, choices=CHOICES)
    enum16 = models.EnumField(null=True, choices=CHOICES)


class ArrayModel(models.ClickhouseModel):
    array = models.ArrayField(base_field=models.GenericIPAddressField())


class TupleModel(models.ClickhouseModel):
    tuple = models.TupleField(base_fields=[models.Int8Field(), models.StringField(), models.GenericIPAddressField])


class MapModel(models.ClickhouseModel):
    map = models.MapField(key_field=models.StringField(), value_field=models.GenericIPAddressField())


class IPv4Model(models.ClickhouseModel):
    ipv4 = models.IPv4Field(null=True, low_cardinality=True)


class IPv6Model(models.ClickhouseModel):
    ipv6 = models.IPv6Field(null=True, low_cardinality=True)


class IPModel(models.ClickhouseModel):
    ip = models.GenericIPAddressField(null=True, low_cardinality=True)
