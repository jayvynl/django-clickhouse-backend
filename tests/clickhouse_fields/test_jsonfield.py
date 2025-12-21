from django.test import TestCase
from django.db import connection

from clickhouse_backend import models


class JsonFieldTests(TestCase):
    def test_disallow_nullable(self):
        field = models.JSONField(null=True, name="field")
        self.assertEqual(
            field.check()[0].msg, "Nullable is not supported by JSONField."
        )

    def test_deconstruct(self):
        field = models.JSONField(name="field")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "clickhouse_backend.models.JSONField")

    def test_query(self):
        class JSONModel(models.ClickhouseModel):
            json = models.JSONField()

        with connection.schema_editor() as editor:
            editor.create_model(JSONModel)

        v = {"a": [1, 2, 3], "b": [{"c": 1}, {"c": 2}], "c": {"d": "e"}}
        o = JSONModel.objects.create(json=v)
        o.refresh_from_db()
        self.assertEqual(o.json, v)

        # test filter
        v = {"a": [1, 2, 3], "b": [{"c": 1}, {"d": 2}], "c": {"d": "e"}}
        JSONModel.objects.create(json=v)
        self.assertTrue(JSONModel.objects.filter(json__a=[1, 2, 3]).exists())
        self.assertTrue(JSONModel.objects.filter(json__b__0__c=1).exists())
        self.assertTrue(JSONModel.objects.filter(json__c__d="e").exists())
        self.assertTrue(JSONModel.objects.filter(json__c={"d": "e"}).exists())

        with connection.schema_editor() as editor:
            editor.delete_model(JSONModel)
