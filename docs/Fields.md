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

| Class                                               | DB Type     | Pythonic Type         | Comments                                                                                                                                    |
|-----------------------------------------------------|-------------|-----------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| django.db.models.SmallAutoField                     | Int16       | int                   | No automatic value, must provide value yourself                                                                                             |
| django.db.models.AutoField                          | Int32       | int                   | No automatic value, must provide value yourself                                                                                             |
| django.db.models.BigAutoField                       | Int64       | int                   | `clickhouse.idworker.snowflake.SnowflakeIDWorker` will generate value automatically.                                                        |
| django.db.models.CharField                          | FixedString | str                   | Encoded as UTF-8 when written to ClickHouse                                                                                                 |
| django.db.models.TextField                          | String      | str                   | Encoded as UTF-8 when written to ClickHouse                                                                                                 |
| django.db.models.BinaryField                        | String      | bytes or str          |                                                                                                                                             |
| django.db.models.SlugField                          | String      |                       |                                                                                                                                             |
| django.db.models.FileField                          | String      |                       |                                                                                                                                             |
| django.db.models.FilePathField                      | String      |                       |                                                                                                                                             |
| django.db.models.DateField                          | Date32      | datetime.date         | Range 1900-01-01 to 2299-12-31; Date exceed this range will be stored as min value or max value.                                            |
| django.db.models.DateTimeField                      | DateTime64  | datetime.datetime     | Range 1900-01-01 00:00:00, 2299-12-31 23:59:59.999999; Timezone aware; Datetime exceed this range will be stored as min value or max value. |
| django.db.models.SmallIntegerField                  | Int16       | int                   | Range -32768 to 32767                                                                                                                       |
| django.db.models.IntegerField                       | Int32       | int                   | Range -2147483648 to 2147483647                                                                                                             |
| django.db.models.BigIntegerField                    | Int64       | int                   | Range -9223372036854775808 to 9223372036854775807                                                                                           |
| django.db.models.SmallIntegerField                  | UInt16      | int                   | Range 0 to 32767                                                                                                                            |
| django.db.models.IntegerField                       | UInt32      | int                   | Range 0 to 2147483647                                                                                                                       |
| django.db.models.BigIntegerField                    | UInt64      | int                   | Range 0 to 9223372036854775807                                                                                                              |
| django.db.models.FloatField                         | Float64     | float                 |                                                                                                                                             |
| django.db.models.DecimalField                       | Decimal     | Decimal               | Pythonic values are rounded to fit the scale of the database field                                                                          |
| django.db.models.UUIDField                          | UUID        | uuid.UUID             |                                                                                                                                             |
| django.db.models.IPAddressField                     | IPv4        | ipaddress.IPv4Address |                                                                                                                                             |
| django.db.models.BooleanField                       | Bool        |                       |                                                                                                                                             |
| NullableField                                       | Nullable    |                       | When null=True                                                                                                                              |

Clickhouse fields
---
If a clickhouse data type supports LowCardinality, there will be a `low_cardinality` parameter in the corresponding model field.

If a clickhouse data type does not support Nullable, an error will occur when performing django checks if you set `null=True` in model field.

Passing `null=True` will make a field [Nullable](https://clickhouse.com/docs/en/sql-reference/data-types/nullable/).

Passing `low_cardinality=True` will make a field [LowCardinality](https://clickhouse.com/docs/en/sql-reference/data-types/lowcardinality).

Name of field class is always concat clickhouse date type name to `Field`.
For example, [DateTime64](https://clickhouse.com/docs/en/sql-reference/data-types/datetime64) field is named as `DateTime64Field`.
All clickhouse fields are imported from `clickhouse_backend.models`

Supported date types are:

- Float32/Float64
- Int8/Int16/Int32/Int64/Int128/Int256
- UInt8/UInt16/UInt32/UInt64/UInt128/UInt256
- Date/Date32
- DateTime/DateTime64
- String/FixedString(N)
- Enum/Enum8/Enum16
- Array(T)
- Bool
- UUID
- Decimal
- IPv4/IPv6
- LowCardinality(T)
- Tuple(T1, T2, ...)
- Map(key, value)


### [U]Int(8|16|32|64|128|256)

Fields importing path: `clickhouse_backend.models.[U]Int(8|16|32|64|128|256)Field`

For example, UInt8 type is imported from `clickhouse_backend.models.UInt8Field`

Both Nullable and LowCardinality are supported for all int types.

All UInt types will have correct range validators.

For example, `clickhouse_backend.models.UInt16Field` have a range from 0 to 65535.
As a contrast, `django.db.models.SmallIntegerField` have a range from 0 to 32767, causing half range waisted.


### Float(32|64)

Fields importing path: `clickhouse_backend.models.Float(32|64)Field`

For example, Float32 type is imported from `clickhouse_backend.models.Float32Field`

Both Nullable and LowCardinality are supported for Float32Field and Float64Field.


### Decimal

Field importing path: `clickhouse_backend.models.DecimalField`

Nullable is supported but LowCardinality is not supported.


### Bool

Field importing path: `clickhouse_backend.models.BoolField`

Both Nullable and LowCardinality are supported.


### String

Field importing path: `clickhouse_backend.models.StringField`

Both Nullable and LowCardinality are supported.

Clickhouse String type is more like bytes type in python.
StringField support bytes or str type when assign value.
Python string will be UTF-8 encoded when stored in clickhouse.

**Note:** `max_length` will have odd behavior when you provide bytes type.
For example, if `max_length=4`, `'世界'` is a valid value,
but the corresponding encoded bytes `b'\xe4\xb8\x96\xe7\x95\x8c'` is an invalid value because it's length is 6.


### FixedString

Field importing path: `clickhouse_backend.models.FixedStringField`

A `max_bytes` parameter is required as the bytes length of FixedString.

Both Nullable and LowCardinality are supported.

Clickhouse FixedString type is more like bytes type in python.
FixedStringField support bytes or str type when assign value.
Python string will be UTF-8 encoded when stored in clickhouse.

**Note:** `max_length` will have odd behavior when you provide bytes type.
For example, if `max_length=4`, `'世界'` is a valid value,
but the corresponding encoded bytes `b'\xe4\xb8\x96\xe7\x95\x8c'` is an invalid value because it's length is 6.


### UUID

Field importing path: `clickhouse_backend.models.UUIDField`

Both Nullable and LowCardinality are supported.

But creating columns of type LowCardinality(Nullable(UUID)) is prohibited by default due to expected negative impact on performance. It can be enabled with the "allow_suspicious_low_cardinality_types" setting.

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

**Note:**

Due to a [bug](https://github.com/mymarilyn/clickhouse-driver/issues/363) of clickhouse-driver 0.2.5,
when set `null=True` and `low_cardinality=True` at the same time to UUIDField, an exception will be raised when inserting a row.

The same bug also exists in DateField and Date32Field.


### Date and Date32

Fields importing path: `clickhouse_backend.models.Date[32]Field`

[Dates query](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#dates) is supported by DateField and Date32Field.

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
as integer and float are treated as unix timestamps,
clickhouse store them as date in the [server timezone](https://clickhouse.com/docs/en/operations/server-configuration-parameters/settings#server_configuration_parameters-timezone), which may not be what you want.
So this feature is not implemented currently.


**Note:**

Due to a [bug](https://github.com/mymarilyn/clickhouse-driver/issues/363) of clickhouse-driver 0.2.5,
when set `null=True` and `low_cardinality=True` at the same time to DateField or Date32Field, an exception will be raised when inserting a row.

The same bug also exists in UUIDField.


### DateTime and DateTime64

Fields importing path: `clickhouse_backend.models.DateTime[64]Field`

DateTime64Field have a [`precision`](https://clickhouse.com/docs/en/sql-reference/data-types/datetime64) parameter which default to 6.

[Dates query](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#dates) and [datetimes query](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#datetimes)
are supported by DateTimeField and DateTime64Field.

All [date lookup](https://docs.djangoproject.com/en/4.1/ref/models/querysets/#date) are supported by DateTimeField and DateTime64Field.

Both Nullable and LowCardinality are supported by DateTime. But LowCardinality is not supported by DateTime64.

Clickhouse support integer or float when assign a DateTime or DateTime64 column. This feature is also implemented by clickhouse backend.

Float value is treated as unix timestamp in DateTime and DateTime64.

Int value is treated as unix timestamp in DateTime.

But meaning of int value depending on the precision of DateTime64.
For example, `DateTime64(3)` treats int vale as milliseconds from unix epoch,
`DateTime64(6)` treats int vale as microseconds from unix epoch.


### Enum[8|16]

Fields importing path: `clickhouse_backend.models.Enum[8|16]Field`

Nullable is supported but LowCardinality is not supported.

The `choices` parameter is required when define an Enum field,
and `choices` must be an iterable containing only (int, str) tuples.
and int in `choices` must not exceed range.
EnumField and Enum16Field range from -32768 to 32767, Enum8Field range from -128 to 127.

Use `return_int` (default `True`) to control whether to get an int or str value when querying from the database.

If an invalid choices is provided, error is raised when execute django checks.

When assign value to an EnumField, both choice value and choice label are supported.

When query from database, str value is returned.

Usage example:

```python
from clickhouse_backend import models
from django.db.models import IntegerChoices

class EnumTest(models.ClickhouseModel):
    class Fruit(IntegerChoices):
        banana = 1, 'banana'
        pear = 2, 'pear'
        apple = 3, 'apple'

    enum = models.EnumField(choices=Fruit.choices, return_int=False)
    
    def __str__(self):
        return str(self.enum)


EnumTest.objects.bulk_create([
    EnumTest(enum=1),
    EnumTest(enum='pear'),
    EnumTest(enum=b'apple')
])
# [<EnumTest: 1>, <EnumTest: pear>, <EnumTest: b'apple'>]

EnumTest.objects.filter(enum=1)
# <QuerySet [<EnumTest: banana>]>
EnumTest.objects.filter(enum='pear')
# <QuerySet [<EnumTest: pear>]>
EnumTest.objects.filter(enum=b'apple')
# <QuerySet [<EnumTest: apple>]>
EnumTest.objects.filter(enum__gt=1)
# <QuerySet [<EnumTest: pear>, <EnumTest: apple>]>
EnumTest.objects.filter(enum__gte='pear')
# <QuerySet [<EnumTest: pear>, <EnumTest: apple>]>
EnumTest.objects.filter(enum__contains='ana')
# <QuerySet [<EnumTest: banana>]>
```

### IPv4 IPv6

Fields importing path: `clickhouse_backend.models.IPv(4|6)Field`

Both Nullable and LowCardinality are supported.

IPv4Field supported `ipaddress.IPv4Address` or str when assign value.
IPv6Field supported `ipaddress.IPv4Address`, `ipaddress.IPv6Address` or str when assign value.

When query from the database, str is returned.

### GenericIPAddressField

The GenericIPAddressField exists to provide same behavior as django builtin GenericIPAddressField.

In the database, GenericIPAddressField is stored as IPv6. So it behave mostly like IPv6Field
except that GenericIPAddressField will try to return ipv4 mapped address when `unpack_ipv4=True`.

Usage Example:

```python
from clickhouse_backend import models

class IPTest(models.ClickhouseModel):
    ipv4 = models.IPv4Field()
    ipv6 = models.IPv6Field()
    ip = models.GenericIPAddressField(unpack_ipv4=True)

    def __str__(self):
        return str(self.ip)

IPTest.objects.create([
    IPTest(ipv4='1.2.3.4',ipv6='1.2.3.4',ip='1.2.3.4'),
    IPTest(ipv4='2.3.4.5',ipv6='2.3.4.5',ip='2.3.4.5'),
])
# [<IPTest: 1.2.3.4>, <IPTest: 2.3.4.5>]
IPTest.objects.filter(ipv4='1.2.3.4')
# <QuerySet [<IPTest: 1.2.3.4>]>
IPTest.objects.filter(ipv6='1.2.3.4')
# <QuerySet [<IPTest: 1.2.3.4>]>
IPTest.objects.filter(ip='1.2.3.4')
# <QuerySet [<IPTest: 1.2.3.4>]>

IPTest.objects.filter(ipv6__gt='1.2.3.4')
# <QuerySet [<IPTest: 2.3.4.5>]>

ip = IPTest.objects.get(ipv6__contains='4.5')
ip.ipv4, ip.ipv6, ip.ip
# ('2.3.4.5', '::ffff:203:405', '2.3.4.5')
```


### Array

Field importing path: `clickhouse_backend.models.ArrayField`

Neither Nullable nor LowCardinality is supported.

A position `base_field` parameter is required when using ArrayField. The base field can be any model field instance
including ArrayField, TupleField and MapField.

An optional `size` parameter can be provided to limit length of array value.

#### Lookups

```python
from clickhouse_backend import models

class NestedArrayModel(models.ClickhouseModel):
    array = models.ArrayField(
        base_field=models.ArrayField(
            base_field=models.ArrayField(
                models.UInt32Field()
            )
        )
    )

NestedArrayModel.objects.create(
    array=[
        [[12, 13, 0, 1], [12]],
        [[12, 13, 0, 1], [12], [13, 14]]
    ]
)
```

##### contains

Contains checks whether one array is a subset of another.

```python
NestedArrayModel.objects.filter(array__contains=[[[12, 13, 0, 1], [12]]]).exists()
# True
```

##### contained_by

Contained by is the reverse lookup of contains

```python
NestedArrayModel.objects.filter(array__contained_by=[
    [[12, 13, 0, 1], [12]],
    [[12, 13, 0, 1], [12], [13, 14]],
    [[1]]
]).exists()
# True
```

##### exact

Exact lookup is also supported.

```python
NestedArrayModel.objects.filter(
    array=[
        [[12, 13, 0, 1], [12]],
        [[12, 13, 0, 1], [12], [13, 14]]
    ]
).exists()
# True
```

##### overlap

Overlap checks whether two arrays have intersection by some elements.

```python
NestedArrayModel.objects.filter(array__overlap=[
    [[12, 13, 0, 1], [12]],
    [[1]]
]).exists()
# True
```

##### any

Any checks whether one array has the specific element.

```python
NestedArrayModel.objects.filter(array__any=[[12, 13, 0, 1], [12]]).exists()
# True
```

##### len

Returns the number of items in the array.

```python
NestedArrayModel.objects.filter(array__len=2).exists()
# True
```

##### index

Returns element by index.

```python
NestedArrayModel.objects.filter(array__1=[[12, 13, 0, 1], [12], [13, 14]]).exists()
# True
NestedArrayModel.objects.filter(array__1__2=[13, 14]).exists()
# True
NestedArrayModel.objects.filter(array__1__2__0=13).exists()
# True
```

##### slice

Returns elements by range.

```python
NestedArrayModel.objects.filter(array__1_2=[[[12, 13, 0, 1], [12], [13, 14]]]).exists()
# True
NestedArrayModel.objects.filter(array__1__0__0_2=[12, 13]).exists()
# True
```


### Tuple

Field importing path: `clickhouse_backend.models.TupleField`

Neither Nullable nor LowCardinality is supported.

A position `base_fields` parameter is required when using TupleField.
`base_fields` must be an iterable containing only(not both) field instances or (field name, field instance) tuples, and field name must be valid python identifier.

The base field can be any model field instance including ArrayField, TupleField and MapField.

When query from the database, TupleFile get tuple or named tuple.

Usage example:

```python
from clickhouse_backend import models

class TupleModel(models.ClickhouseModel):
    tuple = models.TupleField(
        base_fields=[
            models.Int8Field(),
            models.StringField(),
            models.GenericIPAddressField(unpack_ipv4=True)
        ]
    )


class NamedTupleModel(models.ClickhouseModel):
    tuple = models.TupleField(base_fields=[
        ("int", models.Int8Field()),
        ("str", models.StringField()),
        ("ip", models.GenericIPAddressField(unpack_ipv4=True))
    ])

v = [100, "test", "::ffff:3.4.5.6"]
TupleModel.objects.create(tuple=v)
NamedTupleModel.objects.create(tuple=v)

TupleModel.objects.get().tuple
# (100, 'test', '3.4.5.6')
NamedTupleModel.objects.get().tuple
# Tuple(int=100, str='test', ip='3.4.5.6')

# index lookup
TupleModel.objects.filter(tuple__1="test").exists()
# True
NamedTupleModel.objects.filter(tuple__str="test").exists()
# True
NamedTupleModel.objects.filter(tuple__ip__startswith="3.4").exists()
# True
```


### Map

Field importing path: `clickhouse_backend.models.MapField`

Neither Nullable nor LowCardinality is supported.

Position `key_fields` and `value_field` parameter are required when using MapField.

The value field can be any model field instance including ArrayField, TupleField and MapField.

Valid key fields are:

- Int8Field
- Int16Field
- Int32Field
- Int64Field
- Int128Field
- Int256Field
- UInt8Field
- UInt16Field
- UInt32Field
- UInt64Field
- UInt128Field
- UInt256Field
- BooleanField
- StringField
- FixedStringField
- UUIDField
- DateField
- Date32Field
- DateTimeField
- DateTime64Field
- EnumField
- Enum8Field
- Enum16Field
- IPv4Field
- IPv6Field
- GenericIPAddressField


When query from the database, MapFile get dict.


#### Lookups

```python
from clickhouse_backend import models

class MapModel(models.ClickhouseModel):
    map = models.MapField(
        models.StringField(low_cardinality=True),
        models.GenericIPAddressField(unpack_ipv4=True)
    )

MapModel.objects.create(
    map={
          "baidu": "39.156.66.10",
          "bing.com": "13.107.21.200",
          "google.com": "172.217.163.46"
      }
)
```

##### has_key

Test whether a map value contains the key.

```python
MapModel.objects.filter(map__has_key="baidu").exists()
# True
```

##### len

Return elements number in the map.

```python
MapModel.objects.values('map__len')
# <QuerySet [{'map__len': 3}]>
```

##### keys

Return map keys.

```python
MapModel.objects.values('map__keys')
# <QuerySet [{'map__keys': ['baidu', 'bing.com', 'google.com']}]>
```

##### values

Return map values.

```python
MapModel.objects.values('map__values')
# <QuerySet [{'map__values': ['39.156.66.10', '13.107.21.200', '172.217.163.46']}]>
```

##### key

Get the value of specific key.

```python
MapModel.objects.values('map__baidu')
# <QuerySet [{'map__baidu': '39.156.66.10'}]>

# If the map key is conflict with other lookup names
# or if the map key contains spaces or punctuations.
# An explict transform can be used.
from clickhouse_backend import models
from clickhouse_backend.models.fields.map import KeyTransform

MapModel.objects.annotate(
    value=KeyTransform("len", models.StringField(), models.GenericIPAddressField(), "map")
).values('value')
# here return a default empty value of IPv6
# <QuerySet [{'value': '::'}]>
MapModel.objects.annotate(
    value=KeyTransform("bing.com", models.StringField(), models.GenericIPAddressField(), "map")
).values('value')
# <QuerySet [{'value': '::ffff:d6b:15c8'}]>
```
