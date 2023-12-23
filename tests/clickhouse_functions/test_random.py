from django.test import TestCase

from clickhouse_backend import models

from .models import Author


class RandomTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.john = Author.objects.create(name="John Smith")

    def test_rand(self):
        Author.objects.annotate(v=models.Rand()).get(id=self.john.id)
