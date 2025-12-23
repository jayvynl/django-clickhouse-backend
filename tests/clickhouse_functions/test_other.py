from django.test import TestCase

from clickhouse_backend import models

from .models import Author


class OtherTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.john = Author.objects.create(name="John Smith")

    def test_currentDatabase(self):
        john = Author.objects.annotate(v=models.currentDatabase()).get(id=self.john.id)
        self.assertEqual(john.v, "test_default")

    def test_hostName(self):
        john = Author.objects.annotate(v=models.hostName()).get(id=self.john.id)
        self.assertTrue(john.v)

    def test_generateSerialID(self):
        john = Author.objects.annotate(
            v=models.generateSerialID("test_generateSerialID")
        ).get(id=self.john.id)
        self.assertIsInstance(john.v, int)
        john = Author.objects.annotate(
            v=models.generateSerialID(models.currentDatabase(), 100)
        ).get(id=self.john.id)
        self.assertIsInstance(john.v, int)
