from clickhouse_backend import models
from clickhouse_backend import compat


class ColumnTypes(models.ClickhouseModel):
    int8 = models.Int8Field()
    uint8 = models.UInt8Field()
    int16 = models.Int16Field()
    uint16 = models.UInt16Field()
    int32 = models.Int32Field()
    uint32 = models.UInt32Field()
    int64 = models.Int64Field()
    uint64 = models.UInt64Field()
    int128 = models.Int128Field()
    uint128 = models.UInt128Field()
    int256 = models.Int256Field()
    uint256 = models.UInt256Field()
    float32 = models.Float32Field()
    float64 = models.Float64Field()
    decimal = models.DecimalField(max_digits=38, decimal_places=19)
    bool_field = models.BoolField()
    string = models.StringField()
    fixed_string = models.FixedStringField(max_bytes=10)
    uuid = models.UUIDField()
    date = models.DateField()
    date32 = models.Date32Field()
    datetime = models.DateTimeField()
    datetime64 = models.DateTime64Field()
    enum = models.EnumField(choices=[(1, "我"), (2, b"\x90")])
    enum8 = models.Enum8Field(choices=[(1, "我"), (2, b"\x90")])
    enum16 = models.Enum16Field(choices=[(1, "我"), (2, b"\x90")])
    ipv4 = models.IPv4Field()
    ipv6 = models.IPv6Field()
    generic_ip = models.GenericIPAddressField()
    array = models.ArrayField(models.Int8Field())
    tuple_field = models.TupleField([models.Int8Field(), models.StringField()])
    map_field = models.MapField(
        models.FixedStringField(low_cardinality=True, max_bytes=10),
        models.TupleField(
            [
                models.Int8Field(low_cardinality=True, null=True, blank=True),
                models.ArrayField(
                    models.Int8Field(low_cardinality=True, null=True, blank=True)
                ),
            ]
        ),
    )


if compat.dj_ge42:

    class DbComment(models.ClickhouseModel):
        rank = models.Int32Field(db_comment="'Rank' column comment")

        class Meta:
            db_table_comment = "Custom table comment"
