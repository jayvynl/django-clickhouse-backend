from django.core.exceptions import ValidationError
from django.test import TestCase

from clickhouse_backend import models
from clickhouse_backend.models.fields.map import KeyTransform
from .models import MapModel


class MapFieldTests(TestCase):
    def test_disallow_nullable(self):
        field = models.MapField(
            models.Int8Field(name="field"),
            models.StringField(name="field"),
            null=True,
            name="field"
        )
        self.assertEqual(
            field.check()[0].msg,
            "Nullable is not supported by MapField."
        )

    def test_key_value_field(self):
        field = models.MapField(
            models.Float64Field(name="field"),
            models.Int8Field(name="field"),
            name="field"
        )
        self.assertEqual(
            field.check()[0].msg, "This key field type is invalid."
        )

        field = models.MapField(
            models.StringField(name="field", null=True),
            models.Int8Field(name="field"),
            name="field"
        )
        self.assertTrue(
            field.check()[0], "Map key must not be null."
        )

        field = models.MapField(
            models.UUIDField(name="field", low_cardinality=True),
            models.Int8Field(name="field"),
            name="field"
        )
        self.assertTrue(
            field.check()[0].msg, "Only Map key of String and FixedString can be low cardinality."
        )

        field = models.MapField(
            models.EnumField(name="field"),
            models.Int8Field(name="field"),
            name="field"
        )
        self.assertTrue(
            field.check()[0].msg.startswith("Key field for map has errors:")
        )

        field = models.MapField(
            models.Int8Field(name="field"),
            models.EnumField(name="field"),
            name="field"
        )
        self.assertTrue(
            field.check()[0].msg.startswith("Value field for map has errors:")
        )

    def test_deconstruct(self):
        field = models.MapField(
            models.Int8Field(name="field"),
            models.StringField(name="field"),
            name="field"
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(
            path,
            "clickhouse_backend.models.MapField"
        )
        self.assertIn("key_field", kwargs)
        self.assertIn("value_field", kwargs)

    def test_validate(self):
        field = models.MapField(
            models.Int8Field(name="field"),
            models.GenericIPAddressField(name="field", unpack_ipv4=True),
            name="field"
        )
        with self.assertRaises(ValidationError):
            field.clean({130: "1.1.1.1"}, None)

        with self.assertRaises(ValidationError):
            field.clean({13: ".1.1.1"}, None)

        self.assertEqual(
            field.clean({"100": "::ffff:3.4.5.6"}, None),
            {100: "3.4.5.6"}
        )

    def test_value(self):
        v = {
            "baidu.com": "39.156.66.10",
            "bing.com": "13.107.21.200",
            "google.com": "172.217.163.46"
        }
        o = MapModel.objects.create(map=v)
        o.refresh_from_db()
        self.assertEqual(o.map, v)

    def test_filter(self):
        v = {
            "baidu": "39.156.66.10",
            "bing.com": "13.107.21.200",
            "google.com": "172.217.163.46"
        }
        MapModel.objects.create(map=v)
        self.assertTrue(
            MapModel.objects.filter(map__has_key="baidu").exists()
        )
        self.assertFalse(
            MapModel.objects.filter(map__has_key="baidu.com").exists()
        )

        self.assertTrue(
            MapModel.objects.filter(map=v).exists()
        )
        self.assertFalse(
            MapModel.objects.filter(map={"baidu": "39.156.66.10"}).exists()
        )

        self.assertTrue(
            MapModel.objects.filter(map__len=3).exists()
        )
        self.assertFalse(
            MapModel.objects.filter(map__len=2).exists()
        )

        self.assertTrue(
            MapModel.objects.filter(map__keys=["baidu", "bing.com", "google.com"]).exists()
        )
        self.assertFalse(
            MapModel.objects.filter(map__keys=["baidu", "bing.com"]).exists()
        )

        self.assertTrue(
            MapModel.objects.filter(map__values=["39.156.66.10", "13.107.21.200", "172.217.163.46"]).exists()
        )
        self.assertFalse(
            MapModel.objects.filter(map__values=["39.156.66.10", "13.107.21.200"]).exists()
        )

        self.assertTrue(
            MapModel.objects.filter(map__baidu="39.156.66.10").exists()
        )
        self.assertTrue(
            MapModel.objects.annotate(
                value=KeyTransform("bing.com", models.StringField(), models.GenericIPAddressField(), "map")
            ).filter(value="13.107.21.200").exists()
        )
