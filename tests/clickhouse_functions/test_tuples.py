from django.test import TestCase

from clickhouse_backend import models

from .models import Author


class TupleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.john = Author.objects.create(name="John Smith", age=30)

    def test_tuple(self):
        john = Author.objects.annotate(v=models.Tuple("name", "age")).get(
            id=self.john.id
        )
        self.assertEqual(john.v, ("John Smith", 30))

    def test_tupleelement(self):
        john = Author.objects.annotate(
            v=models.tupleElement(
                models.Tuple("name", "age"), 1, output_field=models.UInt16Field()
            )
        ).get(id=self.john.id)
        self.assertEqual(john.v, 30)
