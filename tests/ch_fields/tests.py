from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import F
from django.db.models.functions import Upper
from django.test import TestCase
from django.utils import timezone

from clickhouse_backend import models
from .models import (
    Foo,
    IntModel,
    FloatModel,
    DecimalModel,
    BoolModel,
    StringModel,
    FixedStringModel,
    UUIDModel,
    DateModel,
    Date32Model,
    DateTimeModel,
    DateTime64Model,
    EnumModel,
    ArrayModel,
    MapModel,
    TupleModel,
    IPModel,
    IPv4Model,
    IPv6Model,
)


class BasicFieldTests(TestCase):
    def test_deconstruct(self):
        field = models.StringField(
            unique=True,
            db_index=True,
            unique_for_date=True,
            unique_for_month=True,
            unique_for_year=True,
            db_tablespace="a",
            db_collation="C"
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "clickhouse_backend.models.StringField")
        for key in [
            "unique",
            "db_index",
            "unique_for_date",
            "unique_for_month",
            "unique_for_year",
            "db_tablespace",
            "db_collation",
        ]:
            self.assertNotIn(key, kwargs)

    def test_deconstruct_low_cardinality(self):
        field = models.Int8Field(low_cardinality=False)
        name, path, args, kwargs = field.deconstruct()
        self.assertNotIn("low_cardinality", kwargs)

        field = models.Int8Field(low_cardinality=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertTrue(kwargs["low_cardinality"])

    def test_db_type(self):
        field = models.Int8Field()
        self.assertEqual(field.db_type(connection), "Int8")
        field = models.Int8Field(null=True)
        self.assertEqual(field.db_type(connection), "Nullable(Int8)")
        field = models.Int8Field(low_cardinality=True)
        self.assertEqual(field.db_type(connection), "LowCardinality(Int8)")
        field = models.Int8Field(null=True, low_cardinality=True)
        self.assertEqual(field.db_type(connection), "LowCardinality(Nullable(Int8))")

    def test_db_type_migration(self):
        with connection.cursor() as cursor:
            field_info_list = connection.introspection.get_table_description(
                cursor, Foo._meta.db_table
            )
            _, a, b, c, d = field_info_list
            self.assertEqual(a.type_code, "UInt8")
            self.assertEqual(b.type_code, "Nullable(String)")
            self.assertEqual(c.type_code, "LowCardinality(Bool)")
            self.assertEqual(d.type_code, "LowCardinality(Nullable(DateTime))")


class IntFieldTests(TestCase):
    int_field_classes = [
            models.Int8Field,
            models.UInt8Field,
            models.Int16Field,
            models.UInt16Field,
            models.Int32Field,
            models.UInt32Field,
            models.Int64Field,
            models.UInt64Field,
            models.Int128Field,
            models.UInt128Field,
            models.Int256Field,
            models.UInt256Field
        ]

    def test_deconstruct(self):
        for field_class in self.int_field_classes:
            for bo in [True, False]:
                field = field_class(null=bo, low_cardinality=bo)
                name, path, args, kwargs = field.deconstruct()
                self.assertEqual(path, f"clickhouse_backend.models.{field_class.__name__}")
                if bo:
                    self.assertTrue(kwargs["null"])
                    self.assertTrue(kwargs["low_cardinality"])
                else:
                    self.assertNotIn("null", kwargs)
                    self.assertNotIn("low_cardinality", kwargs)

    def test_validation(self):
        for field_class in self.int_field_classes:
            field = field_class()
            low, high = connection.ops.integer_field_range(field.get_internal_type())
            with self.assertRaises(ValidationError):
                field.clean(low - 1, None)
            with self.assertRaises(ValidationError):
                field.clean(high + 1, None)

    def test_value(self):
        v = 100
        o = IntModel(None, *(v for _ in range(12)))
        o.save()
        for field in IntModel._meta.fields:
            if not field.primary_key:
                self.assertEqual(field.value_from_object(o), v)
                setattr(o, field.attname, str(v + 1))
        o.save()
        o.refresh_from_db()
        for field in IntModel._meta.fields:
            if not field.primary_key:
                self.assertEqual(field.value_from_object(o), v + 1)

    def test_expression(self):
        o = IntModel.objects.create(int8=10)
        IntModel.objects.update(int8=F("int8") * Decimal("3.1"))
        o.refresh_from_db()
        self.assertEqual(o.int8, 31)

    def test_filter(self):
        IntModel.objects.create(int8=101)
        self.assertFalse(
            IntModel.objects.filter(int8__lt=99.9).exists()
        )
        self.assertTrue(
            IntModel.objects.filter(int8__gt="100").exists()
        )


class FloatFieldTests(TestCase):
    def test_value(self):
        v = 12345.0
        o = FloatModel.objects.create(float32=v, float64=v)
        o.refresh_from_db()
        self.assertEqual(o.float32, v)
        self.assertEqual(o.float64, v)

        o.float32 = str(v)
        o.float64 = str(v)
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.float32, v)
        self.assertEqual(o.float64, v)

        o.float32 = Decimal(str(v))
        o.float64 = Decimal(str(v))
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.float32, v)
        self.assertEqual(o.float64, v)

    def test_expression(self):
        o = FloatModel.objects.create(float32=100.0)
        FloatModel.objects.update(float32=F("float32") * Decimal("1.23"))
        o.refresh_from_db()
        self.assertEqual(o.float32, 123)

    def test_filter(self):
        FloatModel.objects.create(float64=123.456)
        self.assertFalse(
            FloatModel.objects.filter(float64__lt=100).exists()
        )
        self.assertTrue(
            FloatModel.objects.filter(float64__gt=Decimal("100")).exists()
        )


class DecimalFieldTests(TestCase):
    def test_disallow_low_cardinality(self):
        field = models.DecimalField(low_cardinality=True, max_digits=10, decimal_places=5, name='field')
        errors = field.check()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].msg, "LowCardinality is not supported by DecimalField.")

    def test_value(self):
        v = Decimal("12345.6789")
        o = DecimalModel.objects.create(decimal=v)
        o.refresh_from_db()
        self.assertEqual(o.decimal, v)

        o.decimal = str(v)
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.decimal, v)

        o.decimal = float(v)
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.decimal, v)

    def test_expression(self):
        o = DecimalModel.objects.create(decimal=Decimal("100.0"))
        DecimalModel.objects.update(decimal=F("decimal") * 1.23)
        o.refresh_from_db()
        self.assertEqual(o.decimal, 123)

    def test_filter(self):
        DecimalModel.objects.create(decimal=Decimal("123.456"))
        self.assertFalse(
            DecimalModel.objects.filter(decimal__lt=99.9).exists()
        )
        self.assertTrue(
            DecimalModel.objects.filter(decimal__gt=100).exists()
        )


class BoolFieldTests(TestCase):
    def test_value(self):
        o = BoolModel.objects.create(boo=True)
        self.assertIs(o.boo, True)

        o.boo = 0
        o.save()
        o.refresh_from_db()
        self.assertIs(o.boo, False)

        o.boo = 1
        o.save()
        o.refresh_from_db()
        self.assertIs(o.boo, True)

    def test_filter(self):
        BoolModel.objects.create(boo=True)
        self.assertFalse(
            BoolModel.objects.filter(boo=False).exists()
        )
        self.assertTrue(
            BoolModel.objects.filter(boo__iexact='true').exists()
        )


class StringFieldTests(TestCase):
    def test_value(self):
        o = StringModel.objects.create(string="Smile 😀")
        o.refresh_from_db()
        self.assertEqual(o.string, "Smile 😀")

        o.string = 1234
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.string, "1234")

        o.string = b"\xff\x00\xff\x00"
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.string, b"\xff\x00\xff\x00")

        o.string = b"\xe6\x88\x91\xe4\xbb\xac"
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.string, "我们")

    def test_expression(self):
        o = StringModel.objects.create(string="lower")
        StringModel.objects.update(string=Upper("string"))
        o.refresh_from_db()
        self.assertEqual(o.string, "LOWER")

    def test_filter(self):
        StringModel.objects.create(string="Quick fox!")
        self.assertFalse(
            StringModel.objects.filter(string=9).exists()
        )
        self.assertTrue(
            StringModel.objects.filter(string__istartswith="quick").exists()
        )


class FixedStringFieldTests(TestCase):
    def test_value(self):
        o = FixedStringModel.objects.create(fixed_string="Smile 😀")
        o.refresh_from_db()
        self.assertEqual(o.fixed_string, "Smile 😀")

        o.fixed_string = 1234
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.fixed_string, "1234")

        o.fixed_string = b"\xff\x00\xff\x00"
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.fixed_string, b"\xff\x00\xff\x00\x00\x00\x00\x00\x00\x00")

        o.fixed_string = b"\xe6\x88\x91\xe4\xbb\xac"
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.fixed_string, "我们")

        # More than 10 bytes.
        o.fixed_string = "我们的爱"
        with self.assertRaises(ValidationError):
            o._meta.get_field("fixed_string").clean(o.fixed_string, o)

    def test_expression(self):
        o = FixedStringModel.objects.create(fixed_string="lower")
        FixedStringModel.objects.update(fixed_string=Upper("fixed_string"))
        o.refresh_from_db()
        self.assertEqual(o.fixed_string, "LOWER")

    def test_filter(self):
        FixedStringModel.objects.create(fixed_string="Quick fox!")
        self.assertFalse(
            FixedStringModel.objects.filter(fixed_string=9).exists()
        )
        self.assertTrue(
            FixedStringModel.objects.filter(fixed_string__istartswith="quick").exists()
        )

    def test_check(self):
        field = models.FixedStringField(name='field')
        self.assertTrue(field.check())

    def test_deconstruct(self):
        field = models.FixedStringField(max_bytes=10)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(kwargs["max_bytes"], 10)


class UUIDFieldTests(TestCase):
    def test_value(self):
        v = uuid4()
        o = UUIDModel.objects.create(uuid=v)
        o.refresh_from_db()
        self.assertEqual(o.uuid, v)

        o.uuid = str(v)
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.uuid, v)

    def test_filter(self):
        v = uuid4()
        UUIDModel.objects.create(uuid=v)
        self.assertFalse(
            UUIDModel.objects.filter(uuid__iexact=str(v).replace("-", "")).exists()
        )
        self.assertTrue(
            UUIDModel.objects.filter(uuid=v).exists()
        )


class DateFieldTests(TestCase):
    def test_value(self):
        dt = timezone.now()
        d = dt.date()
        o = DateModel.objects.create(date=d)
        o.refresh_from_db()
        self.assertEqual(o.date, d)

        o.date = dt
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.date, d)

    def test_filter(self):
        dt = timezone.now()
        DateModel.objects.create(date=dt)
        self.assertTrue(
            DateModel.objects.filter(date=dt.strftime("%Y-%m-%d")).exists()
        )
        self.assertTrue(
            DateModel.objects.filter(date=dt).exists()
        )


class Date32FieldTests(TestCase):
    def test_value(self):
        dt = timezone.now()
        d = dt.date()
        o = Date32Model.objects.create(date32=d)
        o.refresh_from_db()
        self.assertEqual(o.date32, d)

        o.date32 = dt
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.date32, d)

    def test_filter(self):
        dt = timezone.now()
        Date32Model.objects.create(date32=dt)
        self.assertTrue(
            Date32Model.objects.filter(date32=dt.strftime("%Y-%m-%d")).exists()
        )
        self.assertTrue(
            Date32Model.objects.filter(date32=dt).exists()
        )


class DateTimeFieldTests(TestCase):
    def test_value(self):
        dt = timezone.now()
        v = dt.replace(microsecond=0)
        o = DateTimeModel.objects.create(datetime=dt)
        o.refresh_from_db()
        self.assertEqual(o.datetime, v)

        o.datetime = dt.timestamp()
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.datetime, v)

        o.datetime = int(dt.timestamp())
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.datetime, v)

    def test_filter(self):
        dt = timezone.now()
        ts = dt.timestamp()
        DateTimeModel.objects.create(datetime=dt)
        self.assertTrue(
            DateTimeModel.objects.filter(datetime=ts).exists()
        )
        self.assertTrue(
            DateTimeModel.objects.filter(datetime=dt).exists()
        )


class DateTime64FieldTests(TestCase):
    def test_value(self):
        dt = timezone.now()
        o = DateTime64Model.objects.create(datetime64=dt)
        o.refresh_from_db()
        self.assertEqual(o.datetime64, dt)

        o.datetime64 = dt.timestamp()
        o.save()
        o.refresh_from_db()
        self.assertEqual(o.datetime64, dt)

        o = DateTime64Model.objects.create(datetime64=int(dt.timestamp() * 1000000))
        o.refresh_from_db()
        self.assertEqual(o.datetime64, dt)

    def test_filter(self):
        dt = timezone.now()
        ts = dt.timestamp()
        DateTime64Model.objects.create(datetime64=dt)
        self.assertTrue(
            DateTime64Model.objects.filter(datetime64=ts).exists()
        )
        self.assertTrue(
            DateTime64Model.objects.filter(datetime64=dt).exists()
        )

    def test_check(self):
        field = models.DateTime64Field(low_cardinality=True, name='field')
        self.assertEqual(field.check()[0].msg, "LowCardinality is not supported by DateTime64Field.")
        for precision in [None, '6', -1, 10]:
            field = models.DateTime64Field(precision=precision, name='field')
            self.assertEqual(field.check()[0].msg, "'precision' must be an integer, valid range: [ 0 : 9 ].")

    def test_deconstruct(self):
        field = models.DateTime64Field(precision=6)
        name, path, args, kwargs = field.deconstruct()
        self.assertNotIn("precision", kwargs)
        field = models.DateTime64Field(precision=9)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(kwargs["precision"], 9)
