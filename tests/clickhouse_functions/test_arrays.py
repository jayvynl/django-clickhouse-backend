from django.db.models import F, Value
from django.test import TestCase

from clickhouse_backend import models
from clickhouse_backend.models.functions.arrays import (
    array,
    hasAny,
    groupArrayIf,
    groupUniqArrayIf,
)

from .models import Author


class ArrayFunctionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = Author.objects.create(
            name="Alice", alias="alice", age=25, tags=["python", "django"]
        )
        cls.bob = Author.objects.create(
            name="Bob", alias="bob", age=30, tags=["python", "rust"]
        )
        cls.carol = Author.objects.create(
            name="Carol", alias="alice", age=25, tags=["django", "go"]
        )

    def test_array(self):
        result = list(
            Author.objects.values("name")
            .annotate(
                arr=array(
                    Value(1),
                    Value(2),
                    Value(3),
                    output_field=models.ArrayField(models.Int32Field()),
                )
            )
            .order_by("name")[:1]
        )
        self.assertEqual(result[0]["arr"], [1, 2, 3])

    def test_hasAny_with_field(self):
        result = Author.objects.annotate(
            has=hasAny(F("tags"), array(Value("python"), Value("go")))
        ).get(id=self.alice.id)
        self.assertTrue(result.has)

    def test_hasAny_true(self):
        result = Author.objects.annotate(
            has=hasAny(
                array(Value("Alice"), Value("Bob")),
                array(Value("Alice"), Value("Carol")),
            )
        ).first()
        self.assertTrue(result.has)

    def test_hasAny_false(self):
        result = Author.objects.annotate(
            has=hasAny(F("tags"), array(Value("haskell")))
        ).get(id=self.alice.id)
        self.assertFalse(result.has)

    def test_groupArrayIf_func(self):
        from clickhouse_backend.models.aggregates import groupArray

        result = list(
            Author.objects.values("age")
            .annotate(
                all_names=groupArray("name"),
                names=groupArrayIf("name", Value(1)),
            )
            .order_by("age")
        )
        self.assertEqual(len(result), 2)
        for row in result:
            self.assertIsInstance(row["names"], list)
            self.assertTrue(len(row["names"]) > 0)

    def test_groupUniqArrayIf_func(self):
        from clickhouse_backend.models.aggregates import groupUniqArray

        result = list(
            Author.objects.values("age")
            .annotate(
                all_aliases=groupUniqArray("alias"),
                aliases=groupUniqArrayIf("alias", Value(1)),
            )
            .order_by("age")
        )
        self.assertEqual(len(result), 2)
        for row in result:
            self.assertIsInstance(row["aliases"], list)
            self.assertEqual(sorted(row["aliases"]), sorted(set(row["aliases"])))
