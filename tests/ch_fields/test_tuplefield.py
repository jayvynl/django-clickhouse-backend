from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase

from clickhouse_backend import models
from .models import TupleModel, NamedTupleModel


class TupleFieldTests(TestCase):
    def test_disallow_nullable(self):
        field = models.TupleField(base_fields=[models.Int8Field()], null=True, name="field")
        self.assertEqual(
            field.check()[0].msg,
            "Nullable is not supported by TupleField."
        )

    def test_check_base_fields(self):
        msg = (
            "'base_fields' must be an iterable containing only(not both) "
            "field instances or (field name, field instance) tuples, "
            "and field name must be valid python identifier."
        )
        with self.assertRaisesMessage(RuntimeError, msg):
            field = models.TupleField(base_fields=123, name="field")
        with self.assertRaisesMessage(RuntimeError, msg):
            field = models.TupleField(base_fields="123", name="field")
        with self.assertRaisesMessage(RuntimeError, msg):
            field = models.TupleField(base_fields=[1, 2], name="field")
        with self.assertRaisesMessage(RuntimeError, msg):
            field = models.TupleField(base_fields=["12"], name="field")
        with self.assertRaisesMessage(RuntimeError, msg):
            field = models.TupleField(base_fields=[("a", models.UInt32Field(name="field"), 3)], name="field")
        with self.assertRaisesMessage(RuntimeError, msg):
            field = models.TupleField(base_fields=[("12", models.UInt32Field(name="field"))], name="field")
        with self.assertRaisesMessage(RuntimeError, msg):
            field = models.TupleField(base_fields=[("a", 3)], name="field")

        with self.assertRaisesMessage(RuntimeError, "'base_fields' must not be empty."):
            field = models.TupleField(base_fields=[], name="field")

        field = models.TupleField(base_fields=[models.DateTime64Field(precision=100, name="field")], name="field")
        self.assertTrue(field.check()[0].msg.startswith("Field 1s has errors:"))

    def test_db_type(self):
        field = models.TupleField(base_fields=[
            models.UInt8Field(),
            models.DateField(null=True),
            models.StringField(low_cardinality=True)
        ])
        self.assertTrue(
            field.db_type(connection),
            "Tuple(UInt8, Nullable(Date), String)"
        )

        field = models.TupleField(base_fields=[
            ('i', models.UInt8Field()),
            ('d', models.DateField(null=True)),
            ('s', models.StringField(low_cardinality=True))
        ])
        self.assertTrue(
            field.db_type(connection),
            "Tuple(i UInt8, d Nullable(Date), s String)"
        )

    def test_deconstruct(self):
        field = models.TupleField(base_fields=[
            models.UInt8Field(),
            models.DateField(null=True),
            models.StringField(low_cardinality=True)
        ])
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "clickhouse_backend.models.TupleField")
        self.assertIn("base_fields", kwargs)

    def test_validate(self):
        field = models.TupleField(
            base_fields=[
                models.TupleField(
                    base_fields=[
                        models.Int8Field(name="field"),
                        models.IPv4Field(name="field")
                    ],
                    name="field"
                ),
                models.ArrayField(
                    base_field=models.StringField(name="field"),
                    name="field"
                )
            ],
            name="field"
        )
        field.check()
        with self.assertRaises(ValidationError):
            field.clean([130], None)
        with self.assertRaises(ValidationError):
            field.clean(((130, '1.1.1.1'), []), None)
        with self.assertRaises(ValidationError):
            field.clean(((13, '.1.1.1'), []), None)
        with self.assertRaises(ValidationError):
            field.clean(((30, '1.1.1.1'), [None]), None)

        field = models.TupleField(
            base_fields=[
                (
                    "tup",
                    models.TupleField(
                        base_fields=[
                            ("int", models.Int8Field(name="field")),
                            ("ip", models.IPv4Field(name="field"))
                        ],
                        name="field"
                    )
                ),
                (
                    "arr",
                    models.ArrayField(
                        base_field=models.StringField(name="field"),
                        name="field"
                    )
                )
            ],
            name="field"
        )
        field.check()
        with self.assertRaises(ValidationError):
            field.clean([130], None)
        with self.assertRaises(ValidationError):
            field.clean(((130, '1.1.1.1'), []), None)
        with self.assertRaises(ValidationError):
            field.clean(((13, '.1.1.1'), []), None)
        with self.assertRaises(ValidationError):
            field.clean(((30, '1.1.1.1'), [None]), None)

    def test_value(self):
        v = ["100", 100, "::ffff:3.4.5.6"]
        o = TupleModel.objects.create(tuple=v)
        o.refresh_from_db()
        self.assertEqual(o.tuple, (100, "100", "3.4.5.6"))

        o = NamedTupleModel.objects.create(tuple=v)
        o.refresh_from_db()
        self.assertEqual(o.tuple, (100, "100", "3.4.5.6"))

    def test_filter(self):
        v = [100, "test", "::ffff:3.4.5.6"]
        TupleModel.objects.create(tuple=v)
        self.assertTrue(
            TupleModel.objects.filter(tuple=v).exists()
        )
        self.assertFalse(
            TupleModel.objects.filter(tuple=[100, "test"]).exists()
        )

        self.assertTrue(
            TupleModel.objects.filter(tuple__1="test").exists()
        )
        self.assertFalse(
            TupleModel.objects.filter(tuple__0__iexact="test").exists()
        )

        self.assertTrue(
            TupleModel.objects.filter(tuple__2__startswith="3.4").exists()
        )

        NamedTupleModel.objects.create(tuple=v)
        self.assertTrue(
            NamedTupleModel.objects.filter(tuple=v).exists()
        )
        self.assertFalse(
            NamedTupleModel.objects.filter(tuple=[100, "test"]).exists()
        )

        self.assertTrue(
            NamedTupleModel.objects.filter(tuple__1="test").exists()
        )
        self.assertFalse(
            NamedTupleModel.objects.filter(tuple__0__iexact="test").exists()
        )

        self.assertTrue(
            NamedTupleModel.objects.filter(tuple__2__startswith="3.4").exists()
        )

        self.assertTrue(
            NamedTupleModel.objects.filter(tuple__str="test").exists()
        )
        self.assertFalse(
            NamedTupleModel.objects.filter(tuple__int__iexact="test").exists()
        )

        self.assertTrue(
            NamedTupleModel.objects.filter(tuple__ip__startswith="3.4").exists()
        )
