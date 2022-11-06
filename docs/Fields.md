Fields
===

The following field types are supported:

| Class                                               | DB Type      | Pythonic Type         | Comments                                                                             |
|-----------------------------------------------------|--------------|-----------------------|--------------------------------------------------------------------------------------|
| django.db.models.SmallAutoField                     | Int16        | int                   | No automatic value, must provide value yourself                                      |
| django.db.models.AutoField                          | Int32        | int                   | No automatic value, must provide value yourself                                      |
| django.db.models.BigAutoField                       | Int64        | int                   | `clickhouse.idworker.snowflake.SnowflakeIDWorker` will generate value automatically. |
| django.db.models.CharField                          | FixedString  | str                   | Encoded as UTF-8 when written to ClickHouse                                          |
| django.db.models.TextField                          | String       | str                   | Encoded as UTF-8 when written to ClickHouse                                          |
| django.db.models.BinaryField                        | String       | bytes or str          | Encoded as UTF-8 when written to ClickHouse or raw bytes if not valid UTF-8.         |
| django.db.models.SlugField                          | String       |                       |                                                                                      |
| django.db.models.FileField                          | String       |                       |                                                                                      |
| django.db.models.FilePathField                      | String       |                       |                                                                                      |
| django.db.models.DateField                          | Date32       | datetime.date         | Range 1970-01-01 to 2105-12-31                                                       |
| django.db.models.DateTimeField                      | DateTime64   | datetime.datetime     | Minimal value is 1970-01-01 00:00:00; Timezone aware                                 |
| django.db.models.SmallIntegerField                  | Int16        | int                   | Range -32768 to 32767                                                                |
| django.db.models.IntegerField                       | Int32        | int                   | Range -2147483648 to 2147483647                                                      |
| django.db.models.BigIntegerField                    | Int64        | int                   | Range -9223372036854775808 to 9223372036854775807                                    |
| clickhouse_backend.models.PositiveSmallIntegerField | UInt16       | int                   | Range 0 to 65535                                                                     |
| clickhouse_backend.models.PositiveIntegerField      | UInt32       | int                   | Range 0 to 4294967295                                                                |
| clickhouse_backend.models.PositiveBigIntegerField   | UInt64       | int                   | Range 0 to 18446744073709551615                                                      |
| django.db.models.FloatField                         | Float64      | float                 |                                                                                      |
| django.db.models.DecimalField                       | Decimal      | Decimal               | Pythonic values are rounded to fit the scale of the database field                   |
| django.db.models.UUIDField                          | UUID         | uuid.UUID             |                                                                                      |
| clickhouse_backend.models.GenericIPAddressField     | IPv4 or IPv6 | str                   | IPv4 when protocol='ipv4' else IPv6                                                  |
| django.db.models.IPAddressField                     | IPv4         | ipaddress.IPv4Address |                                                                                      |
| django.db.models.BooleanField                       | Int8         |                       |                                                                                      |
| NullableField                                       | Nullable     |                       | When null=True                                                                       |
