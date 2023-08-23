from django.test import TestCase

from . import models


class Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        models.Event.objects.bulk_create([models.Event() for _ in range(10)])

    def test_create(self):
        models.Event.objects.create()
        self.assertEqual(models.Event.objects.count(), 11)

    def test_update(self):
        event = models.Event.objects.create()
        models.Event.objects.filter(id=event.id).settings(mutations_sync=1).update(
            protocol="TCP"
        )
        self.assertTrue(models.Event.objects.filter(protocol="TCP").exists())

    def test_delete(self):
        models.Event.objects.settings(mutations_sync=1).delete()
        self.assertFalse(models.Event.objects.exists())
