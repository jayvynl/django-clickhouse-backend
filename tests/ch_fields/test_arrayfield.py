from ipaddress import IPv4Address, IPv6Address

from django.core.exceptions import ValidationError
from django.test import TestCase

from clickhouse_backend import models
from .models import ArrayModel, NestedArrayModel


class ArrayFieldTests(TestCase):
    def test_disallow_nullable(self):
        field = models.ArrayField(base_field=models.Int8Field(name="field"), null=True, name="field")
        self.assertEqual(
            field.check()[0].msg,
            "Nullable is not supported by ArrayField."
        )

    def test_check_base_field(self):
        field = models.ArrayField(
            base_field=models.DateTime64Field(precision=10,  name="field"),
            name="field"
        )
        self.assertTrue(
            field.check()[0].msg.startswith("Base field for array has errors:")
        )

        field = models.ArrayField(
            base_field=models.ArrayField(
                base_field=models.EnumField(name="field"),
                name="field"
            ),
            name="field"
        )
        self.assertTrue(
            field.check()[0].msg.startswith("Base field for array has errors:")
        )

    def test_deconstruct(self):
        field = models.ArrayField(base_field=models.Int8Field(), name="field")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "clickhouse_backend.models.ArrayField")
        self.assertIn("base_field", kwargs)
        self.assertNotIn("size", kwargs)

        field = models.ArrayField(base_field=models.Int8Field(), size=4, name="field")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(kwargs["size"], 4)

    def test_validate(self):
        field = models.ArrayField(base_field=models.Int8Field(), name="field")
        with self.assertRaises(ValidationError):
            field.clean([130], None)

    def test_value(self):
        v = [
            "1.2.3.4",
            IPv4Address("2.3.4.5"),
            "::ffff:3.4.5.6",
            IPv6Address("::ffff:4.5.6.7"),
            "7ebb:4c3:d267:1ce6:9315:ba70:a14:7b1c",
            IPv6Address("ed51:aaa0:3c7e:a65a:bb72:82b7:4d87:44dd")
        ]
        o = ArrayModel.objects.create(array=v)
        o.refresh_from_db()
        self.assertEqual(
            o.array,
            [
                "1.2.3.4",
                "2.3.4.5",
                "3.4.5.6",
                "4.5.6.7",
                "7ebb:4c3:d267:1ce6:9315:ba70:a14:7b1c",
                "ed51:aaa0:3c7e:a65a:bb72:82b7:4d87:44dd"
            ]
        )

        o.array = ("1.2.3.4", IPv4Address("2.3.4.5"))
        o.save()
        o.refresh_from_db()
        self.assertEqual(
            o.array,
            ["1.2.3.4", "2.3.4.5"]
        )

        # Test generator
        o.array = (i for i in ("1.2.3.4", IPv4Address("2.3.4.5")))
        o.save()
        o.refresh_from_db()
        self.assertEqual(
            o.array,
            ["1.2.3.4", "2.3.4.5"]
        )

    def test_filter(self):
        v = [
            "1.2.3.4",
            "2.3.4.5",
            "7ebb:4c3:d267:1ce6:9315:ba70:a14:7b1c",
        ]
        ArrayModel.objects.create(array=v)

        self.assertEqual(
            ArrayModel.objects.filter(array=v)[0].array,
            v
        )

        self.assertTrue(
            ArrayModel.objects.filter(array__any="2.3.4.5").exists()
        )
        self.assertFalse(
            ArrayModel.objects.filter(array__any="4.5.6.7").exists()
        )

        self.assertTrue(
            ArrayModel.objects.filter(array__contains=["1.2.3.4", "2.3.4.5"]).exists()
        )
        self.assertFalse(
            ArrayModel.objects.filter(array__contains=["1.2.3.4", "4.5.6.7"]).exists()
        )

        self.assertTrue(
            ArrayModel.objects.filter(array__contained_by=[
                "1.2.3.4",
                "2.3.4.5",
                "7ebb:4c3:d267:1ce6:9315:ba70:a14:7b1c",
                "ed51:aaa0:3c7e:a65a:bb72:82b7:4d87:44dd"
            ]).exists()
        )
        self.assertFalse(
            ArrayModel.objects.filter(array__contained_by=[
                "1.2.3.4",
                "3.4.5.6",
                "ed51:aaa0:3c7e:a65a:bb72:82b7:4d87:44dd"
            ]).exists()
        )

        self.assertTrue(
            ArrayModel.objects.filter(array=v).exists()
        )
        self.assertFalse(
            ArrayModel.objects.filter(array=[
                "2.3.4.5",
                "1.2.3.4",
                "7ebb:4c3:d267:1ce6:9315:ba70:a14:7b1c",
            ]).exists()
        )

        self.assertTrue(
            ArrayModel.objects.filter(array__overlap=[
                "1.2.3.4",
                "3.4.5.6",
                "ed51:aaa0:3c7e:a65a:bb72:82b7:4d87:44dd"
            ]).exists()
        )
        self.assertFalse(
            ArrayModel.objects.filter(array__overlap=[
                "3.4.5.6",
                "ed51:aaa0:3c7e:a65a:bb72:82b7:4d87:44dd"
            ]).exists()
        )

        self.assertTrue(
            ArrayModel.objects.filter(array__len=3).exists()
        )
        self.assertFalse(
            ArrayModel.objects.filter(array__len=1).exists()
        )

        self.assertTrue(
            ArrayModel.objects.filter(array__1="2.3.4.5").exists()
        )
        self.assertFalse(
            ArrayModel.objects.filter(array__0="2.3.4.5").exists()
        )

        self.assertTrue(
            ArrayModel.objects.filter(array__0_2=["1.2.3.4", "2.3.4.5"]).exists()
        )
        self.assertFalse(
            ArrayModel.objects.filter(array__0_2=["1.2.3.4", "3.4.5.6"]).exists()
        )

        # self.assertTrue(
        #     ArrayModel.objects.filter(array__size0=3).exists()
        # )

    def test_nested(self):
        v = [[[12, 13, 0, 1], [12]], [[12, 13, 0, 1], [12], [13, 14]]]

        NestedArrayModel.objects.create(array=v)

        self.assertEqual(
            NestedArrayModel.objects.filter(array=v)[0].array,
            v
        )

        self.assertTrue(
            NestedArrayModel.objects.filter(array__any=[[12, 13, 0, 1], [12]]).exists()
        )
        self.assertFalse(
            NestedArrayModel.objects.filter(array__any=[[12]]).exists()
        )

        self.assertTrue(
            NestedArrayModel.objects.filter(array__contains=[[[12, 13, 0, 1], [12]]]).exists()
        )
        self.assertFalse(
            NestedArrayModel.objects.filter(array__contains=[[[12, 13, 0, 1], [13]]]).exists()
        )

        self.assertTrue(
            NestedArrayModel.objects.filter(array__contained_by=[
                [[12, 13, 0, 1], [12]],
                [[12, 13, 0, 1], [12], [13, 14]],
                [[1]]
            ]).exists()
        )
        self.assertFalse(
            NestedArrayModel.objects.filter(array__contained_by=[
                [[12, 13, 0, 1]],
                [[12, 13, 0, 1], [12], [13, 14]],
                [[1]]
            ]).exists()
        )

        self.assertTrue(
            NestedArrayModel.objects.filter(array__overlap=[
                [[12, 13, 0, 1], [12]],
                [[1]]
            ]).exists()
        )
        self.assertFalse(
            NestedArrayModel.objects.filter(array__overlap=[
                [[12, 13, 0, 1], [12], [1]],
                [[12, 13, 0, 1], [13, 14]],
                [[1]]
            ]).exists()
        )

        self.assertTrue(
            NestedArrayModel.objects.filter(array__len=2).exists()
        )
        self.assertFalse(
            NestedArrayModel.objects.filter(array__len=1).exists()
        )

        self.assertTrue(
            NestedArrayModel.objects.filter(array__1=[[12, 13, 0, 1], [12], [13, 14]]).exists()
        )
        self.assertFalse(
            NestedArrayModel.objects.filter(array__1=[[12, 13, 0, 1], [13, 14]]).exists()
        )

        self.assertTrue(
            NestedArrayModel.objects.filter(array__1_2=[[[12, 13, 0, 1], [12], [13, 14]]]).exists()
        )
        self.assertFalse(
            NestedArrayModel.objects.filter(array__1_2=[[[12, 13, 0, 1], [13, 14]]]).exists()
        )

        self.assertTrue(
            NestedArrayModel.objects.filter(array__1__2=[13, 14]).exists()
        )
        self.assertTrue(
            NestedArrayModel.objects.filter(array__1__2__0=13).exists()
        )

        # self.assertTrue(
        #     NestedArrayModel.objects.filter(array__size0=2).exists()
        # )
        # self.assertTrue(
        #     NestedArrayModel.objects.filter(array__size1=[2, 3]).exists()
        # )
        # self.assertTrue(
        #     NestedArrayModel.objects.filter(array__size1=[[4, 1], [4, 1, 2]]).exists()
        # )
        # self.assertTrue(
        #     NestedArrayModel.objects.filter(array__1__size1=[4, 1, 2]).exists()
        # )
