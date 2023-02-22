Fields
===

Clickhouse backend support django builtin fields and clickhouse specific fields.

**Note:** You should always use clickhouse specific fields in new projects.
Support for django built-in fields is only for compatibility with existing third-party apps.

**Note:** [ForeignKey](https://docs.djangoproject.com/en/4.1/ref/models/fields/#foreignkey), [ManyToManyField](https://docs.djangoproject.com/en/4.1/ref/models/fields/#manytomanyfield)
or even [OneToOneField](https://docs.djangoproject.com/en/4.1/ref/models/fields/#onetoonefield) could be used with clickhouse backend.
But no database level constraints will be added, so there could be some consistency problems.


Django fields
---

The following django fields are supported:

| Class                                               | DB Type     | Pythonic Type         | Comments                                                                             |
|-----------------------------------------------------|-------------|-----------------------|--------------------------------------------------------------------------------------|
| django.db.models.SmallAutoField                     | Int16       | int                   | No automatic value, must provide value yourself                                      |
| django.db.models.AutoField                          | Int32       | int                   | No automatic value, must provide value yourself                                      |
| django.db.models.BigAutoField                       | Int64       | int                   | `clickhouse.idworker.snowflake.SnowflakeIDWorker` will generate value automatically. |
| django.db.models.CharField                          | FixedString | str                   | Encoded as UTF-8 when written to ClickHouse                                          |
| django.db.models.TextField                          | String      | str                   | Encoded as UTF-8 when written to ClickHouse                                          |
| django.db.models.BinaryField                        | String      | bytes or str          | Encoded as UTF-8 when written to ClickHouse or raw bytes if not valid UTF-8.         |
| django.db.models.SlugField                          | String      |                       |                                                                                      |
| django.db.models.FileField                          | String      |                       |                                                                                      |
| django.db.models.FilePathField                      | String      |                       |                                                                                      |
| django.db.models.DateField                          | Date32      | datetime.date         | Range 1970-01-01 to 2105-12-31                                                       |
| django.db.models.DateTimeField                      | DateTime64  | datetime.datetime     | Minimal value is 1970-01-01 00:00:00; Timezone aware                                 |
| django.db.models.SmallIntegerField                  | Int16       | int                   | Range -32768 to 32767                                                                |
| django.db.models.IntegerField                       | Int32       | int                   | Range -2147483648 to 2147483647                                                      |
| django.db.models.BigIntegerField                    | Int64       | int                   | Range -9223372036854775808 to 9223372036854775807                                    |
| django.db.models.SmallIntegerField                  | UInt16      | int                   | Range 0 to 32767                                                                     |
| django.db.models.IntegerField                       | UInt32      | int                   | Range 0 to 2147483647                                                                |
| django.db.models.BigIntegerField                    | UInt64      | int                   | Range 0 to 9223372036854775807                                                       |
| django.db.models.FloatField                         | Float64     | float                 |                                                                                      |
| django.db.models.DecimalField                       | Decimal     | Decimal               | Pythonic values are rounded to fit the scale of the database field                   |
| django.db.models.UUIDField                          | UUID        | uuid.UUID             |                                                                                      |
| django.db.models.IPAddressField                     | IPv4        | ipaddress.IPv4Address |                                                                                      |
| django.db.models.BooleanField                       | Int8        |                       |                                                                                      |
| NullableField                                       | Nullable    |                       | When null=True                                                                       |

Clickhouse fields
---
If a clickhouse data type supports LowCardinality, there will be a low_cardinality parameter in the corresponding model field.

If a clickhouse data type does not support Nullable, an error will occur when performing django checks if you set null=True in model field.

Passing `null=True` will make a field [Nullable](https://clickhouse.com/docs/en/sql-reference/data-types/nullable/).

Passing `low_cardinality=True` will make a field [LowCardinality](https://clickhouse.com/docs/en/sql-reference/data-types/lowcardinality).


### [U]Int(8|16|32|64|128|256)

Fields importing path: `clickhouse_backend.models.[U]Int(8|16|32|64|128|256)Field`

For example, UInt8 type is imported from `clickhouse_backend.models.UInt8Field`

Both Nullable and LowCardinality are supported for all int types.

All UInt types will have correct range validators. For example, `clickhouse_backend.models.UInt16Field` have a range from 0 to 65535.
As a contrast, `django.db.models.SmallIntegerField` have a range from 0 to 32767, causing half range waisted.


### Float(32|64)

Fields importing path: `clickhouse_backend.models.Float(32|64)Field`

For example, Float32 type is imported from `clickhouse_backend.models.Float32Field`

Both Nullable and LowCardinality are supported for Float32Field and Float64Field.


### Decimal

Fields importing path: `clickhouse_backend.models.DecimalField`

Nullable is supported but LowCardinality is not supported for Decimal.


### Bool

Fields importing path: `clickhouse_backend.models.BoolField`

Both Nullable and LowCardinality are supported.


### String

Fields importing path: `clickhouse_backend.models.StringField`

Both Nullable and LowCardinality are supported.

Clickhouse String type is more like bytes type in python.
StringField support bytes or str type when assign value.
Python string will be UTF-8 encoded when stored in clickhouse.

**Note:** `max_length` will have odd behavior when you provide bytes type,
for example, if `max_length=4`, `'世界'` is a valid value,
but the corresponding encoded bytes `b'\xe4\xb8\x96\xe7\x95\x8c'` is an invalid value because it's length is 6.


### FixedString

Fields importing path: `clickhouse_backend.models.FixedStringField`

A `max_bytes` parameter is required as the bytes length of FixedString.

Both Nullable and LowCardinality are supported.

Clickhouse FixedString type is more like bytes type in python.
FixedStringField support bytes or str type when assign value.
Python string will be UTF-8 encoded when stored in clickhouse.

**Note:** `max_length` will have odd behavior when you provide bytes type,
for example, if `max_length=4`, `'世界'` is a valid value,
but the corresponding encoded bytes `b'\xe4\xb8\x96\xe7\x95\x8c'` is an invalid value because it's length is 6.


### UUID

Fields importing path: `clickhouse_backend.models.UUIDField`

Both Nullable and LowCardinality are supported.


### Date and Date32

Fields importing path: `clickhouse_backend.models.Date[32]Field`

[Dates query](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#dates) and [datetimes query](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#datetimes)
are supported by DateField and Date32Field.
All [date lookup](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#date) are supported by DateField and Date32Field.

Both Nullable and LowCardinality are supported.

But creating columns of type LowCardinality(DateTime) or LowCardinality(DateTime32) is prohibited by default due to expected negative impact on performance.
It can be enabled with the ["allow_suspicious_low_cardinality_types"](https://clickhouse.com/docs/en/operations/settings/settings/#allow_suspicious_low_cardinality_types) setting.

```python
DATABASES = {
    'default': {
        'ENGINE': 'clickhouse_backend.backend',
        'OPTIONS': {
            'settings': {
                'allow_suspicious_low_cardinality_types': 1,
            }
        }
    }
}
```

Clickhouse support integer or float when assign a Date or Date32 column.
But supporting integer or float may cause strange behavior,
as integer and float are always treated as unix timestamps,
clickhouse store them as date in the [server timezone](https://clickhouse.com/docs/en/operations/server-configuration-parameters/settings#server_configuration_parameters-timezone), which may not be what you want.
So this feature is not implemented currently.


**Note:**

Due to a [bug](https://github.com/mymarilyn/clickhouse-driver/issues/363) of clickhouse-driver 0.2.5,
when set `null=True` and `low_cardinality=True` at the same time to DateField or Date32Field,
an exception will be raised when inserting a row.
The same bug also exists in UUIDField.


### DateTime and DateTime64

Fields importing path: `clickhouse_backend.models.DateTime[64]Field`

DateTime64Field have a [`precision`](https://clickhouse.com/docs/en/sql-reference/data-types/datetime64) parameter which default to 6.

[Dates query](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#dates) and [datetimes query](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#datetimes)
are supported by DateTimeField and DateTime64Field.

All [date lookup](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#date) are supported by DateTimeField and DateTime64Field.

Both Nullable and LowCardinality are supported by DateTime.
But LowCardinality is not supported by DateTime64.

Clickhouse support integer or float when assign a DateTime or DateTime64 column.
This feature is also implemented by clickhouse backend.

Float value is treated as unix timestamp both for DateTime and DateTime64.

Int value is also treated as unix timestamp for DateTime.

But meaning of int value depending on the precision of DateTime64.
For example, `DateTime64(3)` treats int vale as milliseconds for unix epoch.
