from django.test import TestCase

from clickhouse_backend import models
from .models import JSONModel


class MapFieldTests(TestCase):
    def test_disallow_nullable(self):
        field = models.JSONField(
            null=True,
            name="field"
        )
        self.assertEqual(
            field.check()[0].msg,
            "Nullable is not supported by JSONField."
        )

    def test_deconstruct(self):
        field = models.JSONField(
            name="field"
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(
            path,
            "clickhouse_backend.models.JSONField"
        )

    def test_value(self):
        v = {
            "a": [1, 2, 3],
            "b": [{"c": 1}, {"c": 2}],
            "c": {"d": "e"}
        }
        o = JSONModel.objects.create(json=v)
        o.refresh_from_db()
        self.assertEqual(o.json, v)

    def test_filter(self):
        v = {
            "a": [1, 2, 3],
            "b": [{"c": 1}, {"d": 2}],
            "c": {"d": "e"}
        }
        JSONModel.objects.create(json=v)
        assert JSONModel.objects.filter(json__a=[1, 2, 3]).exists()
        assert JSONModel.objects.filter(json__b__0__c=1).exists()
        assert JSONModel.objects.filter(json__c__d="e").exists()
        assert JSONModel.objects.filter(json__c={"d": "e"}).exists()
