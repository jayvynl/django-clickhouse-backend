from django.db import connection
from django.db.models import F
from django.test import TestCase

from . import models


class StartsWithTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = models.Author.objects.create(name="Ärger", num=1001)
        cls.a2 = models.Author.objects.create(name="a%b_c", num=2002)

    def test_startswith_sql(self):
        qs = models.Author.objects.filter(name__startswith="a")
        sql = str(qs.query)
        self.assertIn("startsWith(", sql)
        self.assertNotIn("LIKE", sql)

    def test_istartswith_sql(self):
        qs = models.Author.objects.filter(name__istartswith="a")
        sql = str(qs.query)
        if connection.features.has_starts_with_case_insensitive:
            self.assertIn("startsWithCaseInsensitiveUTF8(", sql)
        else:
            self.assertIn("startsWith(lowerUTF8(", sql)
        self.assertNotIn("ILIKE", sql)

    def test_startswith(self):
        self.assertSequenceEqual(
            models.Author.objects.filter(name__startswith="Är"), [self.a1]
        )
        self.assertSequenceEqual(models.Author.objects.filter(name__startswith="x"), [])

    def test_startswith_is_case_sensitive(self):
        self.assertSequenceEqual(
            models.Author.objects.filter(name__startswith="är"), []
        )

    def test_istartswith_folds_case_beyond_ascii(self):
        self.assertSequenceEqual(
            models.Author.objects.filter(name__istartswith="är"), [self.a1]
        )
        self.assertSequenceEqual(
            models.Author.objects.filter(name__istartswith="A%B_"), [self.a2]
        )

    def test_wildcards_in_prefix_are_literal(self):
        self.assertSequenceEqual(
            models.Author.objects.filter(name__startswith="a%b_"), [self.a2]
        )
        self.assertSequenceEqual(models.Author.objects.filter(name__startswith="_"), [])

    def test_non_text_field_is_cast(self):
        self.assertSequenceEqual(
            models.Author.objects.filter(num__startswith="10"), [self.a1]
        )
        self.assertSequenceEqual(
            models.Author.objects.filter(num__istartswith="20"), [self.a2]
        )

    def test_expression_as_prefix(self):
        self.assertCountEqual(
            models.Author.objects.filter(name__startswith=F("name")),
            [self.a1, self.a2],
        )
        self.assertCountEqual(
            models.Author.objects.filter(name__istartswith=F("name")),
            [self.a1, self.a2],
        )
